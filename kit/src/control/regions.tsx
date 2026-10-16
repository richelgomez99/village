// Control Room regions (T021–T026, T042). Each region states one thing with names and numbers (D18, INTERACTIONS §8).
import { Fragment, forwardRef, useEffect, useMemo, useState, type ReactNode } from "react";
import { QRCodeSVG } from "qrcode.react";
import { captionFor } from "../i18n/captions";
import { Renderer } from "../renderer/Renderer";
import { makePhoneFor, type RenderCtx } from "../renderer/context";
import { viewSchema, type View } from "../renderer/view";
import { useNow } from "../util/time";
import { plural } from "../i18n/plural";
import { authorName, oneLine } from "../components/generic";
import { ProposalBlocks, ReleaseStepper } from "../components/proposal";
import { text } from "../renderer/view";
import { FactHistoryCard, MEMORY_CAPTION, factTarget } from "../components/fact";
import { askVillage, getQr, type ApiConfig, type AskAnswer, type QrEntry } from "./api";
import { displayName, memberDisplay, nameCtx, type AnswerBlock, type CaptionLine, type DecisionRow, type GateRow, type LedgerRow, type LiveMoment, type Mode, type SceneState, type TranscriptLine } from "./scene";

const hhmm = (iso: string) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "America/New_York" });
};

/** D18: a Spanish line with its English line under it, muted. */
export function Cap({ es, en, className }: { es: string; en?: string | null; className?: string }) {
  const english = en ?? captionFor(es);
  return (
    <span className={`cap ${className ?? ""}`}>
      <span lang="es" data-lang="es">{es}</span>
      {english && english !== es ? <span className="caption" lang="en" data-test="caption">{english}</span> : null}
    </span>
  );
}

/** Localized `say` or {es,en}: Spanish first with English under it; English-only stays English. */
export function Say({ value }: { value: { es?: string; en?: string } | null | undefined }) {
  if (!value) return null;
  if (value.es) return <Cap es={value.es} en={value.en} />;
  return <span>{value.en}</span>;
}

function Region({ test, title, children, className, extra }: { test: string; title: ReactNode; children: ReactNode; className?: string; extra?: Record<string, string | number | undefined> }) {
  return (
    <section className={`region ${className ?? ""}`} data-test={test} {...extra}>
      <h2 className="eyebrow">{title}</h2>
      {children}
    </section>
  );
}

/* ---------------- Header ---------------- */

export interface VillageTab { id: string; label: string }
/** pseudo tab id for the empty founding room before POST /villages returns an id */
export const NEW_VILLAGE = "__new__";

export const TAGLINE = "Village builds an app for each person in a group, runs their week, and rebuilds itself when their life changes.";

export function Header({ tabs, tab, onTab, onNew, phones, clock, nowMs, onWarp, warpState, details = false, onDetails }: {
  details?: boolean; onDetails?: (on: boolean) => void;
  tabs: VillageTab[]; tab: string; onTab: (id: string) => void; onNew: () => void; phones: number | null; clock: SceneState["clock"]; nowMs: () => number;
  onWarp: () => void; warpState: "idle" | "busy" | "failed";
}) {
  const now = useNow(nowMs, 1000);
  const shown = clock?.now ?? new Date(now).toISOString();
  const n = phones ?? 0;
  return (
    <header className="cr-header" data-test="cr-header">
      <div className="brand-block">
        <div className="brand-row">
          <span className="brand">Village</span>
          <span className="brand-dot" aria-hidden="true">·</span>
          <nav aria-label="Villages" className="tabs" role="tablist">
            {tabs.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={t.id === tab} className={`tab${t.id === tab ? " active" : ""}`} data-test="village-tab" data-village={t.id} onClick={() => onTab(t.id)}>
                {t.label}
              </button>
            ))}
            <button type="button" role="tab" aria-selected={tab === NEW_VILLAGE} className={`tab tab-new${tab === NEW_VILLAGE ? " active" : ""}`} data-test="new-village" onClick={onNew}>
              + New village
            </button>
          </nav>
        </div>
        <p className="tagline" data-test="tagline">{TAGLINE}</p>
      </div>
      <div className="header-right">
        <span className="pill" data-test="phones-counter" data-count={n} aria-label={`${plural(n, "phone")} live`}>
          <span className="dots" aria-hidden="true">
            {Array.from({ length: Math.min(n, 24) }, (_, i) => <span key={i} className="dot" data-test="phone-dot" />)}
          </span>
          <span className="num">{n}</span>
          <span className="muted">{n === 1 ? "phone live" : "phones live"}</span>
        </span>
        <span className="pill" data-test="demo-clock" data-now={shown}>
          <span className="muted">demo clock</span>
          <span className="num small">{hhmm(shown)}</span>
          {clock?.offset_minutes ? <span className="muted mono">+{clock.offset_minutes}m</span> : null}
          <button type="button" className="warp" data-test="warp" disabled={warpState === "busy"} onClick={onWarp} title="POST /clock/warp">
            {warpState === "busy" ? "warping…" : "+30m"}
          </button>
          {warpState === "failed" ? <span className="coral small" data-test="warp-failed">clock not reachable</span> : null}
        </span>
        {onDetails ? (
          <button type="button" className={`details-toggle${details ? " on" : ""}`} data-test="details-toggle" aria-pressed={details} onClick={() => onDetails(!details)}>details</button>
        ) : null}
      </div>
    </header>
  );
}

/* ---------------- Founding transcript ---------------- */

export function TranscriptRegion({ lines, onSend, speakerName = "Coordinator", onPlayAudio }: { lines: TranscriptLine[]; onSend?: (text: string) => Promise<void>; speakerName?: string; onPlayAudio?: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy || !onSend) return;
    setBusy(true);
    setError(null);
    try {
      await onSend(t);
      setText("");
    } catch {
      setError("Village didn't get that: Core didn't reply. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  };
  const first = !lines.some((l) => l.who !== "village");
  return (
    <Region test="transcript" title="Founding · describe your people" className="r-transcript">
      {first ? <p className="empty-hero" data-test="founding-empty">No village yet. Describe your people.</p> : null}
      {onPlayAudio ? <button type="button" className="play-call" data-test="audio-start" onClick={onPlayAudio}>▶ Play the call</button> : null}
      <ol className="transcript">
        {lines.map((l) => (
          <li key={l.id} className={`tr-line tr-${l.who}`} data-test="transcript-line" data-who={l.who}>
            <span className="eyebrow">{l.who === "village" ? "Village" : l.who === "ana" ? speakerName : l.who}</span>
            <p>{l.who === "village" ? l.text : `“${l.text}”`}</p>
          </li>
        ))}
      </ol>
      {onSend ? (
        <form className="ask-form founding-form" onSubmit={submit}>
          <textarea
            aria-label={first ? "Describe your people" : "Answer Village"} data-test="founding-input" rows={first ? 3 : 2} maxLength={first ? 2000 : 600}
            placeholder={first ? "Who is this group for, who helps, and what goes wrong?" : "Answer Village's question"} value={text} disabled={busy} onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" data-test="founding-submit" disabled={busy || !text.trim()}>{busy ? "Sending…" : first ? "Start" : "Answer"}</button>
        </form>
      ) : null}
      {error ? <p className="coral small" data-test="founding-error">{error}</p> : null}
    </Region>
  );
}

/* ---------------- Blueprint ---------------- */

const AREA_CLASS: Record<string, string> = { health: "amber", money: "coral", people: "mint", home: "sky", daily_living: "plum", information: "sky" };

const RULE_WORDS: Record<string, string> = {
  double_dose_guard: "Dose already recorded → report it, tell the on-duty person",
  no_dose_advice: "Never says how many pills to take",
  missed_dose_ladder: "Missed dose → reminder, then the on-duty person",
  emergency_911_first: "Emergency → 911 first",
  consent_before_calls: "Only calls people who said yes to calls",
  ai_disclosure_family_word: "Every call says it's AI + the family word",
  money_verify_with_member: "Money asked in a family name → check with that person",
  money_never_moves: "Village never moves money",
  money_default_dont_send: "No answer means “don't send”",
  quiet_hours: "Quiet hours: no calls at night",
  rumor_check: "Rumors are checked against an official source",
  medical_priority_matching: "Medical needs matched first",
  address_privacy: "Addresses shown only to matched helpers"
};

const KIND_WORDS: Record<string, string> = { care: "family · aging parent at home", block: "block · neighbors in an emergency" };

const CHANNEL_WORDS: Record<string, string> = {
  phone_line: "Phone line", fridge_card: "Fridge card", outbound_calls: "Village may call", refill_day: "Refill day",
  "verification:app_prompt": "Money checks · app", "verification:call": "Money checks · call"
};
const channelWord = (c: string) => CHANNEL_WORDS[c] ?? (c.startsWith("app:") ? `App · ${c.slice(4)}` : c.replace(/_/g, " "));

const LANG_WORDS: Record<string, string> = { es: "Spanish", en: "English", zh: "Chinese" };

/** Why this person got these channels, from their capability profile + consent (AGENT.md §4). */
export function capabilityReasons(p: any): string[] {
  const out: string[] = [];
  const pr = p?.profile ?? {};
  if (pr.tech_comfort === "phone") out.push("phone, not apps");
  else if (pr.tech_comfort === "app") out.push("uses apps");
  else if (pr.tech_comfort === "both") out.push("app + calls");
  if (pr.lang && pr.lang !== "en") out.push(LANG_WORDS[pr.lang] ?? pr.lang);
  if (pr.vision === "reduced") out.push("big text · read aloud");
  if (pr.memory === "mild_lapses") out.push("memory lapses");
  if (pr.mobility && pr.mobility !== "typical") out.push(pr.mobility === "wheelchair" ? "wheelchair" : "limited mobility");
  if (p?.consent?.ai_calls === true) out.push("agreed to calls");
  if (p?.consent?.money_verifier) out.push("confirms money asks");
  return out;
}

function highlightQuote(text: string, needs: any[], areas: Map<string, string>): ReactNode[] {
  const spans = needs
    .filter((n) => n.source_span && n.source_span.end > n.source_span.start)
    .map((n) => ({ start: n.source_span.start, end: Math.min(text.length, n.source_span.end), area: n.life_area as string }))
    .sort((a, b) => a.start - b.start);
  const out: ReactNode[] = [];
  let i = 0;
  spans.forEach((s, k) => {
    if (s.start < i) return;
    if (s.start > i) out.push(text.slice(i, s.start));
    out.push(<mark key={k} className={`hl hl-${AREA_CLASS[s.area] ?? "amber"}`} data-test="quote-highlight" data-area={s.area} title={areas.get(s.area)}>{text.slice(s.start, s.end)}</mark>);
    i = s.end;
  });
  if (i < text.length) out.push(text.slice(i));
  return out;
}

export function BlueprintRegion({ spec, scene }: { spec: any; scene: SceneState }) {
  const bp = spec?.blueprint;
  const streamed = scene.blueprint.stages;
  const people: any[] = streamed.people ?? bp?.people ?? [];
  const lifeAreas: any[] = streamed.life_areas ?? bp?.life_areas ?? [];
  const needs: any[] = streamed.needs ?? bp?.needs ?? [];
  const rules: string[] = (streamed.rules?.map((r: any) => r.rule ?? r) as string[]) ?? bp?.rules ?? [];
  const kind: string | undefined = streamed.kind?.[0]?.kind ?? spec?.village?.kind;
  const quote: string | undefined = bp?.description?.text;
  const nctx = spec ?? nameCtx(scene);
  const speakerP = people.find((p) => p.id === bp?.description?.speaker);
  const speaker = speakerP ? displayName(speakerP, nctx) : undefined;
  const areaLabels = new Map(lifeAreas.map((a) => [a.id as string, a.label as string]));
  const channels: Record<string, string[]> = spec?.channels ?? {};
  const meter = scene.coverage ? (
    <div className="coverage" data-test="coverage" data-value={scene.coverage.value} data-of={scene.coverage.of}>
      <span className="coverage-num">{scene.coverage.value} of {scene.coverage.of} covered · {plural(Math.max(0, scene.gaps.length || scene.coverage.of - scene.coverage.value), "gap")}</span>
      <span className="coverage-bar" aria-hidden="true"><span style={{ width: `${(100 * scene.coverage.value) / (scene.coverage.of || 10)}%` }} /></span>
      {scene.gaps.length ? <ul className="gaps" data-test="gaps">{scene.gaps.map((g) => <li key={g} data-test="gap">{g}</li>)}</ul> : null}
    </div>
  ) : null;
  if (!bp && !people.length) {
    return (
      <Region test="blueprint" title="What Village heard" className="r-blueprint" extra={{ "data-village": scene.village }}>
        {meter}
        <p className="empty" data-test="blueprint-empty">Nothing heard yet. The blueprint fills in while the coordinator describes the group.</p>
      </Region>
    );
  }
  return (
    <Region test="blueprint" title="What Village heard" className="r-blueprint" extra={{ "data-village": spec?.village?.id ?? scene.village, "data-people": people.length }}>
      {meter}
      {kind ? <p className="group-type" data-test="group-type">group type: <strong>{KIND_WORDS[kind] ?? kind}</strong></p> : null}
      {quote ? (
        <blockquote className="quote" data-test="blueprint-quote">
          {speaker ? <span className="eyebrow">{speaker}</span> : null}
          <p>“{highlightQuote(quote, needs, areaLabels)}”</p>
        </blockquote>
      ) : null}
      <ul className="areas-row" data-test="life-areas-row">
        {lifeAreas.map((a) => (
          <li key={a.id} className={`chip chip-${AREA_CLASS[a.id] ?? "amber"}`} data-test="bp-area" data-area={a.id}>{a.label}</li>
        ))}
        <li className="muted small">{plural(lifeAreas.length, "life area")} · {plural(needs.length, "need")}</li>
      </ul>
      <ul className="people" data-test="bp-people">
        {people.map((p) => (
          <li key={p.id} className={`person${p.role === "care_recipient" ? " center" : ""}`} data-test="bp-person" data-member={p.id}>
            <span className="person-name">{displayName(p, nctx)}</span>
            <span className="muted small">{[p.relation, p.role?.replace(/_/g, " "), LANG_WORDS[p.profile?.lang] ?? p.profile?.lang].filter(Boolean).join(" · ")}</span>
            <span className="chips">
              {(channels[p.id] ?? []).map((c) => <span key={c} className="chip chip-line" data-test="bp-channel">{channelWord(c)}</span>)}
            </span>
            <span className="reasons small" data-test="bp-reasons">{capabilityReasons(p).join(" · ")}</span>
          </li>
        ))}
      </ul>
      {rules.length ? (
        <div className="rules" data-test="bp-rules">
          <span className="eyebrow">Safety rules switched on · {rules.length}</span>
          <ul>{rules.slice(0, 6).map((r) => <li key={r} data-rule={r}><span className="mint">●</span> {RULE_WORDS[r] ?? r.replace(/_/g, " ")}</li>)}</ul>
        </div>
      ) : null}
    </Region>
  );
}

/* ---------------- Founder ledger ---------------- */

const GLYPH: Record<string, string> = { queued: "○", running: "◐", done: "✓", retrying: "↻", fallback: "↪", refused: "✗" };
const STATUS_WORD: Record<string, string> = { queued: "queued", running: "running", done: "done", retrying: "retrying", fallback: "fallback", refused: "refused" };

function Elapsed({ from, nowMs }: { from: string; nowMs: () => number }) {
  const now = useNow(nowMs, 1000);
  const s = Math.max(0, Math.round((now - Date.parse(from)) / 1000));
  if (s < 2 || s > 3600) return null;
  return <span className="mono muted"> · {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>;
}

export function LedgerRegion({ rows, nowMs, details = false }: { rows: LedgerRow[]; nowMs: () => number; details?: boolean }) {
  return (
    <Region test="ledger" title="Village's work log" className="r-ledger">
      {rows.length === 0 ? <p className="empty">No work yet. Each step Village takes shows up here as a row with its result.</p> : null}
      <ol className="ledger">
        {rows.slice(-12).map((r) => (
          <li key={r.id} className={`ledger-row st-${r.status}`} data-test="ledger-row" data-status={r.status} data-role={r.role}>
            <span className="mono muted">{hhmm(r.at)}</span>
            <span className="glyph" aria-label={STATUS_WORD[r.status]}>{GLYPH[r.status]}</span>
            <span className="what">
              <span className="role-tag">{r.role}</span> {r.what}
              {r.status === "running" ? <Elapsed from={r.at} nowMs={nowMs} /> : null}
              {r.attempt ? <span className="muted"> · attempt {r.attempt} of 3</span> : null}
              {r.result ? <span className={`result${r.status === "fallback" ? " bold" : ""}`}> · {r.result}</span> : null}
              {details && r.rule_id ? <span className="mono muted small" data-test="details-ids"> · {r.rule_id}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </Region>
  );
}

/* ---------------- Founding: Village thinking and doing (D33) ---------------- */

function Done({ row }: { row: LedgerRow }) {
  const ms = row.elapsed_ms ?? (row.ended ? Date.parse(row.ended) - Date.parse(row.at) : null);
  return ms != null && ms >= 0 ? <span className="mono muted small"> · {(ms / 1000).toFixed(1)} s</span> : null;
}

/** One block per answer: Heard → Knows → Doing (ledger rows, running → done with real elapsed) → Will build. */
export function FoundingWorkRegion({ blocks, ledger, nowMs }: { blocks: AnswerBlock[]; ledger: LedgerRow[]; nowMs: () => number }) {
  const byId = new Map(ledger.map((r) => [r.id, r]));
  return (
    <Region test="founding-work" title="Village thinking and doing" className="r-work">
      {blocks.length === 0 ? <p className="empty">Village starts working the moment someone answers.</p> : null}
      <ol className="work-blocks">
        {blocks.map((b, i) => (
          <li key={b.id} className="work-block" data-test="work-block" data-index={i}>
            <p className="wb-line"><span className="wb-tag">Heard</span> “{b.heard.length > 110 ? `${b.heard.slice(0, 107)}…` : b.heard}”</p>
            {b.knows ? <p className="wb-line" data-test="wb-knows"><span className="wb-tag mint">Knows</span> {b.knows}</p> : null}
            {b.doing.map((id) => {
              const r = byId.get(id);
              if (!r) return null;
              return (
                <p key={id} className={`wb-line ledger-row st-${r.status}`} data-test="ledger-row" data-status={r.status} data-id={r.id}>
                  <span className="wb-tag amber">Doing</span> <span className="glyph">{GLYPH[r.status]}</span> {r.status === "done" ? r.what : r.what}
                  {r.status === "running" ? <Elapsed from={r.at} nowMs={nowMs} /> : null}
                  {r.result && r.status !== "running" ? <span className="result"> · {r.result}</span> : null}
                  {r.status === "done" ? <Done row={r} /> : null}
                </p>
              );
            })}
            {b.willBuild.map((w, k) => (
              <p key={k} className="wb-line" data-test="will-build" data-role={w.role ?? ""}>
                <span className="wb-tag plum">Will build</span> <strong>{w.component}</strong> for {w.person} · {w.reason}
              </p>
            ))}
          </li>
        ))}
      </ol>
    </Region>
  );
}

/* ---------------- Live moment ---------------- */

const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function LiveMomentRegion({ live, nowMs, spec, data }: { live: LiveMoment | null; nowMs: () => number; spec: any; data?: Record<string, unknown> }) {
  const now = useNow(nowMs, 250);
  if (!live) {
    return (
      <Region test="live-moment" title="Live" className="r-live" extra={{ "data-state": "idle" }}>
        <p className="empty">No call right now. When a caller asks for money, the check with a trusted person plays here.</p>
      </Region>
    );
  }
  const total = 45;
  const left = live.deadline ? Math.max(0, Math.ceil((Date.parse(live.deadline) - now) / 1000)) : null;
  const frac = left == null ? 0 : Math.min(1, left / total);
  const who = memberDisplay(live.claimed, spec, data);
  const subj = memberDisplay(live.subject, spec, data) || "On the line";
  const collapsed = live.state !== "pending";
  const outcome =
    live.state === "denied" ? `Scam stopped · ${who}: “that wasn't me”` :
    live.state === "confirmed" ? `${who} says it was him · Village never sends money` :
    live.state === "pending" ? "" : `No answer from ${who} · safe default: don't send`;
  return (
    <Region test="live-moment" title={collapsed ? "Live · finished" : "Live · money request"} className={`r-live${collapsed ? " collapsed" : ""}`} extra={{ "data-state": live.state, "data-seconds": left ?? undefined }}>
      {live.quote ? (
        <blockquote className="live-quote" data-test="live-quote">
          <span className="eyebrow">{subj}, on the phone line{live.amount ? ` · $${live.amount.toLocaleString("en-US")}` : ""}</span>
          <Cap es={live.quote} />
        </blockquote>
      ) : null}
      {!collapsed ? (
        <div className="live-flow">
          <div className={`wave${reduced() ? " still" : ""}`} aria-hidden="true" data-test="waveform">{[0, 1, 2, 3, 4].map((i) => <span key={i} />)}</div>
          <svg className="flow" viewBox="0 0 300 90" aria-hidden="true">
            <line x1="40" y1="45" x2="150" y2="45" className="flow-line" />
            <line x1="150" y1="45" x2="260" y2="20" className="flow-line" />
            <line x1="150" y1="45" x2="260" y2="70" className="flow-line dim" />
          </svg>
          <div className="nodes">
            <span className="node">{subj}</span>
            <span className="node village" data-test="village-node">Village</span>
            <span className="node">{who} · {live.channels.map((c) => (c === "app_prompt" ? "app" : c === "outbound_call" ? "call" : c)).join(" + ") || "app"}</span>
          </div>
          <div className="ring" data-test="countdown-ring" role="timer" aria-label={`${left ?? total} seconds left`} style={{ ["--frac" as string]: String(frac) }}>
            <span className="ring-num">0:{String(left ?? total).padStart(2, "0")}</span>
          </div>
          <p className="muted small">If nobody answers in {total} s, the answer is “don't send”.</p>
        </div>
      ) : (
        <p className={`outcome st-${live.state}`} data-test="live-outcome">{outcome}</p>
      )}
      {live.say ? <p className="live-say" data-test="live-say"><Say value={live.say} /></p> : null}
    </Region>
  );
}

/* ---------------- Three phones ---------------- */

export function phoneSlots(spec: any): { role: string; label: string; name: string; member: string | null }[] {
  const views = Object.keys(spec?.views ?? {}).slice(0, 3);
  return views.map((role, i) => {
    const p = spec?.blueprint?.people?.find((x: any) => x.view === role);
    const n = p ? displayName(p, spec) : "";
    const center = p?.role === "care_recipient" || (i === 0 && role === "elder");
    const label = n ? `${n}'s phone${center ? " · right now" : ""}` : `${role} view`;
    return { role, member: p?.id ?? null, name: n, label };
  });
}

function PhoneScreen({ view, data, nowMs, role, village, highlight }: { view: View; data: Record<string, unknown>; nowMs: () => number; role: string; village: string; highlight?: string[] }) {
  const ctx: RenderCtx = {
    view, data, lang: view.lang, role, memberId: null, village, nowMs, disabled: true, highlight: new Set(highlight ?? []), results: {},
    send: () => "", ack: () => {}, captions: true, phoneFor: makePhoneFor(data)
  };
  return (
    <div className="phone app" data-theme={view.theme} data-lang={view.lang} data-test="app" data-role={role} lang={view.lang}>
      <Renderer ctx={ctx} />
    </div>
  );
}

/** Join codes for the phones (GET /villages/{id}/qr JSON); null while loading, [] when there are none yet. */
function useQr(cfg: ApiConfig | undefined, village: string): QrEntry[] | null {
  const [entries, setEntries] = useState<QrEntry[] | null>(null);
  useEffect(() => {
    if (!cfg) return;
    let live = true;
    setEntries(null);
    getQr(cfg, village).then((e) => live && setEntries(e), () => live && setEntries([]));
    return () => {
      live = false;
    };
  }, [cfg, village]);
  return entries;
}

/** "Be <name>" for the helper a judge plays (highlighted sage, D11); "Open <name>'s app" for the others. */
function QrTile({ entry, name, judge, center }: { entry: QrEntry | undefined; name: string; judge: boolean; center: boolean }) {
  if (!entry) return <p className="qr-missing small muted" data-test="qr-empty">Join code appears once the village is live.</p>;
  return (
    <figure className={`qr-tile${judge ? " sage" : ""}`} data-test="qr-tile" data-member={entry.member_id}>
      {entry.svg ? <img alt="" src={`data:image/svg+xml;utf8,${encodeURIComponent(entry.svg)}`} width={96} height={96} /> : <QRCodeSVG value={entry.url} size={96} marginSize={1} />}
      <figcaption>{center ? `Open ${name}'s app` : `Be ${name}`}</figcaption>
    </figure>
  );
}

export function PhonesRegion({ spec, data, village, nowMs, viewAs, onViewAs, live, cfg, people, villageName, drafts, draftNew }: {
  spec: any; data: Record<string, unknown>; village: string; nowMs: () => number; viewAs: string | null; onViewAs: (m: string | null) => void;
  live: { role: string; view: View | null; data: Record<string, unknown> } | null; cfg?: ApiConfig;
  /** founding stream: people named so far (skeleton phones before the spec exists) */
  people?: any[];
  villageName?: string | null;
  /** founding: per-role draft views from control patches, and the element ids each just gained (NEW) */
  drafts?: Record<string, any>;
  draftNew?: Record<string, string[]>;
}) {
  const nctx = spec ?? { village: { name: villageName ?? "" } };
  const seen = new Set<string>();
  const slots = spec?.views
    ? phoneSlots(spec)
    : (people ?? [])
        .filter((p) => p.view && !seen.has(p.view) && seen.add(p.view))
        .slice(0, 3)
        .map((p) => ({ role: p.view as string, member: p.id as string, name: displayName(p, nctx), label: `${displayName(p, nctx)}'s phone${p.role === "care_recipient" ? " · right now" : ""}` }));
  const parsed = useMemo(() => {
    const out: Record<string, View | null> = {};
    for (const s of slots) {
      const r = viewSchema.safeParse(spec?.views?.[s.role]);
      out[s.role] = r.success ? r.data : null;
    }
    return out;
  }, [spec, slots.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const qr = useQr(spec?.views ? cfg : undefined, village);
  const host = village.replace(/^v_/, "");
  return (
    <Region test="phones" title="Same address · different software, because it's a different person" className="r-phones" extra={{ "data-view-as": viewAs ?? "" }}>
      <p className="url-caption" data-test="shared-url">village.app/v/{host} · one site · three people</p>
      {spec?.views ? (
        <div className="view-as-bar" role="group" aria-label="View as">
          <span className="muted small">View as</span>
          {slots.filter((s) => s.member).map((s) => (
            <button key={s.role} type="button" className={`chip-btn${viewAs === s.member ? " active" : ""}`} aria-pressed={viewAs === s.member} data-test="view-as-option" data-member={s.member!} onClick={() => onViewAs(viewAs === s.member ? null : s.member)}>
              {s.name || s.role}
            </button>
          ))}
        </div>
      ) : null}
      {slots.length === 0 ? <p className="empty">Each person's phone appears here once Village knows who they are.</p> : null}
      <div className="phones-row">
        {slots.map((s) => {
          const focused = viewAs && s.member === viewAs;
          const dim = viewAs && !focused;
          const v = focused && live?.view ? live.view : parsed[s.role];
          const d = focused && live?.view ? live.data : data;
          return (
            <figure key={s.role} className={`bezel${focused ? " focused" : ""}${dim ? " dim" : ""}`} data-test="phone" data-role={s.role} data-member={s.member ?? ""}>
              <figcaption className="phone-label" data-test="phone-label">{s.label}{focused ? " · live" : ""}</figcaption>
              {v ? (
                <PhoneScreen view={v} data={d} nowMs={nowMs} role={s.role} village={village} />
              ) : drafts?.[s.role] && (drafts[s.role].elements.s.children ?? []).length ? (
                <PhoneScreen view={drafts[s.role]} data={d} nowMs={nowMs} role={s.role} village={village} highlight={draftNew?.[s.role]} />
              ) : spec?.views ? (
                <p className="empty">This view didn't validate.</p>
              ) : (
                <div className="phone skeleton-phone" data-test="phone-skeleton"><p>Building {s.name}'s app…</p></div>
              )}
              {v?.lang === "es" ? <span className="muted small mono">her phone shows Spanish only; captions are for the room</span> : null}
              {spec?.views && qr ? <QrTile entry={qr.find((e) => e.member_id === s.member && e.kind === "app")} name={s.name} judge={s.role === "helper" || (!slots.some((x) => x.role === "helper") && s.role === "volunteer")} center={s.label.endsWith("right now")} /> : null}
            </figure>
          );
        })}
      </div>
    </Region>
  );
}

/* ---------------- What Village knows (Agent Memory) ---------------- */

/** When the snapshot already carries `facts:history?subject=…&key=…`, answer the history read from it (no request);
 *  the as-of re-query still goes to Core. */
function withSnapshotHistory(api: ApiConfig, data: Record<string, unknown>, entity: string, key: string): ApiConfig {
  const hit = data[`facts:history?subject=${entity}&key=${key}`];
  if (!hit || typeof hit !== "object" || api.fake) return api;
  const real = api.fetchImpl ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
  const fetchImpl = (async (url: any, init?: any) =>
    String(url).includes(`/facts/${encodeURIComponent(entity)}/${encodeURIComponent(key)}/history`)
      ? new Response(JSON.stringify({ village: "", degraded: false, ...(hit as object) }), { status: 200, headers: { "content-type": "application/json" } })
      : real(url, init)) as typeof fetch;
  return { ...api, fetchImpl };
}

export function KnowsRegion({ api: api0, village, data, spec }: { api: ApiConfig; village: string; data: Record<string, unknown>; spec: any }) {
  const t = factTarget(data);
  const api = useMemo(() => (t ? withSnapshotHistory(api0, data, t.entity, t.key) : api0), [api0, t?.entity, t?.key, data[t ? `facts:history?subject=${t.entity}&key=${t.key}` : ""]]); // eslint-disable-line react-hooks/exhaustive-deps
  const who = t ? memberDisplay(t.entity, spec, data) : "";
  return (
    <Region test="knows" title="What Village knows" className="r-knows" extra={{ "data-entity": t?.entity, "data-key": t?.key }}>
      {t ? (
        <FactHistoryCard api={api} village={village} entity={t.entity} factKey={t.key} title={`${t.med.charAt(0).toUpperCase()}${t.med.slice(1)}${who ? ` · ${who}` : ""}`} />
      ) : (
        <p className="empty">Nothing has changed yet. When a fact changes (a dose, a phone number), its history shows here.</p>
      )}
      <p className="caption knows-caption" data-test="knows-caption">{MEMORY_CAPTION}</p>
    </Region>
  );
}

/* ---------------- Proposal (same four blocks as Ana's card) ---------------- */

export function ProposalRegion({ proposal, release, spec, details = false }: { proposal: any; release: any; spec: any; details?: boolean }) {
  const names = (spec?.blueprint?.people ?? []).map((p: any) => displayName(p, spec));
  const running = (release?.stages ?? []).find((s: any) => s.status === "running")?.name;
  return (
    <Region test="proposal-region" title="Village proposes a change · needs your yes" className="r-proposal" extra={{ "data-status": proposal.status }}>
      {proposal.title ? <p className="proposal-title">{text(proposal.title, "en")}</p> : null}
      <ProposalBlocks p={proposal} lang="en" names={names} />
      {proposal.status === "verifying" ? <ReleaseStepper stage={running} /> : null}
      {proposal.status === "applied" ? <p className="mint" data-test="proposal-done">Done · every phone updated</p> : null}
      {proposal.status === "proposed" || proposal.status === "ready" ? <p className="muted small">Waiting for the coordinator's yes.</p> : null}
      {details ? (
        <p className="details-ids small" data-test="details-ids">
          <span className="mono muted">{proposal.id}</span>{release?.id ? <span className="mono muted"> · {release.id} · rev {release.rev}</span> : null} <TraceRef id={release?.trace_id ?? proposal.trace_id} />
        </p>
      ) : null}
    </Region>
  );
}

/* ---------------- Gate feed + decisions ---------------- */

const MODE_WORD: Record<Mode, string> = { acted_alone: "acted alone", asked_human: "asked a person", refused: "refused" };

function ModeChip({ mode }: { mode: Mode }) {
  return <span className={`mode mode-${mode}`} data-test="mode-chip" data-mode={mode}>{MODE_WORD[mode]}</span>;
}

const ARIZE_TRACE: string | undefined = (import.meta as any).env?.VITE_ARIZE_TRACE_URL;

/** Details mode (sponsor judges): a trace id becomes an Arize link when VITE_ARIZE_TRACE_URL ("…{trace_id}…") is set. */
export function TraceRef({ id }: { id?: string }) {
  if (!id) return null;
  return ARIZE_TRACE ? (
    <a className="mono small trace" data-test="trace-link" href={ARIZE_TRACE.replace("{trace_id}", id)} target="_blank" rel="noreferrer">trace {id.slice(0, 8)} ↗</a>
  ) : (
    <span className="mono small muted trace" data-test="trace-id">trace {id.slice(0, 8)}</span>
  );
}

export function GateRegion({ gate, decisions, autonomy, details = false }: { gate: GateRow[]; decisions: DecisionRow[]; autonomy: Record<Mode, number>; details?: boolean }) {
  const shownGate = gate.filter((g) => g.say || g.decision !== "allow");
  return (
    <Region test="gate-feed" title="Safety gate · rules in code, not prompts" className="r-gate">
      <p className="autonomy" data-test="autonomy">
        <span data-test="count-acted_alone" data-count={autonomy.acted_alone}><strong>{autonomy.acted_alone}</strong> acted alone</span> ·{" "}
        <span data-test="count-asked_human" data-count={autonomy.asked_human}><strong>{autonomy.asked_human}</strong> asked a person</span> ·{" "}
        <span data-test="count-refused" data-count={autonomy.refused}><strong>{autonomy.refused}</strong> refused</span>
      </p>
      {shownGate.length === 0 && decisions.length === 0 ? <p className="empty">No decisions yet tonight.</p> : null}
      <ol className="gate-rows">
        {shownGate.slice(0, 6).map((g) => (
          <li key={g.id} className={`gate-row m-${g.mode}`} data-test="gate-row" data-rule={g.rule_id} data-decision={g.decision}>
            <span className="mono muted">{hhmm(g.at)}</span> <ModeChip mode={g.mode} /> <span className="sentence" data-test="gate-sentence">{g.sentence}</span>
            {details ? (
              <span className="details-ids" data-test="details-ids"> <span className="mono rule">{g.rule_id}</span> <span className="mono muted small">{g.id}</span> <TraceRef id={g.trace_id} /></span>
            ) : null}
            {g.say ? <p className="say"><Say value={g.say} /></p> : null}
          </li>
        ))}
      </ol>
      <div data-test="decisions-log">
        <h3 className="eyebrow">Village's decisions</h3>
        <ol className="decision-rows">
          {decisions.slice(0, 8).map((d) => (
            <li key={d.id} className={`decision-row m-${d.mode}`} data-test="decision-row" data-role={d.role}>
              <span className="mono muted">{hhmm(d.at)}</span> <span className="role-tag">{d.role}</span> <ModeChip mode={d.mode} />
              <span className="text"> {d.text}</span>
              {details ? <TraceRef id={d.trace_id} /> : null}
            </li>
          ))}
        </ol>
      </div>
    </Region>
  );
}

/* ---------------- Arc strip (Build → Run → Rebuild → Anyone) ---------------- */

export type ArcBeat = "build" | "run" | "rebuild" | "anyone";
const ARC: [ArcBeat, string][] = [["build", "Build"], ["run", "Run"], ["rebuild", "Rebuild"], ["anyone", "Anyone"]];

export function ArcStrip({ beat, onJump }: { beat: ArcBeat | null; onJump: (b: ArcBeat) => void }) {
  return (
    <nav className="arc-strip" data-test="arc-strip" data-beat={beat ?? ""} aria-label="Demo arc">
      {ARC.map(([b, label], i) => (
        <Fragment key={b}>
          {i ? <span className="arc-arrow" aria-hidden="true">→</span> : null}
          <button type="button" className={`arc-beat${beat === b ? " lit" : ""}`} data-test="arc-beat" data-beat={b} aria-current={beat === b ? "step" : undefined} onClick={() => onJump(b)}>{label}</button>
        </Fragment>
      ))}
    </nav>
  );
}

/* ---------------- Autonomy headline (Watcher rounds) ---------------- */

export function AutonomyHeadline({ rounds }: { rounds: SceneState["rounds"] }) {
  const [open, setOpen] = useState<Mode | null>(null);
  const counts = rounds.counts ?? (rounds.rows.length ? rounds.rows.reduce((c, r) => ({ ...c, [r.mode]: c[r.mode] + 1 }), { acted_alone: 0, asked_human: 0, refused: 0 } as Record<Mode, number>) : null);
  if (!counts) return null;
  const part = (mode: Mode, words: string) => (
    <button type="button" className={`headline-count${open === mode ? " active" : ""}`} data-test={`headline-${mode}`} data-count={counts[mode]} aria-expanded={open === mode} onClick={() => setOpen(open === mode ? null : mode)}>
      {words}
    </button>
  );
  const rows = open ? rounds.rows.filter((r) => r.mode === open) : [];
  return (
    <Region test="autonomy-headline" title="Village's rounds" className="r-headline">
      <p className="headline">
        Tonight Village did {part("acted_alone", plural(counts.acted_alone, "thing"))} on its own · asked a person {part("asked_human", String(counts.asked_human))} · refused itself {part("refused", String(counts.refused))}
      </p>
      {open ? (
        <ol className="decision-rows" data-test="headline-rows">
          {rows.length ? rows.map((r) => (
            <li key={r.id} className={`decision-row m-${r.mode}`} data-test="headline-row">
              <span className="role-tag">{r.role}</span> <ModeChip mode={r.mode} /> <span className="text">{r.text}</span>
            </li>
          )) : <li className="muted small">The rows for this count haven't arrived yet.</li>}
        </ol>
      ) : null}
    </Region>
  );
}

/* ---------------- Chat mirror ---------------- */

const KIND_WORD: Record<string, string> = { proposal: "proposal", receipt: "receipt", relayed: "from a call", nudge: "nudge", answer: "answer", incident: "incident" };

export function ChatMirror({ chat, data }: { chat: SceneState["chat"]; data: Record<string, unknown> }) {
  if (!chat.length) return null;
  return (
    <Region test="chat-mirror" title="Village chat" className="r-chat">
      <ol className="chat-mirror">
        {chat.slice(-6).map((m) => {
          const village = !m.author || m.author === "village" || m.author === "system";
          return (
            <li key={m.id} className={`chat-bubble${village ? " village" : ""} kind-${m.kind}`} data-test="chat-mirror-row" data-kind={m.kind}>
              <span className="chat-who">{authorName(m.author, data)}{KIND_WORD[m.kind] ? <span className="chat-kind"> · {KIND_WORD[m.kind]}</span> : null}</span>
              {m.kind === "proposal" && m.title ? <strong className="chat-title">{m.title}</strong> : null}
              <span className="chat-text">{m.kind === "proposal" ? oneLine(m.text) : m.text}</span>
            </li>
          );
        })}
      </ol>
    </Region>
  );
}

/* ---------------- Ask Village why ---------------- */

export function AskWhyRegion({ cfg, village }: { cfg: ApiConfig; village: string }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    try {
      setAnswer(await askVillage(cfg, village, question));
    } catch {
      setError("Village couldn't answer right now: Core didn't reply. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Region test="ask-why" title="Ask Village why · Explainer" className="r-ask">
      <form className="ask-form" onSubmit={submit}>
        <input type="text" aria-label="Ask Village why" placeholder="Ask: why did Village…?" value={q} onChange={(e) => setQ(e.target.value)} disabled={busy} data-test="ask-input" maxLength={600} />
        <button type="submit" disabled={busy || !q.trim()} data-test="ask-submit">{busy ? "Asking…" : "Ask"}</button>
      </form>
      {busy ? <p className="muted small" data-test="ask-busy">Explainer is reading the decision log…</p> : null}
      {error ? <p className="coral small" data-test="ask-error">{error}</p> : null}
      {answer ? (
        <div className="answer" data-test="ask-answer">
          <p>{answer.answer}</p>
          <ul className="chips">
            {answer.citations.map((c) => <li key={`${c.kind}:${c.id}`} className={`chip chip-line cite-${c.kind}`} data-test="citation" data-kind={c.kind}>{c.label}</li>)}
          </ul>
          {answer.degraded ? <p className="muted small">From the ledger and decision log only (memory was unavailable).</p> : null}
        </div>
      ) : null}
    </Region>
  );
}

/* ---------------- Captions layer ---------------- */

export const CaptionsLayer = forwardRef<HTMLDivElement, { captions: CaptionLine[] }>(function CaptionsLayer({ captions }, ref) {
  const last = captions.slice(-2);
  if (!last.length) return null;
  return (
    <div className="captions-layer" data-test="captions-layer" aria-live="polite" ref={ref}>
      {last.map((c) => (
        <p key={c.id} className="caption-line" data-test="caption-line">
          {c.speaker ? <span className="eyebrow">{c.speaker}</span> : null}
          {c.es && c.es !== c.en ? <Cap es={c.es} en={c.en} /> : <span>{c.en || c.es}</span>}
        </p>
      ))}
    </div>
  );
});
