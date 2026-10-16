import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiConfig } from "../src/control/api";
import { PresenterLayer } from "../src/control/PresenterLayer";
import { SCRIPT, presenterRequest } from "../src/control/presenter";
import { KnowsRegion, ReleaseTiles, factScore, factWriter, groupKnowledge, isHousekeeping, stageToolLine } from "../src/control/regions";
import { initialScene, sceneReducer, type SceneState } from "../src/control/scene";
import reyes from "../../contracts/fixtures/reyes_spec.json";

afterEach(() => vi.useRealTimers());
const ctl = (kind: string, payload: any, at = "2026-10-16T14:00:00-04:00") => ({ type: "control", kind, payload, at }) as any;
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe("ROOM-6 Agent Memory list", () => {
  it("ROOM-8: groups knowledge by the group's life areas, counts it in the headline, collapses housekeeping", async () => {
    vi.useFakeTimers();
    const { container } = render(<div className="control"><KnowsRegion api={{ base: "", token: "", fake: true }} village="v_reyes" data={{}} spec={reyes} /></div>);
    await tick(200);
    const rows = Array.from(container.querySelectorAll<HTMLElement>("[data-test='fact-row']"));
    const keys = rows.map((r) => r.dataset.key);
    expect(keys).toContain("quiet_hours");
    rows.unshift(rows.find((r) => r.dataset.key === "quiet_hours")!);
    expect(keys).not.toContain("rota_2026_10_12");
    expect(rows[0].textContent).toContain("quiet hours is 21:30-07:00");
    expect(rows[0].textContent).not.toContain("(m_carmen)");
    const src = rows[0].querySelector<HTMLElement>("[data-test='fact-row-source']")!;
    expect(src.textContent).toBe("call · 1:48");
    expect(src.getAttribute("title")).toContain("Después de las nueve y media, no.");
    fireEvent.click(src);
    expect(rows[0].querySelector("[data-test='fact-row-quote']")?.textContent).toContain("Después de las nueve y media, no.");
    const head = container.querySelector("[data-test='knows-headline']")?.textContent ?? "";
    expect(head).toMatch(/^Village knows \d+ things about Familia Reyes · \d+ heard in calls/);
    const areas = Array.from(container.querySelectorAll<HTMLElement>("[data-test='knows-area']")).map((e) => e.dataset.area);
    expect(areas.length).toBeGreaterThan(0);
    expect(container.querySelector("[data-test='knows-housekeeping']")?.textContent).toMatch(/^and \d+ housekeeping facts$/);
    expect(container.querySelector("[data-test='knows-caption']")?.textContent).toBe("Typed · time-aware · supersedes rather than overwrites · traced to source · shared across agents · SurrealDB Agent Memory");
    expect(factWriter({ labels: { agent: "memory" }, source: { kind: "system", ref: "seed" } } as any)).toBe("seed");
    expect(factScore({ key: "rota_2026_10_12", source: { kind: "system", ref: "seed" } } as any)).toBeLessThan(0);
    expect(isHousekeeping({ key: "consent_ai_calls" } as any)).toBe(true);
    expect(isHousekeeping({ key: "quiet_hours" } as any)).toBe(false);
    const g = groupKnowledge([
      { id: "a", entity: "m_carmen", key: "lisinopril_dose", value: "10 mg", text: "", observed_at: "2026-10-03T09:00:00-04:00", superseded: false, source: { kind: "call", ref: "c", secs: 88 } },
      { id: "b", entity: "m_carmen", key: "lisinopril_dose", value: "5 mg", text: "", observed_at: "2026-09-01T09:00:00-04:00", valid_to: "2026-10-03T09:00:00-04:00", superseded: true, source: { kind: "system", ref: "seed" } },
    ] as any, ["health", "money", "people"]);
    expect(g.groups.health[0].was?.value).toBe("5 mg");
    expect(g.calls).toBe(1);
  });
});

describe("ROOM-6 release tiles name the tools", () => {
  const receipt = {
    id: "rel_reyes_r7", rev: 7, trigger: "proposal", attempt: 1, stages: [
      { name: "spec", status: "passed", details: { summary: "ok" } },
      { name: "daytona_build", status: "passed", details: { duration_ms: 2910, summary: "sandbox 1172d474 · daytonaio/sandbox:0.8.0 · build 2.7 s", sandbox_id: "1172d474-a4ad-48b3" } },
      { name: "tests", status: "passed", details: { tests_passed: 62, tests_failed: 0, summary: "62/62 floor tests · 1.5 s" } },
      { name: "anchor_qa", status: "passed", details: { viewport: "390x844", video_url: "https://x/qa.mp4" }, evidence_urls: [{ kind: "recording", url: "https://x/qa.mp4" }] },
      { name: "arize_evals", status: "passed", details: { summary: "evals passed · Anthropic · claude-haiku-5-5 · 2284 ms TTFT" } },
      { name: "live", status: "passed", details: { summary: "published_rev 6 → 7" } }
    ]
  };
  it("second lines: Daytona sandbox · image · seconds, floor tests, Anchor recording link, Arize model, rev", () => {
    const { container } = render(<ReleaseTiles receipt={receipt} />);
    const lines = Array.from(container.querySelectorAll("[data-test='tile-tool']")).map((t) => t.textContent);
    expect(lines).toEqual(["Daytona sandbox 1172d474 · daytonaio/sandbox · 2.9 s", "62/62 floor tests", "Anchor · 390x844 · recording ▶", "Arize evals · Haiku 5.5 · human approval annotated", "rev 7 · every phone"]);
    expect(container.querySelector("[data-stage='anchor_qa'] a")?.getAttribute("href")).toBe("https://x/qa.mp4");
    expect(stageToolLine(receipt.stages[2], { ...receipt, attempt: 2 }).text).toContain("caught");
  });
});

describe("ROOM-6 live founding renders as the scene", () => {
  it("Core's founder notes become transcript + blocks + meter in an existing village, and the beat stays Build", () => {
    let s: SceneState = { ...initialScene("v_reyes"), spec: reyes, blueprint: { stages: {}, done: false } };
    const note = (text: string) => ctl("reasoning", { source: "founder", kind: "note", text, village: "v_reyes" });
    s = [
      note("Village: Her phone and her language: what will she actually use?"),
      note("Ana: Spanish only. A regular phone, she won't use apps."),
      ctl("ledger", { id: "ch", at: "2026-10-16T14:00:01-04:00", status: "done", what: "channels covered", result: "phone only", role: "founder", village: "v_reyes" }),
      note("phone only, Spanish · 9 of 10 covered · 1 gap · gaps: Consent and the center's own rules · next: When is she sharpest?"),
      ctl("counter", { name: "intake_covered", value: 9, of: 10, label: "topics covered" }),
      ctl("blueprint", { village: "v_reyes", stage: "will_build", items: [{ person: "m_carmen", display_name: "Carmen", role: "elder", component: "BigButton", element: "b_village", reason: "she answers calls, not texts" }] }),
      { type: "patch", rev: 2, base_rev: 1, role: "elder", ops: [{ op: "add", path: "/elements/b_village", value: (reyes as any).views.elder.elements.b_village }, { op: "add", path: "/elements/s/children/0", value: "b_village" }], highlight: ["b_village"] }
    ].reduce((a: SceneState, f: any) => sceneReducer(a, f), s);
    expect(s.foundingLive).toBe(true);
    expect(s.transcript.map((l) => l.who)).toEqual(["village", "ana", "village"]);
    expect(s.blocks).toHaveLength(1);
    expect(s.blocks[0]).toMatchObject({ heard: "Spanish only. A regular phone, she won't use apps.", knows: "phone only, Spanish", doing: ["ch"] });
    expect(s.blocks[0].willBuild[0]).toMatchObject({ person: "Carmen", component: "Big button" });
    expect(s.coverage).toEqual({ value: 9, of: 10 });
    expect(s.gaps).toEqual(["Consent and the center's own rules"]);
    expect(s.drafts.elder.lang).toBe("es");
    expect(s.drafts.elder.elements.s.children).toEqual(["b_village"]);
    expect(s.beat).toBe("build");
  });
});

describe("ROOM-6 presenter keys → real Core requests", () => {
  const ctx = { village: "v_reyes", description: "Mom's seventy-eight…", pendingProposal: "prop_x", coordinatorName: "Ana", caller: "elder" as const, adminKey: "adm" };
  it("pure mapping", () => {
    expect(presenterRequest("r", ctx)).toMatchObject({ path: "/admin/reset", headers: { "X-Admin-Key": "adm" }, after: "reselect" });
    expect(presenterRequest("F", ctx)).toMatchObject({ path: "/villages", body: { description: "Mom's seventy-eight…", language: "en", mode: "fixture", resume: 8, village_id: "v_reyes", pace: 3 }, toast: "Founding resumed at 8 of 10" });
    expect(presenterRequest("2", ctx)).toMatchObject({ path: "/villages/v_reyes/answers", body: { text: SCRIPT[1] } });
    expect(presenterRequest("p", ctx)?.path).toBe("/villages/v_reyes/evolve/trigger");
    expect(presenterRequest("a", ctx)).toMatchObject({ path: "/villages/v_reyes/proposals/prop_x/approve", toast: "Approved as Ana" });
    expect(presenterRequest("a", { ...ctx, pendingProposal: null })).toBeNull();
    expect(presenterRequest("u", ctx)).toMatchObject({ path: "/admin/demo-caller", body: { role: "unknown" } });
  });

  it("keys send Bearer-authenticated requests, toast for 1 s, ignore typing, V/D are room keys, U flips the caller", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn(async () => new Response("{}", { status: 200 }));
    const api: ApiConfig = { base: "http://core", token: "control", fake: true, fetchImpl: fetchImpl as any };
    const next = vi.fn();
    const det = vi.fn();
    const { container } = render(<div><input data-test="typing" /><PresenterLayer api={api} ctx={ctx} onNextVillage={next} onDetails={det} onReselect={() => {}} /></div>);
    await act(async () => { fireEvent.keyDown(window, { key: "1" }); });
    const [url, init] = (fetchImpl.mock.calls as any[])[0];
    expect(url).toBe("http://core/villages/v_reyes/answers");
    expect(init.headers.Authorization).toBe("Bearer control");
    expect(JSON.parse(init.body)).toEqual({ text: SCRIPT[0] });
    expect(container.querySelector("[data-test='presenter-toast']")?.textContent).toBe("Answer 10 sent");
    await tick(1100);
    expect(container.querySelector("[data-test='presenter-toast']")).toBeNull();
    await act(async () => { fireEvent.keyDown(container.querySelector("[data-test='typing']")!, { key: "f" }); });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    act(() => { fireEvent.keyDown(window, { key: "v" }); fireEvent.keyDown(window, { key: "d" }); });
    expect(next).toHaveBeenCalled();
    expect(det).toHaveBeenCalled();
    await act(async () => { fireEvent.keyDown(window, { key: "u" }); });
    await act(async () => { fireEvent.keyDown(window, { key: "u" }); });
    const roles = (fetchImpl.mock.calls as any[]).filter((c) => String(c[0]).endsWith("/admin/demo-caller")).map((c) => JSON.parse(c[1].body).role);
    expect(roles).toEqual(["unknown", "elder"]);
    fireEvent.mouseEnter(container.querySelector("[data-test='presenter-mark']")!);
    expect(container.querySelector("[data-test='key-map']")?.textContent).toContain("now: elder");
    act(() => { fireEvent.keyDown(window, { key: "Escape" }); });
    expect(container.querySelector("[data-test='key-map']")).toBeNull();
  });
});
