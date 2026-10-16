import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiConfig } from "../src/control/api";
import { makeSocket, type LiveConfig } from "../src/live/useLive";
import { ControlRoom } from "../src/pages/control";

const q = (c: HTMLElement, sel: string) => c.querySelector<HTMLElement>(sel);
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

afterEach(() => vi.useRealTimers());

describe("ROOM-4: live Control Room bootstrap (no ?fake, no ?village)", () => {
  it("GET /villages builds the pills, the first village is selected and populated, decisions backfill from Core", async () => {
    vi.useFakeTimers();
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (url: string, init?: any) => {
      calls.push(`${init?.method ?? "GET"} ${url} ${init?.headers?.Authorization ?? ""}`);
      if (url.endsWith("/villages")) return new Response(JSON.stringify([{ id: "v_reyes", name: "Familia Reyes", status: "active", kind: "care", rev: 6 }, { id: "v_w147", name: "West 147th Block — Heat & Blackout", status: "active", kind: "block", rev: 2 }]), { status: 200 });
      if (url.includes("/villages/v_reyes/decisions")) return new Response(JSON.stringify({ decisions: [{ id: "dc_evolve_1", village_id: "v_reyes", at: "2026-10-16T13:25:33-04:00", actor: "evolve", kind: "decision", text: "Weighed 3 fixes; chose the unknown-caller receptionist.", mode: "asked_human", refs: [] }] }), { status: 200 });
      if (url.includes("/decisions")) return new Response(JSON.stringify({ decisions: [] }), { status: 200 });
      return new Response("[]", { status: 404 });
    });
    const api: ApiConfig = { base: "http://core", token: "control", fake: false, fetchImpl: fetchImpl as any };
    // the page's own socket has no village; the room opens one control socket per village (here: the offline fake)
    const cfg: LiveConfig = { url: "ws://core/ws?village=&m=control", village: "", token: "control", client: "control", fake: null };
    const spawn = (o: { village: string }) => makeSocket({ url: "ws://fake/control", village: o.village, token: "control", client: "control", fake: "control" }, "?start=off", { fakeOverrides: { quiet: true } });
    const socket = makeSocket(cfg, "");
    const { container } = render(<ControlRoom socket={socket} cfg={cfg} api={api} spawn={spawn} />);
    await tick(50);
    expect(calls[0]).toBe("GET http://core/villages Bearer control");
    expect(Array.from(container.querySelectorAll("[data-test='village-tab']")).map((t) => t.getAttribute("data-village"))).toEqual(["v_reyes", "v_w147"]);
    await tick(50);
    expect(q(container, "[data-test='control']")?.dataset.village).toBe("v_reyes");
    expect(q(container, "[data-test='founding-empty']")).toBeNull();
    expect(q(container, "[data-test='blueprint']")?.dataset.people).toBe("4");
    expect(container.querySelectorAll("[data-test='phone']")).toHaveLength(3);
    expect(q(container, "[data-test='arc-strip']")?.dataset.beat).toBe("run");
    expect(Array.from(container.querySelectorAll("[data-test='decision-row']")).some((r) => r.textContent?.includes("Weighed 3 fixes"))).toBe(true);
    expect(q(container, "[data-test='autonomy-headline']")).not.toBeNull();
    expect(q(container, "[data-test='chat-mirror']")).not.toBeNull();
    // switching re-keys: the block room, its own decisions
    act(() => q(container, "[data-test='village-tab'][data-village='v_w147']")!.click());
    await tick(50);
    expect(q(container, "[data-test='control']")?.dataset.village).toBe("v_w147");
    expect(container.textContent).not.toContain("Weighed 3 fixes");
    // only "+ New village" opens the empty founding room
    act(() => q(container, "[data-test='new-village']")!.click());
    expect(q(container, "[data-test='founding-empty']")).not.toBeNull();
  });
});
