import { SCALE_C } from './temperature';

/** Chart-recorder window, in seconds. */
export const WINDOW_S = 300;

/** Horizontal scale: wide enough that a laptop viewport cannot show all 300 s at once. */
export const PX_PER_SECOND = 8;

/** Drawable Y range. The spec window (10–50 C) is the default view; 0 C and 60 C are a scroll away. */
export const Y_PLOT_MIN = 0;
export const Y_PLOT_MAX = 60;

/** Vertical scale: tall enough that a 340px viewport cannot show 0–60 C at once. */
export const PX_PER_DEGREE = 8;

/** Plot inner width in CSS pixels. */
export function plotWidthPx(viewportWidth: number, marginX: number): number {
  const inner = Math.max(0, viewportWidth - marginX);
  return Math.max(inner, WINDOW_S * PX_PER_SECOND);
}

/** Plot inner height in CSS pixels. */
export function plotHeightPx(viewportHeight: number, marginY: number): number {
  const inner = Math.max(0, viewportHeight - marginY);
  return Math.max(inner, (Y_PLOT_MAX - Y_PLOT_MIN) * PX_PER_DEGREE);
}

/**
 * Vertical position of a Celsius value on the drawable scale, as a fraction
 * where 0 = bottom (Y_PLOT_MIN) and 1 = top (Y_PLOT_MAX). Unclamped.
 */
export function yFraction(celsius: number): number {
  return (celsius - Y_PLOT_MIN) / (Y_PLOT_MAX - Y_PLOT_MIN);
}

/** scrollTop that puts the spec-window max (50 C) at the top of the plot area. */
export function specWindowScrollTop(plotTop: number, plotH: number): number {
  const y50 = plotTop + (1 - yFraction(SCALE_C.max)) * plotH;
  return y50 - plotTop;
}

/** scrollLeft that shows the live (right) edge. */
export function liveScrollLeft(scrollWidth: number, clientWidth: number): number {
  return Math.max(0, scrollWidth - clientWidth);
}

/** True when the viewport is flush (or nearly flush) to the live edge. */
export function isPinnedToLive(
  scrollLeft: number,
  scrollWidth: number,
  clientWidth: number,
  slop = 12,
): boolean {
  return scrollLeft + clientWidth >= scrollWidth - slop;
}
