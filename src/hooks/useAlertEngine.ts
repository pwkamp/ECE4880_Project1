import { useEffect, useRef, useState } from 'react';
import type { ThermometerFrame } from '../datasource/types';
import {
  INITIAL_ALERT_ENGINE_STATE,
  stepAlertEngine,
  type AlertEngineState,
  type AlertEvent,
  type AlertRecipient,
  type AlertRule,
} from '../lib/alertEngine';

/** How many recent alert events to keep for display. */
const MAX_EVENTS = 40;

/**
 * Runs the SCRUM-621..633 alert state machine against the live frame stream.
 *
 * `frame` is the latest frame from `useThermometer()` - i.e. the same mock data
 * flow the rest of the console renders. There is no separate sensor
 * integration: as each frame arrives the engine advances one step and any
 * transition events are prepended to the returned list.
 *
 * `rules` and `recipients` should be referentially stable (memoise them in the
 * caller); the step is idempotent per frame, so an identity change at most
 * re-runs a no-op.
 */
export function useAlertEngine(
  frame: ThermometerFrame,
  rules: readonly AlertRule[],
  recipients: readonly AlertRecipient[],
): AlertEvent[] {
  const stateRef = useRef<AlertEngineState>(INITIAL_ALERT_ENGINE_STATE);
  const [events, setEvents] = useState<AlertEvent[]>([]);

  useEffect(() => {
    const { state, events: fired } = stepAlertEngine(
      stateRef.current,
      frame,
      rules,
      recipients,
    );
    stateRef.current = state;
    if (fired.length > 0) {
      setEvents((prev) => [...fired.reverse(), ...prev].slice(0, MAX_EVENTS));
    }
  }, [frame, rules, recipients]);

  return events;
}
