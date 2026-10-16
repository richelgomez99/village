// Offline Control Room replays (?fake=control&seq=founding|scam|release|evolve). Contract-shaped control frames
// (ws_messages.schema.json control{kind}) built from the fixtures; caption/ledger kinds are the two kit-proposed
// extensions (LD-9). Times are offsets in ms from the start of the replay; ?speed scales them in the hub.
import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";
import { fakeSnapshot } from "./fixtureData";

export type ControlSeq = "founding" | "scam" | "release" | "evolve";
export interface Timed { ms: number; msg: any }

const DAY = "2026-10-16";
const at = (hhmmss: string) => `${DAY}T${hhmmss}-04:00`;
const ctl = (kind: string, payload: unknown, t: string) => ({ type: "control", kind, payload, at: t });

export function isControlSeq(v: string | null): v is ControlSeq {
  return v === "founding" || v === "scam" || v === "release" || v === "evolve";
}

const TOPICS = [
  "The person at the center", "Who is in the village", "Availability", "Health: medications", "Health: routine",
  "Money", "Home and day", "Emergencies", "Channels and language", "Consent and her own rules"
];

interface Turn { ana: string; know: string; ask?: string; covered: number; ledger?: [string, string, string, string?][]; people?: string[]; stage?: [string, any[]][] }

/** docs/FOUNDING-INTAKE.md §2, compressed: Ana's words, Village's "now I know" + next question, work rows, coverage. */
const TURNS: Turn[] = [
  { ana: "Mom's seventy-eight and alone in Queens. She mixes up her pills, she almost wired money to someone pretending to be Marco last week, and last Thursday nobody went to see her because Marco and I each thought the other was going.",
    know: "Now I know: Carmen, 78, alone in Queens · health, money, people.", ask: "Who else is in this besides you and Marco, and where does everyone live relative to your mom?", covered: 1, people: ["m_carmen", "m_ana", "m_marco"] },
  { ana: "Marco and me, and our sister Lucía in New Jersey. Marco's in Astoria, ten minutes from Mom. I'm in Brooklyn, forty minutes. Lucía does the refills and the insurance calls.",
    know: "Now I know: 4 people · Lucía is backup for refills and insurance.", ask: "What is Marco's week like? When can he actually be there?", covered: 2, people: ["m_carmen", "m_ana", "m_marco", "m_lucia"] },
  { ana: "He works nights. He can do Tuesday, Thursday, Friday and Saturday evenings. He wants a text at three on his days.",
    know: "Now I know: Marco Tue · Thu · Fri · Sat evenings.", ask: "And you?", covered: 2,
    ledger: [["consent_marco", "running", "Calling Marco to confirm Tue/Thu/Fri/Sat and ask if Village may call him"]] },
  { ana: "Monday, Wednesday, Sunday, after four. I do all the doctor visits. Sunday lunch is at Mom's and I fill her pill organizer then.",
    know: "Now I know: every night has a name. Thursday is Marco.", ask: "Her pills: what does she take, and who prescribed them?", covered: 3,
    ledger: [["rota", "done", "Rota coverage check", "every night has a name · Thursday is Marco"]] },
  { ana: "Eliquis morning and night. Lisinopril in the morning, which Dr. Park just doubled to ten milligrams on the third. Metformin twice a day. Atorvastatin at night. The old lisinopril bottle is still in her cabinet.",
    know: "Now I know: 4 medications · lisinopril 10 mg since Oct 3 (was 5 mg, Dr. Park).", ask: "How does she take them, and what happens on the nights she isn't sure?", covered: 4,
    ledger: [["dm_apixaban", "done", "DailyMed: apixaban", "✓ high-alert, bleeding"], ["dm_lisinopril", "done", "DailyMed: lisinopril", "✓"], ["dm_metformin", "done", "DailyMed: metformin", "✓"], ["dm_atorvastatin", "done", "DailyMed: atorvastatin", "✓"]] },
  { ana: "Weekly organizer, yellow lid for morning, blue lid for evening. Two or three nights a week she calls me asking if she took them. Once she took them twice.",
    know: "Now I know: organizer with 2 lids · 3 dose rules on.", ask: "Money. Tell me about the call last week.", covered: 5,
    ledger: [["consent_marco", "done", "Called Marco", "confirmed Tue/Thu/Fri/Sat · yes to calls"]] },
  { ana: "Someone called saying he was Marco, crying, needed fifteen hundred dollars in gift cards. Marco handles her money stuff with her.",
    know: "Now I know: money asks in a family name get checked with that person first · verifier Marco, then Ana.", ask: "Pick a word only the family knows. Every real call from Village says it.", covered: 6 },
  { ana: "Breakfast at eight with the morning pills. Walk to the bakery at eleven with Doña Rosa. Evening pills at seven-thirty. Second-floor walk-up; the super is Luis.",
    know: "Now I know: family word set · her day and 2 neighbors.", ask: "If she falls or can't breathe, who is first?", covered: 7 },
  { ana: "911, then me, then Marco. Elmhurst Hospital.", know: "Now I know: 911 first · then Ana, then Marco.", ask: "Her phone and her language: what will she actually use?", covered: 8 },
  { ana: "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text.",
    know: "Now I know: Carmen gets a phone line, a fridge card, Spanish read aloud.", ask: "When is your mom sharpest, for Village's welcome call?", covered: 9 },
  { ana: "After lunch, around one-thirty. And she hates calls at night.", know: "Now I know: welcome call 13:30 · quiet hours pending her words.", ask: "Here is the draft: four people, three life areas, five needs, ten rules on, one thing pending your mom. What is wrong?", covered: 10,
    ledger: [["draft", "done", "Drafted 3 apps, a refill checklist, a fridge card, a Spanish phone line", "nothing sent until Ana says “send the invites”"]] }
];

function founding(villageId?: string): Timed[] {
  const bp = (reyesSpec as any).blueprint;
  const v = { ...(reyesSpec as any).village, ...(villageId ? { id: villageId } : {}) };
  const out: Timed[] = [];
  let ms = 0;
  let sec = 0;
  const t = () => at(`13:58:${String(Math.min(59, sec)).padStart(2, "0")}`);
  const push = (step: number, msg: any) => {
    ms += step;
    out.push({ ms, msg });
  };
  push(0, ctl("counter", { name: "phones_live", value: 1, label: "phones live" }, at("13:58:00")));
  push(0, ctl("counter", { name: "intake_coverage", value: 0, of: 10, label: "topics covered" }, at("13:58:00")));
  push(0, ctl("blueprint", { village: v.id, stage: "questions", items: TOPICS.map((g) => ({ gap: g })) }, at("13:58:00")));
  push(400, ctl("reasoning", { source: "founder", kind: "note", text: "Who is this village for, and what goes wrong?", village: v.id }, at("13:58:00")));
  for (const turn of TURNS) {
    sec += 5;
    push(900, ctl("caption", { speaker: "ana", es: turn.ana, en: turn.ana, final: true, village: v.id }, t()));
    if (turn.people) push(300, ctl("blueprint", { village: v.id, stage: "people", items: bp.people.filter((p: any) => turn.people!.includes(p.id)) }, t()));
    if (turn.covered === 1) {
      push(200, ctl("blueprint", { village: v.id, stage: "life_areas", items: bp.life_areas }, t()));
      push(200, ctl("blueprint", { village: v.id, stage: "needs", items: bp.needs.filter((n: any) => n.origin === "description") }, t()));
    }
    if (turn.covered === 5) push(200, ctl("blueprint", { village: v.id, stage: "rules", items: bp.rules.slice(0, 3).map((r: string) => ({ rule: r })) }, t()));
    if (turn.covered === 6) push(200, ctl("blueprint", { village: v.id, stage: "rules", items: bp.rules.slice(0, 9).map((r: string) => ({ rule: r })) }, t()));
    for (const [id, status, what, result] of turn.ledger ?? []) {
      push(250, ctl("ledger", { id, at: t(), status, what, ...(result ? { result } : {}), role: "founder", village: v.id }, t()));
    }
    push(200, ctl("counter", { name: "intake_coverage", value: turn.covered, of: 10, label: "topics covered" }, t()));
    push(0, ctl("blueprint", { village: v.id, stage: "questions", items: TOPICS.slice(turn.covered).map((g) => ({ gap: g })) }, t()));
    push(300, ctl("reasoning", { source: "founder", kind: "note", text: turn.ask ? `${turn.know} ${turn.ask}` : turn.know, village: v.id }, t()));
  }
  sec += 5;
  push(900, ctl("caption", { speaker: "ana", es: "Lucía should see the refill list too, she does the ordering. Send the invites.", en: "Lucía should see the refill list too, she does the ordering. Send the invites.", final: true, village: v.id }, t()));
  push(300, ctl("blueprint", { village: v.id, stage: "rules", items: bp.rules.map((r: string) => ({ rule: r })) }, t()));
  push(200, ctl("blueprint", { village: v.id, stage: "kind", items: [{ kind: v.kind }] }, t()));
  push(200, ctl("blueprint", { village: v.id, stage: "done", items: [{ rev: (reyesSpec as any).rev }] }, t()));
  push(100, { ...(fakeSnapshot("control") as any), village: v.id });
  for (let n = 2; n <= 4; n++) push(500, ctl("counter", { name: "phones_live", value: n, label: "phones live" }, at(`13:59:0${n}`)));
  return out;
}

/** What the control socket gets on hello for a replay: founding starts with no village yet. */
export function controlHelloSnapshot(seq: ControlSeq | null | undefined, village?: string): any {
  if (seq !== "founding") return null;
  const snap = fakeSnapshot("control") as any;
  return { ...snap, rev: 0, spec: null, data: {}, village: village ?? snap.village, now: at("13:58:00") };
}

function scam(): Timed[] {
  const seqs = (wsScam as any).sequences;
  const base = Date.parse(seqs.start[0].t);
  // the fixture's own control/event frames come from the hub's start + tail replay; this adds what the room sees on top
  const frames: Timed[] = [];
  const t0 = seqs.start[0].t;
  void base;
  frames.push({ ms: 0, msg: ctl("counter", { name: "phones_live", value: 4, label: "phones live" }, t0) });
  frames.push({ ms: 1, msg: ctl("caption", { speaker: "carmen", village: "v_reyes", es: "Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.", en: "Marco called me crying, he says he's in trouble and needs two thousand dollars.", final: true }, t0) });
  frames.push({ ms: 400, msg: ctl("caption", { speaker: "village", village: "v_reyes", es: "Voy a confirmar con Marco ahora mismo. No mande dinero todavía.", en: "I'm checking with Marco right now. Please don't send any money yet.", final: true }, t0) });
  return frames.sort((a, b) => a.ms - b.ms);
}

function stage(name: string, status: string, summary?: string, extra: Record<string, unknown> = {}) {
  const done = status === "passed" || status === "failed";
  return { name, status, started: status === "pending" || status === "skipped" ? null : at("14:10:00"), ended: done ? at("14:10:12") : null, details: { ...(summary ? { summary } : {}), ...extra } };
}

function receipt(rev: number, attempt: number, stages: any[], result: string) {
  return {
    id: `rel_reyes_r${rev}`, village: "v_reyes", rev, previous_live_rev: rev - 1 >= 1 ? 2 : null, live_rev: result === "released" ? rev : 2,
    attempt, trigger: attempt > 1 ? "repair" : "proposal", stages, result, created_at: at("14:10:00"), ...(attempt > 1 ? { repair_of: `rel_reyes_r${rev - 1}` } : {})
  };
}

function release(): Timed[] {
  const names = ["spec", "daytona_build", "tests", "anchor_qa", "arize_evals", "live"];
  const r3 = (upto: number, fail: boolean) =>
    names.map((n, i) => (i < upto ? stage(n, "passed", n === "daytona_build" ? "built in 12 s" : undefined) : i === upto ? stage(n, fail ? "failed" : "running", fail ? "contrast 4.1:1 on elder view (needs 7:1)" : undefined) : stage(n, fail ? "skipped" : "pending")));
  const r4 = names.map((n) =>
    stage(n, "passed", n === "daytona_build" ? "built in 12 s" : n === "tests" ? "16 of 16 tests passed · contrast 7.4:1" : n === "anchor_qa" ? "opened the calls-screened card at 390×844" : n === "arize_evals" ? "4 of 4 evals passed" : undefined)
  );
  return [
    { ms: 0, msg: ctl("release", { receipt: receipt(3, 1, r3(1, false), "in_progress") }, at("14:10:00")) },
    { ms: 600, msg: ctl("build_log", { release_id: "rel_reyes_r3", rev: 3, stage: "daytona_build", line: "vite build · 13 entries · 453 KiB", level: "info" }, at("14:10:06")) },
    { ms: 1200, msg: ctl("release", { receipt: receipt(3, 1, r3(2, false), "in_progress") }, at("14:10:12")) },
    { ms: 2000, msg: ctl("release", { receipt: receipt(3, 1, r3(2, true), "in_progress") }, at("14:10:20")) },
    { ms: 2300, msg: ctl("reasoning", { source: "release", kind: "decision", text: "rev 3 caught: contrast 4.1:1 on the elder view. Patched the theme token and rebuilt; rev 2 stays live meanwhile.", village: "v_reyes" }, at("14:10:21")) },
    { ms: 3200, msg: ctl("release", { receipt: receipt(4, 2, r4.map((s, i) => (i < 3 ? s : stage(s.name, i === 3 ? "running" : "pending"))), "in_progress") }, at("14:10:40")) },
    { ms: 4400, msg: ctl("release", { receipt: receipt(4, 2, r4, "released") }, at("14:10:58")) }
  ];
}

function evolve(): Timed[] {
  const proposal = {
    id: "prop_reyes_screen", village: "v_reyes", detected_by: "memory_pattern",
    title: { en: "Village answers unknown callers for Mamá", es: "Village contesta a desconocidos por Mamá" },
    rationale: { en: "2nd money request in Marco's name in 30 days (Oct 9, Oct 16)." },
    changes: [{ en: "+ Unknown callers hear Village first; family calls ring through" }, { en: "+ \"Calls screened\" card on Ana's app" }],
    evidence: [{ kind: "call_moment", ref: "conv_demo_1016_scam@9", label: "Oct 16 · call at 0:09 · \"Marco\" asked for $2,000" }],
    ops: { coordinator: [{ op: "add", path: "/elements/screened", value: { type: "Text", props: { text: "Calls screened: 1 today" } } }] },
    status: "proposed", base_rev: 5, created_at: at("20:53:00")
  };
  return [
    { ms: 0, msg: ctl("reasoning", { source: "evolve", kind: "note", text: "Pattern: 2 calls in 30 days claiming to be Marco (Oct 9, Oct 16).", village: "v_reyes" }, at("20:53:00")) },
    { ms: 500, msg: ctl("proposal", { proposal }, at("20:53:00")) },
    { ms: 800, msg: ctl("reasoning", { source: "evolve", kind: "decision", text: "Asked Ana to let Village answer unknown callers for Mamá: 2nd money request in 30 days.", village: "v_reyes" }, at("20:53:01")) },
    { ms: 2500, msg: ctl("proposal", { proposal: { ...proposal, status: "verifying" } }, at("20:53:30")) },
    { ms: 4000, msg: ctl("proposal", { proposal: { ...proposal, status: "applied", target_rev: 6 } }, at("20:54:10")) }
  ];
}

export function controlSequence(seq: ControlSeq, village?: string): Timed[] {
  switch (seq) {
    case "founding":
      return founding(village);
    case "scam":
      return scam();
    case "release":
      return release();
    case "evolve":
      return evolve();
  }
}
