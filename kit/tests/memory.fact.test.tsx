import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiConfig } from "../src/control/api";
import { MemberApp } from "../src/app/MemberApp";
import { FactHistoryCard, MEMORY_CAPTION, factTarget } from "../src/components/fact";
import { makeSocket, type LiveConfig } from "../src/live/useLive";
import { ControlRoom } from "../src/pages/control";
import "../src/theme/floor.css";

const q = (c: HTMLElement, sel: string) => c.querySelector<HTMLElement>(sel);
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const fake: ApiConfig = { base: "", token: "", fake: true };

afterEach(() => vi.useRealTimers());

describe("What Village knows (Agent Memory, D32)", () => {
  it("picks the fact from the data, never hard-coded: first prescription with a superseded dose", () => {
    expect(factTarget({})).toBeNull();
    expect(factTarget({ "prescriptions:current": { subject: "m_x", items: [{ name: "metformin" }, { name: "Warfarin Sodium", superseded: { dose_text: "2 mg" } }] } })).toEqual({ entity: "m_x", key: "warfarin_sodium_dose", med: "Warfarin Sodium" });
  });

  it("Control Room region: current 10 mg since Oct 3 (Dr. Park), struck 5 mg (Sep 1 → Oct 3), source chip with quote on tap, as-of re-query, exact caption", async () => {
    vi.useFakeTimers();
    const cfg: LiveConfig = { url: "ws://fake/control", village: "v_reyes", token: "ct_x_offline_demo_00", client: "control", fake: "control" };
    const socket = makeSocket(cfg, "?start=off");
    const { container } = render(<ControlRoom socket={socket} cfg={cfg} api={fake} />);
    act(() => socket.connect());
    await tick(300);
    await tick(300);
    const region = q(container, "[data-test='knows']")!;
    expect(region.dataset.entity).toBe("m_carmen");
    expect(region.dataset.key).toBe("lisinopril_dose");
    expect(q(region, "[data-test='fact-current']")?.textContent).toContain("10 mg");
    expect(q(region, "[data-test='fact-current']")?.textContent).toContain("since Oct 3");
    expect(q(region, "[data-test='fact-current']")?.textContent).toContain("Lisinopril is 10 mg since Oct 3 (Dr. Park).");
    const old = q(region, "[data-test='fact-superseded']")!;
    expect(old.querySelector("s")?.textContent).toBe("5 mg");
    expect(old.textContent).toContain("(Sep 1 → Oct 3)");
    const chip = q(region, "[data-test='fact-current'] [data-test='fact-source']")!;
    expect(chip.textContent).toBe("call conv_setup_0003 · 1:28");
    expect(q(region, "[data-test='fact-quote']")).toBeNull();
    act(() => chip.click());
    expect(q(region, "[data-test='fact-quote']")?.textContent).toBe("The doctor changed her lisinopril from five to ten on October third.");
    act(() => q(region, "[data-test='fact-asof-toggle'][data-asof='before']")!.click());
    await tick(300);
    expect(q(region, "[data-test='fact-asof-result']")?.textContent).toBe("as of Oct 2 → 5 mg");
    act(() => q(region, "[data-test='fact-asof-toggle'][data-asof='now']")!.click());
    expect(q(region, "[data-test='fact-asof-result']")).toBeNull();
    expect(q(region, "[data-test='knows-caption']")?.textContent).toBe("Typed · time-aware · supersedes rather than overwrites · traced to source · shared across agents (SurrealDB Agent Memory)");
    expect(MEMORY_CAPTION).toBe(q(region, "[data-test='knows-caption']")?.textContent);
  });

  it("calls the contract endpoints against Core: history, then facts?subject&key&as_of", async () => {
    vi.useFakeTimers();
    const history = {
      village: "v_reyes", entity: "m_carmen", key: "lisinopril_dose", degraded: false,
      versions: [
        { id: "f2", value: "10 mg", text: "Lisinopril is 10 mg since Oct 3 (Dr. Park).", observed_at: "2026-10-03T17:40:00-04:00", recorded_at: "2026-10-03T17:41:00-04:00", superseded: false, source: { kind: "call", ref: "conv_setup_0003", secs: 88, quote: "q" } },
        { id: "f1", value: "5 mg", text: "Lisinopril was 5 mg.", observed_at: "2026-09-01T10:00:00-04:00", recorded_at: "2026-10-03T17:41:00-04:00", superseded: true, source: { kind: "system", ref: "seed" } }
      ]
    };
    const fetchImpl = vi.fn(async (url: string) => {
      if (url.includes("/history")) return new Response(JSON.stringify(history), { status: 200 });
      return new Response(JSON.stringify({ village: "v_reyes", as_of: "x", degraded: false, facts: [{ ...history.versions[1], superseded: false, entity: "m_carmen", key: "lisinopril_dose" }] }), { status: 200 });
    });
    const api: ApiConfig = { base: "http://core", token: "mt_ana", fake: false, fetchImpl: fetchImpl as any };
    const { container } = render(<FactHistoryCard api={api} village="v_reyes" entity="m_carmen" factKey="lisinopril_dose" />);
    await tick(10);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("http://core/villages/v_reyes/facts/m_carmen/lisinopril_dose/history");
    act(() => q(container, "[data-test='fact-asof-toggle'][data-asof='before']")!.click());
    await tick(10);
    const asOfUrl = new URL(String((fetchImpl.mock.calls as any[])[1][0]));
    expect(asOfUrl.pathname).toBe("/villages/v_reyes/facts");
    expect(Object.fromEntries(asOfUrl.searchParams)).toEqual({ subject: "m_carmen", key: "lisinopril_dose", as_of: "2026-10-02T12:00:00-04:00" });
    expect(q(container, "[data-test='fact-asof-result']")?.textContent).toBe("as of Oct 2 → 5 mg");
  });

  it("Ana's phone: the refill card's changed dose opens a compact fact card", async () => {
    vi.useFakeTimers();
    const socket = makeSocket({ url: "ws://fake/ana", village: "v_reyes", token: "mt_ana_offline_demo", client: "kit", fake: "ana" }, "?start=off");
    const { container } = render(<MemberApp socket={socket} api={fake} />);
    act(() => socket.connect());
    await tick(10);
    const open = q(container, "[data-test='refill-card'] [data-test='fact-open']")!;
    expect(open.textContent).toBe("How Village knows ›");
    act(() => open.click());
    await tick(300);
    const card = q(container, "[data-test='fact-card']")!;
    expect(q(card, "[data-test='fact-current']")?.textContent).toContain("10 mg");
    expect(q(card, "[data-test='fact-superseded'] s")?.textContent).toBe("5 mg");
    expect(card.textContent).toContain(MEMORY_CAPTION);
  });

  it("no api (read-only mirrors) = no fact affordance", async () => {
    vi.useFakeTimers();
    const socket = makeSocket({ url: "ws://fake/ana", village: "v_reyes", token: "mt_ana_offline_demo", client: "kit", fake: "ana" }, "?start=off");
    const { container } = render(<MemberApp socket={socket} />);
    act(() => socket.connect());
    await tick(10);
    expect(q(container, "[data-test='fact-open']")).toBeNull();
  });
});
