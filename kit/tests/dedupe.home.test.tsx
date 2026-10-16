// KIT-MEMBERS-4: one home for each fact. KIT-MEMBERS-6: only the decider sees Approve.
import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { renderView } from "./helpers";
import { incidentNeedsHuman, incidentResolved, pendingVerificationIds, resolvedMode } from "../src/util/resolved";
import { rightNowLines } from "../src/components/brief";

const R = reyes as any;
const NOW = Date.parse("2026-10-16T21:00:00-04:00");
const scam = { incident_id: "inc_ver_0001", type: "suspected_scam", severity: "high", status: "open", title: { en: "Scam stopped" }, summary: { en: "Someone claiming to be Marco asked Mamá for $2,000. Marco confirmed it wasn't him." }, verification_id: "ver_0001", verification_status: "denied", provenance: [], at: "2026-10-16T20:50:00-04:00" };
const refusedAsk = { incident_id: "inc_stub", type: "unverified_money_request", severity: "high", status: "open", title: { en: "Money request needs review" }, summary: { en: "Unknown caller asked for money" }, verification_id: "ver_0002", provenance: [], at: "2026-10-16T20:55:08-04:00" };
const waiting = { incident_id: "inc_wait", type: "suspected_scam", severity: "high", status: "open", title: { en: "Checking with Marco" }, summary: { en: "Someone says they are Marco." }, verification_id: "ver_0003", provenance: [], at: "2026-10-16T20:58:00-04:00" };
const data = (extra: Record<string, unknown> = {}) => ({
  "alerts:active": [{ id: "al_1", severity: "danger", title: { en: "Scam stopped" }, body: { en: "The request was denied by the real contact." }, verification: { id: "ver_0001", claimed_member_id: "m_marco", deadline: "2026-10-16T20:50:45-04:00", status: "denied" }, at: "2026-10-16T20:50:00-04:00" }],
  "incidents:open": [scam, refusedAsk],
  "rounds:latest": { counts: { acted_alone: 3, asked_human: 2, refused: 1 }, rows: [{ at: "2026-10-16T21:40:00-04:00", text: "Blocked by code: no calls after 9:30 PM.", mode: "refused" }] },
  "timeline:subject=m_carmen": [{ event_id: "ev_0023", kind: "incident", at: "2026-10-16T20:55:08-04:00", text: { en: "Money request needs review" } }],
  ...extra
});

describe("resolved vs pending (from verification / decision data, not strings)", () => {
  it("terminal verification or a closed verification = resolved; a pending one or asked_human = needs a human", () => {
    const none = new Set<string>();
    expect(incidentResolved(scam, none)).toBe(true);
    expect(incidentResolved(refusedAsk, none)).toBe(true);
    expect(resolvedMode(scam)).toBe("asked_human");
    expect(resolvedMode(refusedAsk)).toBe("refused");
    const pending = pendingVerificationIds({ "verifications:pending?member=me": { verification_id: "ver_0003", status: "pending" } });
    expect(incidentNeedsHuman(waiting, pending)).toBe(true);
    expect(incidentNeedsHuman({ ...refusedAsk, decision: { mode: "asked_human" } }, none)).toBe(true);
    expect(incidentNeedsHuman({ incident_id: "x", status: "open" }, none)).toBe(true); // no decision, no verification
  });
});

describe("Ana's home: each fact once", () => {
  it("no urgent card and no Needs-your-yes entry for resolved items; ledger carries them with kind chips; tiles only", () => {
    const { container } = renderView(R.views.coordinator, data(), { role: "coordinator", nowMs: () => NOW });
    expect(container.querySelector("[data-test='alert'][data-severity='danger']")).toBeNull();
    expect(container.querySelector("[data-test='incident-ack']")).toBeNull();
    const rows = [...container.querySelectorAll("[data-test='wvd-row']")].map((r) => r.textContent ?? "");
    expect(rows.some((t) => t.includes("asked a person") && t.includes("Marco confirmed"))).toBe(true);
    expect(rows.some((t) => t.includes("refused itself") && t.includes("Unknown caller asked for money"))).toBe(true);
    expect(container.querySelector("[data-test='wvd-counts']")).toBeNull();
    expect(container.querySelector("[data-test='wvd-stats']")?.textContent).toContain("3 asked a person");
  });
  it("RIGHT NOW's Last: reads what happened, not 'needs review'", () => {
    const last = rightNowLines(data(), NOW, "en").find((l) => l.key === "last")!;
    expect(last.text).toMatch(/^Last: Village refused a money ask · /);
  });
  it("a verification still waiting stays in Needs your attention with I've got it", () => {
    const { container } = renderView(R.views.coordinator, data({ "incidents:open": [scam, waiting], "verifications:pending?member=me": { verification_id: "ver_0003", status: "pending" } }), { role: "coordinator", nowMs: () => NOW, openOnly: true });
    const acks = container.querySelectorAll("[data-test='incident-ack']");
    expect(acks.length).toBe(1);
    expect(acks[0].closest("[data-incident-id]")?.getAttribute("data-incident-id")).toBe("inc_wait");
  });
});

describe("KIT-MEMBERS-6: who decides", () => {
  const card = { proposal_id: "prop_1", status: "awaiting_approval", title: { en: "Answer unknown callers first" }, why: { en: "x" }, changes: [], evidence_labels: [] };
  const chat = [{ id: "m1", author: "village", kind: "proposal", text: "Village proposes answering unknown callers first.", refs: [{ kind: "proposal", id: "prop_1" }], at: "2026-10-16T14:22:27-04:00" }];
  const ana = { member_id: "m_ana", name: "Ana", role: "coordinator" };
  it("a helper sees no Approve anywhere, only 'Ana is deciding'", () => {
    const { container } = renderView(R.views.coordinator, { "proposals:pending": [card], "chat:village": chat, "member:m_ana": ana }, { role: "helper", memberId: "m_marco" });
    expect(container.querySelector("[data-test='proposal-approve']")).toBeNull();
    expect(container.querySelector("[data-test='chat-proposal-approve']")).toBeNull();
    expect(container.querySelector("[data-test='proposal-status']")?.textContent).toBe("Ana is deciding");
  });
  it("after the receipt: 'Approved by Ana · built → live'", () => {
    const rows = [...chat, { id: "m2", author: "village", kind: "receipt", text: "Done.", refs: [{ kind: "proposal", id: "prop_1" }], at: "2026-10-16T14:22:53-04:00" }];
    const { container } = renderView(R.views.coordinator, { "proposals:pending": [], "chat:village": rows, "member:m_ana": ana }, { role: "helper", memberId: "m_marco" });
    expect(container.querySelector("[data-test='proposal-status']")?.textContent).toBe("Approved by Ana · built → live");
  });
  it("the coordinator keeps Approve", () => {
    const { container } = renderView(R.views.coordinator, { "proposals:pending": [card], "chat:village": chat, "member:m_ana": ana }, { role: "coordinator", memberId: "m_ana" });
    expect(container.querySelector("[data-test='proposal-approve']")).not.toBeNull();
  });
});
