import { useMemo, useState } from 'react';
import { AlertLog } from './components/AlertLog';
import { AlertSettings } from './components/AlertSettings';
import { ChartRecorder } from './components/ChartRecorder';
import { DebugPanel } from './components/DebugPanel';
import { DevicePanel } from './components/DevicePanel';
import { RealtimeReadout } from './components/RealtimeReadout';
import { SensorControls } from './components/SensorControls';
import { thermometerSource, SENSOR_IDS, supportsBle } from './datasource';
import { useAlertEngine } from './hooks/useAlertEngine';
import { useAlertNotifier } from './hooks/useAlertNotifier';
import { useThermometer } from './hooks/useThermometer';
import {
  AlertSource,
  type AlertRecipient,
  type AlertRule,
} from './lib/alertEngine';
import { DEFAULT_ALERT_CONFIG, type AlertConfig } from './lib/alerts';
import type { Unit } from './lib/temperature';

/** Sent when a sensor comes back inside the configured band (SCRUM-624). */
const CLEAR_MESSAGE = 'Temperature back within the configured range.';

export default function App() {
  const { frame, history } = useThermometer();
  const [unit, setUnit] = useState<Unit>('C');
  const [alertConfig, setAlertConfig] = useState<AlertConfig>(DEFAULT_ALERT_CONFIG);

  // Adapt the single UI config into the alert engine's rule/recipient model.
  // One rule per physical sensor; the destination becomes the sole recipient.
  const rules = useMemo<AlertRule[]>(() => {
    const shared = {
      minC: alertConfig.minC,
      maxC: alertConfig.maxC,
      enabled: alertConfig.enabled,
      highMessage: alertConfig.maxMessage,
      lowMessage: alertConfig.minMessage,
      clearMessage: CLEAR_MESSAGE,
    };
    return [
      { id: 'sensor-1', source: AlertSource.SENSOR_1, ...shared },
      { id: 'sensor-2', source: AlertSource.SENSOR_2, ...shared },
    ];
  }, [alertConfig]);

  const recipients = useMemo<AlertRecipient[]>(
    () => [{ id: 'primary', destination: alertConfig.destination, enabled: true }],
    [alertConfig.destination],
  );

  const alerts = useAlertEngine(frame, rules, recipients);
  const delivery = useAlertNotifier(alerts);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Networked Thermometer</h1>
          <p className="subtitle">
            {supportsBle(thermometerSource)
              ? 'Computer console — Python BLE connector'
              : 'Computer console — mock data source'}
          </p>
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
        <DevicePanel />
        <SensorControls frame={frame} />
        <AlertSettings config={alertConfig} onChange={setAlertConfig} unit={unit} />
        <AlertLog alerts={alerts} unit={unit} delivery={delivery} />
        <DebugPanel frame={frame} />
      </div>
    </div>
  );
}
