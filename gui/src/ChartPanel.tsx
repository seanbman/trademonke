import {useEffect, useRef} from "react";
import {ColorType, createChart, ISeriesApi, LineStyle, UTCTimestamp} from "lightweight-charts";
import type {ChartAnnotation,ChartPayload,ChartPattern,LiveCandle} from "./types";
import type {ChartLayers,PatternTypeKey} from "./chartLayers";
import {levelStatusLabel,levelTypeLabel,patternLabel} from "./presentation";

export type DrawTool = "none" | "horizontal" | "trendline" | "box";

type Props={
  data:ChartPayload|null;
  live:LiveCandle|null;
  layers:ChartLayers;
  setupIds:string[];
  patternTypes:Record<PatternTypeKey,boolean>;
  simplified?:boolean;
  drawTool?:DrawTool;
  onDrawComplete?:(payload:{kind:DrawTool;geometry:Record<string,number|string>})=>void;
};

export function ChartPanel({data,live,layers,setupIds,patternTypes,simplified=false,drawTool="none",onDrawComplete}:Props) {
  const host = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick">|null>(null);
  const pendingRef = useRef<{t:number;p:number}|null>(null);
  useEffect(() => {
    if (!host.current || !data) return;
    const chart = createChart(host.current, {height:520, layout:{background:{type:ColorType.Solid,color:"#0a0a0a"},textColor:"#e8e8e8"},grid:{vertLines:{color:"#1a1a1a"},horzLines:{color:"#1a1a1a"}},timeScale:{borderColor:"#333"},rightPriceScale:{borderColor:"#333"}});
    const series = chart.addCandlestickSeries({upColor:"#e8e8e8",downColor:"#c41e3a",wickUpColor:"#e8e8e8",wickDownColor:"#c41e3a",borderVisible:false});
    seriesRef.current=series;
    series.setData(data.candles.map(c => ({time:Math.floor(new Date(c.timestamp).getTime()/1000) as UTCTimestamp,open:+c.open,high:+c.high,low:+c.low,close:+c.close})));
    const lineSeries:ISeriesApi<"Line">[]=[];
    let zoneLayer: HTMLDivElement | null = null;
    let renderZones: (() => void) | null = null;
    if (!simplified) {
      const visibleSetups=data.episodes.filter(item=>setupIds.includes(item.id)),visibleLevelIds=new Set(visibleSetups.map(item=>item.liquidity_level_id));
      if(layers.liquidity)data.liquidity_levels.filter(level=>visibleLevelIds.has(level.id)).forEach(level => series.createPriceLine({price:+level.price,color:level.direction==="long"?"#e8e8e8":"#c41e3a",lineWidth:1,lineStyle:level.status==="active"?LineStyle.Solid:LineStyle.Dashed,axisLabelVisible:true,title:`${levelTypeLabel(level.level_type)} · ${levelStatusLabel(level.status)}`}));
      data.recommendations.filter(r=>r.status==="valid"&&setupIds.includes(r.episode_id)).forEach(rec => {
        const stop=rec.geometry.initial_stop?.price; if(layers.stop&&stop) series.createPriceLine({price:+stop,color:"#c41e3a",lineWidth:2,lineStyle:LineStyle.Solid,axisLabelVisible:true,title:"STOP LOSS"});
        if(layers.targets)(rec.geometry.profit_boxes??[]).forEach((tp:any)=>series.createPriceLine({price:+tp.price,color:"#e8e8e8",lineWidth:1,lineStyle:LineStyle.Dashed,axisLabelVisible:true,title:`${tp.label.toUpperCase()} · ${Number(tp.r_multiple).toFixed(2)}R`}));
      });
      if(layers.patterns){
        const enabled=(data.patterns??[]).filter(item=>patternTypes[item.pattern_type as PatternTypeKey]!==false&&item.status!=="expired");
        enabled.forEach(pattern=>drawPattern(chart,lineSeries,data,pattern));
      }
      (data.annotations??[]).forEach(annotation=>drawAnnotation(chart,series,lineSeries,annotation));
      zoneLayer=document.createElement("div");zoneLayer.className="chart-zones";host.current.appendChild(zoneLayer);
      const addZone=(label:string,lower:number,upper:number,start:string,end:string|null,className:string)=>{const top=series.priceToCoordinate(Math.max(lower,upper)),bottom=series.priceToCoordinate(Math.min(lower,upper));if(top===null||bottom===null)return;const width=chart.paneSize().width,startTime=Math.floor(new Date(start).getTime()/1000) as UTCTimestamp,endTime=end?Math.floor(new Date(end).getTime()/1000) as UTCTimestamp:null,startX=chart.timeScale().timeToCoordinate(startTime),endX=endTime?chart.timeScale().timeToCoordinate(endTime):null,left=Math.max(0,startX??0),right=Math.min(width,endX??width),zone=document.createElement("div");if(right<=left)return;zone.className=`chart-zone ${className}`;zone.style.left=`${left}px`;zone.style.width=`${right-left}px`;zone.style.top=`${Math.min(top,bottom)}px`;zone.style.height=`${Math.max(3,Math.abs(bottom-top))}px`;const caption=document.createElement("span");caption.textContent=label;zone.appendChild(caption);zoneLayer?.appendChild(zone)};
      renderZones=()=>{zoneLayer?.replaceChildren();if(layers.fvgZones)data.imbalances.filter(item=>setupIds.includes(item.episode_id)&&!["invalidated","expired","consumed"].includes(item.status)).forEach(item=>addZone(`${item.direction.toUpperCase()} FAIR VALUE GAP`,+item.lower_price,+item.upper_price,item.created_at,null,"fvg-zone"));if(layers.entry)data.recommendations.filter(item=>setupIds.includes(item.episode_id)&&item.status==="valid"&&item.geometry.entry_region).forEach(item=>addZone("APPROVED ENTRY ZONE",+item.geometry.entry_region.lower,+item.geometry.entry_region.upper,item.valid_from,item.valid_until,"entry-zone"));
        (data.annotations??[]).filter(item=>item.kind==="box").forEach(item=>{
          const g=item.geometry;const t1=new Date(Number(g.t1)*1000).toISOString();const t2=new Date(Number(g.t2)*1000).toISOString();
          addZone(item.label,+g.p1,+g.p2,t1,t2,"annotation-zone");
        });
      };
      requestAnimationFrame(renderZones);chart.timeScale().subscribeVisibleTimeRangeChange(renderZones);
      chart.subscribeClick(param=>{
        if(drawTool==="none"||!onDrawComplete||!param.point||param.time===undefined)return;
        const price=series.coordinateToPrice(param.point.y);
        if(price===null)return;
        const t=typeof param.time==="number"?param.time:0;
        if(drawTool==="horizontal"){
          onDrawComplete({kind:"horizontal",geometry:{price:String(price)}});
          return;
        }
        if(!pendingRef.current){
          pendingRef.current={t,p:price};
          return;
        }
        const first=pendingRef.current;
        pendingRef.current=null;
        onDrawComplete({
          kind:drawTool,
          geometry:{t1:first.t,p1:String(first.p),t2:t,p2:String(price)},
        });
      });
    }
    chart.timeScale().fitContent();
    const observer=new ResizeObserver(entries=>{chart.applyOptions({width:entries[0].contentRect.width});if(renderZones)requestAnimationFrame(renderZones)}); observer.observe(host.current);
    return()=>{seriesRef.current=null;pendingRef.current=null;observer.disconnect();if(renderZones)chart.timeScale().unsubscribeVisibleTimeRangeChange(renderZones);zoneLayer?.remove();chart.remove()};
  },[data,layers,setupIds,patternTypes,simplified,drawTool,onDrawComplete]);
  useEffect(()=>{if(!live||!data||!seriesRef.current||simplified)return;const liveTime=new Date(live.timestamp).getTime(),closedTime=new Date(data.candles.at(-1)?.timestamp??0).getTime();if(liveTime<=closedTime)return;seriesRef.current.update({time:Math.floor(liveTime/1000) as UTCTimestamp,open:+live.open,high:+live.high,low:+live.low,close:+live.close})},[live,data,simplified]);
  return <div className="chart" ref={host}>{!data&&<div className="empty">Select an asset to load canonical chart data.</div>}</div>;
}

function drawAnnotation(chart:ReturnType<typeof createChart>,candles:ISeriesApi<"Candlestick">,bucket:ISeriesApi<"Line">[],annotation:ChartAnnotation){
  const label=annotation.label;
  if(annotation.kind==="horizontal"){
    candles.createPriceLine({price:+annotation.geometry.price,color:"#c41e3a",lineWidth:1,lineStyle:LineStyle.Solid,axisLabelVisible:true,title:label});
    return;
  }
  if(annotation.kind==="trendline"||annotation.kind==="ray"){
    const series=chart.addLineSeries({color:"#c41e3a",lineWidth:1,lineStyle:LineStyle.Solid,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,title:label});
    series.setData([
      {time:Number(annotation.geometry.t1) as UTCTimestamp,value:+annotation.geometry.p1},
      {time:Number(annotation.geometry.t2) as UTCTimestamp,value:+annotation.geometry.p2},
    ].sort((a,b)=>a.time-b.time));
    bucket.push(series);
  }
}

function drawPattern(chart:ReturnType<typeof createChart>,bucket:ISeriesApi<"Line">[],data:ChartPayload,pattern:ChartPattern){
  const color=pattern.status==="broken"?"#667986":"#c41e3a";
  const addLine=(line:{index:number;price:string;timestamp:string}[]|null)=>{
    if(!line||line.length<2)return;
    // Span the full formation: extend from first to last formation point using candle timestamps
    const series=chart.addLineSeries({color,lineWidth:1,lineStyle:LineStyle.Dashed,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,title:patternLabel(pattern.pattern_type)});
    const points=line.map(point=>{
      const candle=data.candles[point.index];
      const timestamp=candle?.timestamp??point.timestamp;
      return {time:Math.floor(new Date(timestamp).getTime()/1000) as UTCTimestamp,value:+point.price};
    }).sort((a,b)=>a.time-b.time);
    // Ensure span covers earliest and latest pattern points when available
    if(pattern.points.length>=2){
      const extras=pattern.points.map(point=>{
        const candle=data.candles[point.index];
        const timestamp=candle?.timestamp??point.timestamp;
        return {time:Math.floor(new Date(timestamp).getTime()/1000) as UTCTimestamp,value:+point.price};
      });
      const byTime=new Map<number,number>();
      [...points,...extras].forEach(item=>byTime.set(item.time as number,item.value));
      series.setData([...byTime.entries()].sort((a,b)=>a[0]-b[0]).map(([time,value])=>({time:time as UTCTimestamp,value})));
    }else{
      series.setData(points);
    }
    bucket.push(series);
  };
  addLine(pattern.upper_line);
  addLine(pattern.lower_line);
  if(!pattern.upper_line&&!pattern.lower_line&&pattern.points.length>=2){
    addLine(pattern.points.map(point=>({index:point.index,price:point.price,timestamp:point.timestamp})));
  }
}
