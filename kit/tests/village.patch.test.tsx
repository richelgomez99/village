import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { MemberApp } from "../src/app/MemberApp";
import { liveConfig, persistMember } from "../src/live/useLive";
import { VillageSocket } from "../src/live/ws";

class MockSocket extends EventTarget {
  static instances: MockSocket[] = [];
  readyState = 0;
  sent: any[] = [];
  constructor(public url: string) {
    super();
    MockSocket.instances.push(this);
  }
  send(raw: string) { this.sent.push(JSON.parse(raw)); }
  close() { this.readyState = 3; this.dispatchEvent(new Event("close")); }
  open() { this.readyState = 1; this.dispatchEvent(new Event("open")); }
  message(frame: unknown) { this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(frame) })); }
}

const snap = (role: "elder" | "helper", rev = 5, village = "v_reyes") => ({
  type: "snapshot", contract_version: "1.3.2", rev, village, role, member_id: role === "elder" ? "m_carmen" : "m_marco",
  spec: (reyes as any).views[role], data: {}, now: "2026-10-16T20:50:00-04:00"
});

function client(url = "ws://core/ws?village=&m=mt_marco_9Qe2vLx7Rk3pZ0aB", village = "") {
  MockSocket.instances = [];
  return new VillageSocket({ url, village, token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "kit", WebSocketImpl: MockSocket as any, jitter: 0 });
}

// the ops core/evolve/proposals.py build_ops sends for the receptionist proposal (elder: Text at index 1; others: Text + Timeline)
const ELDER_OPS = [
  { op: "add", path: "/elements/receptionist", value: { type: "Text", props: { text: "Village contesta primero las llamadas desconocidas. Su familia entra directo.", size: "l", tone: "ok" } } },
  { op: "add", path: "/elements/s/children/1", value: "receptionist" }
];
const HELPER_OPS = [
  { op: "add", path: "/elements/receptionist", value: { type: "Text", props: { text: "Village answers unknown calls for Mamá first and checks with the real person before putting them through.", size: "m", tone: "info" } } },
  { op: "add", path: "/elements/s/children/1", value: "receptionist" },
  { op: "add", path: "/elements/screened", value: { type: "Timeline", props: { title: "Calls Village screened", bind: "timeline:subject=m_carmen", subject: "m_carmen", event_kinds: ["money_request", "verification", "incident"], show_provenance: true, limit: 5 } } },
  { op: "add", path: "/elements/s/children/2", value: "screened" }
];

afterEach(() => {
  vi.useRealTimers();
  try { localStorage.clear(); } catch { /* ignore */ }
});

describe("village id travels with the token", () => {
  it("learns the village from the snapshot: hello and the reconnect URL always carry it", () => {
    vi.useFakeTimers();
    const c = client();
    c.connect();
    const s0 = MockSocket.instances[0];
    s0.open();
    s0.message(snap("helper"));
    s0.close();
    vi.advanceTimersByTime(600);
    const s1 = MockSocket.instances[1];
    expect(s1.url).toBe("ws://core/ws?village=v_reyes&m=mt_marco_9Qe2vLx7Rk3pZ0aB");
    s1.open();
    expect(s1.sent[0]).toMatchObject({ type: "hello", village: "v_reyes", last_rev: 5 });
  });

  it("persists the village next to the token and in the URL; liveConfig reads it back for that token only", () => {
    history.replaceState(null, "", "/?m=mt_marco_9Qe2vLx7Rk3pZ0aB");
    persistMember("mt_marco_9Qe2vLx7Rk3pZ0aB", "v_reyes");
    expect(localStorage.getItem("village_id")).toBe("v_reyes");
    expect(new URLSearchParams(location.search).get("village")).toBe("v_reyes");
    history.replaceState(null, "", "/");
    const cfg = liveConfig("kit", location);
    expect(cfg.village).toBe("v_reyes");
    expect(cfg.url).toContain("village=v_reyes&m=mt_marco_9Qe2vLx7Rk3pZ0aB");
    // a different member's link (?m=) never inherits the stored village
    history.replaceState(null, "", "/?m=mt_someone_else_000000");
    expect(liveConfig("kit", location).village).toBe("");
  });
});

describe("approve → release → patch{base_rev, ops} per role", () => {
  it("elder applies its own role's receptionist ops at base_rev, highlighted NEW, no reconnect", () => {
    const c = client("ws://core/ws?village=v_reyes&m=x", "v_reyes");
    const { container } = render(<MemberApp socket={c} />);
    act(() => c.connect());
    const s = MockSocket.instances[0];
    act(() => s.open());
    act(() => s.message(snap("elder")));
    act(() => s.message({ type: "patch", rev: 6, base_rev: 5, role: "elder", ops: ELDER_OPS, proposal_id: "prop_reyes_receptionist_1", highlight: ["receptionist"] }));
    expect(c.state.rev).toBe(6);
    expect(c.state.view?.elements.s.children?.[1]).toBe("receptionist");
    const el = container.querySelector("[data-id='receptionist']")!;
    expect(el.getAttribute("data-new")).toBe("true");
    expect(el.textContent).toContain("Village contesta primero");
    expect(container.querySelector("[data-test='unknown-types']")?.getAttribute("data-count")).toBe("0");
    expect(container.querySelector("[data-test='invalid-props']")?.getAttribute("data-count")).toBe("0");
    expect(MockSocket.instances).toHaveLength(1);
    expect(s.sent.filter((f) => f.type === "hello")).toHaveLength(1);
  });

  it("helper applies its ops (Text + Timeline) and renders both", () => {
    const c = client("ws://core/ws?village=v_reyes&m=x", "v_reyes");
    const { container } = render(<MemberApp socket={c} />);
    act(() => c.connect());
    const s = MockSocket.instances[0];
    act(() => s.open());
    act(() => s.message(snap("helper")));
    act(() => s.message({ type: "patch", rev: 6, base_rev: 5, role: "helper", ops: HELPER_OPS, highlight: ["receptionist", "screened"] }));
    expect(c.state.rev).toBe(6);
    expect(container.querySelector("[data-id='screened'] [data-test='timeline']")).not.toBeNull();
    expect(container.querySelector("[data-test='invalid-props']")?.getAttribute("data-count")).toBe("0");
  });

  it("a patch for another role or a stale base_rev is not applied: the client re-hellos for a fresh snapshot", () => {
    const c = client("ws://core/ws?village=v_reyes&m=x", "v_reyes");
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    s.message(snap("elder"));
    s.message({ type: "patch", rev: 6, base_rev: 5, role: "helper", ops: HELPER_OPS });
    expect(c.state.rev).toBe(5);
    expect(c.state.view?.elements.screened).toBeUndefined();
    expect(s.sent.at(-1)).toMatchObject({ type: "hello", village: "v_reyes", last_rev: 5 });
    s.message({ type: "patch", rev: 8, base_rev: 7, role: "elder", ops: ELDER_OPS });
    expect(c.state.rev).toBe(5);
    expect(s.sent.filter((f) => f.type === "hello")).toHaveLength(3);
  });
});
