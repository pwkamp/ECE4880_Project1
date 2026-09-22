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

export function formatTemp(celsius: number, unit: Unit, digits = 1): string {
  return `${toUnit(celsius, unit).toFixed(digits)} °${unit}`;
}

/** True when a live Celsius reading is outside the 10-50 °C chart window. */
export function isOffScale(celsius: number | null): boolean {
  return celsius != null && (celsius > SCALE_C.max || celsius < SCALE_C.min);
}

export function unitSymbol(unit: Unit): string {
  return `°${unit}`;
}
