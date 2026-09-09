import { expect, test } from 'vitest';
import {
  isPinnedToLive,
  liveScrollLeft,
  plotWidthPx,
  PX_PER_SECOND,
  WINDOW_S,
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
