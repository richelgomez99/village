// Brief blocks (contract 1.3.2 catalog types RightNow · WhatVillageDid · SinceYourTurn, plus PlanBoard · ScreenedCalls · FactCard).
// Composed from snapshot.data in plain words; no village, person or element id is named here.
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { fmtDay, fmtTime } from "../util/time";
import { Bi, Card, memberName } from "./shared";
import { FactHistoryCard, writtenBy } from "./fact";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

export function todayIso(nowMs: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date(nowMs));
}

interface Person { member_id?: string; name?: string }

/** "Right now": who's on tonight · pills today · the last thing that happened. Each line only when its bind is in the snapshot. */
export function rightNowLines(data: Record<string, unknown>, nowMs: number, lang: string): { key: string; text: string }[] {
  const out: { key: string; text: string }[] = [];
  const today = todayIso(nowMs);
  let onDuty: string | undefined;
  const p = data["rota:current.on_duty"] as Person | null | undefined;
  if (p?.name) onDuty = p.name;
  const me = data["rota:current?member=me"] as { on_duty?: Person } | null | undefined;
  if (!onDuty && me?.on_duty?.name) onDuty = me.on_duty.name;
  for (const key of ["rota:current", "rota:week"]) {
    if (onDuty) break;
    const d = arr<{ date: string; on_duty: string }>(data[key]).find((r) => r.date === today);
    if (d?.on_duty) onDuty = memberName(d.on_duty, data);
  }
  if (onDuty) out.push({ key: "tonight", text: `Tonight: ${onDuty}` });

  const doseKey = Object.keys(data).find((k) => k.startsWith("facts:dose_event") && k.includes("valid_at=today"));
  const dose = doseKey ? (data[doseKey] as { slots?: { slot: string; status: string }[] } | null) : null;
  if (dose?.slots?.length) {
    const taken = dose.slots.filter((s) => s.status === "taken").length;
    const open = dose.slots.find((s) => s.status !== "taken");
    out.push({ key: "pills", text: `Pills today: ${taken} of ${dose.slots.length} taken${open ? ` · ${open.slot} ${open.status === "upcoming" ? "still to come" : open.status}` : ""}` });
  }

  const tlKey = Object.keys(data).find((k) => k.startsWith("timeline:"));
  const last = arr<{ at: string; text: unknown; superseded?: boolean }>(tlKey ? data[tlKey] : null)
    .filter((r) => !r.superseded)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
  if (last) out.push({ key: "last", text: `Last: ${text(last.text, lang)} · ${fmtTime(last.at, lang)}` });
  return out;
}

interface Rounds { counts?: Record<string, number>; did_alone?: number; alone?: number; asked?: number; asked_person?: number; refused?: number; rows?: { at?: string; text?: unknown; line?: unknown; summary?: unknown; role?: string; actor?: string; mode?: string }[] }
const MODE_WORDS: Record<string, string> = { acted_alone: "did alone", asked_human: "asked a person", refused: "refused itself" };

/** rounds:latest (core-glue): three counts + rows in words. Absent = hidden. */
/** "last night 9:40 PM" · "today 8:11 AM" · "Thu 9:40 PM" in the village clock. */
export function whenWords(iso: string, nowMs: number): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = fmtTime(iso, "en");
  const day = todayIso(d.getTime());
  const today = todayIso(nowMs);
  const yesterday = todayIso(nowMs - 24 * 3600_000);
  const hour = Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone: "America/New_York" }).format(d));
  if (day === today) return `${hour >= 18 ? "tonight" : "today"} ${time}`;
  if (day === yesterday) return `${hour >= 18 ? "last night" : "yesterday"} ${time}`;
  return `${new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "America/New_York" }).format(d)} ${time}`;
}

export function WhatVillageDid({ data, bind = "rounds:latest", title = "What Village did", maxRows = 6, nowMs = Date.now() }: { data: Record<string, unknown>; bind?: string; title?: unknown; maxRows?: number; nowMs?: number }) {
  const r = data[bind] as Rounds | null | undefined;
  if (!r || typeof r !== "object") return null;
  if (!r.counts && !Array.isArray(r.rows)) return null; // {} = no round yet
  const c = r.counts ?? {};
  const alone = c.acted_alone ?? c.did_alone ?? c.alone ?? r.did_alone ?? r.alone ?? 0;
  const asked = c.asked_human ?? c.asked ?? c.asked_person ?? r.asked ?? r.asked_person ?? 0;
  const refused = c.refused ?? r.refused ?? 0;
  const rows = arr<NonNullable<Rounds["rows"]>[number]>(r.rows);
  return (
    <Card test="what-village-did" title={<Bi value={title} />}>
      <div className="wvd-stats" data-test="wvd-stats">
        <span className="wvd-stat"><b>{alone}</b> on its own</span>
        <span className="wvd-stat"><b>{asked}</b> asked a person</span>
        <span className="wvd-stat"><b>{refused}</b> refused itself</span>
      </div>
      <p className="wvd-counts small muted" data-test="wvd-counts">
        Did {alone} {alone === 1 ? "thing" : "things"} on its own · asked a person {asked} · refused itself {refused}
      </p>
      {rows.length ? (
        <ul className="wvd-rows">
          {rows.slice(0, maxRows).map((row, i) => (
            <li key={i} data-test="wvd-row">
              {row.at ? <span className="wvd-time small muted" data-test="wvd-time">{whenWords(row.at, nowMs)} </span> : null}
              {row.mode || row.role || row.actor ? <span className="chip chip-gray" data-mode={row.mode}>{(row.mode && MODE_WORDS[row.mode]) ?? row.role ?? row.actor}</span> : null} {text(row.text ?? row.line ?? row.summary ?? "", "en")}
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

interface SinceRow { event_id?: string; id?: string; at?: string; text?: unknown }

/** "Since your last turn": core-glue's events:since_last_turn?member=me (3 lines in words). Absent = hidden. */
export function SinceLastTurn({ data, lang, bind = "events:since_last_turn?member=me", title = "Since your last turn", maxRows = 3 }: { data: Record<string, unknown>; lang: string; bind?: string; title?: unknown; maxRows?: number }) {
  const rows = arr<SinceRow>(data[bind]).slice(0, maxRows);
  if (!rows.length) return null;
  return (
    <Card test="since-last-turn" title={<Bi value={title} />}>
      <ul className="right-now">
        {rows.map((r, i) => (
          <li key={r.event_id ?? r.id ?? i} data-test="since-row">{text(r.text, lang)}{r.at ? <span className="small muted"> · {fmtTime(r.at, lang)}</span> : null}</li>
        ))}
      </ul>
    </Card>
  );
}


/** RightNow (1.3.2): who's on tonight · the center person's pills · the last thing that happened, from whatever binds are in data. */
export function RightNow({ props }: CatalogProps) {
  const ctx = useCtx();
  const lines = rightNowLines(ctx.data, ctx.nowMs(), ctx.lang);
  if (!lines.length) return null;
  return <RightNowCard lines={lines} title={props.title ?? (ctx.lang === "es" ? "Ahora" : "Right now")} />;
}
export function RightNowCard({ lines, title }: { lines: { key: string; text: string }[]; title: unknown }) {
  return (
    <Card test="right-now" title={<Bi value={title} />}>
      <ul className="right-now">
        {lines.map((l) => <li key={l.key} data-test="right-now-line" data-line={l.key}>{l.text}</li>)}
      </ul>
    </Card>
  );
}

export function WhatVillageDidEl({ props }: CatalogProps) {
  const ctx = useCtx();
  return <WhatVillageDid data={ctx.data} bind={props.bind} title={props.title ?? "What Village did"} maxRows={props.max_rows ?? 6} nowMs={ctx.nowMs()} />;
}

export function SinceYourTurn({ props }: CatalogProps) {
  const ctx = useCtx();
  return <SinceLastTurn data={ctx.data} lang={ctx.lang} bind={props.bind} title={props.title ?? "Since your last turn"} maxRows={props.max_rows ?? 3} />;
}

interface PlanItem { text: unknown; owner?: string; when?: string; status?: string; kind?: string; note?: unknown }
/** PlanBoard (1.3.2, D36): who brings what, when; owners by name. */
export function PlanBoard({ props }: CatalogProps) {
  const ctx = useCtx();
  const v = ctx.data[props.bind] as { title?: unknown; date?: string; items?: PlanItem[] } | null | undefined;
  const items = arr<PlanItem>(v?.items);
  return (
    <Card test="plan-board" title={props.title || v?.title ? <Bi value={props.title ?? v?.title} /> : undefined}>
      {props.date || v?.date ? <p className="small muted">{props.date ?? fmtDay(v?.date, ctx.lang)}</p> : null}
      {items.length ? (
        <ul className="plan-rows">
          {items.map((it, i) => (
            <li key={i} data-test="plan-item" data-status={it.status ?? "open"} data-kind={it.kind}>
              {it.status === "done" ? "✓ " : ""}<Bi value={it.text} />
              {it.owner ? <span className="small muted"> · {memberName(it.owner, ctx.data)}</span> : it.status === "open" ? <span className="small muted"> · nobody yet</span> : null}
              {it.when ? <span className="small muted"> · {it.when}</span> : null}
              {it.note ? <span className="small muted"> · <Bi value={it.note} /></span> : null}
            </li>
          ))}
        </ul>
      ) : <p className="muted">{k("nothing_yet", ctx.lang)}</p>}
    </Card>
  );
}

const OUTCOME: Record<string, string> = { passed_through: "put through", held: "held", refused: "refused", unknown: "not sure" };
interface Screened { at: string; claimed?: string; outcome: string; verified_by?: string; say?: unknown }
/** ScreenedCalls (1.3.2, D19): calls Village answered first, in words. */
export function ScreenedCalls({ props }: CatalogProps) {
  const ctx = useCtx();
  const rows = arr<Screened>(ctx.data[props.bind]).slice(0, props.max_rows ?? 6);
  return (
    <Card test="screened-calls" title={props.title ? <Bi value={props.title} /> : undefined}>
      {rows.length ? (
        <ul className="plan-rows">
          {rows.map((r, i) => (
            <li key={i} data-test="screened-row" data-outcome={r.outcome}>
              <span className="small muted">{fmtTime(r.at, ctx.lang)} · </span>
              {r.claimed ? `Said they were ${r.claimed}` : "Unknown caller"} · {OUTCOME[r.outcome] ?? r.outcome}
              {r.verified_by ? ` · checked with ${memberName(r.verified_by, ctx.data)}` : ""}
              {r.say ? <span className="small muted"> · <Bi value={r.say} /></span> : null}
            </li>
          ))}
        </ul>
      ) : <p className="muted">{k("nothing_yet", ctx.lang)}</p>}
    </Card>
  );
}

/** FactCard (1.3.2, D32): one fact with history from facts:history?subject=&key=; live history via REST when api is set. */
export function FactCard({ props }: CatalogProps) {
  const ctx = useCtx();
  const m = /^facts:history\?subject=([a-z]_[a-z0-9_]+)&key=([a-z0-9_]+)$/.exec(props.bind);
  const v = ctx.data[props.bind] as { versions?: { text?: string; value?: string; superseded?: boolean; observed_at?: string }[] } | null | undefined;
  const caption = <p className="small muted" data-test="fact-caption">Typed · time-aware · supersedes rather than overwrites · traced to source · shared across agents</p>;
  if (ctx.api && m) return <Card test="fact-card-el" title={props.title ? <Bi value={props.title} /> : undefined}><FactHistoryCard api={ctx.api} village={ctx.village} entity={m[1]} factKey={m[2]} plain />{caption}</Card>;
  type V = { text?: string; value?: string; superseded?: boolean; observed_at?: string; labels?: Record<string, string>; source?: { kind: string } };
  const versions = arr<V>(v?.versions);
  return (
    <Card test="fact-card-el" title={props.title ? <Bi value={props.title} /> : undefined}>
      {versions.length ? (
        <ul className="plan-rows">
          {versions.map((f, i) => <li key={i} data-superseded={f.superseded ? "true" : undefined}>{f.superseded ? <s>{f.text ?? f.value}</s> : f.text ?? f.value}{f.observed_at ? <span className="small muted"> · {fmtDay(f.observed_at, ctx.lang)}</span> : null} <span className="chip chip-gray" data-test="fact-written-by">written by {writtenBy({ labels: f.labels, source: f.source ?? { kind: "seed" } })}</span></li>)}
        </ul>
      ) : <p className="muted">{k("nothing_yet", ctx.lang)}</p>}
      {caption}
    </Card>
  );
}
