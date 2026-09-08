import { useEffect, useRef, useState } from 'react';
import { thermometerSource } from '../datasource';
import type { ThermometerFrame } from '../datasource/types';

/** The chart-recorder window, in seconds. */
export const WINDOW_SECONDS = 300;

export interface ThermometerState {
  /** The latest frame. */
  frame: ThermometerFrame;
  /** Frames for roughly the last WINDOW_SECONDS, oldest first. */
  history: ThermometerFrame[];
}

function trim(history: ThermometerFrame[], now: number): ThermometerFrame[] {
  const cutoff = now - WINDOW_SECONDS * 1000;
  const start = history.findIndex((f) => f.timestamp >= cutoff);
  return start <= 0 ? history : history.slice(start);
}

/**
 * Subscribes to the data source and keeps a rolling window of history.
 *
 * Seeds from `getHistory()` on mount so the chart is populated immediately,
 * then appends one frame per tick. This is the only place the app touches the
 * data source's stream; components receive plain data.
 */
export function useThermometer(): ThermometerState {
  const [state, setState] = useState<ThermometerState>(() => {
    const now = Date.now();
    return {
      frame: thermometerSource.getFrame(),
      history: trim(thermometerSource.getHistory(WINDOW_SECONDS), now),
    };
  });

  const historyRef = useRef<ThermometerFrame[]>(state.history);

  useEffect(() => {
    // Re-seed on mount in case time passed between initial state and effect.
    historyRef.current = trim(
      thermometerSource.getHistory(WINDOW_SECONDS),
      Date.now(),
    );
    setState({
      frame: thermometerSource.getFrame(),
      history: historyRef.current,
    });

    const unsubscribe = thermometerSource.subscribe((frame) => {
      const next = trim(
        [...historyRef.current, frame],
        frame.timestamp,
      );
      historyRef.current = next;
      setState({ frame, history: next });
    });

    thermometerSource.start();
    return unsubscribe;
  }, []);

  return state;
}
