import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import ws from "../../contracts/fixtures/ws_sequence_scam.json";
import { gateMode, initialScene, sceneReducer, type SceneState } from "../src/control/scene";
import { controlSequence } from "../src/dev/fakeControl";

const T = "2026-10-16T14:02:09-04:00";
const ctl = (kind: string, payload: any, at = T) => ({ type: "control", kind, payload, at }) as any;
const run = (frames: any[], s: SceneState = initialScene()): SceneState => frames.reduce((a: SceneState, f: any) => sceneReducer(a, f), s);
const controlFrames = (name: string) => (ws as any).sequences[name].filter((f: any) => f.client === "control" && f.dir === "s2c").map((f: any) => f.msg);

describe("scene reducer", () => {
  it("snapshot (control) stores the whole spec; member snapshots are ignored", () => {
    const s = run([{ type: "snapshot", rev: 5, village: "v_reyes", role: "control", member_id: null, spec: reyes, data: { a: 1 }, now: T }]);
    expect(s.spec.views.elder).toBeDefined();
    expect(s.rev).toBe(5);
    const s2 = sceneReducer(s, { type: "snapshot", rev: 6, village: "v_reyes", role: "helper", member_id: "m_marco", spec: {}, data: {}, now: T } as any);
    expect(s2.spec).toBe(s.spec);
  });

  it("gate: rows newest first with rule ids, D23 mode counts, verification lifecycle in the ledger and live moment", () => {
    const s = run([...controlFrames("start"), ...controlFrames("denied")]);
    expect(s.gate.map((g) => g.rule_id)).toEqual(["R-MONEY-DEFAULT", "R-MONEY-VERIFY"]);
    expect(s.gate[0].mode).toBe("refused");
    expect(s.gate[1].mode).toBe("asked_human");
    expect(s.autonomy.asked_human).toBeGreaterThanOrEqual(1);
    expect(s.autonomy.refused).toBe(1);
    const ver = s.ledger.find((r) => r.id === "ver:ver_1016_01")!;
    expect(ver.status).toBe("done");
    expect(ver.result).toContain("that wasn't me");
    expect(s.live?.state).toBe("denied");
    expect(s.live?.quote).toContain("Me llamó Marco");
  });

  it("gate timeout tail ends as a fallback row (never vanishes)", () => {
    const s = run([...controlFrames("start"), ...controlFrames("timeout_tail")]);
    const ver = s.ledger.find((r) => r.id === "ver:ver_1016_01")!;
    expect(ver.status).toBe("fallback");
    expect(s.ledger.filter((r) => r.id === "ver:ver_1016_01")).toHaveLength(1);
    // the window-closing tick (allow, empty say) isn't an autonomy decision
    expect(s.autonomy.acted_alone).toBe(0);
  });

  it("reasoning: decisions get D23 role names and modes; plans become ledger rows", () => {
    const s = run([
      { type: "snapshot", rev: 5, village: "v_reyes", role: "control", member_id: null, spec: reyes, data: {}, now: T },
      ctl("reasoning", { source: "voice", kind: "decision", text: "Calling Marco to verify (consent on file)." }),
      ctl("reasoning", { source: "evolve", kind: "decision", text: "Did the evening check-in call." }),
      ctl("reasoning", { source: "builder", kind: "plan", text: "Three apps from three profiles." })
    ]);
    expect(s.decisions.map((d) => [d.role, d.mode])).toEqual([["Watcher", "acted_alone"], ["Verifier", "asked_human"]]);
    expect(s.ledger[0]).toMatchObject({ status: "done", role: "Builder", what: "Three apps from three profiles." });
    expect(gateMode("verify_with_member")).toBe("asked_human");
  });

  it("founding: one block per answer (Heard → Knows → Doing → Will build), drafts per role, then the spec", () => {
    const s = run(controlSequence("founding").map((t) => t.msg));
    expect(s.blueprint.done).toBe(true);
    expect(s.blueprint.stages.people).toHaveLength(4);
    expect(s.blocks).toHaveLength(12);
    expect(s.blocks[0].knows).toContain("Carmen, 78");
    expect(s.blocks[2].doing).toEqual(["consent_marco"]);
    expect(s.blocks[4].doing).toEqual(["dm_apixaban", "dm_lisinopril", "dm_metformin", "dm_atorvastatin"]);
    expect(s.blocks[4].willBuild.map((w) => [w.component, w.person])).toEqual([["Refill checklist", "Marco"], ["Refill checklist", "Ana"]]);
    expect(Object.keys(s.drafts).sort()).toEqual(["coordinator", "elder", "helper"]);
    expect(s.drafts.elder.lang).toBe("es");
    expect(s.drafts.helper.elements.s.children).toContain("refill");
    expect(s.ledger.find((r) => r.id === "dm_apixaban")).toMatchObject({ status: "done", role: "Founder" });
    expect(s.ledger.find((r) => r.id === "consent_marco")).toMatchObject({ status: "done", result: "confirmed Tue/Thu/Fri/Sat · yes to calls" });
    expect(s.ledger.filter((r) => r.id === "consent_marco")).toHaveLength(1);
    expect(s.coverage).toEqual({ value: 10, of: 10 });
    expect(s.transcript.filter((l) => l.who === "ana").length).toBeGreaterThanOrEqual(11);
    expect(s.transcript.find((l) => l.who === "village")?.text).toBeTruthy();
    expect(s.spec?.views?.elder).toBeDefined();
    expect(s.decisions.every((d) => d.role === "Founder")).toBe(true);
  });

  it("counter drives the phones count; clock; caption", () => {
    let s = run([ctl("counter", { name: "phones_live", value: 3, label: "phones live" }), ctl("counter", { name: "scams_stopped", value: 1, label: "scams stopped today" })]);
    expect(s.phones).toBe(3);
    expect(s.counters.scams_stopped.value).toBe(1);
    s = run([ctl("counter", { name: "phones_live", value: 7, label: "phones live" }), ctl("clock", { now: "2026-10-16T21:20:00-04:00", offset_minutes: 30 }), ctl("caption", { es: "Hola", en: "Hello" })], s);
    expect(s.phones).toBe(7);
    expect(s.clock?.offset_minutes).toBe(30);
    expect(s.captions.at(-1)).toMatchObject({ es: "Hola", en: "Hello" });
  });

  it("release: rev 3 failure is caught (retrying) then rev 4 goes live; qa + build_log", () => {
    const s = run(controlSequence("release").map((t) => t.msg));
    expect(s.release.result).toBe("released");
    expect(s.ledger.find((r) => r.id === "rel:rel_reyes_r3:tests")).toMatchObject({ status: "retrying", result: "contrast 4.1:1 on elder view (needs 7:1)" });
    expect(s.ledger.find((r) => r.id === "rel:rel_reyes_r4:live")?.status).toBe("done");
    expect(s.buildLog).toHaveLength(1);
    const q = sceneReducer(s, ctl("qa", { release_id: "rel_x", rev: 7, stage: "anchor_qa", status: "running" }));
    expect(q.ledger.at(-1)).toMatchObject({ status: "running", role: "Builder" });
  });

  it("proposal: Watcher row updates in place and counts once as asked_human", () => {
    const s = run(controlSequence("evolve").map((t) => t.msg));
    const rows = s.ledger.filter((r) => r.id === "prop:prop_reyes_screen");
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("done");
    expect(s.proposal.status).toBe("applied");
  });

  it("1.3.4: ledger rows update in place by id (contract role/at/mode), caption speaker, reasoning + gate mode", () => {
    const s = run([
      ctl("ledger", { id: "x", at: T, status: "running", what: "Looking up", role: "watcher" }),
      ctl("ledger", { id: "x", at: T, status: "done", what: "Looked up", result: "ok", role: "watcher", mode: "acted_alone", elapsed_ms: 1200 }),
      ctl("caption", { es: "Hola", en: "Hello", speaker: "carmen" }),
      ctl("reasoning", { source: "watcher", kind: "decision", text: "Did a thing.", mode: "refused" })
    ], { ...initialScene("v_reyes"), spec: reyes });
    expect(s.ledger).toHaveLength(1);
    expect(s.ledger[0]).toMatchObject({ status: "done", result: "ok", role: "Watcher", mode: "acted_alone" });
    expect(s.captions[0].speaker).toBe("Carmen");
    expect(s.decisions[0]).toMatchObject({ role: "Watcher", mode: "refused" });
  });

  it("ignores frames that name another village", () => {
    const s = run([ctl("caption", { es: "Hola", en: "Hello", village: "v_reyes" }), ctl("ledger", { id: "y", at: T, status: "done", what: "w", village: "v_reyes" })], initialScene("v_w147"));
    expect(s.captions).toHaveLength(0);
    expect(s.ledger).toHaveLength(0);
  });

  it("ignores unknown kinds", () => {
    const s0 = initialScene();
    const s = sceneReducer(s0, ctl("mystery", { x: 1 }));
    expect({ ...s, frames: 0 }).toEqual(s0);
  });
});
