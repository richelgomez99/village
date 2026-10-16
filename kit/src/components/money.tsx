import { useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { fmtTime, mmss } from "../util/time";
import { Countdown } from "./care";
import { ProposalBlocks, ReleaseStepper, useAppliedBanner, type ProposalLike } from "./proposal";
import { undoProposal } from "../control/api";
import { Bi, Card, Icon, RAW_REF, memberName, sourceWords } from "./shared";
import { canDecide } from "./generic";
import { incidentNeedsHuman, pendingVerificationIds } from "../util/resolved";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

interface Pending { verification_id: string; question: unknown; detail: unknown; deadline: string; subject: string }

export function useAnswer(elementId: string) {
  const ctx = useCtx();
  return (verification_id: string, answer: "yes" | "no" | "unsure") => {
    if (ctx.disabled) return;
    ctx.send({ name: "answer_verification", element_id: elementId, payload: { verification_id, answer } });
  };
}

/** The verifier's in-app verification (binding-driven). Thanks state shows the gate's `say` from the action result. */
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
  const all = arr<Incident>(ctx.data[props.bind]);
  // Home shows what still needs someone; the area tab keeps the history (acknowledged ones too)
  // Home's group lists only what still needs a human; resolved ones (scam stopped, refused by rule) live in What Village did
  const pending = pendingVerificationIds(ctx.data);
  const items = (ctx.openOnly ? all.filter((i) => incidentNeedsHuman(i, pending)) : all).slice(0, props.limit ?? 5);
  return (
    <Card test="incident-cards" title={props.title && !ctx.inGroup ? <Bi value={props.title} /> : undefined}>
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
                  <li key={p.label}>{RAW_REF.test(p.label) ? null : <>{p.label} · </>}<span className="small">{sourceWords(p.source, inc.at, ctx.data, props.subject, ctx.lang)}</span></li>
                ))}
              </ul>
            ) : null}
            {props.allow_ack ? (
              incidentNeedsHuman(inc, pending) ? (
                <button type="button" className="btn btn-primary" data-test="incident-ack" disabled={ctx.disabled} onClick={() => ctx.ack(inc.incident_id)}>{k("ack", ctx.lang)}</button>
              ) : inc.status !== "open" ? (
                <p className="chip chip-ok" data-test="incident-acked">✓ {k("acked", ctx.lang)}</p>
              ) : null
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

/** "Village proposes a change · needs your yes": the four plain-word blocks, then Approve · Not now (· Ask <name> first);
 *  verifying → release stepper in words; applied → "Done · every phone updated" for 10 s with Undo. */
export function Proposal({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const items = arr<ProposalLike>(ctx.data[props.bind]);
  const [done, clearDone] = useAppliedBanner(items);
  const names = Object.entries(ctx.data).filter(([key]) => key.startsWith("member:")).map(([, v]) => String((v as { name?: string } | null)?.name ?? "")).filter(Boolean);
  const open = items.filter((p) => p.status !== "applied" && p.status !== "rejected" && p.status !== "failed");
  // D39: a member who doesn't decide sees the proposal as Village's chat post with its status line, not as an approval form
  if (!canDecide(ctx, open[0] as never)) return null;
  if (!open.length && !done) return null;
  const undo = async (pid: string) => {
    clearDone();
    if (ctx.api && !ctx.disabled) await undoProposal(ctx.api, ctx.village, pid).catch(() => undefined);
  };
  return (
    <Card test="proposals" title={props.title ? <Bi value={props.title} /> : k("proposal_title", ctx.lang)}>
      {done ? (
        <div className="proposal-done" data-test="proposal-done" role="status">
          <span>{k("proposal_done", ctx.lang)}</span>
          {ctx.api ? <button type="button" className="btn btn-soft" data-test="proposal-undo" disabled={ctx.disabled} onClick={() => undo(done.id)}>{k("undo", ctx.lang)}</button> : null}
        </div>
      ) : null}
      {open.map((p) => {
        const pid = p.proposal_id ?? p.id ?? "";
        const ask = p.allow_ask_other ? (typeof p.allow_ask_other === "string" ? p.allow_ask_other : p.ask_other_name ?? memberName(p.ask_other, ctx.data)) : "";
        return (
          <article key={pid} className="proposal" data-test="proposal" data-status={p.status}>
            {p.title ? <h3><Bi value={p.title} /></h3> : null}
            <ProposalBlocks p={p} lang={ctx.lang} names={names} />
            {p.status === "verifying" ? (
              <ReleaseStepper stage={p.release_stage} />
            ) : props.allow_approve && canDecide(ctx, p as never) ? (
              <div className="row proposal-actions">
                <button type="button" className="btn btn-primary" data-test="proposal-approve" disabled={ctx.disabled} onClick={() => ctx.send({ name: "approve_proposal", arg: pid, element_id: id })}>{k("approve", ctx.lang)}</button>
                <button type="button" className="btn btn-soft" data-test="proposal-reject" disabled={ctx.disabled} onClick={() => ctx.send({ name: "reject_proposal", arg: pid, element_id: id })}>{k("not_now", ctx.lang)}</button>
                {ask ? (
                  <button type="button" className="btn btn-link" data-test="proposal-ask-other" disabled={ctx.disabled} onClick={() => ctx.send({ name: "ask_proposal_other", arg: pid, element_id: id, payload: p.ask_other ? { member_id: p.ask_other } : undefined })}>
                    {k("ask_first", ctx.lang, { name: ask })}
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>
        );
      })}
    </Card>
  );
}
