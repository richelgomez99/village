import { useEffect, useState } from "react";
import { k } from "../i18n/strings";
import type { LiveState } from "../live/ws";
import type { PromptFrame } from "../live/messages";
import type { ResultInfo } from "../renderer/context";
import { text } from "../renderer/view";
import { mmss, secondsLeft, useNow } from "../util/time";
import { memberName } from "./shared";

export function villageName(id: string, lang: string): string {
  const base = id.replace(/^v_/, "");
  const name = base.charAt(0).toUpperCase() + base.slice(1);
  return lang === "es" ? `familia ${name}` : `${name} village`;
}

/** D21: who this app is for, always visible top-right. */
export function IdentityChip({ memberId, role, village, lang }: { memberId: string | null; role: string; village: string; lang: string }) {
  const family = !memberId || role === "guest" || role === "family";
  const label = family ? k("you_are_family", lang, { village: villageName(village, lang) }) : k("you_are", lang, { name: memberName(memberId), village: villageName(village, lang) });
  return (
    <div className="identity-chip" data-test="identity-chip" data-member={memberId ?? "family"} data-role={role}>
      <span aria-hidden="true" className="identity-dot" />
      {label}
    </div>
  );
}

export interface ViewAsOption { member_id: string; name: string }

/** D21 View-as switcher (coordinator / control). Viewing as someone disables their buttons. */
export function ViewAs({ options, current, self, onPick, lang }: { options: ViewAsOption[]; current: string | null; self: string | null; onPick: (m: string | null) => void; lang: string }) {
  return (
    <div className="view-as" data-test="view-as" role="group" aria-label={k("view_as", lang)}>
      <span className="view-as-label">{k("view_as", lang)}</span>
      {options.map((o) => {
        const active = (current ?? self) === o.member_id;
        return (
          <button key={o.member_id} type="button" className={`chip-btn${active ? " active" : ""}`} aria-pressed={active} data-test="view-as-option" data-member={o.member_id} onClick={() => onPick(o.member_id === self ? null : o.member_id)}>
            {o.name}
          </button>
        );
      })}
    </div>
  );
}

export function ViewingAsBanner({ name, onBack, lang }: { name: string; onBack: () => void; lang: string }) {
  return (
    <div className="viewing-as" data-test="viewing-as" role="status">
      <span>{k("viewing_as", lang, { name })}</span>
      <button type="button" className="btn btn-link" data-test="view-as-back" onClick={onBack}>{k("back_to_me", lang)}</button>
    </div>
  );
}

export function StatusStrip({ state, lang }: { state: LiveState; lang: string }) {
  const { status, attempt, closedReason } = state;
  let msg = "";
  if (status === "closed" && closedReason && closedReason !== "closed") msg = k("stopped", lang, { why: closedReason });
  else if (status === "reconnecting") msg = k("reconnecting", lang, { n: attempt });
  else if (status === "connecting" || status === "hello_sent" || status === "idle") msg = k("connecting", lang);
  return (
    <div className={`ws-status ${msg ? "show" : ""}`} data-test="ws-status" data-state={status} data-attempt={attempt} role="status" aria-live="polite">
      {msg}
    </div>
  );
}

/** WS `prompt` frame overlay: "Village is calling you · AI assistant". Shares the answer path with VerificationPrompt. */
export function PromptOverlay({ prompt, lang, nowMs, onAnswer, result, disabled }: {
  prompt: PromptFrame; lang: string; nowMs: () => number; onAnswer: (a: "yes" | "no" | "unsure") => void; result?: ResultInfo | "pending"; disabled?: boolean;
}) {
  const now = useNow(nowMs);
  const s = secondsLeft(prompt.deadline, now);
  const [buzzed, setBuzzed] = useState(false);
  useEffect(() => {
    if (buzzed) return;
    setBuzzed(true);
    try {
      navigator.vibrate?.([200, 100, 200]);
    } catch {
      /* ignore */
    }
  }, [buzzed]);
  const order: ("no" | "yes" | "unsure")[] = ["no", "yes", "unsure"];
  const opts = order.map((id) => prompt.options.find((o) => o.id === id)).filter(Boolean) as PromptFrame["options"];
  return (
    <div className="prompt-backdrop" data-test="prompt-overlay" data-verification-id={prompt.verification_id} role="dialog" aria-modal="true" aria-labelledby="prompt-q">
      <div className="prompt-card">
        <p className="prompt-banner" data-test="prompt-banner">{k("calling_you", lang)}</p>
        <h2 id="prompt-q" className="prompt-q">{text(prompt.question, lang)}</h2>
        <p className="prompt-detail">{text(prompt.detail, lang)}</p>
        <div className="countdown" role="timer" data-test="prompt-countdown" data-seconds={s}>
          <div className="countdown-num">{mmss(s)}</div>
          <p className="countdown-default">{k("then_default", lang)}</p>
        </div>
        {result === "pending" ? <p data-test="prompt-pending">{k("sending", lang)}</p> : null}
        <div className="verify-actions">
          {opts.map((o) => (
            <button key={o.id} type="button" disabled={disabled || result === "pending"} className={`btn ${o.id === "no" ? "btn-danger btn-xl" : o.id === "yes" ? "btn-soft" : "btn-link"}`} data-test={`prompt-${o.id}`} onClick={() => onAnswer(o.id)}>
              {text(o.label, lang)}
            </button>
          ))}
          {!opts.some((o) => o.id === "unsure") ? (
            <button type="button" className="btn btn-link" data-test="prompt-unsure" disabled={disabled || result === "pending"} onClick={() => onAnswer("unsure")}>{k("unsure", lang)}</button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
