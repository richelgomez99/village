import { afterEach, describe, expect, it, vi } from "vitest";
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

const view = { lang: "en", theme: "family", root: "s", elements: { s: { type: "Screen", props: { title: "x" }, children: [] } } };
const snapshot = (rev: number) => ({ type: "snapshot", contract_version: "1.3.1", rev, village: "v_reyes", role: "helper", member_id: "m_marco", spec: view, data: { a: 1 }, now: "2026-10-16T14:00:00-04:00" });

function client() {
  MockSocket.instances = [];
  return new VillageSocket({ url: "ws://test", village: "v_reyes", token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "test", WebSocketImpl: MockSocket as any, jitter: 0 });
}

afterEach(() => vi.useRealTimers());

describe("VillageSocket", () => {
  it("sends a contract hello, reconnects with backoff and last_rev", () => {
    vi.useFakeTimers();
    const c = client();
    c.connect();
    const first = MockSocket.instances[0];
    first.open();
    expect(first.sent[0]).toEqual({ type: "hello", contract_version: "1.3.1", village: "v_reyes", member_token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "test" });
    first.message(snapshot(4));
    expect(c.state.status).toBe("live");
    first.close();
    expect(c.state.status).toBe("reconnecting");
    vi.advanceTimersByTime(499);
    expect(MockSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    const second = MockSocket.instances[1];
    second.open();
    expect(second.sent[0].last_rev).toBe(4);
    second.close();
    vi.advanceTimersByTime(999);
    expect(MockSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(MockSocket.instances).toHaveLength(3);
  });

  it("applies patches only on matching base_rev, else re-hellos", () => {
    const c = client();
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    s.message(snapshot(4));
    s.message({ type: "patch", rev: 6, base_rev: 5, role: "helper", ops: [{ op: "add", path: "/elements/t", value: { type: "Text", props: { text: "hi" } } }] });
    expect(c.state.rev).toBe(4);
    expect(s.sent.at(-1)).toMatchObject({ type: "hello", last_rev: 4 });
    s.message({ type: "patch", rev: 5, base_rev: 4, role: "helper", ops: [{ op: "add", path: "/elements/t", value: { type: "Text", props: { text: "hi" } } }, { op: "add", path: "/elements/s/children/-", value: "t" }], highlight: ["t"] });
    expect(c.state.rev).toBe(5);
    expect(c.state.view?.elements.t.type).toBe("Text");
    expect(c.state.highlight).toEqual(["t"]);
  });

  it("merges event data; contract_mismatch → 'Updating…', SW update, one re-hello; a second mismatch stops", async () => {
    vi.useFakeTimers();
    MockSocket.instances = [];
    let updates = 0;
    const c = new VillageSocket({ url: "ws://test", village: "v_reyes", token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "test", WebSocketImpl: MockSocket as any, jitter: 0, onUpdate: async () => { updates++; } });
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    s.message(snapshot(4));
    s.message({ type: "event", event: { id: "ev_x_123", kind: "ack", at: "2026-10-16T14:00:05-04:00" }, data: { b: 2, a: null } });
    expect(c.state.data).toEqual({ a: null, b: 2 });
    const hellos = () => s.sent.filter((f) => f.type === "hello").length;
    expect(hellos()).toBe(1);
    s.message({ type: "error", code: "contract_mismatch", message: "1.0.0 != 1.1.0" });
    expect(c.state.status).toBe("updating");
    await vi.advanceTimersByTimeAsync(10);
    expect(updates).toBe(1);
    expect(hellos()).toBe(2);
    s.message({ type: "error", code: "contract_mismatch", message: "1.0.0 != 1.1.0" });
    expect(c.state.status).toBe("closed");
    vi.advanceTimersByTime(20000);
    expect(MockSocket.instances).toHaveLength(1);
  });

  it("re-hellos within 2 s even if the service worker update hangs", async () => {
    vi.useFakeTimers();
    MockSocket.instances = [];
    const c = new VillageSocket({ url: "ws://test", village: "v_reyes", token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "test", WebSocketImpl: MockSocket as any, onUpdate: () => new Promise(() => {}) });
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    s.message({ type: "error", code: "contract_mismatch", message: "x" });
    await vi.advanceTimersByTimeAsync(1999);
    expect(s.sent.filter((f) => f.type === "hello")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(2);
    expect(s.sent.filter((f) => f.type === "hello")).toHaveLength(2);
    s.message(snapshot(4));
    expect(c.state.status).toBe("live");
  });

  it("maps result frames to the action's element", () => {
    const c = client();
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    s.message(snapshot(4));
    const req = c.action({ name: "answer_verification", element_id: "vp", payload: { verification_id: "ver_1016_01", answer: "no" } });
    expect(req).toBe("r_marco_0001");
    expect(c.state.results.answer_verification).toBe("pending");
    s.message({ type: "result", req_id: req, ok: true, decision: { say: { es: "a", en: "b" } } });
    expect(c.state.results.answer_verification).toMatchObject({ ok: true, say: { en: "b" } });
  });

  it("pings and drops a dead socket", () => {
    vi.useFakeTimers();
    MockSocket.instances = [];
    const c = new VillageSocket({ url: "ws://t", village: "v_reyes", token: "mt_marco_9Qe2vLx7Rk3pZ0aB", client: "test", WebSocketImpl: MockSocket as any, jitter: 0, pingMs: 1000, deadMs: 500 });
    c.connect();
    const s = MockSocket.instances[0];
    s.open();
    vi.advanceTimersByTime(1000);
    expect(s.sent.at(-1).type).toBe("ping");
    vi.advanceTimersByTime(500);
    expect(c.state.status).toBe("reconnecting");
  });
});
