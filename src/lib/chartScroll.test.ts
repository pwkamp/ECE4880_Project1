import { expect, test } from 'vitest';
import { SCALE_C } from './temperature';
import {
  isPinnedToLive,
  liveScrollLeft,
  plotHeightPx,
  plotWidthPx,
  PX_PER_DEGREE,
  PX_PER_SECOND,
  specWindowScrollTop,
  WINDOW_S,
  yFraction,
  Y_PLOT_MAX,
  Y_PLOT_MIN,
} from './chartScroll';

test('plot is at least 300 s wide at PX_PER_SECOND so a typical viewport can scroll', () => {
  const marginX = 68;
  expect(plotWidthPx(720, marginX)).toBe(WINDOW_S * PX_PER_SECOND);
  expect(WINDOW_S * PX_PER_SECOND).toBeGreaterThan(720 - marginX);
});

test('a very wide viewport still fills the available inner width', () => {
  expect(plotWidthPx(4000, 68)).toBe(4000 - 68);
});

test('live scroll position is flush to the right edge', () => {
  expect(liveScrollLeft(2400, 800)).toBe(1600);
  expect(liveScrollLeft(800, 800)).toBe(0);
});

test('pinned to live when within slop of the right edge', () => {
  expect(isPinnedToLive(1600, 2400, 800)).toBe(true);
  expect(isPinnedToLive(1590, 2400, 800, 12)).toBe(true);
  expect(isPinnedToLive(100, 2400, 800)).toBe(false);
});

test('plot is taller than a 340px viewport so it can scroll vertically', () => {
  const marginY = 52;
  expect(plotHeightPx(340, marginY)).toBe((Y_PLOT_MAX - Y_PLOT_MIN) * PX_PER_DEGREE);
  expect((Y_PLOT_MAX - Y_PLOT_MIN) * PX_PER_DEGREE).toBeGreaterThan(340 - marginY);
});

test('yFraction maps 0 C to the bottom and 60 C to the top', () => {
  expect(yFraction(Y_PLOT_MIN)).toBe(0);
  expect(yFraction(Y_PLOT_MAX)).toBe(1);
  expect(yFraction((Y_PLOT_MIN + Y_PLOT_MAX) / 2)).toBe(0.5);
});

test('spec-window scrollTop puts 50 C at the top of the plot area', () => {
  const plotTop = 16;
  const plotH = (Y_PLOT_MAX - Y_PLOT_MIN) * PX_PER_DEGREE;
  const scrollTop = specWindowScrollTop(plotTop, plotH);
  const y50 = plotTop + (1 - yFraction(SCALE_C.max)) * plotH;
  expect(scrollTop).toBe(y50 - plotTop);
});
