import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
} from "lightweight-charts";
import type { PriceBar } from "../lib/api";

// Theme colors as canvas-safe hex (lightweight-charts renders to canvas).
const C = {
  bg: "rgba(0,0,0,0)",
  grid: "rgba(120,130,160,0.08)",
  text: "#8b94a6",
  up: "#43c98c",
  down: "#e7615a",
  volume: "#3a3f4d",
};

export function PriceChart({ bars }: { bars: PriceBar[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: C.bg },
        textColor: C.text,
        fontFamily: "ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: C.grid },
        horzLines: { color: C.grid },
      },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid },
      crosshair: { mode: 0 },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: C.up,
      downColor: C.down,
      borderUpColor: C.up,
      borderDownColor: C.down,
      wickUpColor: C.up,
      wickDownColor: C.down,
    });
    candles.setData(
      bars.map((b) => ({
        time: b.datetime.slice(0, 10),
        open: b.open_price,
        high: b.max_price,
        low: b.min_price,
        close: b.closed_price,
      })),
    );

    const volume = chart.addSeries(HistogramSeries, {
      color: C.volume,
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(
      bars.map((b) => ({
        time: b.datetime.slice(0, 10),
        value: b.volume,
        color: b.closed_price >= b.open_price ? `${C.up}55` : `${C.down}55`,
      })),
    );

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [bars]);

  return <div ref={ref} className="w-full" />;
}
