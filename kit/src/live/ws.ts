import type { Operation } from "fast-json-patch";
import { applyViewPatch, viewSchema, type View } from "../renderer/view";
import type { ActionRequest, ResultInfo } from "../renderer/context";
import { CONTRACT_VERSION, serverFrameSchema, type ClientHello, type ClientName, type ControlFrame, type Identity, type PromptFrame, type ServerFrame } from "./messages";

/** role the kit gives a member with no app view (Core sends role null): they use the phone line. */
export const PHONE_LINE = "phone_line";

export interface AskPrompt { kind: "ask"; ask_id: string; question: unknown; options?: { id: string; label: unknown }[]; closed?: boolean }

export type SocketStatus = "idle" | "connecting" | "hello_sent" | "live" | "resync" | "reconnecting" | "updating" | "closed";

export interface LiveState {
  status: SocketStatus;
  attempt: number;
  closedReason: string | null;
  lastError: string | null;
  rev: number;
  village: string;
  role: string;
  memberId: string | null;
  /** who this socket really is (first snapshot); differs from role/memberId while viewing as someone (D21). */
  self: { role: string; memberId: string | null } | null;
  viewAs: string | null;
  /** snapshot.identity (1.3.4) when the server sends it. */
  identity: Identity | null;
  view: View | null;
  /** full VillageSpec on control snapshots. */
  spec: unknown;
  data: Record<string, unknown>;
  prompt: PromptFrame | null;
  /** D39 people-ask on this member's phone: {type: prompt, kind: ask, ask_id, question, options} (pre-contract; Core asks.py) */
  ask: AskPrompt | null;
  results: Record<string, ResultInfo | "pending">;
  highlight: string[];
  control: ControlFrame[];
  events: { id: string; kind: string; at: string }[];
}

export interface SocketOptions {
  url: string;
  village: string;
  token: string;
  client: ClientName;
  WebSocketImpl?: typeof WebSocket;
  /** open this socket already viewing as a member (Control Room phones, D21). */
  viewAs?: string;
  /** contract_mismatch: fetch the new bundle (service worker update); resolves when done. Default: SW registration.update(). */
  onUpdate?: () => Promise<unknown>;
  /** max wait for onUpdate before re-helloing (ms, default 2000) */
  updateMs?: number;
  jitter?: number;
  pingMs?: number;
  deadMs?: number;
}

type Listener = (s: LiveState) => void;
export type FrameListener = (f: ServerFrame) => void;

export function initialLiveState(village = ""): LiveState {
  return {
    status: "idle", attempt: 0, closedReason: null, lastError: null, rev: 0, village, role: "", memberId: null,
    self: null, viewAs: null, identity: null, view: null, spec: null, data: {}, prompt: null, ask: null, results: {}, highlight: [], control: [], events: []
  };
}

export class VillageSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private frameListeners = new Set<FrameListener>();
  private s: LiveState;
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;
  private deadTimer: ReturnType<typeof setTimeout> | undefined;
  private seq = 0;
  private offset = 0;
  private pending = new Map<string, ActionRequest>();
  private incidentEvents = new Map<string, string>();
  private stopped = false;
  private updatedOnce = false;

  constructor(private o: SocketOptions) {
    this.s = initialLiveState(o.village);
    this.nowMs = this.nowMs.bind(this);
  }

  get state() {
    return this.s;
  }

  /** Server clock (snapshot.now, advanced by event.at) — countdowns render against this. */
  nowMs(): number {
    return Date.now() + this.offset;
  }

  subscribe(fn: Listener) {
    this.listeners.add(fn);
    fn(this.s);
    return () => {
      this.listeners.delete(fn);
    };
  }

  private frameLog: ServerFrame[] = [];

  /** Every validated server frame, in order (Control Room scene reducer). Frames that arrived before the
   *  listener subscribed (e.g. the snapshot, before React mounted) are replayed to it first. */
  onFrame(fn: FrameListener) {
    this.frameLog.forEach(fn);
    this.frameListeners.add(fn);
    return () => {
      this.frameListeners.delete(fn);
    };
  }

  connect() {
    this.stopped = false;
    clearTimeout(this.reconnectTimer);
    this.set({ status: "connecting" });
    const Impl = this.o.WebSocketImpl ?? (globalThis as any).WebSocket;
    const ws: WebSocket = new Impl(this.url());
    this.ws = ws;
    ws.addEventListener("open", () => {
      if (this.ws !== ws) return;
      this.set({ status: "hello_sent" });
      this.hello();
      this.startPing();
    });
    ws.addEventListener("message", (ev: MessageEvent) => {
      if (this.ws === ws) this.receive(ev.data);
    });
    ws.addEventListener("close", () => {
      if (this.ws === ws) this.onClose();
    });
    ws.addEventListener("error", () => {
      /* close follows */
    });
  }

  close() {
    this.stopped = true;
    this.stopPing();
    clearTimeout(this.reconnectTimer);
    const ws = this.ws;
    this.ws = null;
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
    this.set({ status: "closed", closedReason: this.s.closedReason ?? "closed" });
  }

  /** Village this socket is for: the one the server named in the last snapshot, else the configured one. */
  get village(): string {
    return this.s.village || this.o.village;
  }

  /** Socket URL with the current village filled in (never `?village=&m=…` on a reconnect). */
  url(): string {
    const v = this.village;
    if (!v || !/[?&]village=/.test(this.o.url)) return this.o.url;
    return this.o.url.replace(/([?&])village=[^&]*/, `$1village=${encodeURIComponent(v)}`);
  }

  hello() {
    const frame: ClientHello = {
      type: "hello",
      contract_version: CONTRACT_VERSION,
      village: this.village,
      member_token: this.o.token,
      client: this.o.client
    };
    if (this.o.viewAs && !this.s.viewAs && this.s.rev === 0) this.s = { ...this.s, viewAs: this.o.viewAs };
    if (this.s.rev > 0) frame.last_rev = this.s.rev;
    if (this.s.viewAs) frame.view_as = this.s.viewAs;
    this.sendRaw(frame);
  }

  /** D21: ask Core for another member's snapshot (null = back to me). */
  viewAs(memberId: string | null) {
    const target = memberId && memberId !== this.s.self?.memberId ? memberId : null;
    this.set({ viewAs: target, status: "resync" });
    this.hello();
  }

  /** close the ask sheet locally once answered (Core's answer arrives as chat) */
  clearAsk() {
    this.set({ ask: null });
  }

  action(a: ActionRequest): string {
    const who = (this.s.self?.memberId ?? this.s.memberId ?? "member").replace(/^[a-z]_/, "");
    const req_id = `r_${who}_${String(++this.seq).padStart(4, "0")}`;
    this.pending.set(req_id, a);
    const frame: Record<string, unknown> = { type: "action", req_id, name: a.name, client_ts: isoWithOffset(this.nowMs()) };
    if (a.arg !== undefined) frame.arg = a.arg;
    if (a.element_id) frame.element_id = a.element_id;
    if (a.payload) frame.payload = a.payload;
    this.set({ results: { ...this.s.results, [resultKey(a)]: "pending" } });
    this.sendRaw(frame);
    return req_id;
  }

  /** Ack an incident: `ack{event_id}` when the incident row is known (fixture path), else action ack_incident. */
  ack(incidentOrEvent: string, status: "got_it" | "accepted" | "declined" | "not_needed" = "got_it") {
    const eventId = incidentOrEvent.startsWith("ev_") ? incidentOrEvent : this.incidentEvents.get(incidentOrEvent);
    if (eventId) {
      const who = (this.s.self?.memberId ?? "member").replace(/^[a-z]_/, "");
      this.sendRaw({ type: "ack", event_id: eventId, status, req_id: `r_${who}_${String(++this.seq).padStart(4, "0")}` });
    } else {
      this.action({ name: "ack_incident", arg: incidentOrEvent });
    }
  }

  private receive(raw: unknown) {
    let json: unknown;
    try {
      json = typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch {
      this.set({ lastError: "bad_message" });
      return;
    }
    if ((json as any)?.type === "prompt" && (json as any)?.kind === "ask") {
      const a = json as AskPrompt;
      if (!this.s.viewAs) this.set({ ask: a.closed ? null : a });
      return;
    }
    // a phone-line member (spec person view: null) gets role null and an empty spec from Core: keep the frame, mark the role
    if ((json as any)?.type === "snapshot" && (json as any).role == null) {
      const j = json as any;
      json = { ...j, role: PHONE_LINE, spec: j.spec ?? {}, identity: j.identity ? { ...j.identity, role: PHONE_LINE } : j.identity };
    }
    const parsed = serverFrameSchema.safeParse(json);
    if (!parsed.success) {
      this.set({ lastError: `bad frame: ${(json as any)?.type ?? "?"}` });
      return;
    }
    this.handle(parsed.data);
    if (this.o.client === "control") {
      this.frameLog.push(parsed.data);
      if (this.frameLog.length > 500) this.frameLog.splice(0, this.frameLog.length - 500);
    }
    this.frameListeners.forEach((l) => l(parsed.data));
  }

  private handle(f: ServerFrame) {
    switch (f.type) {
      case "snapshot": {
        this.offset = Date.parse(f.now) - Date.now();
        let view: View | null = null;
        let lastError: string | null = null;
        if (f.role !== "control" && f.role !== PHONE_LINE) {
          const v = viewSchema.safeParse(f.spec);
          if (v.success) view = v.data;
          else lastError = "snapshot view failed validation";
        }
        const self = this.s.self && this.s.viewAs ? this.s.self : { role: f.role, memberId: f.member_id };
        this.set({
          status: "live", attempt: 0, rev: f.rev, village: f.village, role: f.role, memberId: f.member_id, self, identity: f.identity ?? null,
          view, spec: f.role === "control" ? f.spec : null, data: { ...f.data }, highlight: [], lastError,
          prompt: this.s.viewAs ? null : this.s.prompt
        });
        return;
      }
      case "patch": {
        // the Control Room's founding drafts are patches too: its scene reducer applies them, not the socket
        if (this.s.role === "control") return;
        // patches are per role (Core sends each socket its own role's ops); one for another role means our view is stale
        if (f.role && this.s.role && f.role !== this.s.role) {
          this.set({ status: "resync" });
          this.hello();
          return;
        }
        if (!this.s.view || f.base_rev !== this.s.rev) {
          this.set({ status: "resync" });
          this.hello();
          return;
        }
        try {
          const view = applyViewPatch(this.s.view, f.ops as Operation[]);
          this.set({ view, rev: f.rev, status: "live", highlight: f.highlight ?? [] });
        } catch (e) {
          this.set({ status: "resync", lastError: e instanceof Error ? e.message : "patch failed" });
          this.hello();
        }
        return;
      }
      case "event": {
        const at = Date.parse(f.event.at);
        if (!Number.isNaN(at) && at > this.nowMs()) this.offset = at - Date.now();
        if (f.event.kind === "incident" && typeof f.event.payload?.incident_id === "string") {
          this.incidentEvents.set(f.event.payload.incident_id, f.event.id);
        }
        const data = { ...this.s.data, ...(f.data ?? {}) };
        const events = [{ id: f.event.id, kind: f.event.kind, at: f.event.at }, ...this.s.events].slice(0, 50);
        this.set({ data, events });
        return;
      }
      case "prompt":
        if (this.s.viewAs) return;
        this.set({ prompt: f.closed ? null : f });
        return;
      case "result": {
        const req = this.pending.get(f.req_id);
        this.pending.delete(f.req_id);
        const info: ResultInfo = { req_id: f.req_id, ok: f.ok, say: f.decision?.say, error: f.error };
        const key = req ? resultKey(req) : f.decision?.say ? "answer_verification" : f.req_id;
        this.set({ results: { ...this.s.results, [key]: info }, lastError: f.ok ? this.s.lastError : f.error ?? "action failed" });
        return;
      }
      case "control":
        this.set({ control: [...this.s.control, f].slice(-200) });
        return;
      case "chat": {
        const rows = Array.isArray(this.s.data["chat:village"]) ? (this.s.data["chat:village"] as { id: string }[]) : [];
        // the builder re-sends an ask message (same id) as answers arrive: replace it in place
        if (rows.some((r) => r.id === f.message.id)) {
          this.set({ data: { ...this.s.data, "chat:village": rows.map((r) => (r.id === f.message.id ? f.message : r)) } });
          return;
        }
        this.set({ data: { ...this.s.data, "chat:village": [...rows, f.message].slice(-50) } });
        return;
      }
      case "pong":
        clearTimeout(this.deadTimer);
        return;
      case "error":
        if (f.code === "contract_mismatch" && !this.updatedOnce) {
          // a cached bundle met a newer Core: update the service worker, then re-hello once ("Updating…", ≤ 2 s)
          this.updatedOnce = true;
          this.set({ status: "updating", lastError: f.message });
          const update = (this.o.onUpdate ?? swUpdate)().catch(() => undefined);
          const wait = new Promise((r) => setTimeout(r, this.o.updateMs ?? 2000));
          void Promise.race([update, wait]).then(() => {
            if (this.stopped) return;
            if (this.ws && this.ws.readyState === 1) {
              this.set({ status: "hello_sent" });
              this.hello();
            } else {
              this.connect();
            }
          });
          return;
        }
        if (f.code === "bad_token" || f.code === "contract_mismatch") {
          this.set({ closedReason: f.code, lastError: f.message });
          this.close();
        } else {
          this.set({ lastError: `${f.code}: ${f.message}` });
        }
        return;
    }
  }

  private onClose() {
    this.stopPing();
    this.ws = null;
    if (this.stopped) return;
    const attempt = this.s.attempt + 1;
    const base = Math.min(8000, 500 * 2 ** (attempt - 1));
    const j = this.o.jitter ?? 0.2;
    const delay = Math.round(base * (1 + (Math.random() * 2 - 1) * j));
    // results that were in flight are lost with the socket
    const results = Object.fromEntries(Object.entries(this.s.results).filter(([, v]) => v !== "pending"));
    this.pending.clear();
    this.set({ status: "reconnecting", attempt, results });
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private startPing() {
    this.stopPing();
    const every = this.o.pingMs ?? 15000;
    this.pingTimer = setInterval(() => {
      // arm the dead-man before sending: a pong can arrive synchronously (fake server) and must clear it
      clearTimeout(this.deadTimer);
      this.deadTimer = setTimeout(() => {
        try {
          this.ws?.close();
        } catch {
          /* ignore */
        }
      }, this.o.deadMs ?? 10000);
      this.sendRaw({ type: "ping", ts: Date.now() });
    }, every);
  }

  private stopPing() {
    clearInterval(this.pingTimer);
    clearTimeout(this.deadTimer);
  }

  private sendRaw(frame: unknown) {
    if (typeof window !== "undefined") {
      const w = window as any;
      (w.__frames ??= []).push(frame);
    }
    if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(frame));
  }

  private set(p: Partial<LiveState>) {
    this.s = { ...this.s, ...p };
    this.listeners.forEach((l) => l(this.s));
  }
}

function resultKey(a: ActionRequest): string {
  return a.name === "answer_verification" ? "answer_verification" : a.element_id ?? a.name;
}

/** RFC 3339 with the demo's -04:00 offset (contract datetime requires an explicit offset). */
export function isoWithOffset(ms: number): string {
  const d = new Date(ms - 4 * 3600_000);
  return d.toISOString().replace(/\.\d{3}Z$/, "-04:00");
}

/** Ask the service worker for the new bundle (vite-plugin-pwa autoUpdate activates it). */
async function swUpdate(): Promise<unknown> {
  const sw = typeof navigator !== "undefined" ? navigator.serviceWorker : undefined;
  if (!sw) return;
  const reg = await sw.getRegistration();
  return reg?.update();
}
