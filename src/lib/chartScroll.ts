/** Chart-recorder window, in seconds. */
export const WINDOW_S = 300;

/** Horizontal scale: wide enough that a laptop viewport cannot show all 300 s at once. */
export const PX_PER_SECOND = 8;

/** Plot inner width in CSS pixels. */
export function plotWidthPx(viewportWidth: number, marginX: number): number {
  const inner = Math.max(0, viewportWidth - marginX);
  return Math.max(inner, WINDOW_S * PX_PER_SECOND);
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
