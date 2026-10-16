// Presenter transport for the offline Control Room replays (?fake=control&seq=…): play/pause, step, scrub, speed.
// The transport owns delivery of the replay's frames to the control socket. Stepping back emits a "rewind" with the
// hello snapshot + the frame prefix; the room's pure scene reducer rebuilds from them (reset → snapshot → frames).

export interface TFrame { ms: number; msg: any; tail?: boolean }
export interface TransportState { index: number; total: number; playing: boolean; speed: number; ms: number; totalMs: number; village: string | null; seq: string | null }
export type TransportEvent = { type: "state"; state: TransportState } | { type: "rewind"; initial: any; frames: any[]; state: TransportState };

export class Transport {
  frames: TFrame[] = [];
  index = 0;
  playing = true;
  speed: number;
  t = 0;
  initial: any = null;
  village: string | null = null;
  seq: string | null = null;
  media: HTMLMediaElement | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private listeners = new Set<(e: TransportEvent) => void>();

  constructor(private deliver: (msg: any) => void, speed = 1) {
    this.speed = speed;
  }

  get state(): TransportState {
    return { index: this.index, total: this.frames.length, playing: this.playing, speed: this.speed, ms: this.t, totalMs: this.frames.at(-1)?.ms ?? 0, village: this.village, seq: this.seq };
  }

  subscribe(fn: (e: TransportEvent) => void) {
    this.listeners.add(fn);
    fn({ type: "state", state: this.state });
    return () => {
      this.listeners.delete(fn);
    };
  }

  private emit(e?: TransportEvent) {
    const ev = e ?? { type: "state" as const, state: this.state };
    this.listeners.forEach((l) => l(ev));
  }

  load(frames: TFrame[], meta: { village?: string | null; seq?: string | null } = {}) {
    this.frames = [...frames].sort((a, b) => a.ms - b.ms);
    this.index = 0;
    this.t = 0;
    if (meta.village !== undefined) this.village = meta.village;
    if (meta.seq !== undefined) this.seq = meta.seq;
    this.drainDue();
    this.schedule();
    this.emit();
  }

  /** frames due at the current virtual time go out together */
  private drainDue() {
    while (this.index < this.frames.length && this.frames[this.index].ms <= this.t) this.deliver(this.frames[this.index++].msg);
  }

  private schedule() {
    clearTimeout(this.timer);
    if (!this.playing || this.index >= this.frames.length) return;
    const next = this.frames[this.index];
    this.timer = setTimeout(() => {
      this.t = next.ms;
      this.drainDue();
      this.emit();
      this.schedule();
    }, Math.max(0, (next.ms - this.t) / this.speed));
  }

  play() {
    this.playing = true;
    this.media?.play?.().catch?.(() => undefined);
    this.schedule();
    this.emit();
  }

  pause() {
    this.playing = false;
    clearTimeout(this.timer);
    this.media?.pause?.();
    this.emit();
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  setSpeed(x: number) {
    this.speed = x;
    if (this.media) this.media.playbackRate = x;
    this.schedule();
    this.emit();
  }

  /** one frame forward / back (pauses: stepping is for looking) */
  step(dir: 1 | -1) {
    this.pause();
    this.seek(this.index + dir);
  }

  /** go to "n frames delivered": forward delivers the gap, backward rewinds and replays the prefix */
  seek(n: number) {
    const to = Math.max(0, Math.min(this.frames.length, n));
    if (to > this.index) {
      while (this.index < to) this.deliver(this.frames[this.index++].msg);
      this.t = this.frames[to - 1]?.ms ?? 0;
    } else if (to < this.index) {
      this.index = to;
      this.t = to ? this.frames[to - 1].ms : 0;
      this.emit({ type: "rewind", initial: this.initial, frames: this.frames.slice(0, to).map((f) => f.msg), state: this.state });
    }
    if (this.media) {
      try {
        this.media.currentTime = this.t / 1000;
      } catch {
        /* not seekable yet */
      }
    }
    this.schedule();
    this.emit();
  }

  /** frames that arrive mid-replay (a live tail from another tab): placed at the current time; undelivered `tail` frames are dropped */
  append(frames: TFrame[], replaceTail = false) {
    const kept = replaceTail ? this.frames.filter((f, i) => i < this.index || !f.tail) : this.frames;
    const base = this.t;
    const add = frames.map((f) => ({ ...f, ms: f.ms + base }));
    this.frames = [...kept.slice(0, this.index), ...[...kept.slice(this.index), ...add].sort((a, b) => a.ms - b.ms)];
    this.schedule();
    this.emit();
  }

  stop() {
    clearTimeout(this.timer);
  }
}
