// kit-members: tabs from life areas (both fixtures), chat kinds, refill-day rule, Lucía without prompts, names not ids.
import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import block from "../../contracts/fixtures/block_spec.json";
import seed from "../../contracts/fixtures/messages_reyes_seed.json";
import { MemberApp } from "../src/app/MemberApp";
import { TabbedApp, rightNowLines } from "../src/app/TabbedApp";
import { planTabs } from "../src/app/tabs";
import { makeSocket } from "../src/live/useLive";
import { defaultCtx, type RenderCtx } from "../src/renderer/context";
import { viewSchema } from "../src/renderer/view";
import { chipLabel } from "../src/components/generic";
import { PRESCRIPTIONS, ROUNDS } from "../src/dev/fixtureData";
import { renderView } from "./helpers";

const R = reyes as any;
const B = block as any;
const view = (spec: any, role: string) => viewSchema.parse(spec.views[role]);
const areasData = (spec: any) => ({ "blueprint:life_areas": spec.blueprint.life_areas.map((a: any) => ({ id: a.id, label: a.label, status: "ok", need_ids: a.need_ids })) });

function mount(fake: string, search = "?start=off") {
  const socket = makeSocket({ url: `ws://fake/${fake}`, village: "v_reyes", token: `mt_${fake}_offline_demo`, client: "kit", fake }, search);
  const utils = render(<MemberApp socket={socket} />);
  act(() => socket.connect());
  return { socket, ...utils };
}
afterEach(() => vi.useRealTimers());

describe("tabs from life areas (generic)", () => {
  it("Reyes coordinator: Home + the areas its elements serve, in spec order, + Chat", () => {
    const p = planTabs(view(R, "coordinator"), areasData(R), "en");
    expect(p.areas.map((a) => a.id)).toEqual(["health", "money", "people"]);
    expect(p.areas.map((a) => a.label)).toEqual(["Health", "Money", "People"]);
    expect(p.headline).toBe("rn");
    expect(p.chat).toBe("chat");
    expect(p.attention).toEqual(["al", "prop", "inc", "vp"]);
  });
  it("localized labels from the spec's label_i18n when given", () => {
    const p = planTabs(view(R, "coordinator"), {}, "es", R.blueprint);
    expect(p.areas.map((a) => a.label)).toEqual(["Salud", "Dinero", "Familia"]);
  });
  it("Reyes helper serves fewer than two areas on its own tabs: Home + Chat only", () => {
    const p = planTabs(view(R, "helper"), areasData(R), "en");
    expect(p.areas).toEqual([]);
    expect(p.headline).toBe("ans");
    expect(p.chat).toBe("chat");
  });
  it("block coordinator: same code, the block's own areas (Health · Information) + Chat", () => {
    const p = planTabs(view(B, "coordinator"), areasData(B), "en");
    expect(p.areas.map((a) => a.id)).toEqual(["health", "information"]);
    expect(p.headline).toBe("st");
    expect(p.chat).toBe("chat");
  });
  it("block volunteer: Home + Chat", () => {
    const p = planTabs(view(B, "volunteer"), areasData(B), "en");
    expect(p.areas).toEqual([]);
    expect(p.chat).toBe("chat");
  });
  it("no need → area map from Core: everything stays on Home (graceful)", () => {
    const p = planTabs(view(R, "coordinator"), { "blueprint:life_areas": [{ id: "health", label: "Health", status: "ok" }] }, "en");
    expect(p.areas).toEqual([]);
    expect(p.homeRest.length).toBeGreaterThan(3);
  });
  it("Ana's app via the fake: bottom nav Home · <area labels from Core> · Chat, Right now, What Village did", async () => {
    vi.useFakeTimers();
    const { container } = mount("ana");
    await act(async () => { vi.advanceTimersByTime(10); });
    const tabs = [...container.querySelectorAll("[data-test='nav-tab']")].map((b) => b.textContent);
    expect(tabs).toEqual(["Home", "Pills", "Money", "People", "Chat"]); // labels are whatever blueprint:life_areas says
    expect(container.querySelectorAll("[data-test='right-now-line']").length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector("[data-test='wvd-counts']")?.textContent).toContain("Did 3 things on its own · asked a person 1 · refused itself 1");
    expect(container.querySelector("[data-test='chat-preview']")).not.toBeNull();
    act(() => (container.querySelector("[data-tab='chat'][data-test='nav-tab']") as HTMLButtonElement).click());
    expect(container.querySelector("[data-test='tab-chat']")?.hasAttribute("hidden")).toBe(false);
    expect(container.querySelector("[data-test='tab-home']")?.hasAttribute("hidden")).toBe(true);
  });
  it("elder views get no nav", async () => {
    vi.useFakeTimers();
    const { container } = mount("carmen");
    await act(async () => { vi.advanceTimersByTime(10); });
    expect(container.querySelector("[data-test='bottom-nav']")).toBeNull();
  });
});

describe("chat kinds (D16)", () => {
  const rows = (seed as any).messages;
  it("renders each kind distinctly, names from member records, chips in words (no rule ids)", () => {
    const relayed = { id: "msg_relay", village: "v_reyes", author: "village", kind: "incident", text: "She said her grandson called.", text_i18n: { es: "Dijo que llamó su nieto.", en: "She said her grandson called." }, refs: [{ kind: "event", id: "ev_x", label: "her call, 0:09" }], source: { kind: "call", ref: "conv_1" }, at: "2026-10-16T14:03:00-04:00" };
    const data = { "chat:village": [...rows, relayed], "member:m_marco": { member_id: "m_marco", name: "Marco" }, "member:m_lucia": { member_id: "m_lucia", name: "Lucía" }, "member:m_ana": { member_id: "m_ana", name: "Ana" } };
    const { container } = renderView(R.views.coordinator, data, { memberId: "m_ana" });
    const chat = container.querySelector("[data-test='village-chat']")!;
    const kinds = new Set([...chat.querySelectorAll("[data-test='chat-row']")].map((r) => r.getAttribute("data-render")));
    for (const k of ["nudge", "chat", "incident", "proposal", "answer", "receipt", "relayed"]) expect(kinds.has(k), k).toBe(true);
    const authors = [...chat.querySelectorAll("[data-test='chat-author']")].map((a) => a.textContent);
    expect(authors).toContain("Marco");
    expect(authors).toContain("Lucía");
    expect(authors).toContain("Village");
    expect(chat.textContent).not.toMatch(/\bm_[a-z]+/);
    expect(chat.textContent).not.toMatch(/R-MONEY|ev_|dc_/);
    expect(chat.querySelector("[data-render='relayed'] q")?.textContent).toBe("Dijo que llamó su nieto.");
    expect(chat.querySelector("[data-test='chat-proposal-approve']")).not.toBeNull();
    expect(chat.querySelector("[data-test='chat-composer']")).not.toBeNull();
  });
  it("chip labels that carry ids fall back to plain words", () => {
    expect(chipLabel({ kind: "decision", label: "rule R-MONEY-VERIFY" })).toBe("Village's reasoning");
    expect(chipLabel({ kind: "event", label: "her call, 0:09" })).toBe("her call, 0:09");
  });
  it("composer: @Village chip + optimistic append", () => {
    const { container } = renderView(R.views.helper, { "chat:village": rows.slice(0, 2) }, { memberId: "m_marco" });
    fireEvent.click(container.querySelector("[data-test='chat-mention']")!);
    const input = container.querySelector<HTMLInputElement>("[data-test='chat-input']")!;
    expect(input.value).toBe("@Village ");
    fireEvent.change(input, { target: { value: "@Village can someone swap Friday?" } });
    fireEvent.submit(container.querySelector("[data-test='chat-composer']")!);
    const last = [...container.querySelectorAll("[data-test='chat-row']")].pop()!;
    expect(last.textContent).toContain("can someone swap Friday?");
    expect(last.getAttribute("data-pending")).toBe("true");
  });
});

describe("refill-day rule (D22)", () => {
  const fri = Date.parse("2026-10-16T14:00:00-04:00");
  const thu = Date.parse("2026-10-15T14:00:00-04:00");
  const data = { "prescriptions:current": PRESCRIPTIONS };
  it("owner on refill day: the checklist", () => {
    const { container } = renderView(R.views.helper, data, { memberId: "m_marco", nowMs: () => fri });
    expect(container.querySelector("[data-test='refill-card']")).not.toBeNull();
  });
  it("owner on another day: one line", () => {
    const { container } = renderView(R.views.helper, data, { memberId: "m_marco", nowMs: () => thu });
    expect(container.querySelector("[data-test='refill-card']")).toBeNull();
    expect(container.querySelector("[data-test='refill-line']")?.textContent).toBe("Refill Friday · you");
  });
  it("not the owner: always the checklist", () => {
    const { container } = renderView(R.views.coordinator, data, { memberId: "m_ana", nowMs: () => thu });
    expect(container.querySelector("[data-test='refill-card']")).not.toBeNull();
  });
});

describe("Marco and Lucía", () => {
  it("Marco: Yes · tonight headline, Since your last turn, Swap my night prefills the chat", async () => {
    vi.useFakeTimers();
    const { container } = mount("marco");
    await act(async () => { vi.advanceTimersByTime(10); });
    expect(container.querySelector("[data-test='helper-headline']")?.textContent).toBe("Yes · tonight until 9:30");
    expect(container.querySelectorAll("[data-test='since-row']").length).toBe(3);
    act(() => (container.querySelector("[data-test='swap-my-night']") as HTMLButtonElement).click());
    expect(container.querySelector("[data-test='tab-chat']")?.hasAttribute("hidden")).toBe(false);
    expect(container.querySelector<HTMLInputElement>("[data-test='tab-chat'] [data-test='chat-input']")?.value).toBe("@Village can someone swap Friday?");
  });
  it("Lucía never sees a verification prompt; no ids on her screen", async () => {
    vi.useFakeTimers();
    const { container } = mount("lucia", "?start=0");
    await act(async () => { vi.advanceTimersByTime(20_000); });
    expect(container.querySelector("[data-test='prompt-overlay']")).toBeNull();
    const vp = container.querySelector("[data-test='verification-prompt']");
    expect(vp === null || vp.closest("[hidden]") !== null).toBe(true);
    expect(container.querySelector("[data-test='helper-headline']")?.textContent).toMatch(/^No · Marco tonight · you're on Saturday/);
    expect(container.querySelector("[data-test='screen']")?.textContent).not.toMatch(/\bm_[a-z]+/);
  });
});

describe("home brief pieces", () => {
  it("Right now lines from rota, pills, timeline", () => {
    const lines = rightNowLines({
      "rota:week": [{ date: "2026-10-16", day: "Fri", on_duty: "m_marco", backup: "m_ana" }],
      "member:m_marco": { name: "Marco" },
      "facts:dose_event?subject=m_carmen&valid_at=today": { date: "2026-10-16", slots: [{ slot: "morning", status: "taken" }, { slot: "evening", status: "upcoming" }] }
    }, Date.parse("2026-10-16T14:00:00-04:00"), "en");
    expect(lines.map((l) => l.text)).toEqual(["Tonight: Marco", "Pills today: 1 of 2 taken · evening still to come"]);
  });
  it("view-as: buttons say view only", () => {
    const ctx: RenderCtx = { ...defaultCtx, view: viewSchema.parse(R.views.helper), data: { "rounds:latest": ROUNDS }, lang: "en", disabled: true };
    const { container } = render(<TabbedApp ctx={ctx} />);
    expect(container.querySelector("[data-test='view-only']")?.textContent).toBe("View only");
  });
});

describe("rounds:latest absent or empty", () => {
  it("{} (no round yet) hides What Village did", () => {
    const ctx: RenderCtx = { ...defaultCtx, view: viewSchema.parse(R.views.coordinator), data: { "rounds:latest": {} }, lang: "en" };
    const { container } = render(<TabbedApp ctx={ctx} />);
    expect(container.querySelector("[data-test='what-village-did']")).toBeNull();
  });
});

describe("1.3.2 catalog types", () => {
  const v = (elements: Record<string, unknown>, children: string[]) => ({ lang: "en", theme: "dashboard", root: "s", elements: { s: { type: "Screen", props: { title: "T" }, children }, ...elements } });
  it("PlanBoard, ScreenedCalls, FactCard (written by + caption) render from their binds, names not ids", () => {
    const { container } = renderView(v({
      pb: { type: "PlanBoard", props: { bind: "plan:thanksgiving", title: "Thursday" } },
      sc: { type: "ScreenedCalls", props: { bind: "calls:screened", title: "Calls Village answered" } },
      fc: { type: "FactCard", props: { bind: "facts:history?subject=m_carmen&key=lisinopril_dose", title: "Lisinopril" } }
    }, ["pb", "sc", "fc"]), {
      "member:m_marco": { name: "Marco" },
      "plan:thanksgiving": { items: [{ text: "Pick up Mamá", owner: "m_marco", when: "2 PM", status: "claimed", kind: "pickup" }, { text: "Pie", status: "open", kind: "need" }] },
      "calls:screened": [{ at: "2026-10-16T14:02:00-04:00", claimed: "Marco", outcome: "refused", verified_by: "m_marco" }],
      "facts:history?subject=m_carmen&key=lisinopril_dose": { versions: [{ value: "10 mg", text: "10 mg", superseded: false, labels: { agent: "founder" }, source: { kind: "call" } }, { value: "5 mg", superseded: true, source: { kind: "seed" } }] }
    });
    expect(container.querySelectorAll("[data-test='plan-item']").length).toBe(2);
    expect(container.querySelector("[data-test='plan-board']")?.textContent).toContain("Marco");
    expect(container.querySelector("[data-test='screened-row']")?.textContent).toContain("refused");
    expect([...container.querySelectorAll("[data-test='fact-written-by']")].map((e) => e.textContent?.trim())).toEqual(["written by Founder", "written by seed"]);
    expect(container.querySelector("[data-test='fact-caption']")?.textContent).toContain("shared across agents");
    expect(container.textContent).not.toMatch(/\bm_[a-z]+/);
  });
});

describe("kit-members-2 fixes", () => {
  it("chat sorts by time; a call source reads in words", async () => {
    const { byTime } = await import("../src/components/generic");
    const rows = [
      { id: "b", kind: "chat", author: "m_marco", text: "x", at: "2026-10-16T13:55:00-04:00" },
      { id: "a", kind: "nudge", author: "village", text: "y", at: "2026-10-16T13:32:00-04:00", refs: [{ kind: "event", id: "ev_1" }], source: { kind: "call", ref: "conv_1" } }
    ];
    expect(byTime(rows as any).map((r) => r.id)).toEqual(["a", "b"]);
    const { container } = renderView(R.views.helper, { "chat:village": rows }, { memberId: "m_marco" });
    const chips = [...container.querySelectorAll("[data-test='village-chat'] [data-test='chat-chip']")].map((c) => c.textContent);
    expect(chips).toContain("from her check-in call");
    expect(container.querySelector("[data-test='village-chat'] [data-test='chat-row']")?.getAttribute("data-kind")).toBe("nudge");
  });
  it("incident provenance in words, never a raw ref", async () => {
    const { sourceWords } = await import("../src/components/shared");
    expect(sourceWords({ kind: "call", ref: "conv_seed_1009", secs: 21 }, "2026-10-09T19:21:40-04:00", { "member:m_carmen": { short_name: "Mamá" } }, "m_carmen")).toBe("Mamá's call · Oct 9, 7:21 PM · 21 s in");
  });
  it("rounds rows carry their time in words", async () => {
    const { whenWords } = await import("../src/components/brief");
    expect(whenWords("2026-10-15T21:40:00-04:00", Date.parse("2026-10-16T14:00:00-04:00"))).toBe("last night 9:40 PM");
  });
  it("an acknowledged incident is not under Needs your yes", () => {
    const inc = { incident_id: "inc_1", type: "money_request", severity: "high", status: "acked", title: "Scam call", summary: "Nothing sent", at: "2026-10-16T14:02:00-04:00", provenance: [] };
    const ctx: RenderCtx = { ...defaultCtx, view: viewSchema.parse(R.views.coordinator), data: { ...areasData(R), "incidents:open": [inc] }, lang: "en" };
    const { container } = render(<TabbedApp ctx={ctx} />);
    expect(container.querySelector("[data-test='needs-your-yes']")?.hasAttribute("hidden")).toBe(true);
    expect(container.querySelector("[data-test='tab-money'] [data-test='incident-card']")).not.toBeNull();
  });
});
