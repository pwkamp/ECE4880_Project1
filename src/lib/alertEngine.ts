import type { SensorId, ThermometerFrame } from '../datasource/types';

/**
 * The alert rule engine.
 *
 * This one module implements five requirements that together describe a single
 * state machine governing when temperature alerts fire:
 *
 *   SCRUM-633 / SWE-ALR-LLR-715  Alert Source Enum
 *   SCRUM-621 / SWE-ALR-LLR-711  Alert Episode State
 *   SCRUM-622 / SWE-ALR-LLR-712  High Edge Trigger
 *   SCRUM-623 / SWE-ALR-LLR-713  Low Edge Trigger
 *   SCRUM-624 / SWE-ALR-LLR-714  Rearm In Range
 *
 * stepAlertEngine is a pure reducer: (state, frame, rules, recipients) -> new
 * state + the alert events emitted on this frame. It is fed by the existing
 * mock frame stream via src/hooks/useAlertEngine.ts.
 */

/**
 * SCRUM-633 / SWE-ALR-LLR-715 - Alert Source Enum.
 *
 * The monitored signal a rule watches. Each rule stores exactly one of these.
 * erasableSyntaxOnly is enabled in tsconfig, so this is a const object + union
 * rather than a TS enum - the same style as Unit / SwitchState elsewhere.
 */
export const AlertSource = {
  SENSOR_1: 'SENSOR_1',
  SENSOR_2: 'SENSOR_2',
  /** Mean of both sensors. Treated as "no reading" unless BOTH sensors report. */
  AVERAGE: 'AVERAGE',
} as const;

export type AlertSource = (typeof AlertSource)[keyof typeof AlertSource];

const SOURCE_SENSOR: Partial<Record<AlertSource, SensorId>> = {
  [AlertSource.SENSOR_1]: 1,
  [AlertSource.SENSOR_2]: 2,
};

/**
 * SCRUM-621 / SWE-ALR-LLR-711 - Alert Episode State.
 *
 * The current excursion state for one (recipient, rule, source) combination.
 */
export type RuleState = 'NORMAL' | 'HIGH' | 'LOW';

export interface AlertRule {
  id: string;
  /** SCRUM-633: exactly one monitored source per rule. */
  source: AlertSource;
  /**
   * SCRUM-624 rearm band, in Celsius. State returns to NORMAL whenever a valid
   * reading is minC <= value <= maxC.
   */
  minC: number;
  maxC: number;
  enabled: boolean;
  /** Message for the NORMAL/LOW -> HIGH transition. */
  highMessage: string;
  /** Message for the NORMAL/HIGH -> LOW transition. */
  lowMessage: string;
  /** Message for the HIGH -> NORMAL / LOW -> NORMAL recovery transition. */
  clearMessage: string;
}

export interface AlertRecipient {
  id: string;
  /** Free-text phone number or email. Never actually contacted. */
  destination: string;
  enabled: boolean;
}

export interface AlertEvent {
  /** Stable within a run: key + entered state + timestamp. */
  id: string;
  timestamp: number;
  recipientId: string;
  ruleId: string;
  source: AlertSource;
  /** The state that was just entered (the transition target). */
  transition: RuleState;
  destination: string;
  message: string;
  /** The reading that caused the transition. */
  celsius: number;
}

/**
 * SCRUM-621: state is tracked per (recipientId, ruleId, source). Every
 * combination keeps its own independent RuleState.
 */
export interface AlertEngineState {
  states: Record<string, RuleState>;
}

export const INITIAL_ALERT_ENGINE_STATE: AlertEngineState = { states: {} };

export interface AlertEngineStep {
  state: AlertEngineState;
  events: AlertEvent[];
}

const SEP = '::';

/** The composite key an alert episode is tracked under (SCRUM-621 AC). */
export function ruleStateKey(
  recipientId: string,
  ruleId: string,
  source: AlertSource,
): string {
  return [recipientId, ruleId, source].join(SEP);
}

/** Resolve the monitored value for a source from one frame, or null if none. */
export function sourceCelsius(
  frame: ThermometerFrame,
  source: AlertSource,
): number | null {
  if (source === AlertSource.AVERAGE) {
    const a = frame.readings[1].celsius;
    const b = frame.readings[2].celsius;
    return a == null || b == null ? null : (a + b) / 2;
  }
  const sensorId = SOURCE_SENSOR[source];
  return sensorId == null ? null : frame.readings[sensorId].celsius;
}

/** Which zone a reading falls in for a rule's thresholds. */
function zoneFor(celsius: number, rule: AlertRule): RuleState {
  if (celsius > rule.maxC) return 'HIGH';
  if (celsius < rule.minC) return 'LOW';
  return 'NORMAL';
}

function messageFor(rule: AlertRule, zone: RuleState): string {
  switch (zone) {
    case 'HIGH':
      return rule.highMessage;
    case 'LOW':
      return rule.lowMessage;
    case 'NORMAL':
      return rule.clearMessage;
  }
}

/**
 * Advance the alert state machine by one frame.
 *
 *  - SCRUM-622: emit a HIGH alert only on a NORMAL/LOW -> HIGH transition.
 *  - SCRUM-623: emit a LOW alert only on a NORMAL/HIGH -> LOW transition.
 *  - SCRUM-624: a valid reading back within [minC, maxC] resets the state to
 *    NORMAL (rearm), emitting the HIGH->NORMAL / LOW->NORMAL recovery event.
 *
 * Edge-triggered, never level-triggered: repeated samples within the same zone
 * emit nothing. A source with no reading (null) leaves that combination's state
 * untouched - a still-exceeded reading after a data gap is not a fresh crossing.
 */
export function stepAlertEngine(
  prev: AlertEngineState,
  frame: ThermometerFrame,
  rules: readonly AlertRule[],
  recipients: readonly AlertRecipient[],
): AlertEngineStep {
  const states: Record<string, RuleState> = { ...prev.states };
  const events: AlertEvent[] = [];

  for (const recipient of recipients) {
    if (!recipient.enabled) continue;

    for (const rule of rules) {
      if (!rule.enabled) continue;

      const key = ruleStateKey(recipient.id, rule.id, rule.source);
      const current = states[key] ?? 'NORMAL';

      const celsius = sourceCelsius(frame, rule.source);
      if (celsius == null) continue; // hold state across data gaps

      const zone = zoneFor(celsius, rule);
      if (zone === current) continue; // edge-triggered: no repeat within a state

      states[key] = zone;
      events.push({
        id: [key, zone, frame.timestamp].join(SEP),
        timestamp: frame.timestamp,
        recipientId: recipient.id,
        ruleId: rule.id,
        source: rule.source,
        transition: zone,
        destination: recipient.destination,
        message: messageFor(rule, zone),
        celsius,
      });
    }
  }

  return { state: { states }, events };
}
