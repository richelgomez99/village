import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ws from "../../contracts/fixtures/ws_sequence_scam.json";
import { MemberApp } from "../src/app/MemberApp";
import { makeSocket } from "../src/live/useLive";

const denied = (ws as any).sequences.denied;
const marcoResult = denied.find((f: any) => f.client === "marco" && f.msg.type === "result").msg;

function mount(fake: string, search: string) {
  const socket = makeSocket({ url: `ws://fake/${fake}`, village: "v_reyes", token: `mt_${fake}_offline_demo`, client: "kit", fake }, search);
  const utils = render(<MemberApp socket={socket} />);
  act(() => socket.connect());
  return { socket, ...utils };
}
const tick = (ms: number) => act(async () => { vi.advanceTimersByTime(ms); });

beforeEach(() => {
  vi.useFakeTimers();
  (window as any).__frames = [];
});
afterEach(() => vi.useRealTimers());

describe("scam replay through the fake server", () => {
  it("one replayed event updates all three clients, then the denied tail lands", async () => {
    const carmen = mount("carmen", "?start=0&tail=denied");
    const ana = mount("ana", "?start=0&tail=denied");
    const marco = mount("marco", "?start=0&tail=denied");
    await tick(50);
    // verification_pending event → alerts:active on every client
    expect(carmen.container.querySelector("[data-test='alert'][data-severity='warn']")?.textContent).toContain("No mande dinero todavía");
    expect(carmen.container.querySelector("[data-test='countdown']")).not.toBeNull();
    expect(ana.container.querySelector("[data-test='alert'][data-severity='warn']")?.textContent).toContain("Possible scam");
    expect(marco.container.querySelector("[data-test='verification-prompt']")).not.toBeNull();
    expect(marco.container.querySelector("[data-test='prompt-overlay']")?.textContent).toContain("Village is calling you · AI assistant");
    // countdown runs against the server clock (deadline 14:02:54, event at 14:02:09 → 45 s)
    expect(Number(carmen.container.querySelector("[data-test='countdown']")?.getAttribute("data-seconds"))).toBeGreaterThanOrEqual(44);
    await tick(12_500);
    expect(ana.container.querySelector("[data-test='incident-card']")?.getAttribute("data-verification-status")).toBe("denied");
    expect(marco.container.querySelector("[data-test='prompt-overlay']")).toBeNull();
    expect(carmen.container.querySelector("[data-test='alert'][data-severity='warn']")).toBeNull();
    // Ana acks → ack frame + acked state from the fixture
    act(() => ana.container.querySelector<HTMLButtonElement>("[data-test='incident-ack']")!.click());
    expect((window as any).__frames.find((f: any) => f.type === "ack")).toMatchObject({ event_id: "ev_1016_1402_incident", status: "got_it" });
    await tick(10);
    expect(ana.container.querySelector("[data-test='incident-acked']")).not.toBeNull();
  });

  it("Marco taps 'That wasn't me' → one action frame; thanks shows the gate's say.en", async () => {
    const marco = mount("marco", "?start=0");
    await tick(50);
    const no = marco.container.querySelector<HTMLButtonElement>("[data-test='verify-no']")!;
    act(() => no.click());
    const actions = (window as any).__frames.filter((f: any) => f.type === "action");
    expect(actions).toHaveLength(1);
    expect(actions[0]).toMatchObject({ name: "answer_verification", element_id: "vp", payload: { verification_id: "ver_1016_01", answer: "no" } });
    await tick(50);
    expect(marco.container.querySelector("[data-test='verify-thanks']")?.textContent).toBe(marcoResult.decision.say.en);
    expect(marco.container.querySelector("[data-test='prompt-overlay']")).toBeNull();
  });

  it("no answer → the timeout tail arrives on the fixture clock", async () => {
    const ana = mount("ana", "?start=0");
    await tick(50);
    await tick(36_000);
    expect(ana.container.querySelector("[data-test='incident-card']")?.textContent).toContain("Couldn't confirm");
  });

  it("view-as switches the coordinator to Carmen's app with buttons disabled", async () => {
    const ana = mount("ana", "?start=off");
    await tick(20);
    act(() => ana.container.querySelector<HTMLButtonElement>("[data-test='view-as-option'][data-member='m_carmen']")!.click());
    await tick(20);
    const app = ana.container.querySelector("[data-test='app']")!;
    expect(app.getAttribute("data-role")).toBe("elder");
    expect(app.getAttribute("data-view-as")).toBe("m_carmen");
    expect((window as any).__frames.filter((f: any) => f.type === "hello").at(-1)).toMatchObject({ view_as: "m_carmen" });
    const buttons = Array.from(ana.container.querySelectorAll<HTMLButtonElement>("[data-test='bigbutton']"));
    expect(buttons.length).toBe(3);
    expect(buttons.every((b) => b.disabled)).toBe(true);
    act(() => ana.container.querySelector<HTMLButtonElement>("[data-test='view-as-back']")!.click());
    await tick(20);
    expect(app.getAttribute("data-role")).toBe("coordinator");
  });
});
