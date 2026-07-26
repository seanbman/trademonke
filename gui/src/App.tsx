import {Fragment,useCallback,useEffect,useMemo,useState} from "react";
import {ChartPanel} from "./ChartPanel";
import {IndicatorGuide} from "./IndicatorGuide";
import {WatchlistRail} from "./WatchlistRail";
import type {Alert,Bootstrap,ChartPayload,Episode,EpisodeEvent,ExecutionConsole,Health,LiveCandle,WorkstationMessage} from "./types";
import {DEFAULT_INDICATORS,DEFAULT_LAYERS,DEFAULT_PATTERN_TYPES,evidenceSummary,INDICATORS,LAYER_LABELS,PATTERN_LABELS} from "./chartLayers";
import type {ChartLayerKey,IndicatorKey,PatternTypeKey} from "./chartLayers";
import {indicatorCatalogId,layerCatalogId,patternCatalogId} from "./indicatorCatalog";
import {compactPrice,humanizeAlert,isTerminalState,patternLabel,reasonLabel,scoreStateLabel,setupTitle,stateCopy,threeQuestions} from "./presentation";
import "./styles.css";

const api=async<T,>(url:string,token:string,options:RequestInit={}):Promise<T>=>{const response=await fetch(url,{...options,headers:{"Content-Type":"application/json","X-GUI-Token":token,...options.headers}});if(!response.ok)throw new Error(`${response.status} ${response.statusText}`);return response.json()};

export default function App(){
  const [token,setToken]=useState(()=>sessionStorage.getItem("gui-token")??""),[draftToken,setDraftToken]=useState(""),[boot,setBoot]=useState<Bootstrap|null>(null),[chart,setChart]=useState<ChartPayload|null>(null),[liveCandle,setLiveCandle]=useState<LiveCandle|null>(null),[livePrices,setLivePrices]=useState<Record<string,string>>({}),[events,setEvents]=useState<EpisodeEvent[]>([]),[health,setHealth]=useState<Health|null>(null),[alerts,setAlerts]=useState<Alert[]>([]),[execution,setExecution]=useState<ExecutionConsole|null>(null),[symbol,setSymbol]=useState(""),[timeframe,setTimeframe]=useState("5m"),[stream,setStream]=useState<"connecting"|"live"|"offline">("offline"),[feeder,setFeeder]=useState<"live"|"cached"|"offline">("offline"),[market,setMarket]=useState<"connecting"|"waiting"|"live"|"stale"|"offline">("offline"),[lastMarketAt,setLastMarketAt]=useState(0),[error,setError]=useState("");
  const [indicatorDirection,setIndicatorDirection]=useState<"long"|"short">("long"),[enabledIndicators,setEnabledIndicators]=useState(DEFAULT_INDICATORS),[layers,setLayers]=useState(DEFAULT_LAYERS),[selectedIndicator,setSelectedIndicator]=useState<IndicatorKey>("fvg_retest");
  const [patternTypes,setPatternTypes]=useState(DEFAULT_PATTERN_TYPES);
  const [visibleSetupIds,setVisibleSetupIds]=useState<string[]>([]),[focusedSetupId,setFocusedSetupId]=useState<string|null>(null),[setupContextKey,setSetupContextKey]=useState(""),[episodeEvents,setEpisodeEvents]=useState<Record<string,EpisodeEvent[]>>({});
  const [showSignalDetail,setShowSignalDetail]=useState(false),[showAdvanced,setShowAdvanced]=useState(false);
  const [guideOpen,setGuideOpen]=useState(false),[guideId,setGuideId]=useState<string|null>(null);
  const openGuide=(id?:string)=>{setGuideId(id??null);setGuideOpen(true)};
  useEffect(()=>{if(!token)return;api<Bootstrap>("/api/v1/gui/bootstrap",token).then(data=>{setBoot(data);setSymbol(data.watchlist[0]?.symbol??"");setError("")}).catch(e=>{setError(String(e));setToken("");sessionStorage.removeItem("gui-token")})},[token]);
  useEffect(()=>{if(!symbol||!token)return;let socket:WebSocket|null=null,retry:number|undefined,stopped=false,delay=1000;setChart(null);setLiveCandle(null);setEvents([]);setEpisodeEvents({});setMarket("connecting");const connect=()=>{setStream("connecting");const protocol=location.protocol==="https:"?"wss":"ws";socket=new WebSocket(`${protocol}://${location.host}/api/v1/gui/ws`);socket.onopen=()=>{delay=1000;socket?.send(JSON.stringify({type:"subscribe",token,symbol,timeframe}))};socket.onmessage=event=>{const message=JSON.parse(event.data) as WorkstationMessage;setStream("live");if(message.type==="snapshot"){setBoot(message.data.bootstrap);setChart(message.data.chart);setHealth(message.data.health);setAlerts(message.data.alerts);setExecution(message.data.execution);setEpisodeEvents((message.data as {episode_events?:Record<string,EpisodeEvent[]>}).episode_events??{});setError("")}else if(message.type==="feeder_status"){setFeeder(message.status);if(message.status!=="live"){setLiveCandle(null);setMarket(message.status==="cached"?"stale":"offline")}}else if(message.type==="market_status"){setMarket(message.status==="connected"?"waiting":"offline");if(message.status==="connected")setFeeder("live");else if(message.status==="disconnected")setFeeder("offline")}else if(message.type==="live_price"){setFeeder("live");setLivePrices(prices=>({...prices,[message.symbol]:message.price}));setLastMarketAt(Date.now());setMarket("live")}else if(message.type==="live_candle"&&message.symbol===symbol&&message.timeframe===timeframe){setLiveCandle(message.candle)}};socket.onerror=()=>socket?.close();socket.onclose=()=>{if(stopped)return;setStream("offline");setFeeder("offline");setMarket("offline");retry=window.setTimeout(connect,delay);delay=Math.min(delay*2,30000)}};connect();return()=>{stopped=true;if(retry!==undefined)window.clearTimeout(retry);socket?.close()}},[symbol,timeframe,token]);
  useEffect(()=>{const timer=window.setInterval(()=>{if(market==="live"&&Date.now()-lastMarketAt>15000)setMarket("stale")},5000);return()=>window.clearInterval(timer)},[market,lastMarketAt]);
  const degraded=feeder!=="live";
  const potentialSetups=useMemo(()=>degraded?[]:(chart?.episodes??[]).slice().sort((a,b)=>new Date(b.updated_at).getTime()-new Date(a.updated_at).getTime()),[chart,degraded]);
  useEffect(()=>{if(!chart)return;const key=`${chart.symbol}:${chart.timeframe}`;if(key===setupContextKey)return;const preferred=potentialSetups.find(item=>!isTerminalState(item.current_state))??potentialSetups[0]??null;setVisibleSetupIds(preferred?[preferred.id]:[]);setFocusedSetupId(preferred?.id??null);if(preferred)setIndicatorDirection(preferred.direction);setSetupContextKey(key)},[chart,potentialSetups,setupContextKey]);
  const focusedSetup=potentialSetups.find(item=>item.id===focusedSetupId)??null;
  useEffect(()=>{if(!focusedSetupId||degraded){setEvents([]);return}if(episodeEvents[focusedSetupId]){setEvents(episodeEvents[focusedSetupId]);return}if(!token)return;api<EpisodeEvent[]>(`/episodes/${encodeURIComponent(focusedSetupId)}/events`,token).then(setEvents).catch(()=>setEvents([]))},[focusedSetupId,token,degraded,episodeEvents]);
  const latestCandle=chart?.candles.at(-1)?.timestamp;
  const formingCandle=!degraded&&liveCandle&&latestCandle&&new Date(liveCandle.timestamp)>new Date(latestCandle)?liveCandle:null;
  const recommendation=chart?.recommendations.find(r=>r.status==="valid"&&r.episode_id===focusedSetupId);
  const indicatorSnapshot=chart?.indicator_snapshots.find(item=>item.direction===indicatorDirection);
  const selectedEvidence=indicatorSnapshot?.components[selectedIndicator];
  const availableLayers=useMemo(()=>{const ids=new Set(visibleSetupIds),setups=(chart?.episodes??[]).filter(item=>ids.has(item.id)),levelIds=new Set((chart?.liquidity_levels??[]).map(item=>item.id)),plans=(chart?.recommendations??[]).filter(item=>ids.has(item.episode_id)&&item.status==="valid"),patternCount=(chart?.patterns??[]).filter(item=>patternTypes[item.pattern_type as PatternTypeKey]!==false).length;return {liquidity:setups.some(item=>levelIds.has(item.liquidity_level_id)),fvgZones:(chart?.imbalances??[]).some(item=>ids.has(item.episode_id)&&!["invalidated","expired","consumed"].includes(item.status)),entry:plans.some(item=>Boolean(item.geometry.entry_region)),stop:plans.some(item=>Boolean(item.geometry.initial_stop?.price)),targets:plans.some(item=>(item.geometry.profit_boxes??[]).length>0),patterns:patternCount>0}},[chart,visibleSetupIds,patternTypes]);
  const effectiveLayers=useMemo(()=>({...layers,liquidity:layers.liquidity&&availableLayers.liquidity,fvgZones:layers.fvgZones&&availableLayers.fvgZones,entry:layers.entry&&availableLayers.entry,stop:layers.stop&&availableLayers.stop,targets:layers.targets&&availableLayers.targets,patterns:layers.patterns&&availableLayers.patterns}),[layers,availableLayers]);
  const activePatterns=useMemo(()=>(chart?.patterns??[]).filter(item=>patternTypes[item.pattern_type as PatternTypeKey]!==false&&item.status!=="expired"),[chart,patternTypes]);
  const primaryPattern=activePatterns[0]??null;
  const questions=useMemo(()=>{
    const hasLiquidity=Boolean(focusedSetup&&(chart?.liquidity_levels??[]).some(level=>level.id===focusedSetup.liquidity_level_id));
    const hasFvg=(chart?.imbalances??[]).some(item=>item.episode_id===focusedSetupId&&!["invalidated","expired","consumed"].includes(item.status));
    const patternTag=primaryPattern?.pattern_type??null;
    const hint=primaryPattern?.direction_hint;
    const patternConflictsWithContext=Boolean(hint&&indicatorSnapshot?.components?.htf_bias?.passed===false);
    return threeQuestions({indicatorSnapshot,focusedState:focusedSetup?.current_state,hasLiquidity,hasFvg,patternTag,patternConflictsWithContext});
  },[chart,focusedSetup,focusedSetupId,indicatorSnapshot,primaryPattern]);
  const focusSetup=(setup:Episode)=>{setFocusedSetupId(setup.id);setIndicatorDirection(setup.direction);setVisibleSetupIds([setup.id])};
  const toggleLayer=(key:ChartLayerKey)=>setLayers(items=>({...items,[key]:!items[key]}));
  const togglePatternType=(key:PatternTypeKey)=>setPatternTypes(items=>({...items,[key]:!items[key]}));
  const toggleIndicator=(key:IndicatorKey)=>{setSelectedIndicator(key);setEnabledIndicators(items=>({...items,[key]:!items[key]}))};
  const displayPrice=(value:string|undefined)=>compactPrice(value);
  const refreshBootstrap=useCallback(()=>{if(!token)return;api<Bootstrap>("/api/v1/gui/bootstrap",token).then(data=>{setBoot(data);setError("")}).catch(e=>setError(String(e)))},[token]);
  const reportError=useCallback((message:string)=>setError(message),[ ]);
  const login=(event:React.FormEvent)=>{event.preventDefault();sessionStorage.setItem("gui-token",draftToken);setToken(draftToken)};
  const acknowledge=(alert:Alert)=>api(`/api/v1/gui/alerts/${encodeURIComponent(alert.event_id)}/ack`,token,{method:"POST",body:JSON.stringify({user_id:"gui-operator"})}).then(()=>setAlerts(items=>items.map(item=>item.event_id===alert.event_id?{...item,acknowledged:true}:item))).catch(e=>setError(String(e)));
  const shadow=(planId:string)=>api(`/api/v1/gui/execution/${planId}/shadow`,token,{method:"POST",body:JSON.stringify({user_id:"gui-operator"})}).then(()=>api<ExecutionConsole>("/api/v1/gui/execution",token).then(setExecution)).catch(e=>setError(String(e)));
  const reconcile=(planId:string)=>api(`/api/v1/gui/execution/${planId}/reconcile`,token,{method:"POST",body:JSON.stringify({user_id:"gui-operator",would_fill:true,slippage_bps:"0"})}).then(()=>api<ExecutionConsole>("/api/v1/gui/execution",token).then(setExecution)).catch(e=>setError(String(e)));
  if(!token)return <main className="login"><form onSubmit={login}><span className="eyebrow">PRIVATE RESEARCH WORKSTATION</span><h1>TradeMonke <i>Lab</i></h1><p>Enter the server-side GUI access token. It is retained for this browser session only.</p><input type="password" value={draftToken} onChange={e=>setDraftToken(e.target.value)} autoFocus/><button>Open workstation</button>{error&&<div className="error">{error}</div>}</form></main>;
  return <main>
    <header><div><span className="eyebrow">RESEARCH WORKSTATION</span><h1>TradeMonke <i>Lab</i></h1></div><div className="controls"><button type="button" className="guide-launch" onClick={()=>openGuide()}>Guide</button><span className={stream==="live"?"good":"bad"}>WS {stream==="live"?"CONNECTED":stream.toUpperCase()}</span><span className={market==="live"?"good":"bad"}>MARKET {market.toUpperCase()}</span><span className={boot?.controls.paused?"bad":"good"}>{boot?.controls.paused?"PAUSED":"ACTIVE"}</span><span className="dry">DRY RUN · SPOT</span></div></header>
    {degraded&&<div className="degraded-banner">Local data source offline — showing cached snapshots (max 24h)</div>}
    {error&&<div className="error">{error}</div>}
    <section className="workspace">
      <aside>
        <WatchlistRail token={token} assets={boot?.watchlist??[]} selected={symbol} livePrices={livePrices} displayPrice={displayPrice} onSelect={setSymbol} onWatchlistChanged={refreshBootstrap} onError={reportError}/>
        {!degraded&&<>
          <div className="rail-heading"><div><h2>Ideas</h2><span>One focused setup on the chart</span></div></div>
          {potentialSetups.length?potentialSetups.slice(0,6).map(setup=>{
            const copy=stateCopy(setup.current_state),focused=focusedSetupId===setup.id;
            return <div className={`setup-card ${focused?"focused visible":""}`} key={setup.id}>
              <button className="setup-main" onClick={()=>focusSetup(setup)}>
                <span><b className={setup.direction}>{setupTitle(setup.direction)}</b><small>{new Date(setup.updated_at).toLocaleString()}</small></span>
                <strong>{copy.label}</strong>
                <small>{copy.description}</small>
              </button>
            </div>;
          }):<p className="muted setup-empty">No setup candidates for this market and timeframe.</p>}
        </>}
      </aside>
      <div className="primary">
        <div className="toolbar">
          <div>
            <b>{symbol||"No asset"}</b>
            <strong title="Kraken live best-bid-offer midpoint" className="live-quote">{displayPrice(livePrices[symbol])}</strong>
            <span className="quote-kind">BBO MID</span>
            {latestCandle&&<span className="freshness">Last closed bar {new Date(latestCandle).toLocaleString()}</span>}
            {formingCandle&&<span className="forming">Live bar forming</span>}
          </div>
          <select value={timeframe} onChange={e=>setTimeframe(e.target.value)}>{["5m","15m","30m","1h","4h","1d"].map(tf=><option key={tf}>{tf}</option>)}</select>
        </div>
        {!degraded&&<div className="three-questions">
          <article><span>1 · Context</span><strong>{questions.context.answer}</strong><small>{questions.context.detail}</small></article>
          <article><span>2 · Location</span><strong>{questions.location.answer}</strong><small>{questions.location.detail}</small>{questions.location.patternTag&&<em className="pattern-tag">{patternLabel(questions.location.patternTag)} · soft tag</em>}</article>
          <article><span>3 · Confirmation</span><strong>{questions.confirmation.answer}</strong><small>{questions.confirmation.detail}</small></article>
        </div>}
        {!degraded&&<div className="overlay-bar">
          <span>Overlays</span>
          {LAYER_LABELS.map(item=>{
            const available=availableLayers[item.key];
            return <span className="overlay-chip" key={item.key}>
              <button disabled={!available} aria-pressed={effectiveLayers[item.key]} className={`${effectiveLayers[item.key]?"on":""} ${available?"":"unavailable"}`} title={available?`Toggle ${item.label}`:item.unavailable} onClick={()=>toggleLayer(item.key)}>{item.label}</button>
              <button type="button" className="info-btn" title={`About ${item.label}`} aria-label={`About ${item.label}`} onClick={()=>openGuide(layerCatalogId(item.key))}>ⓘ</button>
            </span>;
          })}
          <div className="direction-tabs compact">
            <button className={indicatorDirection==="long"?"active long":""} onClick={()=>setIndicatorDirection("long")}>Long</button>
            <button className={indicatorDirection==="short"?"active short":""} onClick={()=>setIndicatorDirection("short")}>Short</button>
          </div>
        </div>}
        {!degraded&&layers.patterns&&<div className="pattern-kit">
          <span>Pattern kit <small>optional location tags · never a signal</small></span>
          {PATTERN_LABELS.map(item=><span className="overlay-chip" key={item.key}>
            <button aria-pressed={patternTypes[item.key]} className={patternTypes[item.key]?"on":""} onClick={()=>togglePatternType(item.key)}>{item.label}</button>
            <button type="button" className="info-btn" title={`About ${item.label}`} aria-label={`About ${item.label}`} onClick={()=>openGuide(patternCatalogId(item.key))}>ⓘ</button>
          </span>)}
        </div>}
        <ChartPanel data={chart} live={formingCandle} layers={effectiveLayers} setupIds={visibleSetupIds} patternTypes={patternTypes} simplified={degraded}/>
        {!degraded&&<div className="legend">
          <span className="forming">Live bar · display only</span>
          <span className="blue">Support liquidity</span>
          <span className="amber">Resistance liquidity</span>
          <span className="violet">Pattern soft-label</span>
          <span className="green">Profit target</span>
          <span className="red">Stop loss</span>
        </div>}
        {!degraded&&<details className="collapsible" open={showSignalDetail} onToggle={e=>setShowSignalDetail((e.target as HTMLDetailsElement).open)}>
          <summary>Signal detail <small>{indicatorSnapshot?`${indicatorSnapshot.score} of 6 · ${scoreStateLabel(indicatorSnapshot.setup_state)}`:"Waiting for snapshot"}</small></summary>
          <div className="indicator-deck nested">
            <div className="indicator-grid">{INDICATORS.map(item=>{const evidence=indicatorSnapshot?.components[item.key],passed=Boolean(evidence?.passed),enabled=enabledIndicators[item.key];return <div className="indicator-cell" key={item.key}><button aria-pressed={enabled} className={`indicator-toggle ${enabled?"enabled":"disabled"} ${passed?"passed":"missing"} ${selectedIndicator===item.key?"focused":""}`} onClick={()=>toggleIndicator(item.key)} title={item.description}><span>{item.label}</span><strong>{passed?"Confirmed":"Not confirmed"}</strong><em>{enabled?"Tracked":"Ignored"}</em></button><button type="button" className="info-btn" title={`About ${item.label}`} aria-label={`About ${item.label}`} onClick={()=>openGuide(indicatorCatalogId(item.key))}>ⓘ</button></div>})}</div>
            <div className="evidence-detail"><div><b>{INDICATORS.find(item=>item.key===selectedIndicator)?.label}</b><small>{INDICATORS.find(item=>item.key===selectedIndicator)?.description}</small><button type="button" className="info-link" onClick={()=>openGuide(indicatorCatalogId(selectedIndicator))}>Open guide page</button></div><span>{evidenceSummary(selectedIndicator,selectedEvidence)}</span></div>
          </div>
        </details>}
      </div>
      <aside className="inspector">
        <h2>Focused idea</h2>
        {focusedSetup&&!degraded?<div className={`state ${focusedSetup.direction}`}><small>{setupTitle(focusedSetup.direction).toUpperCase()}</small><strong>{stateCopy(focusedSetup.current_state).label}</strong><span>{stateCopy(focusedSetup.current_state).description}</span><small>Furthest: {stateCopy(focusedSetup.highest_state_reached).label}</small></div>:<p className="muted">Choose an idea from the left rail.</p>}
        {!degraded&&focusedSetup&&<>
          <h3>Progress</h3>
          <ol>{events.map(event=><li key={event.event_id}><time>{new Date(event.occurred_at).toLocaleString()}</time><b>{stateCopy(event.current_state).label}</b><small>{event.reason_codes.map(reasonLabel).join(" · ")}</small></li>)}</ol>
        </>}
        <h2>Research plan</h2>
        {recommendation&&!degraded?<div className="plan"><span className="valid">GEOMETRY · V{recommendation.version}</span><dl><dt>Entry zone</dt><dd>{compactPrice(recommendation.geometry.entry_region?.lower)}–{compactPrice(recommendation.geometry.entry_region?.upper)}</dd><dt>Stop loss</dt><dd>{compactPrice(recommendation.geometry.initial_stop?.price)}</dd>{(recommendation.geometry.profit_boxes??[]).map((tp:any)=><Fragment key={tp.label}><dt>{tp.label.toUpperCase()}</dt><dd>{compactPrice(tp.price)} · {Number(tp.r_multiple).toFixed(2)}R</dd></Fragment>)}</dl><small>Research geometry only · no order connected</small></div>:<p className="muted">No approved plan for the focused idea yet.</p>}
        <details className="collapsible" open={showAdvanced} onToggle={e=>setShowAdvanced((e.target as HTMLDetailsElement).open)}>
          <summary>Advanced</summary>
          <h2>Connections</h2>
          <div className="health"><b className={health?.status==="healthy"?"good":"bad"}>{health?.status==="healthy"?"Healthy":"Needs attention"}</b><small>Feed: {health?.feed_status} · DB: {health?.database}</small><small className={feeder==="live"?"good":"bad"}>Feeder: {feeder}</small></div>
          <h2>Shadow execution</h2>
          <div className="operator"><b>{execution?.mode==="disabled"?"ORDER SUBMISSION DISABLED":`MODE · ${execution?.mode??"loading"}`}</b><span className="bad">DRY RUN {execution?.dry_run_submission_locked?"LOCKED":"AVAILABLE"}</span><small>Shadow review only — not live trading.</small>{execution?.plans.slice(0,3).map(plan=><div className="operator-plan" key={plan.id}><span>{plan.id} · {plan.status.replaceAll("_"," ")}</span><button disabled={execution.mode!=="shadow"||execution.controls.paused||execution.controls.kill_switch} onClick={()=>shadow(plan.id)}>Create shadow</button><button disabled={!execution.events.some(event=>event.trade_plan_id===plan.id&&event.event_type==="shadow_order")} onClick={()=>reconcile(plan.id)}>Reconcile</button></div>)}</div>
          <h2>Recent alerts</h2>
          <div className="alerts">{alerts.slice(0,8).map(alert=><button key={alert.event_id} disabled={alert.acknowledged} onClick={()=>acknowledge(alert)}><b>{alert.symbol} · {alert.score} of 6</b><small>{humanizeAlert(alert.message)}</small><span>{alert.acknowledged?"REVIEWED":"MARK REVIEWED"}</span></button>)}</div>
        </details>
      </aside>
    </section>
    <IndicatorGuide open={guideOpen} initialId={guideId} onClose={()=>setGuideOpen(false)}/>
  </main>
}
