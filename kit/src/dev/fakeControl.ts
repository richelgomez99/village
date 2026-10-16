// Offline Control Room replays (?fake=control&seq=founding|scam|release|evolve). Contract-shaped control frames
// (ws_messages.schema.json control{kind}) built from the fixtures; caption/ledger kinds are the two kit-proposed
// extensions (LD-9). Times are offsets in ms from the start of the replay; ?speed scales them in the hub.
import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";
import blockSpec from "../../../contracts/fixtures/block_spec.json";
import { blockControlSnapshot, fakeSnapshot } from "./fixtureData";

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
const BLOCK_TOPICS = ["What happened", "Who needs help", "Who can help", "Rumors", "Phones and languages"];

/** A ledger row started by this answer; `result` lands `doneAfter` ms later, or at turn `doneInTurn` (+1.2 s). */
interface Row { id: string; what: string; doneWhat?: string; result: string; doneAfter?: number; doneInTurn?: number }
/** A capability decided by this answer: a card for a person, its reason, and the spec element that will carry it. */
interface Build { person: string; component: string; reason: string; role: string; el: string }
export interface FoundingTurn { said: string; know: string; ask?: string; covered: number; people?: string[]; rows?: Row[]; build?: Build[]; areas?: boolean; rules?: number }

/** docs/FOUNDING-INTAKE.md §2 A0–A12, one answer every ~5 s: what Ana says → what Village now knows → what it does → what it will build. */
const REYES_TURNS: FoundingTurn[] = [
  { said: "Mom's seventy-eight and alone in Queens. She mixes up her pills, she almost wired money to someone pretending to be Marco last week, and last Thursday nobody went to see her because Marco and I each thought the other was going.",
    know: "Carmen, 78, alone in Queens · health, money, people.", ask: "Who else is in this besides you and Marco, and where does everyone live relative to your mom?", covered: 1, people: ["m_carmen", "m_ana", "m_marco"], areas: true,
    build: [{ person: "Carmen", component: "Alert card", reason: "a scam call already reached her", role: "elder", el: "al" }] },
  { said: "Marco and me, and our sister Lucía in New Jersey. Marco's in Astoria, ten minutes from Mom. I'm in Brooklyn, forty minutes. Lucía does the refills and the insurance calls.",
    know: "4 people · Marco is 10 minutes away · Lucía handles refills and insurance.", ask: "What is Marco's week like? When can he actually be there?", covered: 2, people: ["m_carmen", "m_ana", "m_marco", "m_lucia"],
    build: [{ person: "Carmen", component: "Tonight card", reason: "nobody knew whose night it was", role: "elder", el: "tonight" }] },
  { said: "He works nights. Sunday to Thursday he has to leave by nine-thirty. He can do Tuesday, Thursday, Friday and Saturday evenings. He wants a text at three on his days.",
    know: "Marco: Tue · Thu · Fri · Sat evenings, leaves 9:30.", ask: "And you?", covered: 2,
    rows: [{ id: "consent_marco", what: "Calling Marco: confirm Tue/Thu/Fri/Sat, may Village call him?", doneWhat: "Called Marco", result: "confirmed Tue/Thu/Fri/Sat · yes to calls", doneInTurn: 5 }],
    build: [{ person: "Marco", component: "\"Is it my turn?\" answer", reason: "he only needs to know if tonight is his", role: "helper", el: "ans" }] },
  { said: "Monday, Wednesday, Sunday, after four. I do all the doctor visits. Sunday lunch is at Mom's and I fill her pill organizer then.",
    know: "Ana: Mon · Wed · Sun after 4, doctor visits.", ask: "Her pills: what does she take, and who prescribed them?", covered: 3,
    rows: [{ id: "rota", what: "Rota coverage check: every night of the week", result: "every night has a name · Thursday is Marco", doneAfter: 900 }],
    build: [{ person: "Ana", component: "Rota for the week", reason: "every night has a name now", role: "coordinator", el: "rota" }] },
  { said: "Eliquis morning and night. Lisinopril in the morning, which Dr. Park just doubled to ten milligrams on the third. Metformin twice a day. Atorvastatin at night. The old lisinopril bottle is still in her cabinet, that scares me.",
    know: "4 medications · lisinopril 10 mg since Oct 3 (was 5 mg, Dr. Park) · old bottle in the cabinet.", ask: "How does she take them, and what happens on the nights she isn't sure?", covered: 4,
    rows: [
      { id: "dm_apixaban", what: "DailyMed: apixaban", result: "high-alert · bleeding", doneAfter: 1100 },
      { id: "dm_lisinopril", what: "DailyMed: lisinopril", result: "no interaction flagged", doneAfter: 1500 },
      { id: "dm_metformin", what: "DailyMed: metformin", result: "no interaction flagged", doneAfter: 1800 },
      { id: "dm_atorvastatin", what: "DailyMed: atorvastatin", result: "no interaction flagged", doneAfter: 2100 }
    ],
    build: [
      { person: "Marco", component: "Refill checklist", reason: "he fills the organizer on refill day", role: "helper", el: "refill" },
      { person: "Ana", component: "Refill checklist", reason: "the old 5 mg bottle is still in the cabinet", role: "coordinator", el: "refill" }
    ] },
  { said: "Weekly organizer, yellow lid for morning, blue lid for evening. Two or three nights a week she calls me asking if she took them. Once she took them twice.",
    know: "weekly organizer, morning and evening · 3 dose rules on (never says how many).", ask: "Money. Tell me about the call last week.", covered: 5, rules: 3,
    build: [
      { person: "Ana", component: "Pills today", reason: "Mamá calls her asking \"did I take them?\"", role: "coordinator", el: "dose" },
      { person: "Ana", component: "Pill organizer", reason: "morning and evening compartments", role: "coordinator", el: "org" }
    ] },
  { said: "Someone called saying he was Marco, crying, in trouble, needed fifteen hundred dollars in gift cards. Marco handles her money stuff with her.",
    know: "money asked in a family name gets checked with that person first · verifier Marco, then Ana.", ask: "Pick a word only the family knows. Every real call from Village says it.", covered: 6, rules: 9,
    build: [
      { person: "Marco", component: "Money check prompt", reason: "money asked in his name gets checked with him", role: "helper", el: "vp" },
      { person: "Ana", component: "Incidents card", reason: "she hears about every money call", role: "coordinator", el: "inc" }
    ] },
  { said: "Pavo. Thanksgiving is at her place and Marco always brings the turkey.", know: "family word set (never shown on screen).", ask: "Her day and her home: what does a normal day look like, and is anyone nearby?", covered: 7 },
  { said: "911, then me, then Marco. Elmhurst Hospital.", know: "911 first · then Ana, then Marco · Elmhurst Hospital.", ask: "Her phone and her language: what will she actually use?", covered: 8,
    build: [{ person: "Carmen", component: "911 button", reason: "911 first, always", role: "elder", el: "e911" }] },
  { said: "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text.",
    know: "Carmen: phone line, Spanish, big letters, read aloud.", ask: "When is your mom sharpest, for Village's welcome call?", covered: 9,
    build: [
      { person: "Carmen", component: "\"Llamar a Village\" button", reason: "she answers calls, not texts", role: "elder", el: "b_village" },
      { person: "Carmen", component: "\"Llamar a Ana\" button", reason: "one tap to her daughter", role: "elder", el: "b_call" },
      { person: "Carmen", component: "\"Necesito ayuda\" button", reason: "help without reading", role: "elder", el: "b_help" },
      { person: "Marco", component: "Call Mamá button", reason: "one tap from his phone", role: "helper", el: "b_mom" }
    ] },
  { said: "After lunch, around one-thirty. And she hates calls at night.", know: "welcome call at 13:30 · quiet hours pending her own words.", ask: "Here is the draft: four people, three life areas, five needs, ten rules on, one thing pending your mom. What is wrong?", covered: 10,
    rows: [{ id: "draft", what: "Drafting 3 apps, a refill checklist, a fridge card, a Spanish phone line", doneWhat: "Drafted 3 apps, a refill checklist, a fridge card, a Spanish phone line", result: "nothing sent until Ana says “send the invites”", doneAfter: 2400 }],
    build: [
      { person: "Ana", component: "Her village (life areas)", reason: "health, money, people", role: "coordinator", el: "areas" },
      { person: "Ana", component: "What happened", reason: "every change, with its source", role: "coordinator", el: "tl" }
    ] },
  { said: "Lucía should see the refill list too, she does the ordering. Send the invites.", know: "Lucía gets the refill checklist · invites ready.", covered: 10 }
];

const BLOCK_TURNS: FoundingTurn[] = [
  { said: "Power's out on our whole block and it's ninety-seven degrees. Mrs. Alvarez on five needs her oxygen machine, Mr. Chen's insulin is warming up, and everybody's group chat is full of rumors. Darnell's got a generator, Priya's got a car. Help me.",
    know: "blackout at 97° · oxygen and insulin at risk · rumors · a generator and a car.", ask: "Who needs to be checked on first?", covered: 1, people: ["b_tanya", "b_alvarez", "b_chen", "b_darnell", "b_priya"], areas: true,
    build: [{ person: "Tanya Brooks", component: "Official alerts", reason: "a heat emergency with no power", role: "coordinator", el: "al" }] },
  { said: "Mrs. Alvarez first, her oxygen. Then Mr. Chen's insulin, then the Okafors' newborn, then Mr. James in his wheelchair; the elevator's out.",
    know: "priority: oxygen → insulin → newborn → wheelchair.", ask: "Who can help, and with what?", covered: 2, people: ["b_tanya", "b_alvarez", "b_chen", "b_okafor", "b_james", "b_darnell", "b_priya"],
    rows: [{ id: "match", what: "Matching needs to what neighbors offered", result: "generator → Alvarez (outdoors only) · car → Okafors", doneAfter: 1600 }],
    build: [
      { person: "Tanya Brooks", component: "Needs by priority", reason: "oxygen first, then insulin", role: "coordinator", el: "nb" },
      { person: "Darnell Price", component: "Who needs help first", reason: "he has the generator", role: "volunteer", el: "nb" }
    ] },
  { said: "The bodega on the corner has ice. Darnell's generator has to stay outside. Priya can drive two people.",
    know: "ice at the bodega · generator outdoors only · 2 seats in Priya's car.", ask: "What's going around in the group chat?", covered: 3, people: ["b_tanya", "b_alvarez", "b_chen", "b_okafor", "b_james", "b_darnell", "b_priya", "b_bodega"],
    build: [
      { person: "Tanya Brooks", component: "Offered by neighbors", reason: "generator, car, ice", role: "coordinator", el: "rb" },
      { person: "Priya Raman", component: "What neighbors offered", reason: "she can drive two people", role: "volunteer", el: "rb" }
    ] },
  { said: "People say the library cooling center is open and that the power's back at six.",
    know: "2 rumors to check before they spread.", ask: "Who can only be reached by phone?", covered: 4,
    rows: [{ id: "rumors", what: "Checking NYC cooling centers and the Con Edison outage map", result: "library: not listed · power at six: not confirmed", doneAfter: 2000 }],
    build: [
      { person: "Tanya Brooks", component: "Rumor check", reason: "two rumors in the group chat", role: "coordinator", el: "vf" },
      { person: "The Okafor family (Ngozi & Daniel)", component: "Checked facts", reason: "a newborn in the heat", role: "resident", el: "vf" }
    ] },
  { said: "Mrs. Alvarez and Mr. Chen only on their landlines. Everyone else has the app.",
    know: "2 neighbors by phone line · everyone else in the app.", covered: 5,
    build: [
      { person: "The Okafor family (Ngozi & Daniel)", component: "Are you OK? check-in", reason: "Village checks on them every hour", role: "resident", el: "ci" },
      { person: "Tanya Brooks", component: "Check-ins", reason: "who hasn't answered", role: "coordinator", el: "ci" }
    ] }
];

/** The block founding call as recorded by voice2 ({t_ms, speaker, text}); founder lines time the answers. */
export interface TimelineLine { t_ms: number; speaker: string; text: string }

const FOUNDING_NOW = Date.parse("2026-10-16T13:58:00-04:00");
const isoAt = (ms: number) => new Date(FOUNDING_NOW + ms - 4 * 3600_000).toISOString().replace(/\.\d{3}Z$/, "-04:00");

/** Paced founding replay: nothing before its cause. `starts[i]` = ms of answer i (default every 5 s). */
export function foundingTimed(spec: any, turns: FoundingTurn[], topics: string[], villageId: string, starts?: number[], finalSnapshot?: any): Timed[] {
  const bp = spec.blueprint;
  const out: Timed[] = [];
  const at = (ms: number, msg: any) => out.push({ ms, msg });
  const T = (i: number) => starts?.[i] ?? 1500 + i * 5000;
  at(0, ctl("counter", { name: "phones_live", value: 1, label: "phones live" }, isoAt(0)));
  at(0, ctl("counter", { name: "intake_coverage", value: 0, of: topics.length, label: "topics covered" }, isoAt(0)));
  at(0, ctl("blueprint", { village: villageId, stage: "questions", items: topics.map((g) => ({ gap: g })) }, isoAt(0)));
  at(300, ctl("reasoning", { source: "founder", kind: "note", text: "Who is this group for, and what goes wrong?", village: villageId }, isoAt(300)));
  const seenRoles = new Set<string>();
  turns.forEach((turn, i) => {
    const t0 = T(i);
    at(t0, ctl("caption", { speaker: "ana", es: turn.said, en: turn.said, final: true, village: villageId }, isoAt(t0)));
    if (turn.people) at(t0 + 400, ctl("blueprint", { village: villageId, stage: "people", items: bp.people.filter((p: any) => turn.people!.includes(p.id)) }, isoAt(t0 + 400)));
    if (turn.areas) {
      at(t0 + 450, ctl("blueprint", { village: villageId, stage: "life_areas", items: bp.life_areas }, isoAt(t0 + 450)));
      at(t0 + 500, ctl("blueprint", { village: villageId, stage: "needs", items: bp.needs.filter((n: any) => n.origin === "description") }, isoAt(t0 + 500)));
    }
    at(t0 + 700, ctl("reasoning", { source: "founder", kind: "note", text: `Now I know: ${turn.know}`, village: villageId }, isoAt(t0 + 700)));
    (turn.rows ?? []).forEach((r, k) => {
      const start = t0 + 900 + k * 200;
      at(start, ctl("ledger", { id: r.id, at: isoAt(start), status: "running", what: r.what, role: "founder", village: villageId }, isoAt(start)));
      const end = r.doneInTurn != null ? T(r.doneInTurn) + 1200 : start + (r.doneAfter ?? 1400);
      at(end, ctl("ledger", { id: r.id, at: isoAt(end), status: "done", what: r.doneWhat ?? r.what, result: r.result, role: "founder", elapsed_ms: end - start, village: villageId }, isoAt(end)));
    });
    if (turn.rules) at(t0 + 1100, ctl("blueprint", { village: villageId, stage: "rules", items: bp.rules.slice(0, turn.rules).map((r: string) => ({ rule: r })) }, isoAt(t0 + 1100)));
    at(t0 + 1300, ctl("counter", { name: "intake_coverage", value: turn.covered, of: topics.length, label: "topics covered" }, isoAt(t0 + 1300)));
    at(t0 + 1300, ctl("blueprint", { village: villageId, stage: "questions", items: topics.slice(turn.covered).map((g) => ({ gap: g })) }, isoAt(t0 + 1300)));
    (turn.build ?? []).forEach((b, k) => {
      const tb = t0 + 2000 + k * 250;
      at(tb, ctl("blueprint", { village: villageId, stage: "will_build", items: [{ person: b.person, component: b.component, reason: b.reason, role: b.role }] }, isoAt(tb)));
      // ~1 s after the note, that person's phone gains the card (control patch on the role's draft view)
      const view = spec.views?.[b.role];
      const el = view?.elements?.[b.el];
      if (!view || !el) return;
      const ops: any[] = [];
      if (!seenRoles.has(b.role)) {
        seenRoles.add(b.role);
        ops.push({ op: "replace", path: "/lang", value: view.lang }, { op: "replace", path: "/theme", value: view.theme }, { op: "replace", path: "/elements/s", value: { ...view.elements.s, children: [] } });
      }
      ops.push({ op: "add", path: `/elements/${b.el}`, value: el }, { op: "add", path: "/elements/s/children/-", value: b.el });
      at(tb + 1000, { type: "patch", rev: 0, base_rev: 0, role: b.role, ops, highlight: [b.el] });
    });
    if (turn.ask) at(t0 + 3000, ctl("reasoning", { source: "founder", kind: "note", text: turn.ask, village: villageId }, isoAt(t0 + 3000)));
  });
  const tEnd = T(turns.length - 1) + 4200;
  at(tEnd, ctl("blueprint", { village: villageId, stage: "rules", items: bp.rules.map((r: string) => ({ rule: r })) }, isoAt(tEnd)));
  at(tEnd + 100, ctl("blueprint", { village: villageId, stage: "kind", items: [{ kind: spec.village.kind }] }, isoAt(tEnd + 100)));
  at(tEnd + 200, ctl("blueprint", { village: villageId, stage: "done", items: [{ rev: spec.rev }] }, isoAt(tEnd + 200)));
  if (finalSnapshot) at(tEnd + 300, { ...finalSnapshot, village: villageId });
  for (let n = 2; n <= 4; n++) at(tEnd + 300 + n * 400, ctl("counter", { name: "phones_live", value: n, label: "phones live" }, isoAt(tEnd + 300 + n * 400)));
  return out.sort((a, b) => a.ms - b.ms);
}

function founding(villageId?: string): Timed[] {
  return foundingTimed(reyesSpec, REYES_TURNS, TOPICS, villageId ?? (reyesSpec as any).village.id, undefined, fakeSnapshot("control"));
}

/** Block founding: answers timed by the recorded call's timeline when it loaded, else every ~5 s. */
export function blockFounding(villageId: string, timeline?: TimelineLine[] | null): Timed[] {
  const founder = (timeline ?? []).filter((l) => !/^village$/i.test(l.speaker));
  const starts = founder.length >= BLOCK_TURNS.length ? founder.map((l) => l.t_ms) : undefined;
  const turns = starts ? BLOCK_TURNS.map((t, i) => ({ ...t, said: founder[i].text })) : BLOCK_TURNS;
  return foundingTimed(blockSpec, turns, BLOCK_TOPICS, villageId, starts, blockControlSnapshot());
}

/** What the control socket gets on hello for a replay: founding starts with no village yet. */
export function controlHelloSnapshot(seq: ControlSeq | null | undefined, village?: string): any {
  if (seq !== "founding") return null;
  const snap = (village === (blockSpec as any).village.id ? blockControlSnapshot() : fakeSnapshot("control")) as any;
  return { ...snap, rev: 0, spec: null, data: {}, village: village ?? snap.village, now: isoAt(0) };
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
  const tDeny = Date.parse(seqs.denied.find((f: any) => f.msg.type === "control")?.t ?? t0) - base;
  frames.push({ ms: tDeny + 600, msg: { type: "chat", village: "v_reyes", message: { id: "msg_scam_1", village: "v_reyes", author: "village", kind: "incident", text: "Village stopped a money request in Marco's name. Mamá was told not to send anything; Ana knows.", refs: [{ kind: "incident", id: "inc_ver_1016_01" }], source: { kind: "system", ref: "gate" }, at: t0 } } });
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
    { ms: 600, msg: { type: "chat", village: "v_reyes", message: { id: "msg_prop_1", village: "v_reyes", author: "village", kind: "proposal", title: proposal.title, text: "Village proposes answering unknown callers for Mamá first. Options weighed: blocking unknown numbers, the family word alone, a receptionist.", refs: [{ kind: "proposal", id: proposal.id }], source: { kind: "system", ref: "evolve" }, at: at("20:53:00") } } },
    { ms: 800, msg: ctl("reasoning", { source: "evolve", kind: "decision", text: "Asked Ana to let Village answer unknown callers for Mamá: 2nd money request in 30 days.", village: "v_reyes" }, at("20:53:01")) },
    { ms: 2500, msg: ctl("proposal", { proposal: { ...proposal, status: "verifying" } }, at("20:53:30")) },
    { ms: 4000, msg: ctl("proposal", { proposal: { ...proposal, status: "applied", target_rev: 6 } }, at("20:54:10")) },
    { ms: 4200, msg: { type: "chat", village: "v_reyes", message: { id: "msg_rcpt_1", village: "v_reyes", author: "village", kind: "receipt", text: "Every phone updated · rev 6 · built, tested, tried on a phone, scored.", refs: [{ kind: "release", id: "rel_reyes_r6" }], source: { kind: "system", ref: "release" }, at: at("20:54:12") } } }
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
