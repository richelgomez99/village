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
