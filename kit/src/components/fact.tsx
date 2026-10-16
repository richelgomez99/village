// "What Village knows" (D32): one fact's history from Agent Memory (SurrealDB) — current value, superseded values
// struck through with their valid-time range, the source of each version (quote on tap), and an as-of toggle that
// re-queries GET /villages/{id}/facts?as_of=. Village-agnostic: which fact comes from the data (factTarget).
import { useEffect, useState } from "react";
import { getFactHistory, getFactsAsOf, type ApiConfig, type FactHistory, type FactVersion } from "../control/api";

export const MEMORY_CAPTION = "Typed · time-aware · supersedes rather than overwrites · traced to source · shared across agents (SurrealDB Agent Memory)";

/** The first prescription with a superseded dose → Agent Memory entity (the person) + key ("<med>_dose", as core writes it). */
export function factTarget(data: Record<string, unknown>): { entity: string; key: string; med: string } | null {
  const rx = data["prescriptions:current"] as { subject?: string; items?: { name: string; superseded?: unknown }[] } | null | undefined;
  const item = rx?.items?.find((i) => i.superseded);
  if (!rx || !item) return null;
  const med = String(item.name).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  return { entity: rx.subject ?? "village", key: `${med}_dose`, med: item.name };
}

const day = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "America/New_York" });
};
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

export function sourceLabel(src: FactVersion["source"]): string {
  if (src.kind === "call") return `call ${src.ref}${src.secs != null ? ` · ${mmss(src.secs)}` : ""}`;
  return `${src.kind} · ${src.ref}`;
}

const AGENT_WORDS: Record<string, string> = { founder: "Founder", builder: "Builder", watcher: "Watcher", verifier: "Verifier", explainer: "Explainer", voice: "voice", "mom-line": "voice", memory: "Agent Memory", seed: "seed", system: "seed" };
/** "written by": the fact's agent= label in words, else its source kind (SurrealDB "shared across agents"). */
export function writtenBy(v: { labels?: Record<string, string>; source: { kind: string } }): string {
  const a = v.labels?.agent;
  if (a) return AGENT_WORDS[a.toLowerCase()] ?? a;
  const k = v.source?.kind ?? "";
  return k === "call" || k === "phone_line" ? "voice" : k === "system" || k === "seed" ? "seed" : k || "seed";
}

/** The day before the current version became true, at noon (the "before the change" as-of). */
function beforeChange(v: FactVersion): string {
  const t = new Date(Date.parse(v.observed_at) - 24 * 3600_000);
  const ymd = t.toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  return `${ymd}T12:00:00-04:00`;
}

function localAsOf(h: FactHistory, asOf: string): FactVersion | null {
  const t = Date.parse(asOf);
  return h.versions.filter((v) => Date.parse(v.observed_at) <= t).sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))[0] ?? null;
}

export function FactHistoryCard({ api, village, entity, factKey, title }: { api: ApiConfig | undefined; village: string; entity: string; factKey: string; title?: string }) {
  const [h, setH] = useState<FactHistory | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [asOf, setAsOf] = useState<"now" | "before">("now");
  const [asOfValue, setAsOfValue] = useState<{ value: string; at: string } | null>(null);

  useEffect(() => {
    if (!api) return;
    let live = true;
    setH(null);
    setFailed(false);
    getFactHistory(api, village, entity, factKey).then(
      (r) => live && (Array.isArray(r?.versions) && r.versions.length ? setH(r) : setFailed(true)),
      () => live && setFailed(true)
    );
    return () => {
      live = false;
    };
  }, [api, village, entity, factKey]);

  const sorted = h ? [...h.versions].sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at)) : [];
  const current = sorted.find((v) => !v.superseded) ?? sorted[0];
  const older = sorted.filter((v) => v !== current);

  useEffect(() => {
    if (asOf === "now" || !h || !current || !api) {
      setAsOfValue(null);
      return;
    }
    const at = beforeChange(current);
    let live = true;
    getFactsAsOf(api, village, entity, factKey, at).then(
      (r) => live && setAsOfValue({ value: r.facts[0]?.value ?? "unknown", at }),
      () => {
        const v = localAsOf(h, at);
        if (live) setAsOfValue({ value: v?.value ?? "unknown", at });
      }
    );
    return () => {
      live = false;
    };
  }, [asOf, h, current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!api) return null;
  if (failed) return <p className="fact-empty small muted" data-test="fact-empty">Village's memory didn't answer for this fact yet.</p>;
  if (!h || !current) return <p className="fact-empty small muted" data-test="fact-loading">Reading what Village knows…</p>;

  const Source = ({ v }: { v: FactVersion }) => (
    <>
      <button type="button" className="fact-source" data-test="fact-source" aria-expanded={open === v.id} onClick={() => setOpen(open === v.id ? null : v.id)}>
        {sourceLabel(v.source)}
      </button>
      <span className="chip chip-gray fact-by" data-test="fact-written-by"> written by {writtenBy(v as FactVersion & { labels?: Record<string, string> })}</span>
      {open === v.id ? <q className="fact-quote" data-test="fact-quote">{v.source.quote ?? "No quote recorded for this source."}</q> : null}
    </>
  );

  return (
    <div className="fact" data-test="fact-history" data-entity={entity} data-key={factKey} data-asof={asOf}>
      {title ? <p className="fact-title">{title}</p> : null}
      <div className="fact-current" data-test="fact-current">
        <span className="fact-value">{current.value}</span> <span className="fact-since">since {day(current.observed_at)}</span>
        <p className="fact-text">{current.text}</p>
        <Source v={current} />
      </div>
      <ul className="fact-older">
        {older.map((v, i) => {
          const until = (i === 0 ? current : older[i - 1]).observed_at;
          return (
            <li key={v.id} data-test="fact-superseded">
              <s className="fact-value-old">{v.value}</s> <span className="fact-range">({day(v.observed_at)} → {day(until)})</span> <Source v={v} />
            </li>
          );
        })}
      </ul>
      {older.length ? (
        <div className="fact-asof" role="group" aria-label="As of">
          <button type="button" data-test="fact-asof-toggle" data-asof="now" aria-pressed={asOf === "now"} className={asOf === "now" ? "active" : ""} onClick={() => setAsOf("now")}>Now</button>
          <button type="button" data-test="fact-asof-toggle" data-asof="before" aria-pressed={asOf === "before"} className={asOf === "before" ? "active" : ""} onClick={() => setAsOf("before")}>
            As of {day(beforeChange(current))}
          </button>
          {asOfValue ? <span className="fact-asof-result" data-test="fact-asof-result">as of {day(asOfValue.at)} → {asOfValue.value}</span> : null}
        </div>
      ) : null}
      {h.degraded ? <p className="small muted" data-test="fact-degraded">From the ledger mirror: memory is catching up.</p> : null}
    </div>
  );
}
