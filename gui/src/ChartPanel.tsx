import {useEffect, useRef} from "react";
import {ColorType, createChart, ISeriesApi, LineStyle, UTCTimestamp} from "lightweight-charts";
import type {ChartPayload,ChartPattern,LiveCandle} from "./types";
import type {ChartLayers,PatternTypeKey} from "./chartLayers";
import {levelStatusLabel,levelTypeLabel,patternLabel} from "./presentation";

type Props={
  data:ChartPayload|null;
  live:LiveCandle|null;
  layers:ChartLayers;
  setupIds:string[];
  patternTypes:Record<PatternTypeKey,boolean>;
  simplified?:boolean;
};

export function ChartPanel({data,live,layers,setupIds,patternTypes,simplified=false}:Props) {
  const host = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick">|null>(null);
  useEffect(() => {
    if (!host.current || !data) return;
    const chart = createChart(host.current, {height:520, layout:{background:{type:ColorType.Solid,color:"#091018"},textColor:"#9aabb9"},grid:{vertLines:{color:"#14202a"},horzLines:{color:"#14202a"}},timeScale:{borderColor:"#263440"},rightPriceScale:{borderColor:"#263440"}});
    const series = chart.addCandlestickSeries({upColor:"#20c997",downColor:"#ff647c",wickUpColor:"#20c997",wickDownColor:"#ff647c",borderVisible:false});
    seriesRef.current=series;
    series.setData(data.candles.map(c => ({time:Math.floor(new Date(c.timestamp).getTime()/1000) as UTCTimestamp,open:+c.open,high:+c.high,low:+c.low,close:+c.close})));
    const lineSeries:ISeriesApi<"Line">[]=[];
    let zoneLayer: HTMLDivElement | null = null;
    let renderZones: (() => void) | null = null;
    if (!simplified) {
      const visibleSetups=data.episodes.filter(item=>setupIds.includes(item.id)),visibleLevelIds=new Set(visibleSetups.map(item=>item.liquidity_level_id));
      if(layers.liquidity)data.liquidity_levels.filter(level=>visibleLevelIds.has(level.id)).forEach(level => series.createPriceLine({price:+level.price,color:level.direction==="long"?"#30a7ff":"#ffb454",lineWidth:1,lineStyle:level.status==="active"?LineStyle.Solid:LineStyle.Dashed,axisLabelVisible:true,title:`${levelTypeLabel(level.level_type)} · ${levelStatusLabel(level.status)}`}));
      data.recommendations.filter(r=>r.status==="valid"&&setupIds.includes(r.episode_id)).forEach(rec => {
        const stop=rec.geometry.initial_stop?.price; if(layers.stop&&stop) series.createPriceLine({price:+stop,color:"#ff647c",lineWidth:2,lineStyle:LineStyle.Solid,axisLabelVisible:true,title:"STOP LOSS"});
        if(layers.targets)(rec.geometry.profit_boxes??[]).forEach((tp:any)=>series.createPriceLine({price:+tp.price,color:"#20c997",lineWidth:1,lineStyle:LineStyle.Dashed,axisLabelVisible:true,title:`${tp.label.toUpperCase()} · ${Number(tp.r_multiple).toFixed(2)}R`}));
      });
      if(layers.patterns){
        const enabled=(data.patterns??[]).filter(item=>patternTypes[item.pattern_type as PatternTypeKey]!==false&&item.status!=="expired");
        enabled.forEach(pattern=>drawPattern(chart,lineSeries,data,pattern));
      }
      zoneLayer=document.createElement("div");zoneLayer.className="chart-zones";host.current.appendChild(zoneLayer);
      const addZone=(label:string,lower:number,upper:number,start:string,end:string|null,className:string)=>{const top=series.priceToCoordinate(Math.max(lower,upper)),bottom=series.priceToCoordinate(Math.min(lower,upper));if(top===null||bottom===null)return;const width=chart.paneSize().width,startTime=Math.floor(new Date(start).getTime()/1000) as UTCTimestamp,endTime=end?Math.floor(new Date(end).getTime()/1000) as UTCTimestamp:null,startX=chart.timeScale().timeToCoordinate(startTime),endX=endTime?chart.timeScale().timeToCoordinate(endTime):null,left=Math.max(0,startX??0),right=Math.min(width,endX??width),zone=document.createElement("div");if(right<=left)return;zone.className=`chart-zone ${className}`;zone.style.left=`${left}px`;zone.style.width=`${right-left}px`;zone.style.top=`${Math.min(top,bottom)}px`;zone.style.height=`${Math.max(3,Math.abs(bottom-top))}px`;const caption=document.createElement("span");caption.textContent=label;zone.appendChild(caption);zoneLayer?.appendChild(zone)};
      renderZones=()=>{zoneLayer?.replaceChildren();if(layers.fvgZones)data.imbalances.filter(item=>setupIds.includes(item.episode_id)&&!["invalidated","expired","consumed"].includes(item.status)).forEach(item=>addZone(`${item.direction.toUpperCase()} FAIR VALUE GAP`,+item.lower_price,+item.upper_price,item.created_at,null,"fvg-zone"));if(layers.entry)data.recommendations.filter(item=>setupIds.includes(item.episode_id)&&item.status==="valid"&&item.geometry.entry_region).forEach(item=>addZone("APPROVED ENTRY ZONE",+item.geometry.entry_region.lower,+item.geometry.entry_region.upper,item.valid_from,item.valid_until,"entry-zone"))};
      requestAnimationFrame(renderZones);chart.timeScale().subscribeVisibleTimeRangeChange(renderZones);
    }
    chart.timeScale().fitContent();
    const observer=new ResizeObserver(entries=>{chart.applyOptions({width:entries[0].contentRect.width});if(renderZones)requestAnimationFrame(renderZones)}); observer.observe(host.current);
    return()=>{seriesRef.current=null;observer.disconnect();if(renderZones)chart.timeScale().unsubscribeVisibleTimeRangeChange(renderZones);zoneLayer?.remove();chart.remove()};
  },[data,layers,setupIds,patternTypes,simplified]);
  useEffect(()=>{if(!live||!data||!seriesRef.current||simplified)return;const liveTime=new Date(live.timestamp).getTime(),closedTime=new Date(data.candles.at(-1)?.timestamp??0).getTime();if(liveTime<=closedTime)return;seriesRef.current.update({time:Math.floor(liveTime/1000) as UTCTimestamp,open:+live.open,high:+live.high,low:+live.low,close:+live.close})},[live,data,simplified]);
  return <div className="chart" ref={host}>{!data&&<div className="empty">Select an asset to load canonical chart data.</div>}</div>;
}

function drawPattern(chart:ReturnType<typeof createChart>,bucket:ISeriesApi<"Line">[],data:ChartPayload,pattern:ChartPattern){
  const color=pattern.status==="broken"?"#667986":"#c58cff";
  const addLine=(line:{index:number;price:string;timestamp:string}[]|null)=>{
    if(!line||line.length<2)return;
    const series=chart.addLineSeries({color,lineWidth:1,lineStyle:LineStyle.Dashed,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,title:patternLabel(pattern.pattern_type)});
    series.setData(line.map(point=>{
      const candle=data.candles[point.index];
      const timestamp=candle?.timestamp??point.timestamp;
      return {time:Math.floor(new Date(timestamp).getTime()/1000) as UTCTimestamp,value:+point.price};
    }));
    bucket.push(series);
  };
  addLine(pattern.upper_line);
  addLine(pattern.lower_line);
  if(!pattern.upper_line&&!pattern.lower_line&&pattern.points.length>=2){
    addLine(pattern.points.map(point=>({index:point.index,price:point.price,timestamp:point.timestamp})));
  }
}
