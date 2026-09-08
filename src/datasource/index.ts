import { MockThermometerSource } from './mockThermometerSource';
import type { ThermometerSource } from './types';

/**
 * THE SWAP POINT.
 *
 * The whole app imports its data source from here and nowhere else. To run
 * against real third-box hardware, implement `ThermometerSource` (see
 * ./types.ts) in e.g. `realThermometerSource.ts` and change the single line
 * below. Nothing in src/components, src/hooks, or src/lib needs to change.
 *
 *   import { RealThermometerSource } from './realThermometerSource';
 *   export const thermometerSource: ThermometerSource = new RealThermometerSource(
 *     'ws://third-box.local:8080',
 *   );
 */
export const thermometerSource: ThermometerSource = new MockThermometerSource();

export * from './types';
