// Control Room REST calls (contracts/openapi.yaml): POST /villages/{id}/ask, GET /villages/{id}/qr, POST /clock/warp.
// Bearer = control token (?t=). Offline (?fake=…) every call is answered locally so each region can be demoed.

export interface Citation { kind: "decision" | "fact" | "event" | "rule" | "member"; id: string; label: string; at?: string }
export interface AskAnswer { answer: string; lang: string; citations: Citation[]; degraded: boolean; trace_id?: string }
export interface QrEntry { member_id: string; kind: "app" | "join" | "lid"; url: string; svg?: string }
export interface ClockState { now: string; offset_minutes: number }

import { fakeAsk, fakeCreateVillage, fakeFactHistory, fakeFacts, fakeFactsAsOf, fakeQr } from "../dev/fakeApi";

export interface FactSource { kind: string; ref: string; secs?: number; url?: string; quote?: string }
export interface FactVersion { id: string; value: string; text: string; observed_at: string; recorded_at: string; superseded: boolean; source: FactSource; event_id?: string }
export interface FactHistory { village: string; entity: string; key: string; versions: FactVersion[]; degraded: boolean; degraded_reason?: string }
export interface FactCard extends FactVersion { entity: string; key: string; valid_to?: string | null; labels?: Record<string, string> }
export interface FactsAsOf { village: string; as_of: string; facts: FactCard[]; degraded: boolean }

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
  // the Control Room's control token: ?t=, else ?m=, else the demo default "control"
  return { base, token: p.get("t") ?? p.get("m") ?? (p.get("fake") ? "" : "control"), fake: !!p.get("fake") };
}

async function call<T>(cfg: ApiConfig, method: string, path: string, body?: unknown, extraHeaders: Record<string, string> = {}): Promise<T> {
  const f = cfg.fetchImpl ?? fetch;
  const res = await f(`${cfg.base}${path}`, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}), ...extraHeaders },
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
  // core reads `text`; `answers` is the contract shape
  return call(cfg, "POST", `/villages/${encodeURIComponent(village)}/answers`, { text, answers: [{ question: question.slice(0, 200), text }], lang: "en" });
}

/** Agent Memory (SurrealDB): every version of one fact, newest first (GET /villages/{id}/facts/{entity}/{key}/history). */
export async function getFactHistory(cfg: ApiConfig, village: string, entity: string, key: string): Promise<FactHistory> {
  if (cfg.fake) return fakeFactHistory(village, entity, key);
  return call(cfg, "GET", `/villages/${encodeURIComponent(village)}/facts/${encodeURIComponent(entity)}/${encodeURIComponent(key)}/history`);
}

/** The same fact as of a valid time (GET /villages/{id}/facts?subject&key&as_of). */
export async function getFactsAsOf(cfg: ApiConfig, village: string, entity: string, key: string, asOf: string): Promise<FactsAsOf> {
  if (cfg.fake) return fakeFactsAsOf(village, entity, key, asOf);
  const q = new URLSearchParams({ subject: entity, key, as_of: asOf });
  return call(cfg, "GET", `/villages/${encodeURIComponent(village)}/facts?${q}`);
}

/** Undo an applied proposal within its window (POST /villages/{id}/proposals/{pid}/undo). */
export async function undoProposal(cfg: ApiConfig, village: string, pid: string): Promise<unknown> {
  if (cfg.fake) return { ok: true };
  return call(cfg, "POST", `/villages/${encodeURIComponent(village)}/proposals/${encodeURIComponent(pid)}/undo`);
}

export interface VillageListItem { id: string; name?: string; status?: string; kind?: string; people_count?: number; rev?: number }

/** GET /villages (control bearer): the switcher pills. */
export async function listVillages(cfg: ApiConfig): Promise<VillageListItem[]> {
  if (cfg.fake) return [];
  const r = await call<VillageListItem[] | { villages: VillageListItem[] }>(cfg, "GET", "/villages");
  return Array.isArray(r) ? r : r?.villages ?? [];
}

/** GET /villages/{id}/decisions: the decision log backfill (then control{gate|reasoning} frames). */
export async function listDecisions(cfg: ApiConfig, village: string): Promise<any[]> {
  if (cfg.fake) return [];
  const r = await call<{ decisions: any[] }>(cfg, "GET", `/villages/${encodeURIComponent(village)}/decisions?limit=40`);
  return Array.isArray(r?.decisions) ? r.decisions : [];
}

/** GET /villages/{id}/facts: what Village is running on right now (Agent Memory read model). */
export async function listFacts(cfg: ApiConfig, village: string): Promise<FactsAsOf> {
  if (cfg.fake) return fakeFacts(village);
  return call(cfg, "GET", `/villages/${encodeURIComponent(village)}/facts`);
}

/** Raw request for presenter keys (always real Core, never the fake). */
export async function apiRequest(cfg: ApiConfig, method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<unknown> {
  return call(cfg, method, path, body, headers);
}
