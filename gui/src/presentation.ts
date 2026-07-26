const STATE_COPY:Record<string,{label:string;description:string;terminal?:boolean}>={
  observed:{label:"Watching level",description:"A confirmed liquidity level is being monitored."},
  swept:{label:"Liquidity sweep",description:"Price traded through the level and closed back inside."},
  reclaimed:{label:"Level reclaimed",description:"Price closed back on the setup side of the swept level."},
  displaced:{label:"Momentum confirmed",description:"A strong directional candle confirmed movement away from the level."},
  imbalance_created:{label:"Fair value gap formed",description:"A directional gap formed after the momentum move."},
  retested:{label:"Entry retest",description:"Price returned to the fair value gap and met the retest condition."},
  armed:{label:"Setup qualified",description:"All required setup checks currently pass."},
  approved:{label:"Plan approved",description:"Risk checks passed and research plan geometry is available."},
  accepted_breakout:{label:"Level broken",description:"Price closed through the level instead of rejecting it.",terminal:true},
  failed_recovery:{label:"Reclaim failed",description:"Price did not recover the swept level.",terminal:true},
  invalidated:{label:"Setup invalidated",description:"The setup no longer meets its invalidation rules.",terminal:true},
  expired:{label:"Setup expired",description:"The setup aged out before completion.",terminal:true},
};

const REASON_COPY:Record<string,string>={
  linked_level_sweep:"Liquidity level swept",
  close_reclaimed_level:"Price reclaimed the level",
  close_failed_reclaim:"Price failed to reclaim the level",
  directional_body_threshold:"Momentum candle confirmed",
  linked_directional_fvg:"Fair value gap formed",
  linked_zone_retested:"Price retested the entry zone",
  all_mandatory_gates_passed:"All setup checks passed",
  mandatory_gate_failed:"A required setup check failed",
  disarmed:"Setup returned to watch status",
  risk_approved:"Risk review approved",
};

export const stateCopy=(state:string)=>STATE_COPY[state]??{label:state.replaceAll("_"," "),description:"Stored setup lifecycle state."};
export const reasonLabel=(reason:string)=>REASON_COPY[reason]??reason.replaceAll("_"," ");
export const setupTitle=(direction:string)=>direction==="long"?"Long idea":"Short idea";
export const isTerminalState=(state:string)=>Boolean(STATE_COPY[state]?.terminal);
export const levelTypeLabel=(value:string)=>({swing_low:"Swing low",swing_high:"Swing high",equal_low:"Equal lows",equal_high:"Equal highs"}[value]??value.replaceAll("_"," "));
export const levelStatusLabel=(value:string)=>({active:"Active",swept:"Swept",accepted_breakout:"Broken",expired:"Expired"}[value]??value.replaceAll("_"," "));
export const scoreStateLabel=(value:string)=>({developing:"Early signal",watch:"Watchlist",strong_watch:"Strong setup",eligible:"All six confirmed"}[value]??value.replaceAll("_"," "));

export function humanizeAlert(message:string):string{
  const replacements:Record<string,string>={htf_bias:"higher-timeframe trend",liquidity_sweep:"liquidity sweep",fvg_retest:"fair value gap retest",retest_confirmation:"retest confirmation",smt:"cross-market divergence",structure:"market structure"};
  return Object.entries(replacements).reduce((text,[raw,label])=>text.replaceAll(raw,label),message);
}

export function compactPrice(value:string|number|undefined|null):string{
  if(value===undefined||value===null||value==="")return "—";
  const number=Number(value);
  if(!Number.isFinite(number))return String(value);
  return new Intl.NumberFormat(undefined,{minimumFractionDigits:2,maximumFractionDigits:number<1?8:2}).format(number);
}

export const patternLabel=(value:string)=>({
  rising_wedge:"Rising wedge",
  falling_wedge:"Falling wedge",
  ascending_triangle:"Ascending triangle",
  descending_triangle:"Descending triangle",
  flag:"Flag",
  pennant:"Pennant",
  double_top:"Double top",
  double_bottom:"Double bottom",
}[value]??value.replaceAll("_"," "));

export type ThreeQuestions={
  context:{answer:string;detail:string};
  location:{answer:string;detail:string;patternTag:string|null};
  confirmation:{answer:string;detail:string};
};

/** Derive the learner three questions from closed-candle evidence. Patterns are tags only. */
export function threeQuestions(input:{
  indicatorSnapshot:{components:Record<string,Record<string,any>>;setup_state:string;score:number}|null|undefined;
  focusedState:string|null|undefined;
  hasLiquidity:boolean;
  hasFvg:boolean;
  patternTag:string|null;
  patternConflictsWithContext:boolean;
}):ThreeQuestions{
  const htf=input.indicatorSnapshot?.components?.htf_bias;
  const retest=input.indicatorSnapshot?.components?.retest_confirmation;
  const structure=input.indicatorSnapshot?.components?.structure;
  let contextAnswer="Unsure";
  let contextDetail="Waiting for higher-timeframe closed-candle evidence.";
  if(htf?.passed){
    contextAnswer="Trend aligned";
    contextDetail="Higher-timeframe closes agree with the selected direction.";
  }else if(htf){
    contextAnswer="Chop / unclear";
    contextDetail="Higher-timeframe bias is not confirmed on closed candles.";
  }

  const locationBits:string[]=[];
  if(input.hasLiquidity)locationBits.push("liquidity level");
  if(input.hasFvg)locationBits.push("fair value gap");
  const patternTag=input.patternTag;
  let locationAnswer=locationBits.length?locationBits.join(" + "):"No clear location yet";
  let locationDetail=locationBits.length
    ?"Structure near measured levels or gaps."
    :"No active level or gap tied to the focused idea.";
  if(patternTag){
    locationDetail=`Optional tag: ${patternLabel(patternTag)} (shape nickname only).`;
    if(input.patternConflictsWithContext){
      locationDetail+=` Context disagrees — prefer context over the pattern.`;
    }
  }

  let confirmationAnswer="Waiting";
  let confirmationDetail="Need a closed-candle confirmation before treating location as actionable.";
  const state=input.focusedState??"";
  if(["retested","armed","approved"].includes(state)||retest?.passed){
    confirmationAnswer="Confirmed";
    confirmationDetail=stateCopy(state||"retested").description;
  }else if(["displaced","imbalance_created","swept","reclaimed"].includes(state)){
    confirmationAnswer="Developing";
    confirmationDetail=stateCopy(state).description;
  }else if(structure?.passed){
    confirmationAnswer="Structure break only";
    confirmationDetail="A range extreme broke on a close — still require the full location story.";
  }

  return {
    context:{answer:contextAnswer,detail:contextDetail},
    location:{answer:locationAnswer,detail:locationDetail,patternTag},
    confirmation:{answer:confirmationAnswer,detail:confirmationDetail},
  };
}
