import {useEffect, useMemo, useState} from "react";
import {CATALOG, catalogById, type CatalogEntry, type CatalogKind} from "./indicatorCatalog";

type Props = {
  open: boolean;
  initialId?: string | null;
  onClose: () => void;
};

const KIND_LABEL: Record<CatalogKind, string> = {
  indicator: "Confluence",
  layer: "Chart overlay",
  pattern: "Soft-label pattern",
  future: "Not in workstation yet",
};

export function IndicatorGuide({open, initialId, onClose}: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string>(initialId || CATALOG[0]?.id || "");

  useEffect(() => {
    if (!open) return;
    setSelectedId(initialId || CATALOG[0]?.id || "");
    setQuery("");
  }, [open, initialId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return CATALOG;
    return CATALOG.filter((item) =>
      [item.title, item.summary, item.kind, item.authority].join(" ").toLowerCase().includes(needle));
  }, [query]);

  const selected: CatalogEntry | undefined = catalogById(selectedId) || filtered[0];

  if (!open) return null;

  return (
    <div className="guide-backdrop" role="presentation" onClick={onClose}>
      <div
        className="guide-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Indicator guide"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="guide-header">
          <div>
            <span className="eyebrow">OPERATOR GUIDE</span>
            <h2>Indicators & overlays</h2>
          </div>
          <button type="button" className="guide-close" onClick={onClose} aria-label="Close guide">Close</button>
        </header>
        <div className="guide-body">
          <aside className="guide-list">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter…"
              aria-label="Filter guide entries"
            />
            <ul>
              {filtered.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={selected?.id === item.id ? "selected" : ""}
                    onClick={() => setSelectedId(item.id)}
                  >
                    <b>{item.title}</b>
                    <small>{KIND_LABEL[item.kind]}</small>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
          {selected && (
            <article className="guide-page">
              <span className={`guide-authority ${selected.authority}`}>{KIND_LABEL[selected.kind]}</span>
              <h3>{selected.title}</h3>
              <p>{selected.summary}</p>
              <section>
                <h4>What it looks like</h4>
                <p>{selected.looksLike}</p>
              </section>
              <section>
                <h4>How it is identified</h4>
                <p>{selected.identification}</p>
              </section>
              <section>
                <h4>How the GUI flags it</h4>
                <p>{selected.guiFlags}</p>
              </section>
              {selected.guideHint && (
                <p className="guide-ref">Deeper reading: <code>{selected.guideHint}</code></p>
              )}
            </article>
          )}
        </div>
      </div>
    </div>
  );
}
