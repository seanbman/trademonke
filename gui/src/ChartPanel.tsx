import {memo, useEffect, useRef} from "react";
import {
  ColorType,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  LineStyle,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type {ChartAnnotation, ChartPayload, ChartPattern, LiveCandle} from "./types";
import type {ChartLayers, PatternTypeKey} from "./chartLayers";
import {levelStatusLabel, levelTypeLabel, patternLabel} from "./presentation";

export type DrawTool = "none" | "horizontal" | "trendline" | "box";

type Props = {
  data: ChartPayload | null;
  live: LiveCandle | null;
  layers: ChartLayers;
  setupIds: string[];
  patternTypes: Record<PatternTypeKey, boolean>;
  simplified?: boolean;
  drawTool?: DrawTool;
  onDrawComplete?: (payload: {kind: DrawTool; geometry: Record<string, number | string>}) => void;
};

type OverlayProps = {
  data: ChartPayload | null;
  layers: ChartLayers;
  setupIds: string[];
  patternTypes: Record<PatternTypeKey, boolean>;
  simplified: boolean;
  drawTool: DrawTool;
  onDrawComplete?: Props["onDrawComplete"];
};

function ChartPanelInner({
  data,
  live,
  layers,
  setupIds,
  patternTypes,
  simplified = false,
  drawTool = "none",
  onDrawComplete,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const zoneLayerRef = useRef<HTMLDivElement | null>(null);
  const pendingRef = useRef<{t: number; p: number} | null>(null);
  const renderZonesRef = useRef<(() => void) | null>(null);
  const fitKeyRef = useRef("");
  const overlayPropsRef = useRef<OverlayProps>({
    data, layers, setupIds, patternTypes, simplified, drawTool, onDrawComplete,
  });
  overlayPropsRef.current = {data, layers, setupIds, patternTypes, simplified, drawTool, onDrawComplete};

  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, {
      height: 520,
      layout: {background: {type: ColorType.Solid, color: "#0a0a0a"}, textColor: "#e8e8e8"},
      grid: {vertLines: {color: "#1a1a1a"}, horzLines: {color: "#1a1a1a"}},
      timeScale: {borderColor: "#333"},
      rightPriceScale: {borderColor: "#333"},
    });
    const series = chart.addCandlestickSeries({
      upColor: "#e8e8e8",
      downColor: "#c41e3a",
      wickUpColor: "#e8e8e8",
      wickDownColor: "#c41e3a",
      borderVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const zoneLayer = document.createElement("div");
    zoneLayer.className = "chart-zones";
    host.current.appendChild(zoneLayer);
    zoneLayerRef.current = zoneLayer;

    const addZone = (
      label: string,
      lower: number,
      upper: number,
      start: string,
      end: string | null,
      className: string,
    ) => {
      const top = series.priceToCoordinate(Math.max(lower, upper));
      const bottom = series.priceToCoordinate(Math.min(lower, upper));
      if (top === null || bottom === null) return;
      const width = chart.paneSize().width;
      const startTime = Math.floor(new Date(start).getTime() / 1000) as UTCTimestamp;
      const endTime = end ? Math.floor(new Date(end).getTime() / 1000) as UTCTimestamp : null;
      const startX = chart.timeScale().timeToCoordinate(startTime);
      const endX = endTime ? chart.timeScale().timeToCoordinate(endTime) : null;
      const left = Math.max(0, startX ?? 0);
      const right = Math.min(width, endX ?? width);
      if (right <= left) return;
      const zone = document.createElement("div");
      zone.className = `chart-zone ${className}`;
      zone.style.left = `${left}px`;
      zone.style.width = `${right - left}px`;
      zone.style.top = `${Math.min(top, bottom)}px`;
      zone.style.height = `${Math.max(3, Math.abs(bottom - top))}px`;
      const caption = document.createElement("span");
      caption.textContent = label;
      zone.appendChild(caption);
      zoneLayer.appendChild(zone);
    };

    const renderZones = () => {
      const props = overlayPropsRef.current;
      zoneLayer.replaceChildren();
      if (!props.data || props.simplified) return;
      if (props.layers.fvgZones) {
        props.data.imbalances
          .filter((item) =>
            props.setupIds.includes(item.episode_id)
            && !["invalidated", "expired", "consumed"].includes(item.status))
          .forEach((item) => addZone(
            `${item.direction.toUpperCase()} FAIR VALUE GAP`,
            +item.lower_price,
            +item.upper_price,
            item.created_at,
            null,
            "fvg-zone",
          ));
      }
      if (props.layers.entry) {
        props.data.recommendations
          .filter((item) =>
            props.setupIds.includes(item.episode_id)
            && item.status === "valid"
            && item.geometry.entry_region)
          .forEach((item) => addZone(
            "APPROVED ENTRY ZONE",
            +item.geometry.entry_region.lower,
            +item.geometry.entry_region.upper,
            item.valid_from,
            item.valid_until,
            "entry-zone",
          ));
      }
      (props.data.annotations ?? [])
        .filter((item) => item.kind === "box")
        .forEach((item) => {
          const g = item.geometry;
          const t1 = new Date(Number(g.t1) * 1000).toISOString();
          const t2 = new Date(Number(g.t2) * 1000).toISOString();
          addZone(item.label, +g.p1, +g.p2, t1, t2, "annotation-zone");
        });
    };
    renderZonesRef.current = renderZones;
    chart.timeScale().subscribeVisibleTimeRangeChange(renderZones);

    const onClick = (param: MouseEventParams<Time>) => {
      const props = overlayPropsRef.current;
      if (props.simplified || props.drawTool === "none" || !props.onDrawComplete
        || !param.point || param.time === undefined) return;
      const price = series.coordinateToPrice(param.point.y);
      if (price === null) return;
      const t = typeof param.time === "number" ? param.time : 0;
      if (props.drawTool === "horizontal") {
        props.onDrawComplete({kind: "horizontal", geometry: {price: String(price)}});
        return;
      }
      if (!pendingRef.current) {
        pendingRef.current = {t, p: price};
        return;
      }
      const first = pendingRef.current;
      pendingRef.current = null;
      props.onDrawComplete({
        kind: props.drawTool,
        geometry: {t1: first.t, p1: String(first.p), t2: t, p2: String(price)},
      });
    };
    chart.subscribeClick(onClick);

    const observer = new ResizeObserver((entries) => {
      chart.applyOptions({width: entries[0].contentRect.width});
      requestAnimationFrame(renderZones);
    });
    observer.observe(host.current);

    return () => {
      observer.disconnect();
      chart.timeScale().unsubscribeVisibleTimeRangeChange(renderZones);
      chart.unsubscribeClick(onClick);
      zoneLayer.remove();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      lineSeriesRef.current = [];
      priceLinesRef.current = [];
      zoneLayerRef.current = null;
      renderZonesRef.current = null;
      pendingRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    for (const line of lineSeriesRef.current) chart.removeSeries(line);
    lineSeriesRef.current = [];
    for (const priceLine of priceLinesRef.current) series.removePriceLine(priceLine);
    priceLinesRef.current = [];

    if (!data) {
      series.setData([]);
      zoneLayerRef.current?.replaceChildren();
      return;
    }

    series.setData(data.candles.map((c) => ({
      time: Math.floor(new Date(c.timestamp).getTime() / 1000) as UTCTimestamp,
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
    })));

    if (!simplified) {
      const lineSeries = lineSeriesRef.current;
      const priceLines = priceLinesRef.current;
      const visibleSetups = data.episodes.filter((item) => setupIds.includes(item.id));
      const visibleLevelIds = new Set(visibleSetups.map((item) => item.liquidity_level_id));
      if (layers.liquidity) {
        data.liquidity_levels
          .filter((level) => visibleLevelIds.has(level.id))
          .forEach((level) => {
            priceLines.push(series.createPriceLine({
              price: +level.price,
              color: level.direction === "long" ? "#e8e8e8" : "#c41e3a",
              lineWidth: 1,
              lineStyle: level.status === "active" ? LineStyle.Solid : LineStyle.Dashed,
              axisLabelVisible: true,
              title: `${levelTypeLabel(level.level_type)} · ${levelStatusLabel(level.status)}`,
            }));
          });
      }
      data.recommendations
        .filter((r) => r.status === "valid" && setupIds.includes(r.episode_id))
        .forEach((rec) => {
          const stop = rec.geometry.initial_stop?.price;
          if (layers.stop && stop) {
            priceLines.push(series.createPriceLine({
              price: +stop,
              color: "#c41e3a",
              lineWidth: 2,
              lineStyle: LineStyle.Solid,
              axisLabelVisible: true,
              title: "STOP LOSS",
            }));
          }
          if (layers.targets) {
            (rec.geometry.profit_boxes ?? []).forEach((tp: {price: string; label: string; r_multiple: string | number}) => {
              priceLines.push(series.createPriceLine({
                price: +tp.price,
                color: "#e8e8e8",
                lineWidth: 1,
                lineStyle: LineStyle.Dashed,
                axisLabelVisible: true,
                title: `${tp.label.toUpperCase()} · ${Number(tp.r_multiple).toFixed(2)}R`,
              }));
            });
          }
        });
      if (layers.patterns) {
        const enabled = (data.patterns ?? []).filter((item) =>
          patternTypes[item.pattern_type as PatternTypeKey] !== false && item.status !== "expired");
        enabled.forEach((pattern) => drawPattern(chart, lineSeries, data, pattern));
      }
      (data.annotations ?? []).forEach((annotation) =>
        drawAnnotation(chart, series, lineSeries, priceLines, annotation));
    }

    const fitKey = `${data.symbol}:${data.timeframe}`;
    if (fitKey !== fitKeyRef.current) {
      fitKeyRef.current = fitKey;
      chart.timeScale().fitContent();
    }
    requestAnimationFrame(() => renderZonesRef.current?.());
  }, [data, layers, setupIds, patternTypes, simplified]);

  useEffect(() => {
    if (!live || !data || !seriesRef.current || simplified) return;
    const liveTime = new Date(live.timestamp).getTime();
    const closedTime = new Date(data.candles.at(-1)?.timestamp ?? 0).getTime();
    if (liveTime <= closedTime) return;
    seriesRef.current.update({
      time: Math.floor(liveTime / 1000) as UTCTimestamp,
      open: +live.open,
      high: +live.high,
      low: +live.low,
      close: +live.close,
    });
  }, [live, data, simplified]);

  return (
    <div className="chart" ref={host}>
      {!data && <div className="empty">Select an asset to load canonical chart data.</div>}
    </div>
  );
}

export const ChartPanel = memo(ChartPanelInner);

function drawAnnotation(
  chart: IChartApi,
  candles: ISeriesApi<"Candlestick">,
  bucket: ISeriesApi<"Line">[],
  priceLines: IPriceLine[],
  annotation: ChartAnnotation,
) {
  const label = annotation.label;
  if (annotation.kind === "horizontal") {
    priceLines.push(candles.createPriceLine({
      price: +annotation.geometry.price,
      color: "#c41e3a",
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      axisLabelVisible: true,
      title: label,
    }));
    return;
  }
  if (annotation.kind === "trendline" || annotation.kind === "ray") {
    const series = chart.addLineSeries({
      color: "#c41e3a",
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      title: label,
    });
    series.setData([
      {time: Number(annotation.geometry.t1) as UTCTimestamp, value: +annotation.geometry.p1},
      {time: Number(annotation.geometry.t2) as UTCTimestamp, value: +annotation.geometry.p2},
    ].sort((a, b) => a.time - b.time));
    bucket.push(series);
  }
}

function drawPattern(
  chart: IChartApi,
  bucket: ISeriesApi<"Line">[],
  data: ChartPayload,
  pattern: ChartPattern,
) {
  const color = pattern.status === "broken" ? "#667986" : "#c41e3a";
  const addLine = (line: {index: number; price: string; timestamp: string}[] | null) => {
    if (!line || line.length < 2) return;
    const series = chart.addLineSeries({
      color,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      title: patternLabel(pattern.pattern_type),
    });
    const points = line.map((point) => {
      const candle = data.candles[point.index];
      const timestamp = candle?.timestamp ?? point.timestamp;
      return {
        time: Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp,
        value: +point.price,
      };
    }).sort((a, b) => a.time - b.time);
    if (pattern.points.length >= 2) {
      const extras = pattern.points.map((point) => {
        const candle = data.candles[point.index];
        const timestamp = candle?.timestamp ?? point.timestamp;
        return {
          time: Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp,
          value: +point.price,
        };
      });
      const byTime = new Map<number, number>();
      [...points, ...extras].forEach((item) => byTime.set(item.time as number, item.value));
      series.setData([...byTime.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([time, value]) => ({time: time as UTCTimestamp, value})));
    } else {
      series.setData(points);
    }
    bucket.push(series);
  };
  addLine(pattern.upper_line);
  addLine(pattern.lower_line);
  if (!pattern.upper_line && !pattern.lower_line && pattern.points.length >= 2) {
    addLine(pattern.points.map((point) => ({
      index: point.index,
      price: point.price,
      timestamp: point.timestamp,
    })));
  }
}
