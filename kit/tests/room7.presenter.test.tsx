import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import block from "../../contracts/fixtures/block_spec.json";
import { coordinatorTokenFromQr, coverLine, demoCast, moneyCallBody, thanksgivingLine } from "../src/control/presenter";

afterEach(() => {
  vi.useRealTimers();
  history.replaceState(null, "", "/");
});
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe("ROOM-7 presenter lines come from the spec", () => {
  it("money call body, cover line, Thanksgiving line, coordinator token from the QR", () => {
    const b = moneyCallBody(reyes, "v_reyes", 123);
    expect(b).toMatchObject({ conversation_id: "conv_stage_123", caller_id: "+18482579221", claimed_member: "m_marco", amount: 2000, method: "wire", urgency: "now", lang: "es", call_secs: 9 });
    expect(b.utterance).toBe("Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.");
    expect(coverLine(reyes)).toBe("I need someone to cover for Marco tomorrow");
    expect(thanksgivingLine(reyes)).toContain("Marco brings the turkey, Lucía brings the pie");
    expect(demoCast(block).coordName).toBe("Tanya");
    expect(coordinatorTokenFromQr([{ member_id: "m_ana", kind: "app", url: "https://x/v/v_reyes/?m=mt_ana_123" }], "m_ana")).toBe("mt_ana_123");
  });
});

describe("ROOM-7 presenter keys on the room", () => {
  it("M / S / T / L / W call Core; B opens the block replay with the transport bar and Esc comes back", async () => {
    vi.useFakeTimers();
    vi.resetModules();
    history.replaceState(null, "", "/control.html?t=control&presenter=1&ana=mt_ana_tok&secret=s3");
    const { ControlRoom } = await import("../src/pages/control");
    const { makeSocket } = await import("../src/live/useLive");
    const calls: { url: string; init: any }[] = [];
    const fetchImpl = vi.fn(async (url: string, init?: any) => {
      calls.push({ url, init });
      if (url.endsWith("/releases")) return new Response(JSON.stringify({ receipts: [{ id: "rel_r7", rev: 7, result: "released", created_at: "2026-10-16T13:39:28-04:00", stages: [{ name: "anchor_qa", status: "passed", details: { viewport: "390x844", video_url: "https://x/qa.mp4" } }, { name: "live", status: "passed", details: { summary: "published_rev 6 → 7 · approved by m_ana" } }] }] }), { status: 200 });
      if (url.endsWith("/admin/warm")) return new Response("no", { status: 405 });
      return new Response("{}", { status: 200 });
    });
    const cfg = { url: "ws://fake/control", village: "v_reyes", token: "control", client: "control" as const, fake: "control" };
    const socket = makeSocket(cfg, "?start=off");
    const { container } = render(<ControlRoom socket={socket} cfg={cfg} api={{ base: "http://core", token: "control", fake: false, fetchImpl: fetchImpl as any }} villages={["v_reyes", "v_w147"]} />);
    act(() => socket.connect());
    await tick(50);
    // presenter chrome: clock in words, no warp, no details button, the ⌨ mark
    expect(container.querySelector("[data-test='village-time']")?.textContent).toMatch(/· .*'s night$/);
    expect(container.querySelector("[data-test='warp']")).toBeNull();
    expect(container.querySelector("[data-test='details-toggle']")).toBeNull();
    expect(container.querySelector("[data-test='presenter-mark']")).not.toBeNull();
    await act(async () => { fireEvent.keyDown(window, { key: "m" }); });
    const money = calls.find((c) => c.url === "http://core/tools/report_money_request")!;
    expect(money.init.headers["X-Village-Secret"]).toBe("s3");
    expect(JSON.parse(money.init.body)).toMatchObject({ claimed_member: "m_marco", caller_id: "+18482579221" });
    expect(container.querySelector("[data-test='presenter-toast']")?.textContent).toBe("Carmen reported the call");
    await act(async () => { fireEvent.keyDown(window, { key: "s" }); });
    const s = calls.find((c) => c.url === "http://core/villages/v_reyes/messages")!;
    expect(s.init.headers.Authorization).toBe("Bearer mt_ana_tok");
    expect(JSON.parse(s.init.body)).toEqual({ text: "I need someone to cover for Marco tomorrow" });
    await act(async () => { fireEvent.keyDown(window, { key: "t" }); });
    expect(JSON.parse(calls.filter((c) => c.url.endsWith("/messages")).at(-1)!.init.body).mention).toBe("village");
    await act(async () => { fireEvent.keyDown(window, { key: "w" }); });
    expect(container.querySelector("[data-test='presenter-toast']")?.textContent).toBe("warm");
    await act(async () => { fireEvent.keyDown(window, { key: "l" }); });
    expect(container.querySelector("[data-test='receipt-video']")?.getAttribute("src")).toBe("https://x/qa.mp4");
    expect(container.querySelector("[data-test='receipt-approver']")?.textContent).toBe("approved by Ana");
    await act(async () => { fireEvent.keyDown(window, { key: "Escape" }); });
    expect(container.querySelector("[data-test='receipt-overlay']")).toBeNull();
    // B: the block founding replay in place, transport bar visible even in presenter mode; Esc → live again
    vi.stubGlobal("fetch", vi.fn(async () => new Response("nope", { status: 404 })));
    await act(async () => { fireEvent.keyDown(window, { key: "b" }); });
    await tick(50);
    expect(container.querySelector("[data-test='control']")?.getAttribute("data-village")).toBe("v_w147");
    expect(container.querySelector("[data-test='transport-bar']")).not.toBeNull();
    await act(async () => { fireEvent.keyDown(window, { key: "Escape" }); });
    await tick(50);
    expect(container.querySelector("[data-test='control']")?.getAttribute("data-village")).toBe("v_reyes");
    expect(container.querySelector("[data-test='transport-bar']")).toBeNull();
    vi.unstubAllGlobals();
  });
});
