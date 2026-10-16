// Control Room REST calls (contracts/openapi.yaml): POST /villages/{id}/ask, GET /villages/{id}/qr, POST /clock/warp.
// Bearer = control token (?t=). Offline (?fake=…) every call is answered locally so each region can be demoed.

export interface Citation { kind: "decision" | "fact" | "event" | "rule" | "member"; id: string; label: string; at?: string }
export interface AskAnswer { answer: string; lang: string; citations: Citation[]; degraded: boolean; trace_id?: string }
export interface QrEntry { member_id: string; kind: "app" | "join" | "lid"; url: string; svg?: string }
export interface ClockState { now: string; offset_minutes: number }

export interface ApiConfig {
  base: string;
  token: string;
  fake: boolean;
  fetchImpl?: typeof fetch;
}

export function apiConfig(loc: Location = window.location): ApiConfig {
  const p = new URLSearchParams(loc.search);
  const env = (import.meta as any).env ?? {};
  const base: string = env.VITE_CORE_HTTP ?? (env.DEV ? "http://localhost:8787" : `${loc.protocol}//${loc.host}`);
  return { base, token: p.get("t") ?? p.get("m") ?? "", fake: !!p.get("fake") };
}

async function call<T>(cfg: ApiConfig, method: string, path: string, body?: unknown): Promise<T> {
  const f = cfg.fetchImpl ?? fetch;
  const res = await f(`${cfg.base}${path}`, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as T;
}

const FAKE_ANSWERS: [RegExp, AskAnswer][] = [
  [
    /marco/i,
    {
      answer: "Village called Marco, not Lucía, because the caller used Marco's name and Marco agreed to calls when he joined. If nobody answers in 45 seconds the answer is \"don't send\".",
      lang: "en", degraded: false,
      citations: [
        { kind: "decision", id: "dc_1016_1402_money", label: "Gate · R-MONEY-VERIFY · 14:02" },
        { kind: "member", id: "m_marco", label: "Marco · consent to calls (Oct 16)" },
        { kind: "rule", id: "R-MONEY-DEFAULT", label: "No answer means don't send" }
      ]
    }
  ],
  [
    /screen|differ|app/i,
    {
      answer: "Carmen gets 3 big buttons in Spanish because she uses a flip phone and reads Spanish; Marco gets one question because he works nights and only needs to know whose turn it is.",
      lang: "en", degraded: false,
      citations: [
        { kind: "fact", id: "m_carmen.tech_comfort", label: "Carmen · phone only · Spanish" },
        { kind: "fact", id: "m_marco.availability", label: "Marco · nights, leaves 9:30" }
      ]
    }
  ]
];

export async function askVillage(cfg: ApiConfig, village: string, question: string): Promise<AskAnswer> {
  if (cfg.fake) {
    await new Promise((r) => setTimeout(r, 400));
    const hit = FAKE_ANSWERS.find(([re]) => re.test(question));
    return hit ? hit[1] : { answer: "Village has no decision on record about that yet.", lang: "en", degraded: true, citations: [] };
  }
  return call<AskAnswer>(cfg, "POST", `/villages/${encodeURIComponent(village)}/ask`, { question, lang: "en" });
}

export async function getQr(cfg: ApiConfig, village: string): Promise<QrEntry[]> {
  if (cfg.fake) {
    const here = typeof window !== "undefined" ? `${window.location.origin}${window.location.pathname.replace(/control\.html$/, "")}` : "/";
    return ["m_marco", "m_ana", "m_carmen"].map((m) => ({ member_id: m, kind: "app" as const, url: `${here}?fake=${m.slice(2)}` }));
  }
  return call<QrEntry[]>(cfg, "GET", `/villages/${encodeURIComponent(village)}/qr?kind=app&format=json`);
}

export async function warpClock(cfg: ApiConfig, minutes: number): Promise<ClockState> {
  if (cfg.fake) {
    const f = (window as any).__fake;
    if (f?.warp) return f.warp(minutes);
    throw new Error("no fake hub");
  }
  return call<ClockState>(cfg, "POST", "/clock/warp", { minutes });
}
