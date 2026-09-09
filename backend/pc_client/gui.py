"""Tk desktop client for the ESP32 thermometer protocol."""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from contextlib import suppress
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Coroutine

from .ble_service import OperationState, ThermometerBleService
from .protocol import CONFIG, CurrentSnapshot, VisibleState
from .thermometer_client import HistorySync, describe_ble_error


class BleWorker:
    """Thin Tk/thread adapter around the production BLE service."""

    def __init__(self, events: queue.Queue[dict[str, Any]]) -> None:
        self.events = events
        self.loop: asyncio.AbstractEventLoop | None = None
        self.service: ThermometerBleService | None = None
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(3):
            raise RuntimeError("BLE worker thread did not start")
        if self._startup_error is not None:
            raise RuntimeError(
                f"BLE service failed to start: {describe_ble_error(self._startup_error)}"
            ) from self._startup_error

    def _thread_main(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.service = ThermometerBleService(
            event_handler=self.events.put,
            # The test GUI keeps its explicit Scan/Pair & Connect workflow.
            # The production service uses automatic startup discovery.
            auto_discover_on_start=False,
        )
        try:
            self.loop.run_until_complete(self.service.start())
        except Exception as exc:
            self._startup_error = exc
            self.events.put({"type": "error", "message": describe_ble_error(exc)})
        self.ready.set()
        if self._startup_error is not None:
            self.loop.close()
            return
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()

    def _submit(self, operation: Coroutine[Any, Any, Any]) -> None:
        assert self.loop is not None
        asyncio.run_coroutine_threadsafe(self._run_and_report(operation), self.loop)

    async def _run_and_report(self, operation: Coroutine[Any, Any, Any]) -> None:
        """Consume every GUI operation result inside its owning event loop."""
        try:
            await operation
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.events.put({"type": "error", "message": describe_ble_error(exc)})

    def scan(self) -> None:
        self._submit(self._scan())

    def needs_passkey(self, address: str) -> bool:
        assert self.service is not None
        return self.service.credentials.lookup(address) is None

    async def _scan(self) -> None:
        self.events.put({"type": "status", "message": "Scanning for thermometer..."})
        assert self.service is not None
        await self.service.scan()

    def connect(self, target: Any, passkey: str | None = None) -> None:
        self._submit(self._connect(target, passkey))

    async def _connect(self, target: Any, passkey: str | None = None) -> None:
        self.events.put(
            {
                "type": "status",
                "message": "Pairing, authenticating, and connecting...",
            }
        )
        assert self.service is not None
        operation = await self.service.connect(target, passkey)
        await self._wait_for_operation(operation.operation_id)

    def reset_pairing(self, target: Any) -> None:
        self._submit(self._reset_pairing(target))

    async def _reset_pairing(self, target: Any) -> None:
        self.events.put({"type": "status", "message": "Resetting Windows pairing..."})
        assert self.service is not None
        operation = await self.service.forget_pairing(target)
        await self._wait_for_operation(operation.operation_id)

    def set_display(self, sensor_id: int, enabled: bool) -> None:
        self._submit(self._set_display(sensor_id, enabled))

    async def _set_display(self, sensor_id: int, enabled: bool) -> None:
        assert self.service is not None
        await self.service.set_display(sensor_id, enabled)

    def synchronize_history(self) -> None:
        self._submit(self._synchronize_history())

    async def _synchronize_history(self) -> None:
        self.events.put({"type": "status", "message": "Synchronizing history..."})
        assert self.service is not None
        operation = await self.service.request_history_sync()
        await self._wait_for_operation(operation.operation_id)

    def disconnect(self) -> None:
        self._submit(self._disconnect())

    async def _disconnect(self, announce: bool = True) -> None:
        assert self.service is not None
        await self.service.disconnect()

    async def _wait_for_operation(self, operation_id: str) -> None:
        assert self.service is not None
        operation = await self.service.wait_for_operation(operation_id)
        if operation.state is OperationState.FAILED:
            message = operation.error["message"] if operation.error else "operation failed"
            raise RuntimeError(message)
        if operation.state is OperationState.CANCELLED:
            message = operation.error["message"] if operation.error else "operation cancelled"
            raise RuntimeError(message)

    def stop(self) -> None:
        if self.loop is None:
            return
        assert self.service is not None
        future = asyncio.run_coroutine_threadsafe(self.service.stop(), self.loop)
        with suppress(Exception):
            future.result(timeout=3)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=3)


class ThermometerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ESP32 Thermometer Client")
        self.geometry("940x720")
        self.minsize(820, 640)

        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.worker = BleWorker(self.events)
        self.devices: dict[str, Any] = {}
        sensor_ids = range(1, CONFIG.device.sensor_count + 1)
        self.display_enabled = {sensor_id: False for sensor_id in sensor_ids}

        self.status_var = tk.StringVar(value="Disconnected")
        self.device_var = tk.StringVar()
        self.boot_var = tk.StringVar(value="Boot: --")
        self.sequence_var = tk.StringVar(value="Sequence: --")
        self.average_var = tk.StringVar(value="Average: --")
        self.sensor_temp = {
            sensor_id: tk.StringVar(value="-- deg C")
            for sensor_id in range(1, CONFIG.device.sensor_count + 1)
        }
        self.sensor_state = {
            sensor_id: tk.StringVar(value="UNKNOWN")
            for sensor_id in range(1, CONFIG.device.sensor_count + 1)
        }

        self._build_ui()
        self.worker.start()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        connection = ttk.LabelFrame(outer, text="Connection", padding=10)
        connection.pack(fill="x")
        self.device_box = ttk.Combobox(
            connection, textvariable=self.device_var, state="readonly", width=55
        )
        self.device_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(connection, text="Scan", command=self._scan).grid(row=0, column=1)
        ttk.Button(connection, text="Pair & Connect", command=self._connect).grid(
            row=0, column=2, padx=8
        )
        ttk.Button(connection, text="Disconnect", command=self.worker.disconnect).grid(
            row=0, column=3
        )
        ttk.Button(
            connection, text="Reset Pairing", command=self._reset_pairing
        ).grid(row=0, column=4, padx=(8, 0))
        connection.columnconfigure(0, weight=1)
        ttk.Label(
            connection,
            text=(
                f"Protocol v{CONFIG.protocol_version} | service {CONFIG.service_uuid} | "
                "per-device authentication"
            ),
        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ttk.Label(connection, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(4, 0)
        )

        summary = ttk.Frame(outer, padding=(0, 12, 0, 6))
        summary.pack(fill="x")
        ttk.Label(summary, textvariable=self.boot_var).pack(side="left")
        ttk.Label(summary, textvariable=self.sequence_var).pack(side="left", padx=20)
        ttk.Label(summary, textvariable=self.average_var).pack(side="left")

        sensors = ttk.Frame(outer)
        sensors.pack(fill="x")
        self.display_buttons: dict[int, ttk.Button] = {}
        for sensor_id in range(1, CONFIG.device.sensor_count + 1):
            card = ttk.LabelFrame(
                sensors, text=f"Temperature Sensor {sensor_id}", padding=14
            )
            card.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 6) if sensor_id == 1 else (6, 0),
            )
            ttk.Label(
                card,
                textvariable=self.sensor_temp[sensor_id],
                font=("Segoe UI", 22),
            ).pack()
            ttk.Label(card, textvariable=self.sensor_state[sensor_id]).pack(pady=6)
            button = ttk.Button(
                card,
                text="Enable display",
                state="disabled",
                command=lambda value=sensor_id: self._toggle_display(value),
            )
            button.pack()
            self.display_buttons[sensor_id] = button

        history_seconds = (
            CONFIG.device.history_capacity_records
            * CONFIG.device.sample_period_ms
            / 1000
        )
        history_frame = ttk.LabelFrame(
            outer, text=f"{history_seconds:g}-second history", padding=8
        )
        history_frame.pack(fill="both", expand=True, pady=(12, 0))
        controls = ttk.Frame(history_frame)
        controls.pack(fill="x")
        ttk.Button(
            controls, text="Synchronize now", command=self.worker.synchronize_history
        ).pack(side="left")
        ttk.Label(
            controls,
            text="History is also synchronized on first connection and reconnection.",
        ).pack(side="left", padx=10)

        columns = ("time", "sensor", "sequence", "temperature", "status")
        self.history_tree = ttk.Treeview(
            history_frame, columns=columns, show="headings", height=12
        )
        widths = (170, 70, 100, 110, 120)
        for column, width in zip(columns, widths):
            self.history_tree.heading(column, text=column.replace("_", " ").title())
            self.history_tree.column(column, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(
            history_frame, orient="vertical", command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.pack(side="left", fill="both", expand=True, pady=(8, 0))
        scrollbar.pack(side="right", fill="y", pady=(8, 0))

        self.log = tk.Text(outer, height=5, state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(10, 0))

    def _scan(self) -> None:
        self.status_var.set("Scanning...")
        self.worker.scan()

    def _connect(self) -> None:
        label = self.device_var.get()
        if label not in self.devices:
            messagebox.showinfo("Select a device", "Scan and select the thermometer first.")
            return
        selected = self.devices[label]
        passkey: str | None = None
        if self.worker.needs_passkey(selected.address):
            passkey = simpledialog.askstring(
                "Device passkey",
                "Enter the six-digit passkey for this thermometer:",
                show="*",
                parent=self,
            )
            if passkey is None:
                return
        self.worker.connect(selected.device, passkey)

    def _reset_pairing(self) -> None:
        label = self.device_var.get()
        if label not in self.devices:
            messagebox.showinfo("Select a device", "Scan and select the thermometer first.")
            return
        self.worker.reset_pairing(self.devices[label].device)

    def _toggle_display(self, sensor_id: int) -> None:
        desired = not self.display_enabled[sensor_id]
        self.worker.set_display(sensor_id, desired)

    def _show_snapshot(self, snapshot: CurrentSnapshot) -> None:
        self.status_var.set(
            f"Connected | polling every {CONFIG.service.poll_interval_seconds:g} s"
        )
        self.boot_var.set(f"Boot: 0x{snapshot.boot_id:08X}")
        self.sequence_var.set(f"Sequence: {snapshot.newest_sequence}")
        average = "--" if snapshot.average_c is None else f"{snapshot.average_c:.2f} deg C"
        self.average_var.set(f"Visible average: {average}")
        for sensor in snapshot.sensors:
            sensor_id = sensor.sensor_id
            temperature = (
                "-- deg C"
                if sensor.temperature_c is None
                else f"{sensor.temperature_c:.2f} deg C"
            )
            self.sensor_temp[sensor_id].set(temperature)
            self.sensor_state[sensor_id].set(sensor.visible_state.name)
            self.display_enabled[sensor_id] = sensor.display_enabled
            button = self.display_buttons[sensor_id]
            button.configure(
                text="Disable display" if sensor.display_enabled else "Enable display",
                state=(
                    "disabled"
                    if sensor.visible_state is VisibleState.DISCONNECTED
                    else "normal"
                ),
            )

    def _show_history(self, history: HistorySync) -> None:
        self.history_tree.delete(*self.history_tree.get_children())
        records = sorted(history.records, key=lambda item: (item.sampled_at, item.sensor_id))
        for record in records:
            self.history_tree.insert(
                "",
                "end",
                values=(
                    record.sampled_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                    record.sensor_id,
                    record.sequence,
                    "--"
                    if record.temperature_c is None
                    else f"{record.temperature_c:.2f} deg C",
                    record.data_status.name,
                ),
            )
        record_counts = " + ".join(str(count) for count in history.meta.counts)
        self._write_log(
            f"History synchronized: {record_counts} records, "
            f"boot 0x{history.meta.boot_id:08X}"
        )
        self.status_var.set(
            f"Connected | polling every {CONFIG.service.poll_interval_seconds:g} s"
        )

    def _write_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event["type"]
                if kind == "devices":
                    self.devices = {
                        f"{item.name} - {item.address}": item
                        for item in event["devices"]
                    }
                    self.device_box["values"] = list(self.devices)
                    if self.devices:
                        self.device_box.current(0)
                        self.status_var.set(f"Found {len(self.devices)} thermometer(s)")
                    else:
                        self.status_var.set("No thermometer service found")
                elif kind == "connected":
                    self.status_var.set("Connected securely | synchronizing history")
                    self._write_log("Secure BLE connection established")
                elif kind == "reconnected":
                    self.status_var.set("Reconnected | synchronizing history")
                    self._write_log("Connection restored automatically")
                elif kind == "connection_lost":
                    self.status_var.set(event["message"])
                    self._write_log(event["message"])
                elif kind == "disconnected":
                    self.status_var.set("Disconnected")
                    for button in self.display_buttons.values():
                        button.configure(state="disabled")
                elif kind == "pairing_reset":
                    self.status_var.set("Pairing reset; select Pair & Connect")
                    self._write_log("Windows BLE pairing was reset")
                    for button in self.display_buttons.values():
                        button.configure(state="disabled")
                elif kind == "snapshot":
                    self._show_snapshot(event["snapshot"])
                elif kind == "history":
                    self._show_history(event["history"])
                elif kind == "display":
                    result = event["result"]
                    self._write_log(
                        f"Sensor {result.sensor_id} display is {result.visible_state.name}"
                    )
                elif kind == "status":
                    self.status_var.set(event["message"])
                elif kind == "error":
                    self.status_var.set("Error")
                    self._write_log(f"Error: {event['message']}")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _on_close(self) -> None:
        self.worker.stop()
        self.destroy()


def main() -> None:
    ThermometerApp().mainloop()


if __name__ == "__main__":
    main()
