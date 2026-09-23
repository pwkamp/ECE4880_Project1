"""Discovery of development tools installed outside the current shell.

The VS Code ESP-IDF extension commonly knows where ESP-IDF lives even when
``idf.py`` is not on PATH.  Qualification uses the same installation instead
of requiring the operator to open a special ESP-IDF terminal first.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EspIdfCommand:
    command: tuple[str, ...]
    idf_path: Path
    source: str


def esp_idf_environment(resolved: EspIdfCommand) -> dict[str, str]:
    """Build the environment normally produced by ESP-IDF's export script."""

    environment = os.environ.copy()
    environment["IDF_PATH"] = str(resolved.idf_path)
    environment["PYTHONUTF8"] = "1"
    if len(resolved.command) < 2:
        return environment

    python = Path(resolved.command[0])
    environment["IDF_PYTHON_ENV_PATH"] = str(python.parent.parent)
    tools_root: Path | None = None
    for ancestor in python.parents:
        if (ancestor / "tools" / "xtensa-esp-elf").is_dir():
            tools_root = ancestor
            break
    if tools_root is not None:
        environment["IDF_TOOLS_PATH"] = str(tools_root)
        # Some VS Code installer layouts put the constraint file under
        # IDF_TOOLS_PATH/tools while ESP-IDF expects it at the root. The venv
        # already has pinned packages, so skip only this redundant check.
        if not any(tools_root.glob("espidf.constraints.*.txt")):
            environment["IDF_PYTHON_CHECK_CONSTRAINTS"] = "no"

    exporter = resolved.idf_path / "tools" / "idf_tools.py"
    if not exporter.is_file():
        return environment
    process = subprocess.run(
        [str(python), str(exporter), "export", "--format", "key-value"],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "ESP-IDF tool export failed")
    original_path = environment.get("PATH", "")
    for line in process.stdout.splitlines():
        if "=" not in line or line.startswith("WARNING:"):
            continue
        key, value = line.split("=", 1)
        if not key.replace("_", "").isalnum():
            continue
        environment[key] = value.replace("%PATH%", original_path).replace("$PATH", original_path)
    return environment


def _existing(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(os.path.expandvars(str(path))).expanduser()
    return candidate.resolve() if candidate.is_file() else None


def _settings_candidates(repository: Path) -> list[tuple[Path, Path | None, str]]:
    settings_path = repository / ".vscode" / "settings.json"
    if not settings_path.is_file():
        return []
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    idf_root = settings.get("idf.espIdfPathWin") or settings.get("idf.espIdfPath")
    python = settings.get("idf.pythonBinPathWin") or settings.get("idf.pythonBinPath")
    if not idf_root:
        return []
    return [(Path(os.path.expandvars(idf_root)) / "tools" / "idf.py", _existing(python), "VS Code settings")]


def resolve_esp_idf(repository: Path) -> EspIdfCommand | None:
    """Return an executable idf.py command, including its Python if needed."""

    on_path = shutil.which("idf.py")
    if on_path:
        path = Path(on_path).resolve()
        idf_path = path.parent.parent
        return EspIdfCommand((str(path),), idf_path, "PATH")

    candidates: list[tuple[Path, Path | None, str]] = []
    env_root = os.environ.get("IDF_PATH")
    if env_root:
        candidates.append((Path(env_root) / "tools" / "idf.py", None, "IDF_PATH"))
    candidates.extend(_settings_candidates(repository))

    if os.name == "nt":
        for value in glob.glob(r"C:\esp\*\esp-idf\tools\idf.py"):
            version_root = Path(value).parents[2]
            python_glob = list(Path(r"C:\Espressif\tools\python").glob("*\\venv\\Scripts\\python.exe"))
            python = sorted(python_glob, reverse=True)[0] if python_glob else None
            candidates.append((Path(value), python, "ESP-IDF/VS Code default install"))
    else:
        candidates.extend(
            (Path(value), None, "common ESP-IDF install")
            for pattern in ("~/esp/esp-idf/tools/idf.py", "~/esp/*/esp-idf/tools/idf.py")
            for value in glob.glob(os.path.expanduser(pattern))
        )

    for script, configured_python, source in candidates:
        script = script.expanduser()
        if not script.is_file():
            continue
        python = configured_python or _existing(os.environ.get("IDF_PYTHON_ENV_PATH") and Path(os.environ["IDF_PYTHON_ENV_PATH"]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        if python is None and os.name == "nt":
            # Match the ESP-IDF version folder when both conventional paths exist.
            version = script.parents[2].name
            python = _existing(Path(r"C:\Espressif\tools\python") / version / "venv" / "Scripts" / "python.exe")
        executable = str(python or sys.executable)
        return EspIdfCommand((executable, str(script.resolve())), script.parent.parent.resolve(), source)
    return None
