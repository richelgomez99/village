import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";

let installed = false;

export function installFakeWs(fake: string) {
  if (installed) return;
  installed = true;
  const RealEventTarget = EventTarget;
  class FakeWebSocket extends RealEventTarget {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    readyState = 0;
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;

    constructor(public url: string) {
      super();
      setTimeout(() => this.open(), 0);
    }

    send(raw: string) {
      const frame = JSON.parse(raw);
      if (frame.type === "hello") {
        this.emit(snapshotFor(fake));
        const params = new URLSearchParams(window.location.search);
        const tail = params.get("tail") ?? "denied";
        const speed = Number(params.get("speed") ?? "20");
        replay(this, fake, "start", speed);
        replay(this, fake, tail === "timeout" ? "timeout_tail" : tail === "confirmed" ? "confirmed_tail" : "denied", speed, 700);
      }
      if (frame.type === "action" && frame.name === "answer_verification") {
        const result = frames("denied", fake).find((f: any) => f.msg.type === "result");
        if (result) this.emit(result.msg);
      }
    }

    close() {
      this.readyState = 3;
      const event = new CloseEvent("close");
      this.dispatchEvent(event);
      this.onclose?.(event);
    }

    private open() {
      this.readyState = 1;
      const event = new Event("open");
      this.dispatchEvent(event);
      this.onopen?.(event);
    }

    emit(msg: unknown) {
      const event = new MessageEvent("message", { data: JSON.stringify(msg) });
      this.dispatchEvent(event);
      this.onmessage?.(event);
    }
  }
  (window as any).WebSocket = FakeWebSocket;
}

function snapshotFor(client: string) {
  const role = client === "ana" ? "coordinator" : client === "marco" ? "helper" : "elder";
  const member_id = client === "ana" ? "m_ana" : client === "marco" ? "m_marco" : "m_carmen";
  const connectFrame = frames("connect", client).find((f: any) => f.msg.type === "snapshot");
  if (connectFrame) return connectFrame.msg;
  const view = (reyesSpec as any).views[role];
  return { type: "snapshot", contract_version: "1.1.0", rev: 4, village: "v_reyes", role, member_id, spec: view, data: baseData(role), now: "2026-10-16T14:01:40-04:00" };
}

function baseData(role: string) {
  return {
    "alerts:active": [],
    "verifications:pending?member=me": null,
    "blueprint:life_areas": [
      { id: "health", label: "Health: pills", status: { en: "Refill due Sunday", es: "Relleno el domingo" } },
      { id: "money", label: "Money: scam calls", status: { en: "Marco verifies money calls", es: "Marco confirma llamadas de dinero" } },
      { id: "people", label: "People: whose turn", status: { en: "Marco tonight", es: "Marco esta noche" } }
    ],
    "rota:current?member=me": {
      is_my_turn: role === "helper",
      on_duty: { member_id: "m_marco", name: "Marco" },
      next_shift: "2026-10-17T18:00:00-04:00",
      answer: { en: "Yes. Tonight until 9:30. Nothing to do unless Village calls you." }
    },
    "incidents:open": [],
    "facts:dose_event?subject=m_carmen&valid_at=today": { slots: [] },
    "facts:dose_event?subject=m_carmen&valid_at=week": { days: [] },
    "rota:week": [{ date: "Fri", on_duty: { member_id: "m_marco", name: "Marco" }, backup: { member_id: "m_ana", name: "Ana" } }],
    "timeline:subject=m_carmen": [{ event_id: "ev_med_change", kind: "med_change", text: { en: "Lisinopril changed to 10 mg", es: "Lisinopril cambió a 10 mg" }, source_label: "Dr. Lee, Oct 3", superseded: false }]
  };
}

function frames(sequence: string, client: string) {
  return ((wsScam as any).sequences[sequence] ?? []).filter((f: any) => f.client === client && f.dir === "s2c");
}

function replay(socket: any, client: string, sequence: string, speed: number, offset = 100) {
  frames(sequence, client).forEach((frame: any, index: number) => {
    setTimeout(() => socket.emit(frame.msg), offset + (index * 400) / Math.max(1, speed));
  });
}
