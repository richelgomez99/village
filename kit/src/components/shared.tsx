import { useRef, useState, type ReactNode } from "react";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { captionFor } from "../i18n/captions";

const PATHS: Record<string, string> = {
  phone: "M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z",
  pill: "M4.2 12.5l8.3-8.3a5 5 0 0 1 7.1 7.1l-8.3 8.3a5 5 0 0 1-7.1-7.1zm1.4 1.4a3 3 0 0 0 4.2 4.2L12 16 8 12z",
  sos: "M12 2 1 21h22L12 2zm1 15h-2v-2h2v2zm0-4h-2V9h2v4z",
  check: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
  heart: "M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6C19 16.5 12 21 12 21z",
  home: "M12 3 2 12h3v8h5v-6h4v6h5v-8h3z",
  shield: "M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5z",
  help: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 17h-2v-2h2v2zm2-7.3-.9.9A3 3 0 0 0 13 15h-2v-.5a4 4 0 0 1 1.2-2.8l1.2-1.3A2 2 0 1 0 10 9H8a4 4 0 1 1 7 2.7z",
  speaker: "M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z",
  person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5z"
};

export function Icon({ name }: { name?: string }) {
  if (!name) return null;
  const d = PATHS[name] ?? PATHS[name === "question" ? "help" : "check"];
  return (
    <svg data-icon={name} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={d} />
    </svg>
  );
}

/** Localized text; on projector surfaces (ctx.captions) Spanish gets the English line under it (D18). */
export function Bi({ value, className, say = true }: { value: unknown; className?: string; say?: boolean }) {
  const ctx = useCtx();
  const primary = text(value, ctx.lang);
  let caption = "";
  if (ctx.captions && value && typeof value === "object") {
    const v = value as Record<string, string>;
    if (v.es && primary === v.es && v.en && v.en !== v.es) caption = v.en;
    else if (v.es && primary === v.es) caption = captionFor(v.es) ?? "";
  } else if (ctx.captions && typeof value === "string" && ctx.lang === "es") {
    caption = captionFor(value) ?? "";
  }
  return (
    <>
      <span className={className} data-say={say ? "" : undefined}>{primary}</span>
      {caption ? <span className="caption" data-test="caption" lang="en">{caption}</span> : null}
    </>
  );
}

export function ReadAloud({ target }: { target: React.RefObject<HTMLElement | null> }) {
  const { lang } = useCtx();
  const [speaking, setSpeaking] = useState(false);
  const onClick = () => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) return;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    const nodes = target.current ? Array.from(target.current.querySelectorAll("[data-say]")) : [];
    const words = nodes.map((n) => n.textContent?.trim()).filter(Boolean).join(". ");
    if (!words) return;
    synth.cancel();
    const Utter = (window as any).SpeechSynthesisUtterance;
    if (Utter) {
      const u = new Utter(words);
      u.lang = lang === "es" ? "es-US" : lang;
      u.onend = () => setSpeaking(false);
      synth.speak(u);
    } else {
      synth.speak(words as any);
    }
    setSpeaking(true);
  };
  return (
    <button type="button" className="read-aloud" data-test="read-aloud" data-speaking={speaking} aria-pressed={speaking} onClick={onClick}>
      <Icon name="speaker" />
      <span><Bi value={speaking ? k("stop_reading", lang) : k("read_aloud", lang)} say={false} /></span>
    </button>
  );
}

export function ConfirmSheet({ text: question, onYes, onNo }: { text: string; onYes: () => void; onNo: () => void }) {
  const { lang } = useCtx();
  return (
    <div className="sheet-backdrop" data-test="confirm-sheet" role="dialog" aria-modal="true" aria-label={question}>
      <div className="sheet">
        <p className="sheet-q"><Bi value={question} /></p>
        <button type="button" className="btn btn-danger" data-test="confirm-yes" onClick={onYes}>{k("confirm_yes", lang)}</button>
        <button type="button" className="btn btn-soft" data-test="confirm-no" onClick={onNo}>{k("confirm_no", lang)}</button>
      </div>
    </div>
  );
}

export function Card({ title, children, tone, test, extra }: { title?: ReactNode; children: ReactNode; tone?: string; test: string; extra?: Record<string, string | undefined> }) {
  return (
    <section className={`card${tone ? ` card-${tone}` : ""}`} data-test={test} {...extra}>
      {title ? <h2 className="card-title">{title}</h2> : null}
      {children}
    </section>
  );
}

export function useScreenRef() {
  return useRef<HTMLElement | null>(null);
}

export function memberName(id: string | null | undefined, data?: Record<string, unknown>): string {
  if (!id) return "";
  const person = data?.[`member:${id}`] as { name?: string } | undefined;
  if (person?.name) return person.name;
  const base = id.replace(/^[a-z]_/, "").split("_")[0];
  return base.charAt(0).toUpperCase() + base.slice(1);
}
