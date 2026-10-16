import { useEffect, useState } from "react";

export function fmtTime(iso: unknown, lang: string): string {
  if (typeof iso !== "string") return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang, { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }).format(d);
}

export function fmtDay(iso: unknown, lang: string): string {
  if (typeof iso !== "string") return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00-04:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang, { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" }).format(d);
}

/** Re-render every `ms` and return the current server-synced time. */
export function useNow(nowMs: () => number, ms = 250): number {
  const [now, setNow] = useState(() => nowMs());
  useEffect(() => {
    const t = setInterval(() => setNow(nowMs()), ms);
    return () => clearInterval(t);
  }, [nowMs, ms]);
  return now;
}

export function secondsLeft(deadline: string | undefined, now: number): number {
  if (!deadline) return 0;
  const end = Date.parse(deadline);
  return Number.isNaN(end) ? 0 : Math.max(0, Math.ceil((end - now) / 1000));
}

export function mmss(s: number): string {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
