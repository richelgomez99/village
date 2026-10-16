// Presenter mode (control.html?t=control&presenter=1): keys drive the REAL Core (Bearer control token), never fakes.
// presenterRequest(key, ctx) is pure (key → request + toast) so the mapping is testable with a mocked fetch.

/** Scripted founding answers read on stage (docs/FOUNDING-INTAKE.md A10, A11, A12, verbatim). */
export const SCRIPT = [
  "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text.",
  "After lunch, around one-thirty. And she hates calls at night.",
  "Lucía should see the refill list too, she does the ordering."
];

export type CallerRole = "elder" | "unknown";

export interface PresenterCtx {
  village: string;
  /** spec.blueprint.description.text of the selected village (or a demo_spoken_description) */
  description: string;
  /** first pending proposal id, if any */
  pendingProposal: string | null;
  coordinatorName: string;
  caller: CallerRole;
  adminKey: string;
}

export interface PresenterRequest {
  method: "POST";
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
  toast: string;
  /** after success: re-open the village socket (reset), flip the caller state, … */
  after?: "reselect" | "caller";
}

export const KEY_MAP: [string, string][] = [
  ["R", "Reset the demo (Core) and re-open the village"],
  ["F", "Resume the founding at 8 of 10"],
  ["1 · 2 · 3", "Send answer 10 · 11 · 12"],
  ["P", "Ask the Watcher to look again (rebuild)"],
  ["A", "Approve the first pending proposal"],
  ["U", "Switch the presenter phone: elder ↔ unknown caller"],
  ["V", "Next village"],
  ["D", "Details on/off"],
  ["Esc", "Hide this map"]
];

/** Key → Core request (null for room-only keys or when it can't apply). */
export function presenterRequest(key: string, c: PresenterCtx): PresenterRequest | null {
  const v = encodeURIComponent(c.village);
  switch (key.toLowerCase()) {
    case "r":
      return { method: "POST", path: "/admin/reset", body: {}, headers: { "X-Admin-Key": c.adminKey }, toast: "Demo reset · every phone back to the start", after: "reselect" };
    case "f":
      return {
        method: "POST", path: "/villages",
        body: { description: c.description, language: "en", mode: "fixture", resume: 8, village_id: c.village, pace: 3 },
        toast: "Founding resumed at 8 of 10"
      };
    case "1":
    case "2":
    case "3": {
      const i = Number(key) - 1;
      return { method: "POST", path: `/villages/${v}/answers`, body: { text: SCRIPT[i] }, toast: `Answer ${10 + i} sent` };
    }
    case "p":
      return { method: "POST", path: `/villages/${v}/evolve/trigger`, toast: "The Watcher is weighing fixes" };
    case "a":
      return c.pendingProposal
        ? { method: "POST", path: `/villages/${v}/proposals/${encodeURIComponent(c.pendingProposal)}/approve`, toast: `Approved as ${c.coordinatorName}` }
        : null;
    case "u": {
      const next: CallerRole = c.caller === "elder" ? "unknown" : "elder";
      return { method: "POST", path: "/admin/demo-caller", body: { role: next }, toast: next === "elder" ? "Presenter phone calls as the elder" : "Presenter phone calls as an unknown caller", after: "caller" };
    }
    default:
      return null;
  }
}

/** ROOM-7 keys (M S T W L B X), shown in the key map. */
export const KEY_MAP_7: [string, string][] = [
  ["M", "The elder reports a money call (scam beat)"],
  ["S", "Coordinator asks the chat for cover"],
  ["T", "Coordinator posts the Thanksgiving plan (@Village)"],
  ["W", "Warm Core"],
  ["L", "Latest receipt, with the phone-check recording"],
  ["B", "The block village's founding call (replay) · Esc back"],
  ["X", "Panic: this beat as a replay with controls · X again back"]
];

/** The people a demo line needs, from the spec: the center person, the coordinator, the money verifier, another helper. */
export function demoCast(spec: any) {
  const people: any[] = spec?.blueprint?.people ?? [];
  const first = (p: any) => (p ? String(p.short_name && p.role !== "care_recipient" ? p.short_name : p.name).split(" ")[0] : "");
  const center = people.find((p) => p.role === "care_recipient");
  const coord = people.find((p) => p.id === spec?.village?.coordinator_id) ?? people.find((p) => p.role === "coordinator");
  const money = (spec?.blueprint?.life_areas ?? []).find((a: any) => a.id === "money");
  const verifier = people.find((p) => p.id === money?.trusted_contacts?.[0]) ?? people.find((p) => p.consent?.money_verifier && p.role !== "coordinator");
  const other = people.find((p) => p !== center && p !== coord && p !== verifier && p.view);
  return { center, coord, verifier, other, centerName: first(center), coordName: first(coord), verifierName: first(verifier), otherName: first(other) };
}

/** M: the money call the elder reports (voice tool body, contract req_report_money_request). */
export function moneyCallBody(spec: any, village: string, now = Date.now()) {
  const c = demoCast(spec);
  return {
    conversation_id: `conv_stage_${now}`, caller_id: c.center?.phone ?? "", call_secs: 9, village_id: village,
    utterance: `Me llamó ${c.verifierName} llorando, dice que está en problemas y necesita dos mil dólares.`,
    claimed_member: c.verifier?.id, amount: 2000, currency: "USD", method: "wire", urgency: "now", lang: "es"
  };
}

/** S / T: the coordinator's chat lines (names from the spec). */
export function coverLine(spec: any): string {
  return `I need someone to cover for ${demoCast(spec).verifierName || "the helper"} tomorrow`;
}
export function thanksgivingLine(spec: any): string {
  const c = demoCast(spec);
  return `@Village we're doing Thanksgiving at Mom's on the 27th. Twelve of us. ${c.verifierName} brings the turkey, ${c.otherName} brings the pie and comes in on the 11:40 train, someone has to pick her up at Penn Station at 1. Grandpa needs a low-salt plate. And no politics at the table.`;
}

/** The coordinator's member token: ?ana=… (named by role, not person: ?coord=… also works) or the `m=` of their app QR. */
export function coordinatorTokenFromQr(entries: { member_id: string; kind: string; url: string }[], coordinatorId: string | undefined): string | null {
  const e = entries.find((x) => x.member_id === coordinatorId && x.kind === "app") ?? entries.find((x) => x.member_id === coordinatorId);
  if (!e) return null;
  const m = e.url.match(/[?#&]m=([^&#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
