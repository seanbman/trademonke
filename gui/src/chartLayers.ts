export type IndicatorKey="htf_bias"|"liquidity_sweep"|"fvg_retest"|"retest_confirmation"|"smt"|"structure";
export type ChartLayerKey="liquidity"|"fvgZones"|"entry"|"stop"|"targets"|"patterns";
export type ChartLayers=Record<ChartLayerKey,boolean>;
export type PatternTypeKey="rising_wedge"|"falling_wedge"|"ascending_triangle"|"descending_triangle"|"flag"|"pennant"|"double_top"|"double_bottom";

export const INDICATORS:{key:IndicatorKey;label:string;description:string;reveals:string}[]=[
  {key:"htf_bias",label:"Higher-timeframe trend",description:"Closes aligned with the 50-period average",reveals:"Context evidence"},
  {key:"liquidity_sweep",label:"Liquidity sweep",description:"Wick crossed a confirmed level and closed back inside",reveals:"Liquidity levels and profit targets"},
  {key:"fvg_retest",label:"Fair value gap retest",description:"Price revisited an active directional gap",reveals:"FVG and entry zones"},
  {key:"retest_confirmation",label:"Retest confirmation",description:"Close confirmed beyond the gap midpoint and prior close",reveals:"Approved entry zone"},
  {key:"smt",label:"Cross-market divergence",description:"BTC and ETH extremes disagreed over the lookback",reveals:"Comparison evidence"},
  {key:"structure",label:"Market structure break",description:"Closed beyond the prior range extreme",reveals:"Structural stop loss"},
];

export const LAYER_LABELS:{key:ChartLayerKey;label:string;unavailable:string}[]=[
  {key:"liquidity",label:"Liquidity",unavailable:"No linked level"},
  {key:"fvgZones",label:"Fair value gap",unavailable:"Not formed yet"},
  {key:"entry",label:"Entry zone",unavailable:"No approved plan"},
  {key:"stop",label:"Stop loss",unavailable:"No approved plan"},
  {key:"targets",label:"Targets",unavailable:"No approved plan"},
  {key:"patterns",label:"Patterns",unavailable:"No soft-label shapes"},
];

export const PATTERN_LABELS:{key:PatternTypeKey;label:string}[]=[
  {key:"rising_wedge",label:"Rising wedge"},
  {key:"falling_wedge",label:"Falling wedge"},
  {key:"ascending_triangle",label:"Ascending triangle"},
  {key:"descending_triangle",label:"Descending triangle"},
  {key:"flag",label:"Flag"},
  {key:"pennant",label:"Pennant"},
  {key:"double_top",label:"Double top"},
  {key:"double_bottom",label:"Double bottom"},
];

export const DEFAULT_LAYERS:ChartLayers={liquidity:true,fvgZones:true,entry:true,stop:true,targets:true,patterns:true};
export const DEFAULT_INDICATORS:Record<IndicatorKey,boolean>={htf_bias:true,liquidity_sweep:true,fvg_retest:true,retest_confirmation:true,smt:true,structure:true};
export const DEFAULT_PATTERN_TYPES:Record<PatternTypeKey,boolean>={
  rising_wedge:true,falling_wedge:true,ascending_triangle:true,descending_triangle:true,
  flag:true,pennant:true,double_top:true,double_bottom:true,
};

const price=(value:unknown)=>{const number=Number(value);return Number.isFinite(number)?new Intl.NumberFormat(undefined,{minimumFractionDigits:2,maximumFractionDigits:number<1?8:2}).format(number):String(value)};

export function evidenceSummary(key:IndicatorKey,value:Record<string,any>|undefined):string{
  if(!value)return "No closed-candle evidence available";
  if(key==="htf_bias")return Object.entries(value.values??{}).map(([timeframe,item]:[string,any])=>item?`${timeframe}: close ${price(item.close)} vs EMA-50 ${price(item.ema50)}`:`${timeframe}: waiting for history`).join(" · ")||"No higher-timeframe values";
  if(key==="liquidity_sweep")return value.level?`Swept level: ${price(value.level)}`:"No confirmed level swept";
  if(key==="fvg_retest")return value.zone?`Gap zone: ${price(value.zone.lower)}–${price(value.zone.upper)} · ${String(value.zone.status).replaceAll("_"," ")}`:"No active directional gap";
  if(key==="retest_confirmation")return value.passed?"Midpoint and prior-close confirmation passed":"Confirmation conditions not met";
  if(key==="smt")return `Compared with ${value.comparison??"unavailable"} · data ${String(value.data_quality??"unknown").replaceAll("_"," ")}`;
  return `Prior range lookback: ${value.lookback??"unavailable"} closed candles`;
}
