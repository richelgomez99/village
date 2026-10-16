// Control Room REST calls (contracts/openapi.yaml): POST /villages/{id}/ask, GET /villages/{id}/qr, POST /clock/warp.
// Bearer = control token (?t=). Offline (?fake=…) every call is answered locally so each region can be demoed.

export interface Citation { kind: "decision" | "fact" | "event" | "rule" | "member"; id: string; label: string; at?: string }
export interface AskAnswer { answer: string; lang: string; citations: Citation[]; degraded: boolean; trace_id?: string }
export interface QrEntry { member_id: string; kind: "app" | "join" | "lid"; url: string; svg?: string }
export interface ClockState { now: string; offset_minutes: number }

import { fakeAsk, fakeCreateVillage, fakeQr } from "../dev/fakeApi";

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

export async function askVillage(cfg: ApiConfig, village: string, question: string): Promise<AskAnswer> {
  if (cfg.fake) return fakeAsk(question);
  return call<AskAnswer>(cfg, "POST", `/villages/${encodeURIComponent(village)}/ask`, { question, lang: "en" });
}

export async function getQr(cfg: ApiConfig, village: string): Promise<QrEntry[]> {
  if (cfg.fake) return fakeQr(village);
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

/** Founding: POST /villages {description} → 202 {village_id, ws_url}; the room then follows that village's socket. */
export async function createVillage(cfg: ApiConfig, description: string): Promise<{ village_id: string; plan?: string }> {
  if (cfg.fake) return fakeCreateVillage(description);
  return call(cfg, "POST", "/villages", { description, language: "en" });
}

/** Founding follow-up: POST /villages/{id}/answers {answers:[{question, text}]}. */
export async function answerFollowUp(cfg: ApiConfig, village: string, question: string, text: string): Promise<{ village_id: string; state: string }> {
  if (cfg.fake) return { village_id: village, state: "building" };
  return call(cfg, "POST", `/villages/${encodeURIComponent(village)}/answers`, { answers: [{ question: question.slice(0, 200), text }], lang: "en" });
}
