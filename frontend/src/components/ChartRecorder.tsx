import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { SensorId, ThermometerFrame } from '../datasource/types';
import {
  isPinnedToLive,
  liveScrollLeft,
  plotHeightPx,
  plotWidthPx,
  specWindowScrollTop,
  WINDOW_S,
  yFraction,
  Y_PLOT_MAX,
  Y_PLOT_MIN,
} from '../lib/chartScroll';
import { cToF, type Unit } from '../lib/temperature';

interface Props {
  history: ThermometerFrame[];
  /** Timestamp of the newest frame; the right edge of the chart. */
  nowMs: number;
  unit: Unit;
}

const VIEWPORT_H = 340;
const M = { top: 16, right: 16, bottom: 36, left: 12 };
const Y_LABEL_W = 44;

const COLOR: Record<SensorId, string> = { 1: '#1f5c8b', 2: '#b3541e' };
const GRID = '#e4e4e4';
const AXIS_TEXT = '#555';
const MISSING_FILL = 'rgba(110,110,110,0.13)';

interface Sample {
  x: number;
  celsius: number | null;
}

/**
 * A fixed-scale chart recorder.
 *
 *  - Drawable Y is 0–60 C; the default view is the spec window 10–50 C.
 *  - X axis is "seconds ago", 300 on the left to 0 on the right.
 *  - New points enter at the right; the trace scrolls left; old points fall off.
 *  - Missing data (switch off / unplugged / display off) is drawn as a
 *    hatched band in the sensor's colour. Off-scale readings (outside 0–60 C)
 *    are drawn as a solid triangle clipped to the rail. The two are distinct.
 *  - The chart keeps scrolling during an outage.
 */
export function ChartRecorder({ history, nowMs, unit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const vInitRef = useRef(false);
  const dragRef = useRef<{
    x: number;
    y: number;
    scrollLeft: number;
    scrollTop: number;
  } | null>(null);
  const [viewportW, setViewportW] = useState(720);

  const plotW = plotWidthPx(viewportW, M.left + M.right);
  const plotH = plotHeightPx(VIEWPORT_H, M.top + M.bottom);
  const canvasCssW = M.left + M.right + plotW;
  const canvasCssH = M.top + M.bottom + plotH;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setViewportW(Math.max(360, Math.floor(w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    if (!vInitRef.current) {
      el.scrollTop = specWindowScrollTop(M.top, plotH);
      vInitRef.current = true;
    }
    if (pinnedRef.current) {
      el.scrollLeft = liveScrollLeft(el.scrollWidth, el.clientWidth);
    }
  }, [history, nowMs, canvasCssW, plotH]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasCssW * dpr;
    canvas.height = canvasCssH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvasCssW, canvasCssH);

    const plot = {
      left: M.left,
      right: canvasCssW - M.right,
      top: M.top,
      bottom: canvasCssH - M.bottom,
    };

    const xFor = (secondsAgo: number) =>
      plot.right - (secondsAgo / WINDOW_S) * plotW;
    const yForC = (celsius: number) =>
      plot.bottom - yFraction(celsius) * plotH;

    ctx.font =
      "11px ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";
    ctx.textBaseline = 'middle';

    ctx.strokeStyle = GRID;
    ctx.fillStyle = AXIS_TEXT;
    ctx.lineWidth = 1;
    for (let c = Y_PLOT_MIN; c <= Y_PLOT_MAX; c += 10) {
      const y = yForC(c);
      ctx.beginPath();
      ctx.moveTo(plot.left, y);
      ctx.lineTo(plot.right, y);
      ctx.stroke();
    }

    ctx.textAlign = 'center';
    for (let s = 0; s <= WINDOW_S; s += 60) {
      const x = xFor(s);
      ctx.strokeStyle = GRID;
      ctx.beginPath();
      ctx.moveTo(x, plot.top);
      ctx.lineTo(x, plot.bottom);
      ctx.stroke();
      ctx.fillStyle = AXIS_TEXT;
      ctx.fillText(String(s), x, plot.bottom + 14);
    }

    ctx.strokeStyle = '#bdbdbd';
    ctx.strokeRect(plot.left, plot.top, plotW, plotH);

    ([1, 2] as SensorId[]).forEach((sensorId) => {
      const samples: Sample[] = history.map((f) => ({
        x: xFor((nowMs - f.timestamp) / 1000),
        celsius: f.readings[sensorId].celsius,
      }));

      drawMissingBands(ctx, samples, plot.top, plot.bottom, sensorId);
      drawTrace(ctx, samples, yForC, plot, sensorId);
    });

    drawLegend(ctx, plot.right, yForC(50));
  }, [history, nowMs, unit, canvasCssW, canvasCssH, plotW, plotH]);

  const yTicks: Array<{ c: number; y: number; label: string }> = [];
  for (let c = Y_PLOT_MIN; c <= Y_PLOT_MAX; c += 10) {
    yTicks.push({
      c,
      y: M.top + (1 - yFraction(c)) * plotH,
      label: unit === 'C' ? String(c) : String(Math.round(cToF(c))),
    });
  }

  return (
    <>
      <p className="chart-hint">
        Drag or scroll to look back in time or up and down the temperature scale.
        Newest readings stay on the right; the default view is 10–50 °C.
      </p>
      <div className="chart-frame">
        <div
          className="chart-wrap"
          ref={wrapRef}
          style={{ height: VIEWPORT_H }}
          onScroll={(e) => {
            const el = e.currentTarget;
            pinnedRef.current = isPinnedToLive(
              el.scrollLeft,
              el.scrollWidth,
              el.clientWidth,
            );
          }}
          onPointerDown={(e) => {
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            const el = wrapRef.current;
            if (!el) return;
            dragRef.current = {
              x: e.clientX,
              y: e.clientY,
              scrollLeft: el.scrollLeft,
              scrollTop: el.scrollTop,
            };
            el.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const drag = dragRef.current;
            const el = wrapRef.current;
            if (!drag || !el) return;
            el.scrollLeft = drag.scrollLeft - (e.clientX - drag.x);
            el.scrollTop = drag.scrollTop - (e.clientY - drag.y);
          }}
          onPointerUp={() => {
            dragRef.current = null;
          }}
          onPointerCancel={() => {
            dragRef.current = null;
          }}
        >
          <div
            className="chart-scroll-inner"
            style={{ width: Y_LABEL_W + canvasCssW, height: canvasCssH }}
          >
            <div
              className="chart-y-labels"
              style={{ height: canvasCssH, width: Y_LABEL_W }}
              aria-hidden
            >
              {yTicks.map((t) => (
                <span key={t.c} style={{ top: t.y }}>
                  {t.label}
                </span>
              ))}
            </div>
            <canvas
              ref={canvasRef}
              style={{ width: canvasCssW, height: canvasCssH, display: 'block' }}
            />
          </div>
        </div>
      </div>
      <p className="chart-xaxis-caption">seconds ago from current time</p>
    </>
  );
}

function drawMissingBands(
  ctx: CanvasRenderingContext2D,
  samples: Sample[],
  top: number,
  bottom: number,
  sensorId: SensorId,
) {
  let runStart = -1;
  for (let i = 0; i <= samples.length; i++) {
    const missing = i < samples.length && samples[i].celsius == null;
    if (missing && runStart < 0) runStart = i;
    if (!missing && runStart >= 0) {
      const x0 = samples[runStart - 1]?.x ?? samples[runStart].x;
      const x1 = samples[i]?.x ?? samples[i - 1].x;
      paintBand(ctx, x0, x1, top, bottom, sensorId);
      runStart = -1;
    }
  }
}

/**
 * A missing-data span: a hatched band in the sensor's own colour. Distinct
 * from an off-scale reading, which is a solid filled triangle at the rail.
 */
function paintBand(
  ctx: CanvasRenderingContext2D,
  x0: number,
  x1: number,
  top: number,
  bottom: number,
  sensorId: SensorId,
) {
  const h = bottom - top;
  const w = Math.max(1, x1 - x0);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x0, top, w, h);
  ctx.fillStyle = MISSING_FILL;
  ctx.fill();
  ctx.clip();
  ctx.strokeStyle = COLOR[sensorId];
  ctx.globalAlpha = 0.35;
  ctx.lineWidth = 1;
  const dir = sensorId === 1 ? 1 : -1;
  for (let x = x0 - h; x < x1 + h; x += 8) {
    ctx.beginPath();
    ctx.moveTo(x, bottom);
    ctx.lineTo(x + dir * h, top);
    ctx.stroke();
  }
  ctx.restore();
  if (w > 52) {
    ctx.fillStyle = '#5a5a5a';
    ctx.textAlign = 'center';
    ctx.fillText('no data', (x0 + x1) / 2, top + 10 + (sensorId === 1 ? 0 : 12));
  }
}

function drawTrace(
  ctx: CanvasRenderingContext2D,
  samples: Sample[],
  yForC: (c: number) => number,
  plot: { top: number; bottom: number },
  sensorId: SensorId,
) {
  const color = COLOR[sensorId];
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  let penDown = false;
  for (const s of samples) {
    if (s.celsius == null) {
      penDown = false;
      continue;
    }
    const y = yForC(s.celsius);
    if (penDown) ctx.lineTo(s.x, y);
    else ctx.moveTo(s.x, y);
    penDown = true;
  }
  ctx.stroke();

  for (const s of samples) {
    if (s.celsius == null) continue;
    if (s.celsius >= Y_PLOT_MIN && s.celsius <= Y_PLOT_MAX) continue;
    const high = s.celsius > Y_PLOT_MAX;
    const y = high ? plot.top : plot.bottom;
    ctx.fillStyle = color;
    ctx.beginPath();
    if (high) {
      ctx.moveTo(s.x, y);
      ctx.lineTo(s.x - 4, y + 7);
      ctx.lineTo(s.x + 4, y + 7);
    } else {
      ctx.moveTo(s.x, y);
      ctx.lineTo(s.x - 4, y - 7);
      ctx.lineTo(s.x + 4, y - 7);
    }
    ctx.closePath();
    ctx.fill();
  }
}

function drawLegend(
  ctx: CanvasRenderingContext2D,
  right: number,
  top: number,
) {
  const items: Array<[string, (x: number, y: number) => void]> = [
    ['Sensor 1', (x, y) => swatch(ctx, x, y, COLOR[1])],
    ['Sensor 2', (x, y) => swatch(ctx, x, y, COLOR[2])],
    ['off-scale', (x, y) => {
      ctx.fillStyle = '#333';
      ctx.beginPath();
      ctx.moveTo(x + 6, y - 4);
      ctx.lineTo(x + 2, y + 3);
      ctx.lineTo(x + 10, y + 3);
      ctx.closePath();
      ctx.fill();
    }],
    ['missing', (x, y) => {
      ctx.fillStyle = MISSING_FILL;
      ctx.fillRect(x, y - 5, 12, 10);
      ctx.strokeStyle = 'rgba(70,70,70,0.5)';
      ctx.beginPath();
      ctx.moveTo(x, y + 5);
      ctx.lineTo(x + 12, y - 5);
      ctx.stroke();
    }],
  ];
  ctx.textAlign = 'left';
  let y = top + 8;
  for (const [label, draw] of items) {
    const w = ctx.measureText(label).width + 18;
    const x = right - w;
    draw(x, y);
    ctx.fillStyle = AXIS_TEXT;
    ctx.fillText(label, x + 16, y);
    y += 15;
  }
}

function swatch(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  color: string,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + 12, y);
  ctx.stroke();
}
