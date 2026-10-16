import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiConfig } from "../src/control/api";
import { Transport } from "../src/dev/transport";
import { makeSocket, type LiveConfig } from "../src/live/useLive";
import { ControlRoom } from "../src/pages/control";

const cfg: LiveConfig = { url: "ws://fake/control", village: "v_reyes", token: "ct_x_offline_demo_00", client: "control", fake: "control" };
const api: ApiConfig = { base: "", token: "", fake: true };
const q = (c: HTMLElement, sel: string) => c.querySelector<HTMLElement>(sel);
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
function mount(search: string) {
  const socket = makeSocket(cfg, search);
  const utils = render(<ControlRoom socket={socket} cfg={cfg} api={api} />);
  act(() => socket.connect());
  return utils;
}
const tr = () => (window as any).__fake.transport as Transport;

afterEach(() => vi.useRealTimers());

describe("ROOM-5 transport", () => {
  it("Transport unit: step forward delivers one frame, step back rewinds with the prefix, scrub both ways, speed rescales", () => {
    vi.useFakeTimers();
    const got: any[] = [];
    const rewinds: any[] = [];
    const t = new Transport((m) => got.push(m), 1);
    t.initial = { type: "snapshot" };
    t.subscribe((e) => e.type === "rewind" && rewinds.push(e));
    t.load([{ ms: 0, msg: "a" }, { ms: 1000, msg: "b" }, { ms: 2000, msg: "c" }, { ms: 3000, msg: "d" }]);
    expect(got).toEqual(["a"]);
    vi.advanceTimersByTime(1000);
    expect(got).toEqual(["a", "b"]);
    t.step(1);
    expect(t.playing).toBe(false);
    expect(got).toEqual(["a", "b", "c"]);
    vi.advanceTimersByTime(5000);
    expect(got).toHaveLength(3); // paused
    t.step(-1);
    expect(t.index).toBe(2);
    expect(rewinds.at(-1)).toMatchObject({ initial: { type: "snapshot" }, frames: ["a", "b"] });
    t.seek(4);
    expect(got.slice(-2)).toEqual(["c", "d"]);
    t.seek(0);
    expect(rewinds.at(-1).frames).toEqual([]);
    t.setSpeed(4);
    t.play();
    vi.advanceTimersByTime(250);
    expect(got.at(-1)).toBe("b"); // 1000 ms of replay in 250 ms at 4×
  });

  it("bar: pause, step back rebuilds the scene from frame 0, step forward, scrub, keyboard; hidden in hero", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(17000);
    const bar = q(container, "[data-test='transport-bar']")!;
    expect(bar).not.toBeNull();
    expect(q(container, "[data-test='tr-beat']")?.textContent).toBe("RUN");
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
    const at = tr().index;
    expect(at).toBeGreaterThan(0);
    // ◀ steps back; scrub to the start of the call → the scene is rebuilt, the outcome undone
    act(() => q(container, "[data-test='tr-back']")!.click());
    expect(tr().playing).toBe(false);
    expect(tr().index).toBe(at - 1);
    // the first frame of Marco's "no" (the denial event comes just before the gate decision)
    const pending = tr().frames.findIndex((f) => (f.msg?.type === "event" && f.msg.event.kind === "verification_denied") || (f.msg?.type === "control" && f.msg.kind === "gate" && f.msg.payload.decision.verification?.state === "denied"));
    act(() => { fireEvent.change(q(container, "[data-test='tr-scrub']")!, { target: { value: String(pending) } }); });
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("pending");
    expect(container.querySelectorAll("[data-test='gate-row']")).toHaveLength(1);
    // ▶| delivers Marco's "no" again
    act(() => q(container, "[data-test='tr-forward']")!.click());
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
    // keyboard: ← back, → forward, space play
    act(() => { fireEvent.keyDown(window, { key: "ArrowLeft" }); });
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("pending");
    act(() => { fireEvent.keyDown(window, { key: "ArrowRight" }); });
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
    act(() => { fireEvent.keyDown(window, { key: " " }); });
    expect(tr().playing).toBe(true);
    // speed buttons
    act(() => q(container, "[data-test='tr-speed'][data-speed='2']")!.click());
    expect(tr().speed).toBe(2);
    expect(q(container, "[data-test='tr-pos']")?.textContent).toMatch(/^\d+\/\d+ · /);
    // scrub to 0: back to the bare snapshot (no call, nothing in the gate feed)
    act(() => { fireEvent.change(q(container, "[data-test='tr-scrub']")!, { target: { value: "0" } }); });
    expect(q(container, "[data-test='live-moment']")).toBeNull();
    expect(container.querySelectorAll("[data-test='gate-row']")).toHaveLength(0);
    expect(q(container, "[data-test='blueprint']")?.dataset.people).toBe("4");
  });

  it("founding replay: stepping back removes the last answer's block", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=founding");
    await tick(9000);
    const blocks = () => container.querySelectorAll("[data-test='work-block']").length;
    expect(blocks()).toBe(2);
    const lastAnswer = [...tr().frames.slice(0, tr().index)].map((f, i) => [f, i] as const).filter(([f]) => f.msg?.kind === "caption").at(-1)![1];
    act(() => tr().seek(lastAnswer));
    expect(blocks()).toBe(1);
    expect(q(container, "[data-test='tr-beat']")?.textContent).toBe("BUILD");
  });

  it("no transport bar without ?seq, nor in hero mode", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    expect(q(container, "[data-test='transport-bar']")).toBeNull();
  });
});
