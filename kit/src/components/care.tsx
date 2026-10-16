import { useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { FactHistoryCard, MEMORY_CAPTION } from "./fact";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { fmtDay, fmtTime, mmss, secondsLeft, useNow } from "../util/time";
import { Bi, Card, Icon, memberName } from "./shared";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

const SEVERITY_WORD: Record<string, Record<string, string>> = {
  es: { danger: "Urgente", warn: "Atención", info: "Aviso" },
  en: { danger: "Urgent", warn: "On hold", info: "Info" }
};

export function Countdown({ deadline, showDefault = true }: { deadline: string; showDefault?: boolean }) {
  const ctx = useCtx();
  const now = useNow(ctx.nowMs);
  const s = secondsLeft(deadline, now);
  const total = 45;
  return (
    <div className="countdown" data-test="countdown" role="timer" aria-live="off" data-seconds={s}>
      <div className="countdown-num" data-say="">{mmss(s)}</div>
      <div className="countdown-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, (s / total) * 100)}%` }} /></div>
      {showDefault ? <p className="countdown-default">{k("then_default", ctx.lang)}</p> : null}
    </div>
  );
}

interface BvAlert {
  id: string;
  severity: "danger" | "warn" | "info";
  title: unknown;
  body: unknown;
  verification?: { id: string; claimed_member_id: string; deadline: string; status: string };
  escalation?: { to: string; channel: string; status: string };
}

export function Alert({ props }: CatalogProps) {
  const ctx = useCtx();
  const levels: string[] = props.severity_levels ?? ["danger", "warn", "info"];
  const alerts = arr<BvAlert>(ctx.data[props.bind]).filter((a) => levels.includes(a.severity));
  if (!alerts.length) {
    return (
      <section className="alert alert-empty" data-test="alert" data-count="0">
        <Icon name="check" />
        <span><Bi value={props.empty_text ?? k("no_alerts", ctx.lang)} /></span>
      </section>
    );
  }
  return (
    <div className="alerts" data-test="alerts" data-count={alerts.length}>
      {alerts.map((a) => (
        <section key={a.id} className={`alert alert-${a.severity}`} data-test="alert" data-severity={a.severity} data-alert-id={a.id} role="alert">
          <div className="alert-head">
            <Icon name={a.severity === "info" ? "help" : "shield"} />
            <span className="chip">{(SEVERITY_WORD[ctx.lang] ?? SEVERITY_WORD.en)[a.severity]}</span>
          </div>
          <h2 className="alert-title"><Bi value={a.title} /></h2>
          <p className="alert-body"><Bi value={a.body} /></p>
          {props.show_countdown && a.verification?.status === "pending" ? <Countdown deadline={a.verification.deadline} /> : null}
          {props.show_escalation_status && a.escalation ? (
            <p className="alert-escalation" data-test="escalation" data-status={a.escalation.status}>
              <Icon name="phone" /> {k("escalation", ctx.lang, { name: memberName(a.escalation.to, ctx.data) })} · {a.escalation.status}
            </p>
          ) : null}
        </section>
      ))}
    </div>
  );
}

interface DoseSlot { slot: string; status: string; taken_at: string | null; via: string | null; lid_color?: string; meds?: string[] }

const STATUS_ICON: Record<string, string> = { taken: "✓", uncertain: "?", missed: "✗", due: "●", upcoming: "○" };

export function DoseTracker({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const day = ctx.data[props.bind] as { slots?: DoseSlot[] } | undefined;
  const slots = arr<DoseSlot>(day?.slots);
  const showMeds = props.show_med_names === true && ctx.view.theme !== "elder";
  return (
    <Card test="dose-tracker" title={props.title ? <Bi value={props.title} /> : undefined} extra={{ "data-big": props.big ? "true" : undefined }}>
      <ul className="dose-slots">
        {(props.slots as string[]).map((slotId) => {
          const s = slots.find((x) => x.slot === slotId);
          const status = s?.status ?? "upcoming";
          const statusText = k(status as "taken", ctx.lang);
          return (
            <li key={slotId} className={`dose-slot st-${status}`} data-test="dose-slot" data-slot={slotId} data-status={status}>
              <span className="lid" style={s?.lid_color ? ({ "--lid": s.lid_color } as React.CSSProperties) : undefined} aria-hidden="true" />
              <span className="dose-name" data-say="">{slotLabel(slotId, ctx.lang)}</span>
              <span className="dose-status" data-say="">
                {STATUS_ICON[status] ?? ""} {statusText}
                {s?.taken_at ? ` · ${fmtTime(s.taken_at, ctx.lang)}` : ""}
              </span>
              {showMeds && s?.meds?.length ? <span className="dose-meds" data-test="dose-meds">{s.meds.join(" · ")}</span> : null}
              {props.allow_log && status === "due" && ctx.view.theme !== "elder" ? (
                <button type="button" className="btn btn-soft" disabled={ctx.disabled} onClick={() => ctx.send({ name: "log_dose", arg: `slot:${slotId}`, element_id: id })}>
                  {k("taken", ctx.lang)}
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function slotLabel(slot: string, lang: string): string {
  const es: Record<string, string> = { morning: "Mañana", evening: "Noche", noon: "Mediodía", night: "Noche" };
  const en: Record<string, string> = { morning: "Morning", evening: "Evening", noon: "Noon", night: "Night" };
  return (lang === "es" ? es : en)[slot] ?? slot;
}

interface RotaMe { is_my_turn: boolean; date?: string; on_duty: { name: string }; backup: { name: string }; until: string | null; next_shift: string | null; answer: unknown; status_line?: unknown }

const WD_EN = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** Weekday name of an ISO date/datetime in the village clock ("2026-10-17" → "Saturday"). */
export function weekdayName(iso: string | null | undefined, lang = "en"): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00-04:00` : iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(lang === "es" ? "es-US" : "en-US", { weekday: "long", timeZone: "America/New_York" }).format(d);
}

/** Short weekday ("Fri") of now in the village clock: the refill-day rule compares it with prescriptions.refill_day. */
export function todayShort(nowMs: number): string {
  return new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "America/New_York" }).format(new Date(nowMs));
}

/** "Yes · tonight until 9:30" / "No · Ana tonight · you're on Thursday", composed from bv_rota_me; Core's answer stays under it. */
export function turnHeadline(v: RotaMe, lang: string): string {
  if (v.is_my_turn) {
    const said = text(v.answer, "en").match(/until (\d{1,2}(:\d{2})?\s?([AaPp]\.?[Mm]\.?)?)/);
    const until = v.until ? fmtTime(v.until, lang) : said ? said[1].trim() : "";
    return `Yes · tonight${until ? ` until ${until}` : ""}`;
  }
  const who = v.on_duty?.name ? `${v.on_duty.name} tonight` : "not tonight";
  const next = v.next_shift ? ` · you're on ${weekdayName(v.next_shift, lang) || WD_EN[0]}` : "";
  return `No · ${who}${next}`;
}

export function HelperAnswer({ props }: CatalogProps) {
  const ctx = useCtx();
  const v = ctx.data[props.bind] as RotaMe | null | undefined;
  const swapDay = v ? (v.is_my_turn ? weekdayName(v.date ?? null, "en") || "tonight" : weekdayName(v.next_shift, "en")) : "";
  return (
    <Card test="helper-answer" title={<Bi value={props.question} />} tone={v?.is_my_turn ? "sage" : undefined} extra={{ "data-my-turn": v ? String(v.is_my_turn) : undefined }}>
      {v ? (
        <>
          <p className="helper-answer helper-headline" data-test="helper-headline" data-say="">{turnHeadline(v, ctx.lang)}</p>
          <p className="muted" data-test="helper-answer-text"><Bi value={v.answer} /></p>
          {props.show_status && v.status_line ? <p className="muted"><Bi value={v.status_line} /></p> : null}
          {props.show_next_shift && v.next_shift && v.is_my_turn ? <p className="muted" data-say="">{k("next_shift", ctx.lang, { date: fmtDay(v.next_shift, ctx.lang) })}</p> : null}
          {ctx.openChat && swapDay ? (
            <button type="button" className="btn btn-link" data-test="swap-my-night" disabled={ctx.disabled} onClick={() => ctx.openChat?.(`@Village can someone swap ${swapDay}?`)}>Swap my night</button>
          ) : null}
        </>
      ) : (
        <p className="muted">{k("nothing_yet", ctx.lang)}</p>
      )}
    </Card>
  );
}

interface TimelineItem { event_id: string; kind: string; at: string; text: unknown; source: { kind: string; ref: string; secs?: number }; source_label?: unknown; rule_id?: string; superseded: boolean }

function kindMatches(kinds: string[] | undefined, kind: string): boolean {
  if (!kinds?.length) return true;
  if (kinds.includes(kind)) return true;
  if (kinds.includes("verification") && kind.startsWith("verification_")) return true;
  if (kinds.includes("dose_blocked") && (kind === "dose_repeat_scan" || kind === "dose_repeat")) return true;
  return false;
}

export function Timeline({ props }: CatalogProps) {
  const ctx = useCtx();
  const items = arr<TimelineItem>(ctx.data[props.bind])
    .filter((i) => kindMatches(props.event_kinds, i.kind))
    .filter((i) => props.show_superseded || !i.superseded)
    .slice(0, props.limit ?? 50);
  return (
    <Card test="timeline" title={props.title ? <Bi value={props.title} /> : undefined}>
      {items.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
      <ol className="timeline">
        {items.map((i) => (
          <li key={i.event_id} className="tl-row" data-test="timeline-row" data-kind={i.kind} data-superseded={i.superseded}>
            <time className="tl-time">{fmtDay(i.at, ctx.lang)} {fmtTime(i.at, ctx.lang)}</time>
            <span className="tl-text">
              {i.superseded ? <s><Bi value={i.text} /></s> : <Bi value={i.text} />}
              {i.superseded ? <span className="chip chip-gray"> {k("superseded", ctx.lang)}</span> : null}
            </span>
            {props.show_provenance ? (
              <span className="tl-source" data-test="provenance">
                {k("source", ctx.lang)}: {i.source_label ? text(i.source_label, ctx.lang) : `${i.source.kind} ${i.source.ref}${i.source.secs != null ? ` @${mmss(Math.round(i.source.secs))}` : ""}`}
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </Card>
  );
}

interface RotaDay { date: string; day: string; on_duty: string; backup: string }

export function CareRota({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const days = arr<RotaDay>(ctx.data[props.bind]);
  return (
    <Card test="care-rota" title={props.title ? <Bi value={props.title} /> : undefined}>
      <table className="rota">
        <tbody>
          {days.map((d) => {
            const mine = props.highlight_current_user && d.on_duty === ctx.memberId;
            return (
              <tr key={d.date} data-test="rota-row" data-date={d.date} data-on-duty={d.on_duty} className={mine ? "mine" : undefined}>
                <th scope="row">{d.day}</th>
                <td data-say="">{memberName(d.on_duty, ctx.data)}</td>
                {props.show_backup ? <td className="muted">{k("backup", ctx.lang)}: {memberName(d.backup, ctx.data)}</td> : null}
                {props.allow_swap && d.on_duty === ctx.memberId ? (
                  <td><button type="button" className="btn btn-link" disabled={ctx.disabled} onClick={() => ctx.send({ name: "swap_shift", arg: d.date, element_id: id })}>Swap</button></td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      {days.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
    </Card>
  );
}

interface LifeArea { id: string; label: string; status: unknown; rules?: string[]; trusted_contacts?: string[] }

/** Family phones get plain words per life area ("Money: 1 scam stopped"); rule ids live on the Control Room only. */
export function LifeAreas({ props }: CatalogProps) {
  const ctx = useCtx();
  const areas = arr<LifeArea>(ctx.data[props.bind]).filter((a) => (props.areas as string[]).includes(a.id));
  return (
    <Card test="life-areas" title={props.title ? <Bi value={props.title} /> : undefined}>
      <ul className="areas">
        {areas.map((a) => {
          const word = a.label.split(":")[0].trim();
          return (
            <li key={a.id} className={`area area-${a.id}`} data-test="life-area" data-area={a.id}>
              <span className="area-line" data-test="life-area-status"><strong>{word}:</strong> <Bi value={a.status} /></span>
              {props.show_contacts && a.trusted_contacts?.length ? <span className="small muted"> · {a.trusted_contacts.map((m) => memberName(m, ctx.data)).join(", ")}</span> : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function PillOrganizer({ props }: CatalogProps) {
  const ctx = useCtx();
  const week = ctx.data[props.bind] as { days?: { date: string; slots: DoseSlot[] }[] } | undefined;
  const byDay = new Map<string, DoseSlot[]>();
  for (const d of arr<{ date: string; slots: DoseSlot[] }>(week?.days)) {
    byDay.set(WEEKDAYS[new Date(`${d.date}T12:00:00-04:00`).getDay()], d.slots);
  }
  const days: string[] = props.days ?? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return (
    <Card test="pill-organizer" title={props.title ? <Bi value={props.title} /> : undefined}>
      <table className="organizer">
        <thead>
          <tr><th />{days.map((d) => <th key={d} scope="col">{d}</th>)}</tr>
        </thead>
        <tbody>
          {(props.slots as string[]).map((slot, i) => (
            <tr key={slot}>
              <th scope="row">{props.labels[i]}</th>
              {days.map((d) => {
                const st = byDay.get(d)?.find((s) => s.slot === slot)?.status ?? "upcoming";
                return (
                  <td key={d} data-test="pill-lid" data-day={d} data-slot={slot} data-status={st} style={{ "--lid": props.lid_colors[i] } as React.CSSProperties}>
                    <span aria-label={`${d} ${props.labels[i]}: ${st}`}>{STATUS_ICON[st] ?? ""}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

interface RefillItem {
  med_id?: string; name: string; dose_mg?: number; dose_text?: string; schedule: string[]; valid_from: string; changed_by?: string;
  superseded?: { dose_text: string; valid_until: string }; source_label?: unknown;
}
/** bv_prescriptions (contract 1.3.3, D22). */
export interface Prescriptions { subject?: string; refill_day: string; next_refill?: string; owner_member_id: string; owner_name?: string; items: RefillItem[] }

const WEEKDAY_LONG: Record<string, Record<string, string>> = {
  en: { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday", Fri: "Friday", Sat: "Saturday", Sun: "Sunday" },
  es: { Mon: "lunes", Tue: "martes", Wed: "miércoles", Thu: "jueves", Fri: "viernes", Sat: "sábado", Sun: "domingo" }
};

function shortDate(iso: string, lang: string): string {
  const d = new Date(`${iso}T12:00:00-04:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang === "es" ? "es-US" : "en-US", { month: "short", day: "numeric", timeZone: "America/New_York" });
}

/** D22: the refill checklist for whoever is on duty on refill day. Superseded doses are struck through, never deleted. */
export function RefillCard({ props }: CatalogProps) {
  const ctx = useCtx();
  const v = ctx.data[props.bind] as Prescriptions | null | undefined;
  if (!v || !Array.isArray(v.items)) return null;
  const owner = props.owner ?? v.owner_name ?? memberName(v.owner_member_id, ctx.data);
  const day = props.day ?? (WEEKDAY_LONG[ctx.lang] ?? WEEKDAY_LONG.en)[v.refill_day] ?? v.refill_day;
  const showSup = props.show_superseded !== false;
  const showSched = props.show_schedule !== false;
  const showSrc = props.show_source !== false;
  const sub = k("refill_title", ctx.lang, { day, owner });
  // D22 refill-day rule: the owner sees the checklist only on refill day; other days, one line ("Refill Friday · you")
  if (ctx.memberId && v.owner_member_id === ctx.memberId && v.refill_day !== todayShort(ctx.nowMs())) {
    return <p className="refill-line" data-test="refill-line" data-day={v.refill_day}>Refill {day} · you</p>;
  }
  return (
    <Card test="refill-card" title={props.title ? <Bi value={props.title} /> : sub} extra={{ "data-owner": owner, "data-day": v.refill_day }}>
      {props.title ? <p className="small muted" data-test="refill-owner">{sub}</p> : null}
      <ul className="refill">
        {v.items.map((it) => {
          const dose = it.dose_text ?? (it.dose_mg != null ? `${it.dose_mg} mg` : "");
          const changed = showSup && it.superseded;
          return (
            <li key={it.med_id ?? it.name} data-test="refill-item" data-med={it.name} data-changed={changed ? "true" : undefined} className={changed ? "changed" : undefined}>
              <span className="refill-med" data-say="">{it.name} {dose}</span>
              {changed ? (
                <span className="refill-change" data-test="refill-change">
                  {" "}({k("changed_short", ctx.lang)} {shortDate(it.superseded!.valid_until, ctx.lang)}{it.changed_by ? `, ${it.changed_by}` : ""}; {k("was", ctx.lang)} <s data-test="refill-superseded">{it.superseded!.dose_text}</s>)
                </span>
              ) : null}
              {showSched && it.schedule?.length ? <span className="refill-sched small muted"> · {it.schedule.map((sl) => slotLabel(sl, ctx.lang)).join(", ")}</span> : null}
              {showSrc && it.source_label ? <span className="refill-src small muted" data-test="refill-source"> · {k("source", ctx.lang)}: {text(it.source_label, ctx.lang)}</span> : null}
              {changed && ctx.api ? <FactToggle entity={v.subject ?? "village"} med={it.name} /> : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

/** Ana's compact fact card (D32): tap a changed dose to see its Agent Memory history, source and as-of. */
function FactToggle({ entity, med }: { entity: string; med: string }) {
  const ctx = useCtx();
  const [open, setOpen] = useState(false);
  const key = `${med.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")}_dose`;
  return (
    <div className="fact-toggle">
      <button type="button" className="btn btn-link" data-test="fact-open" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? k("hide_history", ctx.lang) : k("how_village_knows", ctx.lang)}
      </button>
      {open ? (
        <div className="fact-card" data-test="fact-card">
          <FactHistoryCard api={ctx.api} village={ctx.village} entity={entity} factKey={key} plain />
          <p className="small muted">{MEMORY_CAPTION}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Elder: who is caring for her tonight (TonightCard, template "Esta noche cuida {name}"). Absent key = render nothing; null = nobody (amber). */
export function TonightCard({ props }: CatalogProps) {
  const ctx = useCtx();
  if (!(props.bind in ctx.data)) return null;
  const p = ctx.data[props.bind] as { name?: string } | null;
  const line = p?.name ? (props.template ? String(props.template).replace("{name}", p.name) : k("tonight", ctx.lang, { name: p.name })) : k("tonight_nobody", ctx.lang);
  return (
    <section className={`tonight ${p ? "tonight-ok" : "tonight-nobody"}`} data-test="tonight-card" data-on-duty={p?.name ?? ""}>
      <Icon name={p ? "heart" : "help"} />
      <span><Bi value={line} /></span>
    </section>
  );
}
