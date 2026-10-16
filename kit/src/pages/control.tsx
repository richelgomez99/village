import { useMemo } from "react";
import { createRoot } from "react-dom/client";
import { ViewAs } from "../components/chrome";
import { REYES_MEMBERS, useSocketState } from "../app/MemberApp";
import { liveConfig, makeSocket } from "../live/useLive";
import type { VillageSocket } from "../live/ws";
import { Renderer } from "../renderer/Renderer";
import { text } from "../renderer/view";
import { fmtTime } from "../util/time";
import "../theme/fonts.css";
import "../theme/floor.css";
import "../theme/a.css";

/** D18: Spanish on the projector always carries the English line under it. */
function Captioned({ value }: { value: unknown }) {
  const es = text(value, "es");
  const en = text(value, "en");
  if (value && typeof value === "object" && (value as any).es && en && en !== es) {
    return (
      <>
        <span lang="es">{es}</span>
        <span className="caption" lang="en" data-test="caption">{en}</span>
      </>
    );
  }
  return <span>{en || es}</span>;
}

export function ControlRoom({ socket }: { socket: VillageSocket }) {
  const state = useSocketState(socket);
  const gate = state.control.filter((c) => c.kind === "gate").reverse();
  const reasoning = state.control.filter((c) => c.kind === "reasoning").reverse();
  const counters = useMemo(() => {
    const m = new Map<string, any>();
    state.control.filter((c) => c.kind === "counter").forEach((c) => m.set(String(c.payload.name), c.payload));
    return [...m.values()];
  }, [state.control]);
  const lastGate = gate[0]?.payload as any;
  const ctx = state.view
    ? { view: state.view, data: state.data, lang: state.view.lang, role: state.role, memberId: state.memberId, village: state.village, nowMs: socket.nowMs, disabled: true, highlight: new Set<string>(), results: {}, send: () => "", ack: () => {}, captions: true }
    : null;
  return (
    <main data-test="control" className="control" data-status={state.status}>
      <header>
        <strong>Village · Control Room</strong>
        <span data-test="phones-counter">{counters.map((c) => `${c.value} ${c.label}`).join(" · ") || "live"}</span>
        <time data-test="demo-clock">{fmtTime(new Date(socket.nowMs()).toISOString(), "en")}</time>
        <ViewAs options={REYES_MEMBERS.slice(0, 3)} current={state.viewAs} self={null} onPick={(m) => socket.viewAs(m)} lang="en" />
      </header>
      <section data-test="live-moment">
        <h2>Safety gate</h2>
        {lastGate ? (
          <div data-test="gate-now" data-rule={lastGate.decision?.rule_id} data-decision={lastGate.decision?.decision}>
            <p className="mono">{lastGate.decision?.rule_id} · {lastGate.decision?.decision}</p>
            {lastGate.decision?.say ? <p className="big"><Captioned value={lastGate.decision.say} /></p> : null}
          </div>
        ) : (
          <p className="caption">Waiting for the first call.</p>
        )}
      </section>
      <section data-test="phone-mirror">
        <h2>{state.viewAs ? "Same URL · this person's app" : "Pick a person to see their app"}</h2>
        <p className="caption">village.app/v/reyes · one site · three people</p>
        {ctx ? (
          <div className="phone app" data-theme={ctx.view.theme} data-test="app" data-role={state.role}>
            <Renderer ctx={ctx} />
          </div>
        ) : null}
      </section>
      <section data-test="gate-feed">
        <h2>Gate decisions</h2>
        {gate.map((g, i) => (
          <div key={i} data-test="gate-row" data-rule={(g.payload as any).decision?.rule_id}>
            <span className="mono">{fmtTime(g.at, "en")} · {(g.payload as any).decision?.rule_id}</span>
            {(g.payload as any).decision?.say ? <p><Captioned value={(g.payload as any).decision.say} /></p> : null}
          </div>
        ))}
      </section>
      <section data-test="decisions-log">
        <h2>Decisions</h2>
        {reasoning.map((r, i) => (
          <div key={i} data-test="decision-row"><span className="mono">{fmtTime(r.at, "en")}</span> {String((r.payload as any).text ?? "")}</div>
        ))}
      </section>
    </main>
  );
}

if (typeof document !== "undefined" && document.getElementById("root")) {
  const socket = makeSocket(liveConfig("control"));
  socket.connect();
  createRoot(document.getElementById("root")!).render(<ControlRoom socket={socket} />);
}
