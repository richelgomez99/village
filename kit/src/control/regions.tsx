// Control Room regions (T021–T026, T042). Each region states one thing with names and numbers (D18, INTERACTIONS §8).
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { QRCodeSVG } from "qrcode.react";
import { captionFor } from "../i18n/captions";
import { Renderer } from "../renderer/Renderer";
import type { RenderCtx } from "../renderer/context";
import { viewSchema, type View } from "../renderer/view";
import { useNow } from "../util/time";
import { askVillage, getQr, type ApiConfig, type AskAnswer, type QrEntry } from "./api";
import type { CaptionLine, DecisionRow, GateRow, LedgerRow, LiveMoment, Mode, SceneState } from "./scene";

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

export const VILLAGE_TABS = [
  { id: "v_reyes", label: "Reyes family" },
  { id: "v_w147", label: "West 147th St" }
];

export function Header({ tab, onTab, phones, clock, nowMs, onWarp, warpState }: {
  tab: string; onTab: (id: string) => void; phones: number | null; clock: SceneState["clock"]; nowMs: () => number;
  onWarp: () => void; warpState: "idle" | "busy" | "failed";
}) {
  const now = useNow(nowMs, 1000);
  const shown = clock?.now ?? new Date(now).toISOString();
  const n = phones ?? 0;
  return (
    <header className="cr-header" data-test="cr-header">
      <span className="brand">Village</span>
      <span className="eyebrow">Control room · {VILLAGE_TABS.find((t) => t.id === tab)?.label ?? tab}</span>
      <nav aria-label="Villages" className="tabs" role="tablist">
        {VILLAGE_TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={t.id === tab} className={`tab${t.id === tab ? " active" : ""}`} data-test="village-tab" data-village={t.id} onClick={() => onTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      <div className="header-right">
        <span className="pill" data-test="phones-counter" data-count={n} aria-label={`${n} phones live`}>
          <span className="dots" aria-hidden="true">
            {Array.from({ length: Math.min(n, 24) }, (_, i) => <span key={i} className="dot" data-test="phone-dot" />)}
          </span>
          <span className="num">{n}</span>
          <span className="muted">phones live</span>
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
      </div>
    </header>
  );
}

/* ---------------- Blueprint ---------------- */

const AREA_CLASS: Record<string, string> = { health: "amber", money: "coral", people: "mint", home: "sky", daily_living: "plum", information: "sky" };

const RULE_WORDS: Record<string, string> = {
  double_dose_guard: "Lid already logged → report it, tell the on-duty person",
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
  const speaker = people.find((p) => p.id === bp?.description?.speaker)?.name?.split(" ")[0];
  const areaLabels = new Map(lifeAreas.map((a) => [a.id as string, a.label as string]));
  const channels: Record<string, string[]> = spec?.channels ?? {};
  if (!bp && !people.length) {
    return (
      <Region test="blueprint" title="What Village heard" className="r-blueprint">
        <p className="empty" data-test="blueprint-empty">Nothing heard yet. The blueprint appears here while the coordinator describes the group.</p>
      </Region>
    );
  }
  return (
    <Region test="blueprint" title="What Village heard" className="r-blueprint" extra={{ "data-village": spec?.village?.id, "data-people": people.length }}>
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
        <li className="muted small">{lifeAreas.length} life areas · {needs.length} needs</li>
      </ul>
      <ul className="people" data-test="bp-people">
        {people.map((p) => (
          <li key={p.id} className={`person${p.role === "care_recipient" ? " center" : ""}`} data-test="bp-person" data-member={p.id}>
            <span className="person-name">{String(p.name).split(" ")[0]}</span>
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

export function LedgerRegion({ rows, nowMs }: { rows: LedgerRow[]; nowMs: () => number }) {
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
              {r.rule_id ? <span className="mono muted small"> · {r.rule_id}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </Region>
  );
}

/* ---------------- Live moment ---------------- */

const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function LiveMomentRegion({ live, nowMs, spec }: { live: LiveMoment | null; nowMs: () => number; spec: any }) {
  const now = useNow(nowMs, 250);
  if (!live) {
    return (
      <Region test="live-moment" title="Live" className="r-live" extra={{ "data-state": "idle" }}>
        <p className="empty">No call right now. When someone asks Carmen for money, the check with the family plays here.</p>
      </Region>
    );
  }
  const total = 45;
  const left = live.deadline ? Math.max(0, Math.ceil((Date.parse(live.deadline) - now) / 1000)) : null;
  const frac = left == null ? 0 : Math.min(1, left / total);
  const who = spec?.blueprint?.people?.find((p: any) => p.id === live.claimed)?.name?.split(" ")[0] ?? (live.claimed ?? "").replace(/^[a-z]_/, "");
  const collapsed = live.state !== "pending";
  const outcome =
    live.state === "denied" ? `Scam stopped · ${who}: “that wasn't me”` :
    live.state === "confirmed" ? `${who} says it was him · Village never sends money` :
    live.state === "pending" ? "" : `No answer from ${who} · safe default: don't send`;
  return (
    <Region test="live-moment" title={collapsed ? "Live · finished" : "Live · money request"} className={`r-live${collapsed ? " collapsed" : ""}`} extra={{ "data-state": live.state, "data-seconds": left ?? undefined }}>
      {live.quote ? (
        <blockquote className="live-quote" data-test="live-quote">
          <span className="eyebrow">Carmen, on the phone line{live.amount ? ` · $${live.amount.toLocaleString("en-US")}` : ""}</span>
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
            <span className="node">Carmen</span>
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

export function phoneSlots(spec: any): { role: string; label: string; member: string | null }[] {
  const views = Object.keys(spec?.views ?? {}).slice(0, 3);
  return views.map((role) => {
    const p = spec?.blueprint?.people?.find((x: any) => x.view === role);
    const first = p ? String(p.name).split(" ")[0] : "";
    return { role, member: p?.id ?? null, label: `${first ? `${first} · ` : ""}${role}`.toUpperCase() };
  });
}

function PhoneScreen({ view, data, nowMs, role, village }: { view: View; data: Record<string, unknown>; nowMs: () => number; role: string; village: string }) {
  const ctx: RenderCtx = {
    view, data, lang: view.lang, role, memberId: null, village, nowMs, disabled: true, highlight: new Set(), results: {},
    send: () => "", ack: () => {}, captions: true
  };
  return (
    <div className="phone app" data-theme={view.theme} data-lang={view.lang} data-test="app" data-role={role} lang={view.lang}>
      <Renderer ctx={ctx} />
    </div>
  );
}

export function PhonesRegion({ spec, data, village, nowMs, viewAs, onViewAs, live }: {
  spec: any; data: Record<string, unknown>; village: string; nowMs: () => number; viewAs: string | null; onViewAs: (m: string | null) => void;
  live: { role: string; view: View | null; data: Record<string, unknown> } | null;
}) {
  const slots = phoneSlots(spec);
  const parsed = useMemo(() => {
    const out: Record<string, View | null> = {};
    for (const s of slots) {
      const r = viewSchema.safeParse(spec?.views?.[s.role]);
      out[s.role] = r.success ? r.data : null;
    }
    return out;
  }, [spec]); // eslint-disable-line react-hooks/exhaustive-deps
  const host = village === "v_w147" ? "west147" : village.replace(/^v_/, "");
  return (
    <Region test="phones" title="Same address · different software, because it's a different person" className="r-phones" extra={{ "data-view-as": viewAs ?? "" }}>
      <p className="url-caption" data-test="shared-url">village.app/v/{host} · one site · three people</p>
      <div className="view-as-bar" role="group" aria-label="View as">
        <span className="muted small">View as</span>
        {slots.filter((s) => s.member).map((s) => (
          <button key={s.role} type="button" className={`chip-btn${viewAs === s.member ? " active" : ""}`} aria-pressed={viewAs === s.member} data-test="view-as-option" data-member={s.member!} onClick={() => onViewAs(viewAs === s.member ? null : s.member)}>
            {s.label.split(" · ")[0]}
          </button>
        ))}
      </div>
      {slots.length === 0 ? <p className="empty">The three apps appear once the village has a spec.</p> : null}
      <div className="phones-row">
        {slots.map((s) => {
          const focused = viewAs && s.member === viewAs;
          const dim = viewAs && !focused;
          const v = focused && live?.view ? live.view : parsed[s.role];
          const d = focused && live?.view ? live.data : data;
          return (
            <figure key={s.role} className={`bezel${focused ? " focused" : ""}${dim ? " dim" : ""}`} data-test="phone" data-role={s.role} data-member={s.member ?? ""}>
              <figcaption className="eyebrow">{s.label}{focused ? " · live" : ""}</figcaption>
              {v ? <PhoneScreen view={v} data={d} nowMs={nowMs} role={s.role} village={village} /> : <p className="empty">This view didn't validate.</p>}
              {v?.lang === "es" ? <span className="muted small mono">her phone shows Spanish only; captions are for the room</span> : null}
            </figure>
          );
        })}
      </div>
    </Region>
  );
}

/* ---------------- Gate feed + decisions ---------------- */

const MODE_WORD: Record<Mode, string> = { acted_alone: "acted alone", asked_human: "asked a person", refused: "refused" };

function ModeChip({ mode }: { mode: Mode }) {
  return <span className={`mode mode-${mode}`} data-test="mode-chip" data-mode={mode}>{MODE_WORD[mode]}</span>;
}

export function GateRegion({ gate, decisions, autonomy }: { gate: GateRow[]; decisions: DecisionRow[]; autonomy: Record<Mode, number> }) {
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
            <span className="mono muted">{hhmm(g.at)}</span> <span className="mono rule">{g.rule_id}</span> <ModeChip mode={g.mode} />
            {g.say ? <p className="say"><Say value={g.say} /></p> : <p className="muted small">{g.decision.replace(/_/g, " ")}</p>}
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
            </li>
          ))}
        </ol>
      </div>
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
        <input type="text" aria-label="Ask Village why" placeholder="Why did you call Marco?" value={q} onChange={(e) => setQ(e.target.value)} disabled={busy} data-test="ask-input" maxLength={600} />
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

/* ---------------- Join QR tiles ---------------- */

const TILE_LABEL: Record<string, string> = { m_marco: "Be Marco", m_ana: "Be Ana", m_carmen: "See Carmen's app" };

export function JoinQrRegion({ cfg, village }: { cfg: ApiConfig; village: string }) {
  const [entries, setEntries] = useState<QrEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    setEntries(null);
    setFailed(false);
    getQr(cfg, village).then((e) => live && setEntries(e), () => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [cfg, village]);
  const order = ["m_marco", "m_ana", "m_carmen"];
  const tiles = (entries ?? []).filter((e) => e.kind === "app").sort((a, b) => (order.indexOf(a.member_id) + 9) % 9 - (order.indexOf(b.member_id) + 9) % 9).slice(0, 3);
  return (
    <Region test="join-qr" title="Scan to join" className="r-qr">
      {failed ? <p className="empty" data-test="qr-empty">Join codes appear once the village is live (Ana taps “Invite everyone”).</p> : null}
      {!failed && !entries ? <p className="muted small">Loading join codes…</p> : null}
      <div className="qr-tiles">
        {tiles.map((t) => (
          <figure key={t.member_id} className={`qr-tile${t.member_id === "m_marco" ? " sage" : ""}`} data-test="qr-tile" data-member={t.member_id}>
            {t.svg ? <img alt="" src={`data:image/svg+xml;utf8,${encodeURIComponent(t.svg)}`} width={120} height={120} /> : <QRCodeSVG value={t.url} size={120} marginSize={1} />}
            <figcaption>{TILE_LABEL[t.member_id] ?? t.member_id.replace(/^[a-z]_/, "")}</figcaption>
          </figure>
        ))}
      </div>
    </Region>
  );
}

/* ---------------- Captions layer ---------------- */

export function CaptionsLayer({ captions }: { captions: CaptionLine[] }) {
  const last = captions.slice(-2);
  if (!last.length) return null;
  return (
    <div className="captions-layer" data-test="captions-layer" aria-live="polite">
      {last.map((c) => (
        <p key={c.id} className="caption-line" data-test="caption-line">
          {c.speaker ? <span className="eyebrow">{c.speaker}</span> : null}
          {c.es ? <Cap es={c.es} en={c.en} /> : <span>{c.en}</span>}
        </p>
      ))}
    </div>
  );
}

