// Proposal (INTERACTIONS §3 "Options", design/Options.dc.html): four labelled blocks in plain words —
// What happened · What changes · What stays the same · Village checked — then Approve · Not now (· Ask <name> first).
// Verifying → the release stepper in words; applied → "Done · every phone updated" for 10 s with Undo.
// Defensive about content: works with bv_proposal (title/changes/evidence_labels) and the richer shape
// (rationale, stays_the_same, checked, allow_ask_other) the evolve lane is moving to. Never shows ids.
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { text } from "../renderer/view";

export interface ProposalLike {
  proposal_id?: string;
  id?: string;
  title?: unknown;
  rationale?: unknown;
  changes?: unknown[];
  stays_the_same?: unknown[] | unknown;
  checked?: unknown;
  evidence_labels?: string[];
  evidence?: { label?: string }[];
  status?: string;
  allow_ask_other?: boolean | string;
  ask_other?: string;
  ask_other_name?: string;
  release_stage?: string;
}

const STAYS = /^\s*[+=•·-]?\s*(nothing|her rules|his rules|their rules|can turn|she can turn|he can turn|they can turn|no change)/i;
const ID_LIKE = /=|trace|\b(src|ev|dc|ver|inc|conv|rel|prop|m|b)_[a-z0-9_]+\b/i;

const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : v == null || v === "" ? [] : [v]);
const clean = (s: string) => s.replace(/^\s*[+=•·]\s*/, "").trim();

export function proposalBlocks(p: ProposalLike, lang: string) {
  const lines = list(p.changes).map((c) => clean(text(c, lang))).filter(Boolean);
  const stays = [...list(p.stays_the_same).map((c) => clean(text(c, lang))), ...lines.filter((l) => STAYS.test(l))].filter(Boolean);
  const changes = lines.filter((l) => !STAYS.test(l));
  const checkedRaw = list(p.checked).map((c) => text(c, lang));
  const evidence = [...(p.evidence_labels ?? []), ...(p.evidence ?? []).map((e) => e?.label ?? "")];
  const checked = (checkedRaw.length ? checkedRaw : evidence).map((s) => String(s).trim()).filter((s) => s && !ID_LIKE.test(s)).slice(0, 2);
  const happened = text(p.rationale, lang).trim();
  return { happened, changes, stays: [...new Set(stays)], checked };
}

/** Bold every known person's name in a line ("**Ana** sees the screened calls"). */
function withNames(line: string, names: string[]): ReactNode {
  const ns = names.filter((n) => n && n.length > 1).sort((a, b) => b.length - a.length);
  if (!ns.length) return line;
  const re = new RegExp(`(${ns.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return line.split(re).map((part, i) => (ns.includes(part) ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>));
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" className="cal-icon">
      <path d="M7 2v2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2zm12 8v9H5v-9z" fill="currentColor" />
    </svg>
  );
}

export function ProposalBlocks({ p, lang, names }: { p: ProposalLike; lang: string; names: string[] }) {
  const b = proposalBlocks(p, lang);
  return (
    <div className="proposal-blocks">
      {b.happened ? (
        <section className="pb" data-test="pb-happened">
          <h4>What happened</h4>
          <p>{withNames(b.happened, names)}</p>
        </section>
      ) : null}
      {b.changes.length ? (
        <section className="pb" data-test="pb-changes">
          <h4>What changes</h4>
          <ul>{b.changes.map((l, i) => <li key={i}>{withNames(l, names)}</li>)}</ul>
        </section>
      ) : null}
      {b.stays.length ? (
        <section className="pb" data-test="pb-stays">
          <h4>What stays the same</h4>
          <ul>{b.stays.map((l, i) => <li key={i}>{withNames(l, names)}</li>)}</ul>
        </section>
      ) : null}
      {b.checked.length ? (
        <section className="pb" data-test="pb-checked">
          <h4>Village checked</h4>
          <ul className="pb-checked">{b.checked.map((l, i) => <li key={i}><CalendarIcon /> {l}</li>)}</ul>
        </section>
      ) : null}
    </div>
  );
}

export const RELEASE_STEPS: [string, string][] = [
  ["spec", "Checking the change…"],
  ["daytona_build", "Building…"],
  ["tests", "Testing…"],
  ["anchor_qa", "Trying it on a phone…"],
  ["arize_evals", "Scoring…"],
  ["live", "Publishing"]
];

/** Verifying: the six release steps in words; the current one is marked (first one when the stage isn't known). */
export function ReleaseStepper({ stage }: { stage?: string }) {
  const at = Math.max(0, RELEASE_STEPS.findIndex(([s]) => s === stage));
  return (
    <ol className="release-stepper" data-test="release-stepper" data-stage={RELEASE_STEPS[at][0]}>
      {RELEASE_STEPS.map(([s, words], i) => (
        <li key={s} className={i < at ? "done" : i === at ? "active" : "todo"} data-step={s}>{i < at ? `✓ ${words.replace("…", "")}` : words}</li>
      ))}
    </ol>
  );
}

/** Remembers proposals it has seen; when one is applied (or leaves the pending list after verifying) it shows
 *  "Done · every phone updated" for 10 s with Undo. */
export function useAppliedBanner(items: ProposalLike[], undoMs = 10_000) {
  const seen = useRef(new Map<string, string>());
  const [done, setDone] = useState<{ id: string; title: unknown; until: number } | null>(null);
  useEffect(() => {
    const now = Date.now();
    const ids = new Set(items.map((p) => p.proposal_id ?? p.id ?? ""));
    for (const p of items) {
      const id = p.proposal_id ?? p.id ?? "";
      if (p.status === "applied" && seen.current.get(id) !== "applied") setDone({ id, title: p.title, until: now + undoMs });
      seen.current.set(id, p.status ?? "");
    }
    for (const [id, st] of seen.current) {
      if (!ids.has(id) && (st === "verifying" || st === "ready" || st === "approved")) {
        setDone({ id, title: null, until: now + undoMs });
        seen.current.set(id, "applied");
      }
    }
  }, [items, undoMs]);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(null), Math.max(0, done.until - Date.now()));
    return () => clearTimeout(t);
  }, [done]);
  return [done, () => setDone(null)] as const;
}
