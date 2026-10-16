import { useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { fmtTime, mmss } from "../util/time";
import { Countdown } from "./care";
import { Bi, Card, Icon, memberName } from "./shared";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

interface Pending { verification_id: string; question: unknown; detail: unknown; deadline: string; subject: string }

export function useAnswer(elementId: string) {
  const ctx = useCtx();
  return (verification_id: string, answer: "yes" | "no" | "unsure") => {
    if (ctx.disabled) return;
    ctx.send({ name: "answer_verification", element_id: elementId, payload: { verification_id, answer } });
  };
}

/** Marco's in-app verification (binding-driven). Thanks state shows the gate's `say` from the action result. */
export function VerificationPrompt({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const answer = useAnswer(id);
  const p = ctx.data[props.bind] as Pending | null | undefined;
  const result = ctx.results.answer_verification;
  if (result && result !== "pending" && result.say) {
    return (
      <Card test="verify-done" tone="ok">
        <p className="muted">{k("thanks", ctx.lang)}</p>
        <p className="verify-say" data-test="verify-thanks" data-say="">{text(result.say, ctx.lang)}</p>
      </Card>
    );
  }
  if (result === "pending") {
    return <Card test="verify-pending"><p data-say="">{k("sending", ctx.lang)}</p></Card>;
  }
  if (!p) return null;
  return (
    <Card test="verification-prompt" tone="amber" extra={{ "data-verification-id": p.verification_id }}>
      <p className="eyebrow"><Icon name="phone" /> {k("calling_you", ctx.lang)}</p>
      <h2 className="verify-q"><Bi value={p.question} /></h2>
      <p className="verify-detail"><Bi value={p.detail} /></p>
      {props.show_countdown ? <Countdown deadline={p.deadline} /> : null}
      <div className="verify-actions">
        <button type="button" className="btn btn-danger btn-xl" data-test="verify-no" disabled={ctx.disabled} onClick={() => answer(p.verification_id, "no")}>{props.no_label}</button>
        <button type="button" className="btn btn-soft" data-test="verify-yes" disabled={ctx.disabled} onClick={() => answer(p.verification_id, "yes")}>{props.yes_label}</button>
        <button type="button" className="btn btn-link" data-test="verify-unsure" disabled={ctx.disabled} onClick={() => answer(p.verification_id, "unsure")}>{k("unsure", ctx.lang)}</button>
      </div>
    </Card>
  );
}

interface Incident {
  incident_id: string; type: string; severity: string; status: string; title: unknown; summary: unknown;
  verification_status?: string; claimed_identity?: string; amount?: number | null; red_flags?: string[]; pattern_flag?: string;
  provenance: { label: string; source: { kind: string; ref: string; secs?: number } }[]; at: string;
}

const OUTCOME_TONE: Record<string, string> = { denied: "tomato", timeout: "amber", pending: "amber", confirmed: "ok" };
const FLAG_WORDS: Record<string, string> = { urgency: "Urgency", emotional_pressure: "Emotional pressure", secrecy: "Secrecy", gift_cards: "Gift cards", wire: "Wire transfer", crypto: "Crypto", courier: "Courier pickup" };

export function IncidentCard({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const items = arr<Incident>(ctx.data[props.bind]).slice(0, props.limit ?? 5);
  return (
    <Card test="incident-cards" title={props.title ? <Bi value={props.title} /> : undefined}>
      {items.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
      {items.map((inc) => {
        const tone = OUTCOME_TONE[inc.verification_status ?? ""] ?? "amber";
        return (
          <article key={inc.incident_id} className={`incident tone-${tone}`} data-test="incident-card" data-incident-id={inc.incident_id} data-verification-status={inc.verification_status ?? ""} data-status={inc.status}>
            <h3 className="incident-title"><Icon name="shield" /> <Bi value={inc.title} /></h3>
            <p><Bi value={inc.summary} /></p>
            <p className="small muted">{fmtTime(inc.at, ctx.lang)}{inc.pattern_flag ? " · possible pattern" : ""}</p>
            {props.show_red_flags && inc.red_flags?.length ? (
              <p className="flags" data-test="red-flags">{k("red_flags", ctx.lang)}: {inc.red_flags.map((f) => FLAG_WORDS[f] ?? f).join(" · ")}</p>
            ) : null}
            {props.show_provenance && inc.provenance.length ? (
              <ul className="provenance" data-test="provenance">
                {inc.provenance.map((p) => (
                  <li key={p.label}>{p.label} <span className="mono small">{p.source.kind}:{p.source.ref}{p.source.secs != null ? ` @${mmss(Math.round(p.source.secs))}` : ""}</span></li>
                ))}
              </ul>
            ) : null}
            {props.allow_ack ? (
              inc.status === "open" ? (
                <button type="button" className="btn btn-primary" data-test="incident-ack" disabled={ctx.disabled} onClick={() => ctx.ack(inc.incident_id)}>{k("ack", ctx.lang)}</button>
              ) : (
                <p className="chip chip-ok" data-test="incident-acked">✓ {k("acked", ctx.lang)}</p>
              )
            ) : null}
          </article>
        );
      })}
    </Card>
  );
}

interface MyVerification { verification_id: string; claimed_member_id: string; claimed_name: string; status: string; state: string; deadline: string; say: { es: string; en: string } | null }

/** Elder "¿Es de verdad?": idle → choosing → checking (countdown) → denied / timeout / confirmed (gate say only). */
export function ScamCheck({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const [choosing, setChoosing] = useState(false);
  const v = ctx.data[props.bind] as MyVerification | null | undefined;
  const start = (arg: string) => {
    setChoosing(false);
    if (!ctx.disabled) ctx.send({ name: "start_verification", arg, element_id: id });
  };
  if (v && v.status === "pending") {
    return (
      <Card test="scam-check" tone="amber" extra={{ "data-state": "checking" }}>
        <p className="big-line" data-say="">{k("scam_checking", ctx.lang, { name: v.claimed_name })}</p>
        <Countdown deadline={v.deadline} />
      </Card>
    );
  }
  if (v && v.say) {
    const tone = v.status === "confirmed" ? "ok" : v.status === "denied" ? "tomato" : "amber";
    return (
      <Card test="scam-check" tone={tone} extra={{ "data-state": v.status }}>
        <p className="big-line" data-test="scam-say" data-say="">{text(v.say, ctx.lang)}</p>
      </Card>
    );
  }
  if (choosing) {
    return (
      <Card test="scam-check" title={k("scam_who", ctx.lang)} extra={{ "data-state": "choosing" }}>
        {(props.choices_member_ids as string[]).map((m) => (
          <button key={m} type="button" className="bigbutton tone-info" data-test="scam-choice" data-member={m} onClick={() => start(m)}>
            <Icon name="person" /><span className="bigbutton-label">{memberName(m, ctx.data)}</span>
          </button>
        ))}
        <button type="button" className="bigbutton tone-warn" data-test="scam-choice" data-member="other" onClick={() => start("other")}>
          <Icon name="help" /><span className="bigbutton-label">{props.other_label ?? k("other", ctx.lang)}</span>
        </button>
      </Card>
    );
  }
  return (
    <button type="button" className="bigbutton tone-warn" data-test="scam-check" data-state="idle" disabled={ctx.disabled} onClick={() => setChoosing(true)}>
      <Icon name="question" />
      <span className="bigbutton-label" data-say="">{props.label}</span>
    </button>
  );
}

interface BvProposal { proposal_id: string; title: unknown; changes: unknown[]; evidence_labels: string[]; status: string; release_id?: string }

export function Proposal({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const items = arr<BvProposal>(ctx.data[props.bind]);
  if (!items.length) return null;
  return (
    <Card test="proposals" title={props.title ? <Bi value={props.title} /> : undefined}>
      {items.map((p) => (
        <article key={p.proposal_id} className="proposal" data-test="proposal" data-status={p.status}>
          <h3><Bi value={p.title} /></h3>
          <ul>{p.changes.map((c, i) => <li key={i}><Bi value={c} /></li>)}</ul>
          {props.show_evidence ? <p className="small muted">{p.evidence_labels.join(" · ")}</p> : null}
          {props.show_release_status ? <p className="chip">{p.status}</p> : null}
          {props.allow_approve ? (
            <div className="row">
              <button type="button" className="btn btn-primary" data-test="proposal-approve" disabled={ctx.disabled || p.status === "verifying"} onClick={() => ctx.send({ name: "approve_proposal", arg: p.proposal_id, element_id: id })}>{k("approve", ctx.lang)}</button>
              <button type="button" className="btn btn-soft" data-test="proposal-reject" disabled={ctx.disabled} onClick={() => ctx.send({ name: "reject_proposal", arg: p.proposal_id, element_id: id })}>{k("not_now", ctx.lang)}</button>
            </div>
          ) : null}
        </article>
      ))}
    </Card>
  );
}
