import { useEffect, useRef, useState } from 'react';
import { AlertLog } from './components/AlertLog';
import { AlertSettings } from './components/AlertSettings';
import { ChartRecorder } from './components/ChartRecorder';
import { DebugPanel } from './components/DebugPanel';
import { RealtimeReadout } from './components/RealtimeReadout';
import { SensorControls } from './components/SensorControls';
import { SENSOR_IDS } from './datasource/types';
import { useThermometer } from './hooks/useThermometer';
import {
  DEFAULT_ALERT_CONFIG,
  EMPTY_LATCH,
  evaluateAlerts,
  type AlertConfig,
  type AlertLatch,
  type SimulatedAlert,
} from './lib/alerts';
import type { Unit } from './lib/temperature';

const MAX_LOG = 40;

export default function App() {
  const { frame, history } = useThermometer();
  const [unit, setUnit] = useState<Unit>('C');
  const [alertConfig, setAlertConfig] = useState<AlertConfig>(DEFAULT_ALERT_CONFIG);
  const [alerts, setAlerts] = useState<SimulatedAlert[]>([]);
  const latchRef = useRef<AlertLatch>(EMPTY_LATCH);

  useEffect(() => {
    const { latch, fired } = evaluateAlerts(frame, alertConfig, latchRef.current);
    latchRef.current = latch;
    if (fired.length > 0) {
      setAlerts((prev) => [...fired.reverse(), ...prev].slice(0, MAX_LOG));
    }
  }, [frame, alertConfig]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Networked Thermometer</h1>
          <p className="subtitle">Computer console &mdash; mock data source</p>
        </div>
        <div className="unit-toggle" role="group" aria-label="Temperature unit">
          {(['C', 'F'] as Unit[]).map((u) => (
            <button
              key={u}
              type="button"
              className={u === unit ? 'active' : ''}
              onClick={() => setUnit(u)}
            >
              °{u}
            </button>
          ))}
        </div>
      </header>

      <section className="readouts">
        {SENSOR_IDS.map((id) => (
          <RealtimeReadout key={id} frame={frame} sensorId={id} unit={unit} />
        ))}
      </section>

      <section className="chart-section">
        <h2>Temperature history &mdash; last 300 s</h2>
        <ChartRecorder history={history} nowMs={frame.timestamp} unit={unit} />
      </section>

      <div className="panels">
        <SensorControls frame={frame} />
        <AlertSettings config={alertConfig} onChange={setAlertConfig} unit={unit} />
        <AlertLog alerts={alerts} unit={unit} />
        <DebugPanel frame={frame} />
      </div>
    </div>
  );
}
