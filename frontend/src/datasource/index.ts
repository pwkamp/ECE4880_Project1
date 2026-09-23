import { MockThermometerSource } from './mockThermometerSource';
import { BleApiClient } from './bleClient';
import { PythonBleSource } from './pythonBleSource';
import type { ThermometerSource } from './types';

/**
 * THE SWAP POINT.
 *
 * The production/default path talks to the Python connector
 * (`backend/main.py`, OpenAPI at http://127.0.0.1:8000/docs) and reads
 * temperatures from MySQL when `MYSQL_URL` is set on the Node service.
 * Set `VITE_DATA_SOURCE=mock` only for an intentional UI-only simulation.
 */
const configuredSource = import.meta.env.VITE_DATA_SOURCE?.trim().toLowerCase();
const useMockSource =
  configuredSource === 'mock' ||
  (import.meta.env.MODE === 'test' && configuredSource !== 'ble');

export const thermometerSource: ThermometerSource =
  useMockSource
    ? new MockThermometerSource()
    : new PythonBleSource({
        client: new BleApiClient(
          import.meta.env.VITE_BLE_API_BASE?.trim()
            ? { bleBase: import.meta.env.VITE_BLE_API_BASE.trim() }
            : {},
        ),
      });

export * from './types';
