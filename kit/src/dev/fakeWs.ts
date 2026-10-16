// In-browser fake Core: ?fake=carmen|ana|marco|lucia|control. Sends the role's snapshot (reyes_spec.json + fixture data,
// D22 overlay), then replays ws_sequence_scam.json: `start` after ?start=<s> (default 2; "off" = wait for window.__fake.play),
// then the tail: ?tail=denied|timeout_tail|confirmed_tail, or — without ?tail — whatever Marco answers (any tab, via
// BroadcastChannel), else timeout_tail at the fixture's own times. ?speed=<x> scales time. Every sent frame is on window.__frames.
import { FAKE_CLIENTS, clientForMember, fakeSnapshot, sequence, type FakeClient, type SeqFrame } from "./fixtureData";

type Tail = "denied" | "timeout_tail" | "confirmed_tail";

export interface FakeOptions {
  start?: number | "off";
  tail?: Tail | null;
  speed?: number;
}

export function parseFakeOptions(search: string): FakeOptions {
  const p = new URLSearchParams(search);
  const startRaw = p.get("start");
  const tailRaw = p.get("tail");
  const tail: Tail | null =
    tailRaw === "denied" ? "denied" : tailRaw === "timeout" || tailRaw === "timeout_tail" ? "timeout_tail" : tailRaw === "confirmed" || tailRaw === "confirmed_tail" ? "confirmed_tail" : null;
  return {
    start: startRaw === "off" ? "off" : startRaw != null && !Number.isNaN(Number(startRaw)) ? Number(startRaw) : 2,
    tail,
    speed: Number(p.get("speed") ?? "1") || 1
  };
}

const ms = (iso: string) => Date.parse(iso);

class FakeHub {
  sockets = new Set<FakeSocket>();
  timers: ReturnType<typeof setTimeout>[] = [];
  timeoutTimers: ReturnType<typeof setTimeout>[] = [];
  played = new Set<string>();
  ackReplay: SeqFrame[] = [];
  channel: BroadcastChannel | null = null;

  constructor(public opts: FakeOptions) {
    try {
      if (typeof BroadcastChannel !== "undefined") {
        this.channel = new BroadcastChannel("village-fake");
        this.channel.onmessage = (e) => this.onBroadcast(e.data, false);
      }
    } catch {
      this.channel = null;
    }
  }

  broadcast(msg: { kind: "tail"; tail: Tail } | { kind: "ack" }) {
    this.onBroadcast(msg, true);
  }

  private onBroadcast(msg: any, local: boolean) {
    if (local) this.channel?.postMessage(msg);
    if (msg?.kind === "tail") this.playTail(msg.tail);
    if (msg?.kind === "ack") this.playFrames(this.ackReplay, 0);
  }

  play(name: "start" | Tail) {
    if (name === "start") this.playStart();
    else this.playTail(name);
  }

  playStart() {
    if (this.played.has("start")) return;
    this.played.add("start");
    const frames = sequence("start");
    this.playFrames(frames, 0);
    const base = ms(frames[0].t);
    if (this.opts.tail) {
      const tail = sequence(this.opts.tail);
      const delay = (ms(tail[0].t) - base) / this.speed;
      this.timers.push(setTimeout(() => this.playTail(this.opts.tail!), delay));
    } else {
      // nobody answers → the safe default arrives on the fixture's own clock
      const tail = sequence("timeout_tail");
      const delay = (ms(tail[0].t) - base) / this.speed;
      this.timeoutTimers.push(setTimeout(() => this.playTail("timeout_tail"), delay));
    }
  }

  playTail(tail: Tail) {
    if (this.played.has("tail")) return;
    this.played.add("tail");
    this.timeoutTimers.forEach(clearTimeout);
    const frames = sequence(tail);
    const ackAt = frames.findIndex((f) => f.dir === "c2s" && f.msg.type === "ack");
    this.ackReplay = ackAt >= 0 ? frames.slice(ackAt) : [];
    this.playFrames(ackAt >= 0 ? frames.slice(0, ackAt) : frames, 0);
  }

  get speed() {
    return this.opts.speed ?? 1;
  }

  playFrames(frames: SeqFrame[], extraDelay: number) {
    const s2c = frames.filter((f) => f.dir === "s2c");
    if (!s2c.length) return;
    const base = ms(s2c[0].t);
    for (const f of s2c) {
      const delay = extraDelay + (ms(f.t) - base) / this.speed;
      const fire = () => this.sockets.forEach((s) => s.deliver(f));
      if (delay <= 0) fire();
      else this.timers.push(setTimeout(fire, delay));
    }
  }

  scheduleStart() {
    if (this.opts.start === "off" || this.played.has("start") || this.startScheduled) return;
    this.startScheduled = true;
    this.timers.push(setTimeout(() => this.playStart(), ((this.opts.start as number) ?? 2) * 1000 / this.speed));
  }
  startScheduled = false;

  reset() {
    this.timers.forEach(clearTimeout);
    this.timeoutTimers.forEach(clearTimeout);
    this.timers = [];
    this.timeoutTimers = [];
    this.played.clear();
    this.startScheduled = false;
    this.ackReplay = [];
  }
}

class FakeSocket extends EventTarget {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: Event) => void) | null = null;
  target: FakeClient;
  private lastActionReq: Record<string, string> = {};

  constructor(public url: string, private hub: FakeHub, private me: FakeClient) {
    super();
    this.target = me;
    hub.sockets.add(this);
    setTimeout(() => {
      this.readyState = 1;
      this.fire(new Event("open"));
    }, 0);
  }

  send(raw: string) {
    const f = JSON.parse(raw);
    if (f.type === "hello") {
      const viewAs: string | undefined = f.view_as;
      const asClient = viewAs ? clientForMember(viewAs) : null;
      this.target = asClient ?? this.me;
      this.emit(fakeSnapshot(this.target));
      this.hub.scheduleStart();
    } else if (f.type === "ping") {
      this.emit({ type: "pong", ts: f.ts });
    } else if (f.type === "ack") {
      this.hub.broadcast({ kind: "ack" });
    } else if (f.type === "action") {
      if (f.name === "answer_verification") {
        this.lastActionReq.answer_verification = f.req_id;
        if (this.hub.played.has("tail")) {
          const r = sequence("denied").find((x) => x.client === this.target && x.msg.type === "result");
          this.emit(r && this.hub.opts.tail === "denied" ? { ...r.msg, req_id: f.req_id } : { type: "result", req_id: f.req_id, ok: true });
          return;
        }
        const answer = f.payload?.answer;
        const tail: Tail = answer === "no" ? "denied" : answer === "yes" ? "confirmed_tail" : "timeout_tail";
        this.hub.broadcast({ kind: "tail", tail: this.hub.opts.tail ?? tail });
        // the denied fixture carries Marco's result; the other outcomes get a synthesized ok result
        if ((this.hub.opts.tail ?? tail) !== "denied") this.emit({ type: "result", req_id: f.req_id, ok: true });
      } else {
        this.emit({ type: "result", req_id: f.req_id, ok: true });
      }
    }
  }

  deliver(f: SeqFrame) {
    if (f.client !== this.target) return;
    let msg = f.msg;
    if (msg.type === "result" && this.lastActionReq.answer_verification) msg = { ...msg, req_id: this.lastActionReq.answer_verification };
    this.emit(msg);
  }

  close() {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.hub.sockets.delete(this);
    this.fire(new Event("close"));
  }

  emit(msg: unknown) {
    if (this.readyState !== 1) return;
    this.fire(new MessageEvent("message", { data: JSON.stringify(msg) }));
  }

  private fire(e: Event) {
    this.dispatchEvent(e);
    const h = (this as any)[`on${e.type}`];
    if (typeof h === "function") h.call(this, e);
  }
}

export function isFakeClient(v: string | null): v is FakeClient {
  return !!v && v in FAKE_CLIENTS;
}

/** Returns a WebSocket-compatible constructor bound to one fake client; also exposes window.__fake for the presenter. */
export function createFakeWebSocket(client: FakeClient, opts: FakeOptions): typeof WebSocket {
  const hub = new FakeHub(opts);
  if (typeof window !== "undefined") (window as any).__fake = { play: (n: "start" | Tail) => hub.play(n), reset: () => hub.reset(), hub };
  const Ctor = function (this: unknown, url: string) {
    return new FakeSocket(url, hub, client);
  } as unknown as typeof WebSocket;
  return Ctor;
}
