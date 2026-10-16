// Presenter transport bar for offline replays: ▶/⏸ · ◀ step · ▶ step · scrubber · speed · current beat · Jump to.
// Keyboard: space = play/pause, ←/→ = step. Hidden in hero mode (the page decides).
import { useEffect, useState } from "react";
import type { Transport, TransportState } from "../dev/transport";

export const SPEEDS = [0.5, 1, 2, 4];
const SEQS = ["founding", "scam", "release", "evolve"];

export function useTransportState(t: Transport | null): TransportState | null {
  const [s, setS] = useState<TransportState | null>(t ? t.state : null);
  useEffect(() => (t ? t.subscribe((e) => setS(e.state)) : undefined), [t]);
  return s;
}

const secs = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

export function TransportBar({ transport, beat, villages }: { transport: Transport; beat: string | null; villages: { id: string; label: string }[] }) {
  const s = useTransportState(transport);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        transport.toggle();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        transport.step(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        transport.step(1);
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [transport]);
  if (!s) return null;
  const jump = (v: string) => {
    if (!v || typeof window === "undefined") return;
    const [kind, value] = v.split(":");
    const p = new URLSearchParams(window.location.search);
    p.set("fake", "control");
    if (kind === "seq") {
      p.set("seq", value);
      if (value !== "founding") p.delete("village");
    } else if (kind === "village") {
      if (value === "new") {
        p.set("seq", "founding");
        p.delete("village");
      } else {
        p.set("village", value);
        if (value !== villages[0]?.id) p.set("seq", "founding");
      }
    }
    window.location.search = p.toString();
  };
  return (
    <div className="transport-bar" data-test="transport-bar" role="toolbar" aria-label="Replay controls">
      <button type="button" data-test="tr-back" aria-label="Step back one frame" onClick={() => transport.step(-1)} disabled={s.index === 0}>◀</button>
      <button type="button" data-test="tr-play" aria-label={s.playing ? "Pause" : "Play"} onClick={() => transport.toggle()}>{s.playing ? "⏸" : "▶"}</button>
      <button type="button" data-test="tr-forward" aria-label="Step forward one frame" onClick={() => transport.step(1)} disabled={s.index >= s.total}>▶|</button>
      <input
        type="range" min={0} max={s.total} value={s.index} data-test="tr-scrub" aria-label="Replay position"
        onChange={(e) => transport.seek(Number(e.target.value))}
      />
      <span className="tr-pos mono" data-test="tr-pos">{s.index}/{s.total} · {secs(s.ms)} / {secs(s.totalMs)}</span>
      <span className="tr-speeds" role="group" aria-label="Speed">
        {SPEEDS.map((x) => (
          <button key={x} type="button" data-test="tr-speed" data-speed={x} aria-pressed={s.speed === x} className={s.speed === x ? "active" : ""} onClick={() => transport.setSpeed(x)}>{x}×</button>
        ))}
      </span>
      <span className="tr-beat mono" data-test="tr-beat">{beat ? beat.toUpperCase() : "—"}</span>
      <select aria-label="Jump to" data-test="tr-jump" value="" onChange={(e) => jump(e.target.value)}>
        <option value="">Jump to…</option>
        <optgroup label="Scene">
          {SEQS.map((q) => <option key={q} value={`seq:${q}`}>{q}</option>)}
        </optgroup>
        <optgroup label="Village">
          {villages.map((v) => <option key={v.id} value={`village:${v.id}`}>{v.label}</option>)}
          <option value="village:new">New village</option>
        </optgroup>
      </select>
    </div>
  );
}
