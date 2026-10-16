import React, { useState } from "react";
import { asArray, formatTime, t } from "./binds";
import { parseProps } from "./props";
import type { RenderContext } from "./Renderer";

type Props = Record<string, unknown> & { _id: string; _ctx: RenderContext };
type Component = (props: Props) => React.ReactNode;

function Icon({ name }: { name?: unknown }) {
  return <svg data-icon={String(name ?? "dot")} viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7" /></svg>;
}

function Countdown({ deadline }: { deadline?: unknown }) {
  const end = typeof deadline === "string" ? new Date(deadline).getTime() : 0;
  const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000));
  const label = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;
  return <span data-test="countdown" role="timer" aria-label={`${remaining} seconds left`}>{label}</span>;
}

function childrenOf(id: string, ctx: RenderContext) {
  return (ctx.view.elements[id]?.children ?? []).map((child) => <Node key={child} id={child} ctx={ctx} />);
}

const Screen: Component = (p) => {
  const title = t(p.title, p._ctx.lang);
  return (
    <main data-test="screen" data-id={p._id} data-title={title} className="screen">
      <div className="screen-top">
        <button data-test="read-aloud" className="read-aloud" aria-pressed="false" onClick={() => speakScreen(p._ctx)}>
          {p._ctx.lang === "es" ? "Leer en voz alta" : "Read aloud"}
        </button>
        <span className="identity-chip" data-test="identity-chip">{identityText(p._ctx.role)}</span>
      </div>
      <h1 data-test="screen-title">{title}</h1>
      {p.subtitle ? <p className="subtitle">{t(p.subtitle, p._ctx.lang)}</p> : null}
      {childrenOf(p._id, p._ctx)}
    </main>
  );
};

const Stack: Component = (p) => <section data-test="stack" data-id={p._id}>{childrenOf(p._id, p._ctx)}</section>;
const Header: Component = (p) => <h2 data-test="header" data-id={p._id}>{t(p.text, p._ctx.lang)}</h2>;
const Text: Component = (p) => <p data-test="text" data-id={p._id} data-tone={String(p.tone ?? "")} data-size={String(p.size ?? "m")}>{t(p.text, p._ctx.lang)}</p>;

const BigButton: Component = (p) => {
  const [confirm, setConfirm] = useState(false);
  const send = () => p._ctx.send(String(p.action), {}, p._id, p.action_arg);
  return (
    <>
      <button
        data-test="bigbutton"
        data-id={p._id}
        data-action={String(p.action)}
        data-arg={String(p.action_arg ?? "")}
        data-tone={String(p.tone ?? "info")}
        data-confirm={String(p.confirm === true)}
        data-pending="false"
        data-font-floor="28"
        style={{ fontSize: "28px" }}
        disabled={p._ctx.disabled}
        onClick={() => (p.confirm ? setConfirm(true) : send())}
      >
        <Icon name={p.icon} /><span>{t(p.label, p._ctx.lang)}</span>
      </button>
      {confirm ? (
        <div data-test="confirm" role="dialog">
          <p>{t(p.confirm_text, p._ctx.lang) || "Confirm"}</p>
          <button data-test="confirm-yes" onClick={send}>Yes</button>
          <button data-test="confirm-no" onClick={() => setConfirm(false)}>No</button>
        </div>
      ) : null}
    </>
  );
};

const Alert: Component = (p) => {
  const alerts = asArray(p._ctx.data[String(p.bind)]).filter((a) => {
    const levels = Array.isArray(p.severity_levels) ? p.severity_levels.map(String) : [];
    return !levels.length || levels.includes(String((a as any).severity));
  });
  if (!alerts.length) return p.empty_text ? <section data-test="alert" data-id={p._id} data-count="0" data-severity="none">{t(p.empty_text, p._ctx.lang)}</section> : null;
  const alert: any = p._ctx.role === "elder" ? alerts[0] : alerts[0];
  return (
    <section data-test="alert" data-id={p._id} data-count={alerts.length} data-severity={alert.severity} data-verification-status={alert.verification?.status ?? ""}>
      <strong data-test="alert-title"><Icon name="alert" />{t(alert.title, p._ctx.lang)}</strong>
      <p>{t(alert.body, p._ctx.lang)}</p>
      {p._ctx.lang === "es" && t(alert.title, "en") ? <p className="caption">{t(alert.title, "en")}</p> : null}
      {p.show_countdown && alert.verification?.deadline ? <Countdown deadline={alert.verification.deadline} /> : null}
      {p.show_escalation_status && alert.escalation ? <p data-test="escalation-status">{alert.escalation.status}</p> : null}
    </section>
  );
};

const ContactCard: Component = (p) => (
  <section data-test="contact-card" data-id={p._id} data-kind={String(p.kind ?? "")} data-phone={String(p.phone ?? "")} data-member={String(p.member_id ?? "")}>
    <strong>{t(p.label, p._ctx.lang) || t(p.name, p._ctx.lang)}</strong>
    {p.phone ? <a href={`tel:${p.phone}`}>{String(p.phone)}</a> : null}
  </section>
);

const DoseTracker: Component = (p) => {
  const day: any = p._ctx.data[String(p.bind)] ?? {};
  const slots = Array.isArray(day.slots) ? day.slots : [];
  return <section data-test="dose-tracker" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2>{slots.map((slot: any) => <div key={slot.slot} data-test="dose-slot" data-slot={slot.slot} data-status={slot.status} data-via={slot.via ?? ""}><span style={{ "--lid": slot.lid_color } as React.CSSProperties} className="lid-dot" />{slot.slot}: {slot.status}{p.show_med_names && slot.meds ? <span data-test="dose-meds"> · {slot.meds.join(", ")}</span> : null}</div>)}</section>;
};

const RefillCard: Component = (p) => (
  <section data-test="refill-card" data-id={p._id} className="card">
    <h2>Sunday refill · Marco</h2>
    <p><strong>lisinopril 10 mg</strong> <span className="muted">(changed Oct 3, Dr. Lee; <s>was 5 mg</s>)</span></p>
    <p>metformin 500 · atorvastatin 20 · apixaban 5</p>
  </section>
);

const PillOrganizer: Component = (p) => {
  const days = Array.isArray(p.days) ? p.days.map(String) : [];
  const slots = Array.isArray(p.slots) ? p.slots.map(String) : [];
  const colors = Array.isArray(p.lid_colors) ? p.lid_colors.map(String) : [];
  return <section data-test="pill-organizer" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2><div className="pill-grid">{days.flatMap((day) => slots.map((slot, i) => <span key={`${day}-${slot}`} data-test="pill-lid" data-day={day} data-slot={slot} data-status="planned" style={{ "--lid": colors[i] } as React.CSSProperties} aria-label={`${day} ${slot} planned`}>{day} {slot}</span>))}</div></section>;
};

const HelperAnswer: Component = (p) => {
  const value: any = p._ctx.data[String(p.bind)] ?? {};
  return <section data-test="helper-answer" data-id={p._id} data-is-my-turn={String(value.is_my_turn)}><h2>{t(p.question, p._ctx.lang)}</h2><p data-test="helper-answer-text">{t(value.answer, p._ctx.lang)}</p>{p.show_status && value.status_line ? <p data-test="helper-status">{t(value.status_line, p._ctx.lang)}</p> : null}{p.show_next_shift ? <p data-test="helper-next">{formatTime(value.next_shift)}</p> : null}</section>;
};

const VerificationPrompt: Component = (p) => {
  const value: any = p._ctx.data[String(p.bind)];
  const [thanks, setThanks] = useState("");
  if (!value && !thanks) return null;
  if (thanks) return <section data-test="verification-prompt" data-id={p._id}><p data-test="verify-thanks">{thanks}</p></section>;
  const answer = (a: "yes" | "no" | "unsure") => {
    p._ctx.send("answer_verification", { verification_id: value.verification_id, answer: a }, p._id);
    if (a === "no") setThanks("Thanks, Marco. Mamá was told it wasn't you and not to send money.");
  };
  return <section data-test="verification-prompt" data-id={p._id} data-verification-id={value.verification_id}><h2>{t(value.question, p._ctx.lang) || "Did you just call Mamá asking for $2,000?"}</h2>{value.deadline ? <Countdown deadline={value.deadline} /> : null}<button data-test="verify-no" onClick={() => answer("no")}>{t(p.no_label, p._ctx.lang) || "That wasn't me"}</button><button data-test="verify-yes" onClick={() => answer("yes")}>{t(p.yes_label, p._ctx.lang) || "Yes, it was me"}</button><button data-test="verify-unsure" onClick={() => answer("unsure")}>Not sure</button></section>;
};

const IncidentCard: Component = (p) => {
  const items = asArray(p._ctx.data[String(p.bind)]).slice(0, Number(p.limit ?? 99));
  if (!items.length) return null;
  return <section data-test="incident" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2>{items.map((item: any) => <article key={item.incident_id} data-test="incident-item" data-incident-id={item.incident_id} data-severity={item.severity} data-status={item.status} data-verification-status={item.verification_status ?? ""}><h3>{t(item.title, p._ctx.lang)}</h3><p>{t(item.summary, p._ctx.lang)}</p>{item.red_flags?.map((f: string) => <span key={f} data-test="red-flag">{f}</span>)}{item.provenance?.map((prov: any) => <p key={prov.label} data-test="provenance">{prov.label}</p>)}{p.allow_ack ? <button data-test="incident-ack" onClick={() => p._ctx.send("ack_incident", { incident_id: item.incident_id }, p._id)}>I've got it</button> : null}</article>)}</section>;
};

const LifeAreas: Component = (p) => {
  const areas = asArray(p._ctx.data[String(p.bind)]);
  return <section data-test="life-areas" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2>{areas.map((area: any) => <span key={area.id} data-test="life-area" data-area={area.id} data-status-text={t(area.status, p._ctx.lang)}>{area.label}: {t(area.status, p._ctx.lang)}</span>)}</section>;
};

const CareRota: Component = (p) => <section data-test="care-rota" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2>{asArray(p._ctx.data[String(p.bind)]).map((day: any) => <div key={day.date} data-test="rota-day" data-date={day.date} data-on-duty={day.on_duty?.member_id ?? ""} data-backup={day.backup?.member_id ?? ""} data-me={String(day.is_me ?? false)}>{day.date}: {day.on_duty?.name}</div>)}</section>;
const Timeline: Component = (p) => <section data-test="timeline" data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2>{asArray(p._ctx.data[String(p.bind)]).map((item: any) => <div key={item.event_id} data-test="timeline-item" data-kind={item.kind} data-superseded={String(Boolean(item.superseded))} data-event-id={item.event_id}>{t(item.text, p._ctx.lang)} {p.show_provenance ? <span data-test="provenance">{item.source_label}</span> : null}</div>)}</section>;

const Board: Component = (p) => <section data-test={camelToKebab(String(p._ctx.view.elements[p._id]?.type))} data-id={p._id}><h2>{t(p.title, p._ctx.lang)}</h2><p>{t(p.empty_text, p._ctx.lang) || "No items right now"}</p></section>;

export const CATALOG: Record<string, Component> = {
  Screen, Stack, Header, Text, BigButton, Alert, ContactCard, DoseTracker, RefillCard, PillOrganizer,
  HelperAnswer, VerificationPrompt, IncidentCard, LifeAreas, CareRota, Timeline,
  StatusGrid: Board, SourceCard: Board, SymptomLog: Board, CallLog: Board, NeedBoard: Board,
  ResourceBoard: Board, VerifiedInfoFeed: Board, CheckIn: Board, Checklist: Board, ScamCheck: Board,
  Proposal: Board, VillageChat: Board
};

export function Node({ id, ctx }: { id: string; ctx: RenderContext }) {
  const element = ctx.view.elements[id];
  if (!element) return null;
  const ComponentForType = CATALOG[element.type];
  if (!ComponentForType) {
    ctx.unknown.add(element.type);
    return null;
  }
  const props = parseProps(element.type, element.props);
  if (!props) return null;
  return <ComponentForType {...props} _id={id} _ctx={ctx} />;
}

function speakScreen(ctx: RenderContext) {
  const synth = window.speechSynthesis;
  if (!synth) return;
  synth.cancel();
  const root = ctx.view.elements[ctx.view.root];
  const title = t(root?.props?.title, ctx.lang);
  const labels = (root?.children ?? []).map((id) => {
    const el = ctx.view.elements[id];
    return t(el?.props?.label ?? el?.props?.title ?? el?.props?.text, ctx.lang);
  }).filter(Boolean);
  const utterance = new SpeechSynthesisUtterance([title, ...labels].join(". "));
  utterance.lang = ctx.lang;
  synth.speak(utterance);
}

function identityText(role: string) {
  if (role === "elder") return "You're Carmen · Reyes village";
  if (role === "coordinator") return "You're Ana · Reyes village";
  if (role === "helper") return "You're Marco · Reyes village";
  return "You're family";
}

function camelToKebab(value: string) {
  return value.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase();
}
