import type { Operation } from "fast-json-patch";
import { normalizeReyesView, applyViewPatch, viewSchema, type View } from "../renderer/view";
import { serverFrameSchema, type ServerFrame } from "./messages";

export type SocketStatus = "idle" | "connecting" | "hello_sent" | "open" | "resync" | "reconnecting" | "closed";

export interface LiveSnapshot {
  status: SocketStatus;
  attempt: number;
  role: string;
  member_id: string | null;
  rev: number;
  view: View | null;
  data: Record<string, unknown>;
  now: string;
  prompt: any | null;
  lastError: string | null;
  sent: unknown[];
}

type Listener = (state: LiveSnapshot) => void;

const initialState: LiveSnapshot = {
  status: "idle",
  attempt: 0,
  role: "elder",
  member_id: null,
  rev: 0,
  view: null,
  data: {},
  now: new Date().toISOString(),
  prompt: null,
  lastError: null,
  sent: []
};

export class VillageSocket {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private state: LiveSnapshot = { ...initialState };
  private reconnectTimer = 0;
  private seq = 0;

  constructor(private options: { url: string; village: string; token: string; client: "kit" | "control" | "test"; fakeRole?: string }) {}

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  connect(lastRev?: number) {
    this.set({ status: "connecting" });
    this.socket = new WebSocket(this.options.url);
    this.socket.addEventListener("open", () => {
      this.set({ status: "hello_sent" });
      this.sendRaw({ type: "hello", contract_version: "1.1.0", village: this.options.village, member_token: this.options.token, last_rev: lastRev, client: this.options.client });
    });
    this.socket.addEventListener("message", (event) => this.receive(event.data));
    this.socket.addEventListener("close", () => this.scheduleReconnect());
  }

  action(name: string, payload: Record<string, unknown> = {}, elementId?: string, arg?: unknown) {
    const req_id = `r_${this.state.member_id ?? "member"}_${String(++this.seq).padStart(4, "0")}`;
    this.sendRaw({ type: "action", req_id, name, arg, element_id: elementId, payload, client_ts: new Date().toISOString() });
  }

  hello() {
    this.sendRaw({ type: "hello", contract_version: "1.1.0", village: this.options.village, member_token: this.options.token, last_rev: this.state.rev, client: this.options.client });
  }

  close() {
    window.clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.set({ status: "closed" });
  }

  private receive(raw: unknown) {
    const parsed = serverFrameSchema.safeParse(typeof raw === "string" ? JSON.parse(raw) : raw);
    if (!parsed.success) {
      this.set({ lastError: "bad_message" });
      return;
    }
    const frame = parsed.data;
    if (frame.type === "snapshot") this.applySnapshot(frame);
    if (frame.type === "patch") this.applyPatch(frame);
    if (frame.type === "event") this.applyEvent(frame);
    if (frame.type === "prompt") this.set({ prompt: (frame as any).closed ? null : frame });
    if (frame.type === "result") this.set({ lastError: (frame as any).ok ? null : String((frame as any).error ?? "action failed") });
    if (frame.type === "error") this.set({ status: (frame as any).code === "bad_token" || (frame as any).code === "contract_mismatch" ? "closed" : this.state.status, lastError: String((frame as any).message ?? (frame as any).code) });
  }

  private applySnapshot(frame: ServerFrame) {
    const raw = (frame as any).spec ?? (frame as any).view;
    const role = String((frame as any).role ?? this.options.fakeRole ?? "elder");
    const parsed = viewSchema.parse(raw);
    this.set({
      status: "open",
      attempt: 0,
      role,
      member_id: (frame as any).member_id ?? null,
      rev: Number((frame as any).rev ?? 0),
      view: normalizeReyesView(parsed, role),
      data: ((frame as any).data ?? {}) as Record<string, unknown>,
      now: String((frame as any).now ?? new Date().toISOString()),
      prompt: null
    });
  }

  private applyPatch(frame: ServerFrame) {
    const patch = frame as any;
    if (Number(patch.base_rev) !== this.state.rev || !this.state.view) {
      this.set({ status: "resync" });
      this.hello();
      return;
    }
    try {
      const view = applyViewPatch(this.state.view, patch.ops as Operation[]);
      this.set({ view: normalizeReyesView(view, this.state.role), rev: Number(patch.rev), status: "open" });
    } catch (error) {
      this.set({ lastError: error instanceof Error ? error.message : "patch failed", status: "resync" });
      this.hello();
    }
  }

  private applyEvent(frame: ServerFrame) {
    const data = { ...this.state.data };
    for (const [key, value] of Object.entries(((frame as any).data ?? {}) as Record<string, unknown>)) {
      if (value === null) delete data[key];
      else data[key] = value;
    }
    this.set({ data });
  }

  private scheduleReconnect() {
    if (this.state.status === "closed") return;
    const attempt = this.state.attempt + 1;
    this.set({ status: "reconnecting", attempt });
    const delay = Math.min(8000, 500 * 2 ** (attempt - 1));
    this.reconnectTimer = window.setTimeout(() => this.connect(this.state.rev), delay);
  }

  private sendRaw(frame: unknown) {
    (window as any).__frames = [...((window as any).__frames ?? []), frame];
    this.set({ sent: [...this.state.sent, frame] });
    this.socket?.send(JSON.stringify(frame));
  }

  private set(patch: Partial<LiveSnapshot>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener(this.state));
  }
}
