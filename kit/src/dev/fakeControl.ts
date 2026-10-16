// Offline Control Room replays (?fake=control&seq=founding|scam|release|evolve). Contract-shaped control frames
// (ws_messages.schema.json control{kind}) built from the fixtures; caption/ledger kinds are the two kit-proposed
// extensions (LD-9). Times are offsets in ms from the start of the replay; ?speed scales them in the hub.
import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";

export type ControlSeq = "founding" | "scam" | "release" | "evolve";
export interface Timed { ms: number; msg: any }

const DAY = "2026-10-16";
const at = (hhmmss: string) => `${DAY}T${hhmmss}-04:00`;
const ctl = (kind: string, payload: unknown, t: string) => ({ type: "control", kind, payload, at: t });

export function isControlSeq(v: string | null): v is ControlSeq {
  return v === "founding" || v === "scam" || v === "release" || v === "evolve";
}

function founding(): Timed[] {
  const bp = (reyesSpec as any).blueprint;
  const v = (reyesSpec as any).village;
  const out: Timed[] = [];
  let ms = 0;
  const push = (step: number, msg: any) => {
    ms += step;
    out.push({ ms, msg });
  };
  push(0, ctl("counter", { name: "phones_live", value: 1, label: "phones live" }, at("13:58:00")));
  push(600, ctl("reasoning", { source: "builder", kind: "plan", text: "Listening to Ana: one sentence, then at most two follow-up questions.", village: v.id }, at("13:58:02")));
  push(900, ctl("blueprint", { village: v.id, stage: "people", items: bp.people.filter((p: any) => p.id !== "m_lucia") }, at("13:58:12")));
  push(500, ctl("blueprint", { village: v.id, stage: "needs", items: bp.needs.filter((n: any) => n.origin === "description") }, at("13:58:12")));
  push(500, ctl("blueprint", { village: v.id, stage: "life_areas", items: bp.life_areas }, at("13:58:13")));
  push(400, ctl("ledger", { id: "dailymed", status: "running", what: "Looking up 4 medications on DailyMed", role: "Founder" }, at("13:58:13")));
  push(1200, ctl("ledger", { id: "dailymed", status: "done", what: "Looked up 4 medications on DailyMed", result: "no interactions flagged", role: "Founder" }, at("13:58:19")));
  push(300, ctl("ledger", { id: "call_marco", status: "running", what: "Calling Marco (number from Ana): his days, and may Village call him?", role: "Founder" }, at("13:58:19")));
  push(1400, ctl("ledger", { id: "call_marco", status: "done", what: "Called Marco", result: "Tue · Thu · Fri · Sat · agreed to calls", role: "Founder" }, at("13:58:31")));
  push(300, ctl("blueprint", { village: v.id, stage: "questions", items: [{ question: "Does anyone else help with your mom? And what does she like to be called?" }] }, at("13:58:32")));
  push(700, ctl("blueprint", { village: v.id, stage: "people", items: bp.people }, at("13:58:33")));
  push(300, ctl("reasoning", { source: "builder", kind: "decision", text: "Carmen: phone line + 3 big buttons, Spanish, read aloud. She uses a flip phone and mixes up her pills.", village: v.id }, at("13:58:34")));
  push(300, ctl("reasoning", { source: "builder", kind: "decision", text: "Marco: one question (\"Is it my turn?\") + money checks in his name. He works nights and agreed to calls.", village: v.id }, at("13:58:35")));
  push(300, ctl("blueprint", { village: v.id, stage: "rules", items: bp.rules.map((r: string) => ({ rule: r })) }, at("13:58:36")));
  push(300, ctl("blueprint", { village: v.id, stage: "kind", items: [{ kind: v.kind }] }, at("13:58:36")));
  push(300, ctl("ledger", { id: "draft", status: "running", what: "Drafting 3 apps, a refill checklist, a fridge card, a Spanish phone line", result: "nothing sent yet", role: "Founder" }, at("13:58:38")));
  push(1600, ctl("ledger", { id: "draft", status: "done", what: "Drafted 3 apps, a refill checklist, a fridge card, a Spanish phone line", result: "waiting for Ana: “Invite everyone”", role: "Founder" }, at("13:58:44")));
  push(200, ctl("blueprint", { village: v.id, stage: "done", items: [{ rev: (reyesSpec as any).rev }] }, at("13:58:44")));
  for (let n = 2; n <= 4; n++) push(500, ctl("counter", { name: "phones_live", value: n, label: "phones live" }, at(`13:59:0${n}`)));
  return out;
}

function scam(): Timed[] {
  const seqs = (wsScam as any).sequences;
  const base = Date.parse(seqs.start[0].t);
  const frames: Timed[] = [];
  for (const name of ["start", "denied"]) {
    for (const f of seqs[name]) {
      if (f.client !== "control" || f.dir !== "s2c") continue;
      frames.push({ ms: Date.parse(f.t) - base, msg: f.msg });
    }
  }
  const t0 = seqs.start[0].t;
  const tDenied = seqs.denied.find((f: any) => f.msg.type === "control")?.t ?? t0;
  frames.push({ ms: 0, msg: ctl("counter", { name: "phones_live", value: 4, label: "phones live" }, t0) });
  frames.push({ ms: 1, msg: ctl("caption", { speaker: "Carmen", es: "Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.", en: "Marco called me crying, he says he's in trouble and needs two thousand dollars.", final: true }, t0) });
  frames.push({ ms: 400, msg: ctl("caption", { speaker: "Village", es: "Voy a confirmar con Marco ahora mismo. No mande dinero todavía.", en: "I'm checking with Marco right now. Please don't send any money yet.", final: true }, t0) });
  frames.push({ ms: Date.parse(tDenied) - base + 300, msg: ctl("caption", { speaker: "Village", es: "Ese no era Marco. No mande dinero. Ana ya lo sabe.", en: "That wasn't Marco. Don't send any money. Ana already knows.", final: true }, tDenied) });
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

export function controlSequence(seq: ControlSeq): Timed[] {
  switch (seq) {
    case "founding":
      return founding();
    case "scam":
      return scam();
    case "release":
      return release();
    case "evolve":
      return evolve();
  }
}
