import { MockThermometerSource } from './mockThermometerSource';
import { PythonBleSource } from './pythonBleSource';
import type { ThermometerSource } from './types';

/**
 * THE SWAP POINT.
 *
 * `VITE_DATA_SOURCE=ble` talks to the teammate Python connector
 * (`backend/main.py`, OpenAPI at http://127.0.0.1:8000/docs) and reads
 * temperatures from MySQL when `MYSQL_URL` is set on the Node service.
 * Anything else keeps the in-browser mock.
 */
export const thermometerSource: ThermometerSource =
  import.meta.env.VITE_DATA_SOURCE === 'ble'
    ? new PythonBleSource()
    : new MockThermometerSource();

export * from './types';
