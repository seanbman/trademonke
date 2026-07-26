import {useEffect, useState} from "react";

export type WatchlistAsset = {symbol: string; status: string; protected: boolean};
export type SymbolHit = {
  symbol: string;
  base: string;
  quote: string;
  active: boolean;
  on_watchlist: boolean;
  watchlist_status: string | null;
  protected: boolean;
  quote_volume: number | null;
  spread_bps: number | null;
  recommendation: string | null;
  source: string;
  display_name?: string;
  subtitle?: string;
  last_price?: string | null;
  price_kind?: string | null;
};
type PendingChange = {
  change_id: string;
  symbol: string;
  target_status: string;
  message: string;
};

type Props = {
  token: string;
  assets: WatchlistAsset[];
  selected: string;
  livePrices: Record<string, string>;
  displayPrice: (value: string | undefined) => string;
  onSelect: (symbol: string) => void;
  onWatchlistChanged: () => void;
  onError: (message: string) => void;
};

const api = async <T,>(url: string, token: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(url, {
    ...options,
    headers: {"Content-Type": "application/json", "X-GUI-Token": token, ...options.headers},
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return response.json();
};

function hitStatusLabel(hit: SymbolHit): string {
  if (hit.on_watchlist) return hit.watchlist_status || "watchlist";
  if (hit.recommendation === "investigate") return "candidate";
  if (hit.active) return "available";
  return "inactive";
}

export function WatchlistRail({
  token, assets, selected, livePrices, displayPrice, onSelect, onWatchlistChanged, onError,
}: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SymbolHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 1) {
      setHits([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setSearching(true);
      api<{items: SymbolHit[]}>(`/api/v1/gui/watchlist/search?q=${encodeURIComponent(trimmed)}&limit=20`, token)
        .then((data) => {
          if (!cancelled) setHits(data.items);
        })
        .catch((error) => {
          if (!cancelled) {
            setHits([]);
            onError(String(error));
          }
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 280);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, token, onError]);

  const requestChange = (symbol: string, action: "probe" | "add" | "remove") => {
    setBusy(true);
    api<PendingChange>("/api/v1/gui/watchlist/changes", token, {
      method: "POST",
      body: JSON.stringify({symbol, action, user_id: "gui-operator"}),
    })
      .then((change) => setPending(change))
      .catch((error) => onError(String(error)))
      .finally(() => setBusy(false));
  };

  const confirmPending = () => {
    if (!pending) return;
    setBusy(true);
    api<{symbol: string; status: string}>(
      `/api/v1/gui/watchlist/changes/${encodeURIComponent(pending.change_id)}/confirm`,
      token,
      {method: "POST", body: JSON.stringify({user_id: "gui-operator"})},
    )
      .then((asset) => {
        setPending(null);
        setQuery("");
        setHits([]);
        onSelect(asset.symbol);
        onWatchlistChanged();
      })
      .catch((error) => onError(String(error)))
      .finally(() => setBusy(false));
  };

  return (
    <>
      <h2>Watchlist</h2>
      <div className="watchlist-search">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search symbols (SOL, LINK…)"
          aria-label="Search symbols"
        />
        {searching && <small className="muted">Searching…</small>}
      </div>
      {pending && (
        <div className="watchlist-pending">
          <b>{pending.symbol} → {pending.target_status}</b>
          <small>{pending.message}</small>
          <div className="watchlist-pending-actions">
            <button disabled={busy} onClick={confirmPending}>Confirm</button>
            <button disabled={busy} className="ghost" onClick={() => setPending(null)}>Cancel</button>
          </div>
        </div>
      )}
      {hits.length > 0 && (
        <div className="watchlist-hits">
          {hits.map((hit) => {
            const price = hit.last_price || livePrices[hit.symbol];
            const name = hit.display_name || hit.base;
            const subtitle = hit.subtitle || `${hit.quote} spot`;
            return (
              <div className="watchlist-hit" key={hit.symbol}>
                <button className="hit-main" onClick={() => onSelect(hit.symbol)} disabled={!hit.on_watchlist}>
                  <span className="asset-line">
                    <b>{hit.symbol}</b>
                    <strong
                      title={hit.price_kind === "bbo_midpoint" ? "BBO midpoint" : hit.price_kind || "Search price"}
                      className={price ? "live-price" : "muted"}
                    >
                      {price ? displayPrice(price) : "—"}
                    </strong>
                  </span>
                  <small>
                    {name} · {subtitle} · {hitStatusLabel(hit)}
                    {hit.quote_volume != null ? ` · vol $${Math.round(hit.quote_volume).toLocaleString()}` : ""}
                  </small>
                </button>
                {!hit.on_watchlist && hit.active && (
                  <button disabled={busy} className="hit-action" onClick={() => requestChange(hit.symbol, "probe")}>
                    Add probe
                  </button>
                )}
                {hit.on_watchlist && hit.watchlist_status === "probe" && (
                  <button disabled={busy} className="hit-action" onClick={() => requestChange(hit.symbol, "add")}>
                    Promote
                  </button>
                )}
                {hit.on_watchlist && !hit.protected && hit.watchlist_status !== "disabled" && (
                  <button disabled={busy} className="hit-action danger" onClick={() => requestChange(hit.symbol, "remove")}>
                    Remove
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
      {assets.map((asset) => (
        <button
          className={selected === asset.symbol ? "asset selected" : "asset"}
          onClick={() => onSelect(asset.symbol)}
          key={asset.symbol}
        >
          <span className="asset-line">
            <b>{asset.symbol}</b>
            <strong
              title="Kraken live best-bid-offer midpoint"
              className={livePrices[asset.symbol] ? "live-price" : "muted"}
            >
              {displayPrice(livePrices[asset.symbol])}
            </strong>
          </span>
          <small>
            {asset.status}
            {asset.protected ? " · anchor" : ""}
          </small>
        </button>
      ))}
    </>
  );
}
