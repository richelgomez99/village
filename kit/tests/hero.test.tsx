import { act, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../src/theme/floor.css";
import "../src/theme/a.css";

describe("hero screenshots (?hero=1)", () => {
  it("hides the dev chrome: clock warp, connection banner, view-as bar", async () => {
    vi.resetModules();
    history.replaceState(null, "", "/control.html?fake=control&seq=scam&hero=1");
    const { ControlRoom } = await import("../src/pages/control");
    const { makeSocket } = await import("../src/live/useLive");
    const cfg = { url: "ws://fake/control", village: "v_reyes", token: "ct_x_offline_demo_00", client: "control" as const, fake: "control" };
    const socket = makeSocket(cfg, "?start=off");
    const { container } = render(<ControlRoom socket={socket} cfg={cfg} api={{ base: "", token: "", fake: true }} />);
    await act(async () => { socket.connect(); await new Promise((r) => setTimeout(r, 20)); });
    const main = container.querySelector<HTMLElement>("[data-test='control']")!;
    expect(main.className).toContain("hero");
    expect(getComputedStyle(container.querySelector("[data-test='warp']")!).display).toBe("none");
    expect(getComputedStyle(container.querySelector(".view-as-bar")!).display).toBe("none");
    history.replaceState(null, "", "/");
  });
});
