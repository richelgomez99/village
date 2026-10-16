// One home for each fact (KIT-MEMBERS-4, D35). "Resolved vs pending" from the data the kit already has, never from strings:
// - a verification is pending while some bound record says so (verifications:pending*, an alert's verification.status === "pending");
// - an incident is resolved when its verification reached a terminal status (denied · confirmed · timeout), when its decision
//   mode says Village decided (refused · acted_alone), or when it carries a verification that is not pending anywhere
//   (the gate closed it with its default, e.g. the receptionist refusing an unknown caller's money ask under Carmen's rule, D37);
// - it still needs a human when a verification is pending, when its decision mode is asked_human, or when Village has no
//   decision and no verification for it.
const TERMINAL = new Set(["denied", "confirmed", "timeout", "refused", "expired", "cancelled"]);
const DECIDED = new Set(["refused", "acted_alone"]);

export interface IncidentLike {
  incident_id?: string; type?: string; status?: string; at?: string; title?: unknown; summary?: unknown;
  verification_id?: string; verification_status?: string; decision?: { mode?: string } | null; mode?: string;
}

/** verification ids some bound record still lists as pending */
export function pendingVerificationIds(data: Record<string, unknown>): Set<string> {
  const out = new Set<string>();
  for (const [key, v] of Object.entries(data)) {
    const rows = Array.isArray(v) ? v : v && typeof v === "object" ? [v] : [];
    for (const r of rows as Record<string, any>[]) {
      if (!r || typeof r !== "object") continue;
      if (key.startsWith("verifications:") && r.verification_id && (r.status == null || r.status === "pending")) out.add(r.verification_id);
      if (r.verification?.id && r.verification.status === "pending") out.add(r.verification.id);
      if (key.startsWith("verifications:") && r.id && r.status === "pending") out.add(r.id);
    }
  }
  return out;
}

export function decisionMode(inc: IncidentLike): string | undefined {
  return inc.decision?.mode ?? inc.mode;
}

export function incidentResolved(inc: IncidentLike, pending: Set<string>): boolean {
  if (inc.verification_id && pending.has(inc.verification_id)) return false;
  if (inc.verification_status === "pending") return false;
  const mode = decisionMode(inc);
  if (mode === "asked_human") return false;
  if (inc.verification_status && TERMINAL.has(inc.verification_status)) return true;
  if (mode && DECIDED.has(mode)) return true;
  return !!inc.verification_id;
}

/** an open incident that still needs someone (Home's attention group, the only place "I've got it" shows) */
export function incidentNeedsHuman(inc: IncidentLike, pending: Set<string>): boolean {
  return inc.status === "open" && !incidentResolved(inc, pending);
}

/** the ledger kind of a resolved incident: Village checked with a person (a verification answered), or refused on its own */
export function resolvedMode(inc: IncidentLike): "asked_human" | "refused" | "acted_alone" {
  const mode = decisionMode(inc);
  if (mode === "refused" || mode === "acted_alone") return mode;
  if (inc.verification_status === "denied" || inc.verification_status === "confirmed") return "asked_human";
  if (inc.verification_status === "timeout") return "acted_alone";
  return "refused";
}

/** resolved incidents from every incidents:* bind, newest first, deduped by id */
export function resolvedIncidents(data: Record<string, unknown>): IncidentLike[] {
  const pending = pendingVerificationIds(data);
  const seen = new Set<string>();
  const out: IncidentLike[] = [];
  for (const [key, v] of Object.entries(data)) {
    if (!key.startsWith("incidents:") || !Array.isArray(v)) continue;
    for (const inc of v as IncidentLike[]) {
      const id = inc?.incident_id ?? "";
      if (!inc || seen.has(id) || !incidentResolved(inc, pending)) continue;
      seen.add(id);
      out.push(inc);
    }
  }
  return out.sort((a, b) => Date.parse(b.at ?? "") - Date.parse(a.at ?? ""));
}
