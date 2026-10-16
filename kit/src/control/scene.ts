// Control Room scene reducer (T020). Pure: (scene, server frame) → scene. Every region reads from this.
// Inputs are contract 1.3.3 frames (ws_messages.schema.json control{kind}, event, snapshot), incl. caption + ledger
// and `mode` on reasoning/ledger rows. One scene per village: frames that name another village are ignored.
// Unknown kinds are ignored.
import type { ServerFrame } from "../live/messages";
import { applyViewPatch } from "../renderer/view";

/** A founding is in progress: no spec yet, or a blueprint stream that hasn't reached `done`. */
export function foundingNow(s: { spec: any; blueprint: { stages: object; done: boolean } }): boolean {
  return !s.spec || (Object.keys(s.blueprint.stages).length > 0 && !s.blueprint.done);
}

/** Starting point for a role's draft phone before its first patch. */
export function emptyDraft(role: string): any {
  return { lang: "en", theme: role === "elder" ? "elder" : "family", root: "s", elements: { s: { type: "Screen", props: { title: " " }, children: [] } } };
}

export type Mode = "acted_alone" | "asked_human" | "refused";
export type AgentRole = "Founder" | "Watcher" | "Verifier" | "Builder" | "Explainer";
export type LedgerStatus = "queued" | "running" | "done" | "retrying" | "fallback" | "refused";
export type BlueprintStage = "people" | "needs" | "life_areas" | "rules" | "kind" | "questions" | "done";

export interface LedgerRow { id: string; at: string; status: LedgerStatus; what: string; result?: string; role: AgentRole; attempt?: number; rule_id?: string; mode?: Mode; elapsed_ms?: number; ended?: string }
export interface GateRow { id: string; at: string; rule_id: string; decision: string; say: { es?: string; en?: string } | null; mode: Mode; input_kind: string; verification_state?: string; sentence: string; trace_id?: string }
export type Beat = "build" | "run" | "rebuild";
export interface RoundRow { id: string; at: string; text: string; mode: Mode; role: AgentRole; rule_id?: string }
export interface ChatLine { id: string; at: string; kind: string; author: string; text: string; title?: string }
export interface DecisionRow { id: string; at: string; text: string; role: AgentRole; mode: Mode; source: string; trace_id?: string }
export interface CaptionLine { id: string; at: string; es: string; en: string; speaker?: string }
export interface TranscriptLine { id: string; at: string; who: "ana" | "village" | string; text: string }
export interface WillBuild { person: string; component: string; reason: string; role?: string }
/** D33: one block per founder answer — Heard → Knows → Doing (ledger ids) → Will build. */
export interface AnswerBlock { id: string; at: string; heard: string; knows: string | null; doing: string[]; willBuild: WillBuild[] }
export interface LiveMoment {
  verification_id: string | null;
  quote: string | null;
  claimed: string | null;
  amount: number | null;
  deadline: string | null;
  started: string;
  state: "pending" | "denied" | "confirmed" | "timeout" | "default_spoken";
  /** who the call is with (money_request.subject) */
  subject: string | null;
  say: { es?: string; en?: string } | null;
  channels: string[];
}

export interface SceneState {
  village: string;
  spec: any | null;
  data: Record<string, unknown>;
  rev: number;
  blueprint: { stages: Partial<Record<BlueprintStage, any[]>>; done: boolean };
  ledger: LedgerRow[];
  gate: GateRow[];
  decisions: DecisionRow[];
  autonomy: Record<Mode, number>;
  live: LiveMoment | null;
  counters: Record<string, { value: number; of?: number; label: string }>;
  phones: number | null;
  clock: { now: string; offset_minutes: number } | null;
  captions: CaptionLine[];
  release: any | null;
  buildLog: { at: string; stage: string; line: string; level: string }[];
  proposal: any | null;
  /** village.name (spec) or snapshot.identity.village_name — names exist before the spec does during founding */
  villageName: string | null;
  /** founding intake (docs/FOUNDING-INTAKE.md): transcript, coverage meter, gap list */
  transcript: TranscriptLine[];
  /** the arc beat the last cause belongs to (Build → Run → Rebuild); "Anyone" is the village switch, decided by the room */
  beat: Beat | null;
  /** Watcher rounds (rounds:latest / control{counter rounds_*} / reasoning "[rounds · mode] …") */
  rounds: { counts: Record<Mode, number> | null; rows: RoundRow[] };
  chat: ChatLine[];
  /** verification id → when Village started checking (for "said no in 12 s") */
  verifyStart: Record<string, string>;
  blocks: AnswerBlock[];
  /** founding: per-role draft views built from control `patch` frames (phones gain cards as capabilities are decided) */
  drafts: Record<string, any>;
  draftNew: Record<string, string[]>;
  coverage: { value: number; of: number } | null;
  gaps: string[];
  frames: number;
}

export function initialScene(village = ""): SceneState {
  return {
    village, spec: null, data: {}, rev: 0, blueprint: { stages: {}, done: false }, ledger: [], gate: [], decisions: [],
    autonomy: { acted_alone: 0, asked_human: 0, refused: 0 }, live: null, counters: {}, phones: null, clock: null, captions: [],
    release: null, buildLog: [], proposal: null, villageName: null, transcript: [], beat: null, rounds: { counts: null, rows: [] }, chat: [], verifyStart: {}, blocks: [], drafts: {}, draftNew: {}, coverage: null, gaps: [], frames: 0
  };
}

const REFUSED = new Set(["deny", "refuse_medical_advice", "advise_do_not_send", "report_already_logged"]);
const ASKED = new Set(["verify_with_member", "escalate_family", "require_approval", "advise_talk_to_coordinator", "verify_with_source"]);

/** D23 autonomy mode of a gate decision. */
export function gateMode(decision: string): Mode {
  if (REFUSED.has(decision)) return "refused";
  if (ASKED.has(decision)) return "asked_human";
  return "acted_alone";
}

/** D23 mode of a reasoning row: payload.mode when Core sends it (proposed), else from the words. */
export function textMode(text: string, explicit?: unknown): Mode {
  if (explicit === "acted_alone" || explicit === "asked_human" || explicit === "refused") return explicit;
  const t = text.toLowerCase();
  if (/\b(refus|blocked|never|won't|don't send|denied)/.test(t)) return "refused";
  if (/\b(ask(ed)?|check with|verify|confirm with|calling|approval|approve)/.test(t)) return "asked_human";
  return "acted_alone";
}

/** D23 on-screen role names for contract reasoning sources. */
export function roleFor(source: string, founding = false): AgentRole {
  switch (source) {
    case "builder":
      return founding ? "Founder" : "Builder";
    case "release":
      return "Builder";
    case "evolve":
    case "memory":
      return "Watcher";
    case "gate":
    case "voice":
      return "Verifier";
    case "explainer":
      return "Explainer";
    case "founder":
      return "Founder";
    case "watcher":
      return "Watcher";
    case "verifier":
      return "Verifier";
    default:
      return "Watcher";
  }
}

const STAGE_STATUS: Record<string, LedgerStatus> = { pending: "queued", running: "running", passed: "done", skipped: "done", failed: "refused" };
const STAGE_WORDS: Record<string, string> = {
  spec: "Spec checked against the contract", daytona_build: "Built in a Daytona sandbox", tests: "Floor and policy tests",
  anchor_qa: "Anchor tapped through the phones", arize_evals: "Arize evals", live: "Live on every phone"
};

function upsertLedger(rows: LedgerRow[], row: LedgerRow): LedgerRow[] {
  const i = rows.findIndex((r) => r.id === row.id);
  if (i < 0) return [...rows, row];
  const next = rows.slice();
  // rows never vanish; running becomes result in place
  const finished = row.status !== "running" && row.status !== "queued" && (rows[i].status === "running" || rows[i].status === "queued");
  next[i] = { ...rows[i], ...row, at: rows[i].at, ended: finished ? row.at : rows[i].ended };
  return next;
}

/** Display name from the member record: display_name, else the full name with the family surname dropped
 *  ("Ana Diaz" in "Familia Diaz" → "Ana"); households and titles stay whole ("Mrs. Ruth Ng"). Never split on spaces. */
export function displayName(p: any, spec?: any): string {
  if (!p) return "";
  if (p.display_name) return String(p.display_name);
  const full = String(p.name ?? p.id ?? "");
  const vname = String(spec?.village?.name ?? "");
  const m = vname.match(/^(?:familia|family)\s+(\S+)$/i) ?? vname.match(/^(?:the\s+)?(\S+)\s+family$/i);
  const fam = m ? m[1] : "";
  if (fam && full.endsWith(` ${fam}`) && !/^(mr|mrs|ms|dr|the)\b/i.test(full)) return full.slice(0, -fam.length - 1);
  return full;
}

/** Spec, or a stand-in carrying the village name while the spec doesn't exist yet (founding). */
export function nameCtx(s: { spec: any; villageName: string | null }): any {
  return s.spec ?? { village: { name: s.villageName ?? "" } };
}

/** Proper-cased member name from the record (spec people, then data member:<id>), else from the id. */
export function memberDisplay(id: string | undefined | null, spec: any, data?: Record<string, unknown>): string {
  if (!id) return "";
  const p = spec?.blueprint?.people?.find((x: any) => x.id === id);
  if (p) return displayName(p, spec);
  const m = data?.[`member:${id}`] as { name?: string } | undefined;
  if (m?.name) return m.name;
  return id.replace(/^[a-z]_/, "").split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

const name = (id: string | undefined | null, spec: any, data?: Record<string, unknown>) => memberDisplay(id, spec, data);

function stageWords(stage: string, items: any[], spec: any): string {
  const n = items.length;
  switch (stage) {
    case "people":
      return `Found ${n} ${n === 1 ? "person" : "people"}: ${items.map((p) => displayName(p, spec)).filter(Boolean).join(", ")}`;
    case "needs":
      return `${n} ${n === 1 ? "need" : "needs"} heard in the description`;
    case "life_areas":
      return `${n} life ${n === 1 ? "area" : "areas"}: ${items.map((a) => a.label ?? a.id).join(" · ")}`;
    case "rules":
      return `${n} safety ${n === 1 ? "rule" : "rules"} switched on`;
    case "kind":
      return `Group type: ${items.map((k) => k.kind ?? k).join(", ")}`;
    case "questions":
      return `Asked ${n} follow-up ${n === 1 ? "question" : "questions"}${items[0]?.question ? `: “${items[0].question}”` : ""}`;
    case "done":
      return `Draft ready${items[0]?.rev ? ` · rev ${items[0].rev}` : ""}${spec?.views ? ` · ${Object.keys(spec.views).length} apps` : ""}`;
    default:
      return stage;
  }
}

const ACTOR_ROLE: Record<string, AgentRole> = { evolve: "Watcher", watcher: "Watcher", gate: "Verifier", voice: "Verifier", "voice:setup": "Founder", builder: "Builder", release: "Builder", founder: "Founder", explainer: "Explainer" };

export function sceneReducer(s: SceneState, f: ServerFrame | { type: "reset"; village?: string } | { type: "decisions"; rows: any[] }): SceneState {
  if (f.type === "reset") return initialScene(f.village ?? s.village);
  if (f.type === "decisions") {
    // GET /villages/{id}/decisions backfill: oldest last, never duplicating live rows
    const known = new Set(s.decisions.map((d) => d.id));
    const rows: DecisionRow[] = f.rows
      .filter((r) => r && r.text && r.kind !== "plan" && !known.has(String(r.id)))
      .map((r) => {
        const text = String(r.text).replace(ROUND_PREFIX, "");
        return { id: String(r.id), at: String(r.at ?? ""), text, role: ACTOR_ROLE[String(r.actor)] ?? "Watcher", mode: textMode(text, r.mode), source: String(r.actor ?? ""), trace_id: r.trace_id };
      })
      .sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
    const autonomy = rows.reduce((c, r) => ({ ...c, [r.mode]: c[r.mode] + 1 }), s.autonomy);
    return { ...s, autonomy, decisions: [...s.decisions, ...rows].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 100) };
  }
  const frames = s.frames + 1;
  const fv = frameVillage(f);
  if (s.village && fv && fv !== s.village) return s;
  switch (f.type) {
    case "snapshot": {
      if (f.role !== "control") return { ...s, frames };
      const villageName = (f.spec as any)?.village?.name ?? (f as any).identity?.village_name ?? s.villageName;
      const next = { ...s, frames, spec: f.spec ?? null, data: { ...f.data }, rev: f.rev, villageName };
      return withRoundsAndChat(next, f.data);
    }
    case "patch": {
      // control socket during founding: a role's draft view gains cards as each capability is decided
      if (!foundingNow(s)) return { ...s, frames, rev: f.rev };
      const role = (f as any).role as string | undefined;
      if (!role) return { ...s, frames };
      try {
        const base = s.drafts[role] ?? emptyDraft(role);
        const next = applyViewPatch(base, f.ops as any);
        return { ...s, frames, drafts: { ...s.drafts, [role]: next }, draftNew: { ...s.draftNew, [role]: (f as any).highlight ?? [] } };
      } catch {
        return { ...s, frames };
      }
    }
    case "event": {
      const e = eventStep({ ...s, frames, data: { ...s.data, ...(f.data ?? {}) } }, f.event as any);
      const runKinds = ["money_request", "verification_pending", "verification_denied", "verification_confirmed", "verification_timeout", "incident"];
      return withRoundsAndChat(runKinds.includes((f.event as any).kind) ? { ...e, beat: "run" } : e, f.data ?? {});
    }
    case "chat": {
      const m = (f as any).message ?? {};
      if (!m.id || s.chat.some((c) => c.id === m.id)) return { ...s, frames };
      return { ...s, frames, chat: [...s.chat, chatLine(m)].slice(-30) };
    }
    case "control":
      return controlStep({ ...s, frames }, f.kind, f.payload as any, f.at);
    default:
      return { ...s, frames };
  }
}

function chatLine(m: any): ChatLine {
  return { id: String(m.id), at: String(m.at ?? ""), kind: String(m.kind ?? "member"), author: String(m.author ?? "village"), text: String(m.text_i18n?.en ?? m.text ?? ""), title: m.title ? String(m.title?.en ?? m.title) : undefined };
}

const ROUND_PREFIX = /^\[rounds · (acted_alone|asked_human|refused)\]\s*/;

/** rounds:latest (Watcher round result) and chat:village from snapshot/event data. */
function withRoundsAndChat(s: SceneState, data: Record<string, unknown>): SceneState {
  let next = s;
  const r = data["rounds:latest"] as { counts?: Record<Mode, number>; rows?: any[] } | null | undefined;
  if (r && typeof r === "object") {
    const rows: RoundRow[] = (r.rows ?? []).map((x: any, i: number) => ({ id: String(x.id ?? x.decision_id ?? `rr_${i}`), at: String(x.at ?? ""), text: String(x.text ?? "").replace(ROUND_PREFIX, ""), mode: (x.mode ?? "acted_alone") as Mode, role: ACTOR_ROLE[String(x.role ?? x.actor ?? "watcher").toLowerCase()] ?? "Watcher", rule_id: x.rule_id }));
    next = { ...next, rounds: { counts: r.counts ?? next.rounds.counts, rows: rows.length ? rows : next.rounds.rows } };
  }
  const chat = data["chat:village"];
  if (Array.isArray(chat)) {
    const known = new Set(next.chat.map((c) => c.id));
    const add = chat.filter((m: any) => m?.id && !known.has(m.id)).map(chatLine);
    if (add.length) next = { ...next, chat: [...next.chat, ...add].slice(-30) };
  }
  return next;
}

const DECISION_WORDS: Record<string, string> = {
  record: "recorded it",
  remind: "sent a reminder",
  report_already_logged: "dose already recorded · told the on-duty person",
  refuse_medical_advice: "didn't give medical advice · pointed to her doctor",
  escalate_family: "called the family",
  advise_911: "told her to call 911 first",
  verify_with_member: "asked {who}",
  advise_do_not_send: "told her not to send money",
  advise_talk_to_coordinator: "told her to talk to the family first",
  mark_unverified: "marked it as not confirmed",
  verify_with_source: "checked an official source",
  require_approval: "asked for a yes first",
  allow: "let it through",
  deny: "refused"
};

/** A gate decision as a sentence with actor + result ("Verifier · asked Ana · said no in 12 s · told her not to send money"). */
export function gateSentence(d: any, who: string, startedAt: string | undefined, at: string): string {
  const action = (DECISION_WORDS[d.decision] ?? String(d.decision ?? "").replace(/_/g, " ")).replace("{who}", who || "the family");
  const st = d.verification?.state;
  const secs = startedAt ? Math.max(0, Math.round((Date.parse(at) - Date.parse(startedAt)) / 1000)) : null;
  const took = secs != null ? ` in ${secs} s` : "";
  if (st === "denied") return `Verifier · asked ${who} · said no${took} · ${action}`;
  if (st === "confirmed") return `Verifier · asked ${who} · said it was them${took} · Village never sends money`;
  if (st === "default_spoken") return `Verifier · asked ${who} · no answer${took} · ${action}`;
  if (st === "timed_out") return `Verifier · asked ${who} · the window closed${took}`;
  if (st === "pending") return `Verifier · ${action} · waiting for an answer`;
  return `Verifier · ${action}`;
}

/** The village a frame names, if any (snapshot.village, event.village, control payload.village / receipt / proposal). */
export function frameVillage(f: any): string | null {
  if (f.type === "snapshot") return f.village ?? null;
  if (f.type === "event") return f.event?.village ?? null;
  if (f.type === "chat") return f.village ?? f.message?.village ?? null;
  if (f.type === "control") {
    const p = f.payload ?? {};
    return p.village ?? p.receipt?.village ?? p.proposal?.village ?? null;
  }
  return null;
}

function eventStep(s: SceneState, ev: { id: string; kind: string; at: string; payload?: any; source?: any }): SceneState {
  const p = ev.payload ?? {};
  switch (ev.kind) {
    case "money_request":
      return {
        ...s,
        live: {
          verification_id: p.verification_id ?? s.live?.verification_id ?? null,
          quote: p.utterance ?? ev.source?.quote ?? null,
          claimed: p.claimed_member_id ?? null,
          subject: p.subject ?? s.live?.subject ?? null,
          amount: typeof p.amount === "number" ? p.amount : null,
          deadline: s.live?.deadline ?? null,
          started: ev.at,
          state: "pending",
          say: s.live?.say ?? null,
          channels: s.live?.channels ?? []
        }
      };
    case "verification_pending":
      return { ...s, live: s.live ? { ...s.live, deadline: p.deadline ?? s.live.deadline, channels: p.channels ?? s.live.channels } : s.live };
    case "verification_denied":
      return { ...s, live: s.live ? { ...s.live, state: "denied" } : s.live };
    case "verification_confirmed":
      return { ...s, live: s.live ? { ...s.live, state: "confirmed" } : s.live };
    case "verification_timeout":
      return { ...s, live: s.live ? { ...s.live, state: s.live.state === "pending" ? "timeout" : s.live.state } : s.live };
    default:
      return s;
  }
}

function controlStep(s0: SceneState, kind: string, p: any, at: string): SceneState {
  const s = controlStepInner(s0, kind, p, at);
  if (s === s0) return s;
  let beat = s.beat;
  if (kind === "blueprint" || (kind === "ledger" && String(p?.role ?? "founder").toLowerCase() === "founder" && foundingNow(s0))) beat = "build";
  else if (kind === "caption" && foundingNow(s0)) beat = "build";
  else if (kind === "caption" || kind === "gate") beat = "run";
  else if (kind === "proposal" || kind === "release" || kind === "qa" || kind === "build_log") beat = "rebuild";
  return beat === s.beat ? s : { ...s, beat };
}

function controlStepInner(s: SceneState, kind: string, p: any, at: string): SceneState {
  switch (kind) {
    case "gate": {
      const d = p?.decision;
      if (!d) return s;
      const explicit = d.mode ?? p.mode;
      const mode: Mode = explicit === "acted_alone" || explicit === "asked_human" || explicit === "refused" ? explicit : gateMode(d.decision);
      const say = d.say && (d.say.es || d.say.en) ? d.say : null;
      const vid = d.verification?.id as string | undefined;
      const verifyStart = vid && d.verification?.state === "pending" && !s.verifyStart[vid] ? { ...s.verifyStart, [vid]: at } : s.verifyStart;
      const sentence = gateSentence(d, name(d.verification?.claimed_member, s.spec, s.data), vid ? verifyStart[vid] : undefined, at);
      const row: GateRow = { id: d.id, at, rule_id: d.rule_id, decision: d.decision, say, mode, input_kind: p.input_kind ?? "", verification_state: d.verification?.state, sentence, trace_id: p.trace_id };
      const known = s.gate.some((g) => g.id === d.id);
      const gate = known ? s.gate.map((g) => (g.id === d.id ? row : g)) : [row, ...s.gate];
      // a timer tick that only closes the window (allow + empty say) is not an autonomy decision
      const counts = !known && !(d.decision === "allow" && !say) ? { ...s.autonomy, [mode]: s.autonomy[mode] + 1 } : s.autonomy;
      let ledger = s.ledger;
      let live = s.live;
      const v = d.verification;
      if (v) {
        const who = name(v.claimed_member, s.spec, s.data);
        const subject: string | null = (d.writes ?? []).map((w: any) => w?.payload?.subject).find(Boolean) ?? s.live?.subject ?? null;
        const subjName = name(subject, s.spec, s.data);
        const notified = (d.notify ?? []).map((n: any) => name(n.member_id, s.spec, s.data)).filter(Boolean).join(", ");
        const ch = (v.channels ?? []).map((c: string) => (c === "app_prompt" ? "app" : c === "outbound_call" ? "call" : c)).join(" + ");
        const id = `ver:${v.id}`;
        if (v.state === "pending") {
          ledger = upsertLedger(ledger, { id, at, status: "running", what: `Checking with ${who}${ch ? ` (${ch})` : ""}`, role: "Verifier", rule_id: d.rule_id });
        } else if (v.state === "denied") {
          ledger = upsertLedger(ledger, { id, at, status: "done", what: `Checked with ${who}`, result: `${who}: “that wasn't me” · ${subjName || "she"} told not to send`, role: "Verifier", rule_id: d.rule_id });
        } else if (v.state === "confirmed") {
          ledger = upsertLedger(ledger, { id, at, status: "done", what: `Checked with ${who}`, result: `${who} says it was him · Village never sends money`, role: "Verifier", rule_id: d.rule_id });
        } else if (v.state === "default_spoken" || v.state === "timed_out") {
          ledger = upsertLedger(ledger, { id, at, status: "fallback", what: `No answer from ${who}`, result: `Safe default: told ${subjName || "her"} “don't send”${notified ? `, ${notified} notified` : ""}`, role: "Verifier", rule_id: d.rule_id });
        }
        if (v.state === "pending") {
          live = {
            verification_id: v.id, quote: s.live?.quote ?? null, claimed: v.claimed_member, subject, amount: s.live?.amount ?? null, deadline: v.deadline,
            started: s.live?.started ?? at, state: "pending", say, channels: v.channels ?? []
          };
        } else if (live) {
          const st = v.state === "denied" ? "denied" : v.state === "confirmed" ? "confirmed" : v.state === "default_spoken" ? "default_spoken" : live.state === "pending" ? "timeout" : live.state;
          live = { ...live, state: st, say: say ?? live.say };
        }
      } else if (REFUSED.has(d.decision)) {
        ledger = upsertLedger(ledger, { id: `gate:${d.id}`, at, status: "refused", what: say?.en ?? d.decision.replace(/_/g, " "), result: `blocked by ${d.rule_id}`, role: "Verifier", rule_id: d.rule_id });
      }
      return { ...s, gate: gate.slice(0, 100), autonomy: counts, ledger, live, verifyStart, beat: "run" };
    }
    case "reasoning": {
      const text = String(p?.text ?? "");
      if (!text) return s;
      const founding = !s.spec || (!s.blueprint.done && Object.keys(s.blueprint.stages).length > 0);
      const role = roleFor(String(p.source ?? ""), founding);
      if (p.kind === "decision") {
        const rm = text.match(ROUND_PREFIX);
        const clean = text.replace(ROUND_PREFIX, "");
        const mode = rm ? (rm[1] as Mode) : textMode(clean, p.mode);
        const row: DecisionRow = { id: `dr_${s.frames}`, at, text: clean, role: rm ? "Watcher" : role, mode, source: String(p.source ?? ""), trace_id: p.trace_id };
        if (rm) {
          const rr: RoundRow = { id: `rr_${s.frames}`, at, text: clean, mode, role: "Watcher" };
          return { ...s, decisions: [row, ...s.decisions].slice(0, 100), autonomy: { ...s.autonomy, [mode]: s.autonomy[mode] + 1 }, rounds: { counts: s.rounds.counts, rows: [...s.rounds.rows, rr].slice(-50) } };
        }
        // gate decisions are already counted from their control{gate} frame
        const counts = p.source === "gate" ? s.autonomy : { ...s.autonomy, [mode]: s.autonomy[mode] + 1 };
        return { ...s, decisions: [row, ...s.decisions].slice(0, 100), autonomy: counts };
      }
      if (role === "Founder" && p.kind === "note") {
        // the Founder's "now I know" line + its next question (FOUNDING-INTAKE §4); "Now I know" also fills the answer's block
        const transcript = [...s.transcript, { id: `tr_${s.frames}`, at, who: "village", text }].slice(-60);
        const m = text.match(/^now i know:?\s*(.+)$/i);
        if (m && s.blocks.length) {
          const blocks = s.blocks.slice();
          const last = blocks[blocks.length - 1];
          blocks[blocks.length - 1] = { ...last, knows: m[1] };
          return { ...s, transcript, blocks };
        }
        return { ...s, transcript };
      }
      return { ...s, ledger: upsertLedger(s.ledger, { id: `rs_${s.frames}`, at, status: "done", what: text, role }) };
    }
    case "blueprint": {
      const stage = p?.stage as BlueprintStage;
      if (!stage) return s;
      const items = Array.isArray(p.items) ? p.items : [];
      const stages = { ...s.blueprint.stages, [stage]: items };
      const gaps = stage === "questions" ? items.map((q: any) => String(q.gap ?? q.topic ?? q.question ?? "")).filter(Boolean) : s.gaps;
      const done = stage === "done" || s.blueprint.done;
      if ((stage as string) === "will_build") {
        // builder: blueprint{stage:"will_build", items:[{person, component, reason}]} → the current answer's block
        if (!s.blocks.length) return s;
        const wb: WillBuild[] = items.map((it: any) => ({ person: String(it.person ?? ""), component: String(it.component ?? ""), reason: String(it.reason ?? ""), role: it.role }));
        const blocks = s.blocks.slice();
        const last = blocks[blocks.length - 1];
        blocks[blocks.length - 1] = { ...last, willBuild: [...last.willBuild, ...wb] };
        return { ...s, blocks };
      }
      // during a paced founding the right column shows these; the middle shows the answer blocks
      const ledger = s.blocks.length ? s.ledger : upsertLedger(s.ledger, { id: `bp:${stage}`, at, status: "done", what: stageWords(stage, items, nameCtx(s)), role: "Founder" });
      if (stage === "questions") return { ...s, blueprint: { stages, done }, gaps };
      return { ...s, blueprint: { stages, done }, ledger, gaps: done ? [] : s.gaps };
    }
    case "counter": {
      if (!p?.name) return s;
      const counters = { ...s.counters, [p.name]: { value: Number(p.value) || 0, of: p.of, label: String(p.label ?? p.name) } };
      const phones = /^(phones|phones_live|sockets|phones_connected)$/.test(p.name) ? Number(p.value) || 0 : s.phones;
      const coverage = p.name === "intake_coverage" ? { value: Number(p.value) || 0, of: Number(p.of) || 10 } : s.coverage;
      const rm = String(p.name).match(/^rounds_(acted_alone|asked_human|refused)$/);
      const rounds = rm ? { ...s.rounds, counts: { ...(s.rounds.counts ?? { acted_alone: 0, asked_human: 0, refused: 0 }), [rm[1]]: Number(p.value) || 0 } } : s.rounds;
      return { ...s, counters, phones, coverage, rounds };
    }
    case "clock":
      return p?.now ? { ...s, clock: { now: p.now, offset_minutes: Number(p.offset_minutes) || 0 } } : s;
    case "caption": {
      if (!p?.es && !p?.en) return s;
      const speaker = p.speaker ? String(p.speaker).charAt(0).toUpperCase() + String(p.speaker).slice(1) : undefined;
      const line: CaptionLine = { id: `cap_${s.frames}`, at, es: String(p.es ?? ""), en: String(p.en ?? ""), speaker };
      // during founding, the coordinator's words (speaker "ana" in the contract enum) are the transcript (English; es may repeat it)
      if (foundingNow(s) && p.speaker && String(p.speaker) !== "village" && String(p.speaker) !== "caller") {
        const words = line.en || line.es;
        const block: AnswerBlock = { id: `blk_${s.frames}`, at, heard: words, knows: null, doing: [], willBuild: [] };
        return { ...s, transcript: [...s.transcript, { id: `tr_${s.frames}`, at, who: "ana", text: words }].slice(-60), blocks: [...s.blocks, block] };
      }
      return { ...s, captions: [...s.captions, line].slice(-6) };
    }
    case "ledger": {
      if (!p?.id || !p?.what) return s;
      const status: LedgerStatus = ["queued", "running", "done", "retrying", "fallback", "refused"].includes(p.status) ? p.status : "done";
      const r = String(p.role ?? "founder").toLowerCase();
      const role = (["founder", "watcher", "verifier", "builder", "explainer"].includes(r) ? r.charAt(0).toUpperCase() + r.slice(1) : "Founder") as AgentRole;
      const ledger = upsertLedger(s.ledger, { id: String(p.id), at: p.at ?? at, status, what: String(p.what), result: p.result, role, attempt: p.attempt, mode: p.mode, elapsed_ms: p.elapsed_ms });
      let blocks = s.blocks;
      const known = s.blocks.some((b) => b.doing.includes(String(p.id)));
      if (!known && s.blocks.length && foundingNow(s)) {
        blocks = s.blocks.slice();
        const last = blocks[blocks.length - 1];
        blocks[blocks.length - 1] = { ...last, doing: [...last.doing, String(p.id)] };
      }
      return { ...s, ledger, blocks };
    }
    case "release": {
      const r = p?.receipt;
      if (!r) return s;
      let ledger = s.ledger;
      for (const st of r.stages ?? []) {
        let status = STAGE_STATUS[st.status] ?? "queued";
        if (st.status === "failed" && r.result === "in_progress") status = "retrying";
        const result = st.status === "failed" ? (st.details?.summary ?? st.summary ?? "failed") : st.status === "passed" ? (st.details?.summary ?? st.summary ?? undefined) : undefined;
        ledger = upsertLedger(ledger, { id: `rel:${r.release_id ?? r.id}:${st.name}`, at, status, what: `rev ${r.rev} · ${STAGE_WORDS[st.name] ?? st.name}`, result: typeof result === "string" ? result : undefined, role: "Builder" });
      }
      return { ...s, release: r, ledger };
    }
    case "qa": {
      const status = STAGE_STATUS[p?.status] ?? "queued";
      const ledger = upsertLedger(s.ledger, { id: `rel:${p.release_id}:${p.stage}`, at, status, what: `rev ${p.rev} · ${STAGE_WORDS[p.stage] ?? p.stage}`, result: p.summary, role: "Builder" });
      return { ...s, ledger };
    }
    case "build_log":
      return { ...s, buildLog: [...s.buildLog, { at, stage: p.stage, line: p.line, level: p.level }].slice(-30) };
    case "proposal": {
      const pr = p?.proposal;
      if (!pr) return s;
      const title = typeof pr.title === "string" ? pr.title : pr.title?.en ?? pr.summary?.en ?? pr.id;
      const ledger = upsertLedger(s.ledger, { id: `prop:${pr.id}`, at, status: pr.status === "applied" ? "done" : pr.status === "rejected" || pr.status === "failed" ? "refused" : "running", what: `Watcher proposed: ${title}`, result: pr.status, role: "Watcher" });
      const counts = s.proposal?.id === pr.id ? s.autonomy : { ...s.autonomy, asked_human: s.autonomy.asked_human + 1 };
      return { ...s, proposal: pr, ledger, autonomy: counts };
    }
    default:
      return s;
  }
}
