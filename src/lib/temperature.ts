export type Unit = 'C' | 'F';

/** Fixed chart-recorder scale, from the spec. Never auto-scales. */
export const SCALE_C = { min: 10, max: 50 } as const;

export function cToF(celsius: number): number {
  return celsius * (9 / 5) + 32;
}

/** Convert a raw Celsius reading to the display unit. */
export function toUnit(celsius: number, unit: Unit): number {
  return unit === 'C' ? celsius : cToF(celsius);
}

/** The chart scale bounds expressed in the display unit. */
export function scaleBounds(unit: Unit): { min: number; max: number } {
  return unit === 'C'
    ? { min: SCALE_C.min, max: SCALE_C.max }
    : { min: cToF(SCALE_C.min), max: cToF(SCALE_C.max) };
}

/**
 * Vertical position of a Celsius value on the fixed scale, as a fraction where
 * 0 = bottom (10 C) and 1 = top (50 C). Values outside [0, 1] are off-scale.
 */
export function scaleFraction(celsius: number): number {
  return (celsius - SCALE_C.min) / (SCALE_C.max - SCALE_C.min);
}

export function formatTemp(celsius: number, unit: Unit, digits = 1): string {
  return `${toUnit(celsius, unit).toFixed(digits)} °${unit}`;
}

export function unitSymbol(unit: Unit): string {
  return `°${unit}`;
}
