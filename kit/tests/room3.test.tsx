import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiConfig } from "../src/control/api";
import { gateSentence, initialScene, sceneReducer, type SceneState } from "../src/control/scene";
import { makeSocket, type LiveConfig } from "../src/live/useLive";
import { ControlRoom } from "../src/pages/control";
import "../src/theme/a.css";

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
const ctl = (kind: string, payload: any, at = "2026-10-16T14:02:09-04:00") => ({ type: "control", kind, payload, at }) as any;

afterEach(() => vi.useRealTimers());

describe("ROOM-3", () => {
  it("arc strip lights the beat from frames: Run on the scam, Rebuild on a proposal, Anyone on the village switch", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(10);
    expect(Array.from(container.querySelectorAll("[data-test='arc-beat']")).map((b) => b.textContent)).toEqual(["Build", "Run", "Rebuild", "Anyone"]);
    await tick(2000);
    expect(q(container, "[data-test='arc-strip']")?.dataset.beat).toBe("run");
    act(() => q(container, "[data-test='arc-beat'][data-beat='anyone']")!.click());
    await tick(10);
    expect(q(container, "[data-test='control']")?.dataset.village).toBe("v_w147");
    expect(q(container, "[data-test='arc-strip']")?.dataset.beat).toBe("anyone");
    let s: SceneState = initialScene("v_reyes");
    s = sceneReducer(s, ctl("proposal", { proposal: { id: "prop_x", village: "v_reyes", title: { en: "t" }, status: "proposed" } }));
    expect(s.beat).toBe("rebuild");
    s = sceneReducer(s, ctl("blueprint", { village: "v_reyes", stage: "people", items: [] }));
    expect(s.beat).toBe("build");
  });

  it("autonomy headline from rounds:latest, each count opens its rows with role + mode chips", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    const h = q(container, "[data-test='autonomy-headline']")!;
    expect(h.querySelector(".headline")?.textContent).toBe("Tonight Village did 3 things on its own · asked a person 1 · refused itself 1");
    act(() => q(h, "[data-test='headline-refused']")!.click());
    const rows = h.querySelectorAll("[data-test='headline-row']");
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("Watcher");
    expect(rows[0].querySelector("[data-test='mode-chip']")?.getAttribute("data-mode")).toBe("refused");
    expect(rows[0].textContent).toContain("after 9:30 PM, no calls");
    // hidden until data exists
    const s = initialScene("v_x");
    expect(s.rounds.counts).toBeNull();
    const c2 = sceneReducer(s, ctl("counter", { name: "rounds_acted_alone", value: 2, label: "x" }));
    expect(c2.rounds.counts).toEqual({ acted_alone: 2, asked_human: 0, refused: 0 });
  });

  it("chat mirror shows Village posting the incident as it happens, Village bubble style", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(10);
    expect(container.querySelectorAll("[data-test='chat-mirror-row']")).toHaveLength(2);
    await tick(15000);
    const rows = Array.from(container.querySelectorAll<HTMLElement>("[data-test='chat-mirror-row']"));
    const inc = rows.find((r) => r.dataset.kind === "incident")!;
    expect(inc.className).toContain("village");
    expect(inc.textContent).toContain("Village stopped a money request");
    expect(rows.find((r) => r.dataset.kind === "chat")?.textContent).toContain("Marco");
    expect(q(container, "[data-test='chat-mirror']")?.textContent).not.toContain("m_marco");
  });

  it("decisions read as sentences; ids, rule ids and traces only behind details", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(17000);
    const sentences = Array.from(container.querySelectorAll("[data-test='gate-sentence']")).map((s) => s.textContent);
    expect(sentences[0]).toBe("Verifier · asked Marco · said no in 12 s · told her not to send money");
    expect(sentences[1]).toBe("Verifier · asked Marco · waiting for an answer");
    expect(q(container, "[data-test='gate-feed']")?.textContent).not.toMatch(/verify_with_member|advise_do_not_send|R-MONEY|dc_1016/);
    expect(q(container, "[data-test='details-ids']")).toBeNull();
    act(() => q(container, "[data-test='details-toggle']")!.click());
    expect(q(container, "[data-test='details-toggle']")?.getAttribute("aria-pressed")).toBe("true");
    expect(q(container, "[data-test='gate-feed']")?.textContent).toMatch(/R-MONEY-DEFAULT/);
    expect(q(container, "[data-test='gate-feed']")?.textContent).toMatch(/dc_1016_1402_denied/);
  });

  it("sentence dictionary falls back to words, never the raw name", () => {
    expect(gateSentence({ decision: "refuse_medical_advice" }, "", undefined, "x")).toBe("Verifier · didn't give medical advice · pointed to her doctor");
    expect(gateSentence({ decision: "some_new_thing" }, "", undefined, "x")).toBe("Verifier · some new thing");
  });
});
