import { describe, expect, it, vi } from "vitest";
import { VillageSocket } from "../src/live/ws";

class MockSocket extends EventTarget {
  static instances: MockSocket[] = [];
  readyState = 0;
  sent: string[] = [];
  constructor(public url: string) {
    super();
    MockSocket.instances.push(this);
  }
  send(raw: string) { this.sent.push(raw); }
  close() { this.dispatchEvent(new CloseEvent("close")); }
  open() { this.dispatchEvent(new Event("open")); }
  message(frame: unknown) { this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(frame) })); }
}

describe("VillageSocket", () => {
  it("reconnects with last_rev and resyncs on patch rev gaps", () => {
    vi.useFakeTimers();
    (globalThis as any).WebSocket = MockSocket;
    const client = new VillageSocket({ url: "ws://test", village: "v_reyes", token: "mt", client: "test" });
    client.connect();
    const first = MockSocket.instances[0];
    first.open();
    first.message({ type: "snapshot", rev: 4, role: "helper", member_id: "m_marco", spec: { lang: "en", theme: "family", root: "s", elements: { s: { type: "Screen", props: { title: "x" } } } }, data: {}, now: "2026-10-16T14:00:00-04:00" });
    first.message({ type: "patch", base_rev: 3, rev: 5, ops: [] });
    expect(first.sent.some((raw) => JSON.parse(raw).last_rev === 4)).toBe(true);
    first.close();
    vi.advanceTimersByTime(500);
    const second = MockSocket.instances[1];
    second.open();
    expect(second.sent.some((raw) => JSON.parse(raw).last_rev === 4)).toBe(true);
    vi.useRealTimers();
  });
});
