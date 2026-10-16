// Fake "Core" data for offline demo/tests. Shapes follow ws_messages.schema.json bv_* defs.
// Values not present in contracts/fixtures are marked FAKE and listed in LANE-REPORT (LD-6).
import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";
import blockSpec from "../../../contracts/fixtures/block_spec.json";
import type { View } from "../renderer/view";

export type FakeClient = "carmen" | "ana" | "marco" | "lucia" | "control";

export const FAKE_CLIENTS: Record<FakeClient, { member_id: string | null; role: string; name: string }> = {
  carmen: { member_id: "m_carmen", role: "elder", name: "Carmen" },
  ana: { member_id: "m_ana", role: "coordinator", name: "Ana" },
  marco: { member_id: "m_marco", role: "helper", name: "Marco" },
  lucia: { member_id: "m_lucia", role: "helper", name: "Lucía" },
  control: { member_id: null, role: "control", name: "Control Room" }
};

export function clientForMember(memberId: string): FakeClient | null {
  return (Object.keys(FAKE_CLIENTS) as FakeClient[]).find((c) => FAKE_CLIENTS[c].member_id === memberId) ?? null;
}

export const SNAPSHOT_NOW = "2026-10-16T14:01:40-04:00";

const marcoPerson = { member_id: "m_marco", name: "Marco" };
const anaPerson = { member_id: "m_ana", name: "Ana" };

/** bv_prescriptions straight from the fixture's connect snapshot (contract 1.2.2, D22). */
export const PRESCRIPTIONS = (connectSnapshot()?.data?.["prescriptions:current"] ?? null) as unknown;

const doseToday = (withMeds: boolean) => ({
  date: "2026-10-16",
  slots: [
    { slot: "morning", status: "taken", taken_at: "2026-10-16T08:11:04-04:00", via: "lid_qr", lid_color: "#E8B12F", ...(withMeds ? { meds: ["lisinopril 10 mg", "metformin 500 mg", "apixaban 5 mg"] } : {}) },
    { slot: "evening", status: "upcoming", taken_at: null, via: null, lid_color: "#2F5FA7", ...(withMeds ? { meds: ["metformin 500 mg", "atorvastatin 20 mg", "apixaban 5 mg"] } : {}) }
  ]
});

const doseWeek = {
  days: ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"].map((date, i) => ({
    date,
    slots: [
      { slot: "morning", status: "taken", taken_at: `${date}T08:1${i}:00-04:00`, via: "phone_line" },
      { slot: "evening", status: date === "2026-10-16" ? "upcoming" : date === "2026-10-14" ? "uncertain" : "taken", taken_at: null, via: null }
    ]
  }))
};

const rotaWeek = [
  ["2026-10-12", "Mon", "m_ana", "m_marco"], ["2026-10-13", "Tue", "m_lucia", "m_ana"], ["2026-10-14", "Wed", "m_ana", "m_lucia"],
  ["2026-10-15", "Thu", "m_marco", "m_ana"], ["2026-10-16", "Fri", "m_marco", "m_ana"], ["2026-10-17", "Sat", "m_lucia", "m_marco"],
  ["2026-10-18", "Sun", "m_marco", "m_ana"]
].map(([date, day, on_duty, backup]) => ({ date, day, on_duty, backup }));

const timeline = [
  { event_id: "ev_1016_0811_dose_morning", kind: "dose", at: "2026-10-16T08:11:04-04:00", text: { en: "Morning pills taken", es: "Pastillas de la mañana tomadas" }, source: { kind: "scan", ref: "st_reyes_morning" }, source_label: { en: "Check-in call, morning" }, superseded: false },
  { event_id: "ev_1012_0900_shift_1016", kind: "shift", at: "2026-10-12T09:00:00-04:00", text: { en: "Friday: Marco on duty, Ana backup" }, source: { kind: "system", ref: "seed" }, superseded: false },
  { event_id: "ev_1009_1922_incident", kind: "incident", at: "2026-10-09T19:22:15-04:00", text: { en: "Couldn't confirm a $1,500 gift-card request in Marco's name" }, source: { kind: "system", ref: "gate" }, rule_id: "R-MONEY-DEFAULT", superseded: false },
  { event_id: "ev_1003_1740_med_change", kind: "med_change", at: "2026-10-03T17:40:00-04:00", text: { en: "Lisinopril 10 mg (Dr. Park)" }, source: { kind: "call", ref: "conv_setup_0003", secs: 41 }, source_label: { en: "Ana's call, Oct 3 at 0:41" }, superseded: false },
  { event_id: "ev_0901_med_lisinopril_5", kind: "med_change", at: "2026-09-01T10:00:00-04:00", text: { en: "Lisinopril 5 mg" }, source: { kind: "system", ref: "seed" }, source_label: { en: "Prescription on file (FAKE seed)" }, superseded: true }
];

const lifeAreas = [
  { id: "health", label: "Pills", status: { en: "morning pills taken · refill Friday · Marco", es: "pastillas de la mañana tomadas · relleno el viernes · Marco" } },
  { id: "money", label: "Money: scam calls", status: { en: "1 scam stopped · Marco checks money calls", es: "1 estafa detenida · Marco confirma llamadas de dinero" }, rules: ["R-MONEY-VERIFY", "R-MONEY-DEFAULT"], trusted_contacts: ["m_marco", "m_ana"] },
  { id: "people", label: "People: whose turn", status: { en: "Marco on duty tonight", es: "Marco de turno esta noche" } }
];

export function baseData(client: FakeClient): Record<string, unknown> {
  switch (client) {
    case "carmen":
      return {
        "alerts:active": [],
        "member:m_ana": memberRecords()["member:m_ana"],
        "facts:dose_event?subject=m_carmen&valid_at=today": doseToday(false),
        "rota:current.on_duty": marcoPerson
      };
    case "ana":
      return {
        "alerts:active": [],
        ...memberRecords(),
        "blueprint:life_areas": lifeAreas,
        "incidents:open": [],
        "verifications:pending?member=me": null,
        "facts:dose_event?subject=m_carmen&valid_at=today": doseToday(true),
        "facts:dose_event?subject=m_carmen&valid_at=week": doseWeek,
        "rota:week": rotaWeek,
        "timeline:subject=m_carmen": timeline,
        "prescriptions:current": PRESCRIPTIONS
      };
    case "marco":
    case "lucia": {
      const snap = connectSnapshot();
      const data = { ...(snap?.data ?? {}), "member:m_carmen": memberRecords()["member:m_carmen"] } as Record<string, unknown>;
      if (client === "lucia") {
        data["rota:current?member=me"] = {
          is_my_turn: false, date: "2026-10-16", on_duty: marcoPerson, backup: anaPerson, until: null, next_shift: "2026-10-17",
          answer: { en: "No. Marco is on tonight; you're next on Saturday." }
        };
      }
      return data;
    }
    default:
      return {};
  }
}

function connectSnapshot(): any {
  return (wsScam as any).sequences.connect.find((f: any) => f.dir === "s2c" && f.msg.type === "snapshot")?.msg;
}

export const VILLAGE_NAME = "Familia Reyes";

/** snapshot.identity (contract 1.2.2, D21). */
/** The Village line (identity.village_number); the fixture's printables still say [NÚMERO]. */
export const FAKE_VILLAGE_NUMBER = "+18482579221";

export function fakeIdentity(client: FakeClient, viewAs = false) {
  const meta = FAKE_CLIENTS[client];
  const lang = meta.role === "elder" ? "es" : "en";
  return { member_id: meta.member_id, name: meta.name, role: meta.role, village_name: VILLAGE_NAME, village_number: FAKE_VILLAGE_NUMBER, lang, ...(viewAs ? { view_as: true } : {}) };
}

/** member:<id> records (bv_person with phone) for everyone in the fixture's blueprint. */
function memberRecords(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const p of (reyesSpec as any).blueprint.people) out[`member:${p.id}`] = { member_id: p.id, name: String(p.name).split(" ")[0], ...(p.phone ? { phone: p.phone } : {}) };
  return out;
}

/** The fixture's views are sent unchanged (rev 5 already carries D22). */
export function fakeSnapshot(client: FakeClient, opts: { viewAs?: boolean; rev?: number } = {}) {
  const meta = FAKE_CLIENTS[client];
  const rev = opts.rev ?? (reyesSpec as any).rev ?? 5;
  const identity = fakeIdentity(client, opts.viewAs);
  if (client === "control") {
    return { type: "snapshot", contract_version: "1.2.2", rev, village: "v_reyes", role: "control", member_id: null, spec: reyesSpec, data: controlData(), now: SNAPSHOT_NOW, identity };
  }
  const view = (reyesSpec as any).views[meta.role] as View;
  return { type: "snapshot", contract_version: "1.2.2", rev, village: "v_reyes", role: meta.role, member_id: meta.member_id, spec: view, data: baseData(client), now: SNAPSHOT_NOW, identity };
}

/** Control Room snapshot data: every bind any view uses, so the three-phone mirror renders the whole spec. */
export function controlData(): Record<string, unknown> {
  return { ...baseData("carmen"), ...baseData("marco"), ...baseData("ana"), "rounds:latest": ROUNDS, "chat:village": CHAT_SEED };
}

/** Last night's Watcher round (core/watcher/rounds.py result shape). */
export const ROUNDS = {
  village: "v_reyes", round_at: "2026-10-15T20:00:00-04:00",
  counts: { acted_alone: 3, asked_human: 1, refused: 1 },
  rows: [
    { id: "dc_round_r1_01", at: "2026-10-15T20:02:00-04:00", mode: "acted_alone", text: "Evening check-in call: she looked at her organizer, evening pills taken; nobody needed a call." },
    { id: "dc_round_r1_02", at: "2026-10-15T20:03:00-04:00", mode: "acted_alone", text: "Told Marco he's on tomorrow, Friday, at 3 PM as he asked." },
    { id: "dc_round_r1_03", at: "2026-10-15T20:04:00-04:00", mode: "acted_alone", text: "Re-ran the scam eval set: 30/30 caught." },
    { id: "dc_round_r1_04", at: "2026-10-15T20:05:00-04:00", mode: "asked_human", text: "Asked Ana: Lucía has had no nights in 14 days; does she want Saturdays?" },
    { id: "dc_round_r1_05", at: "2026-10-15T20:06:00-04:00", mode: "refused", rule_id: "P-QH-01", text: "Didn't call Carmen at 9:40 PM to remind her about water: after 9:30 PM, no calls (her words)." }
  ]
};

/** A week of family chat (D16), seeded. */
export const CHAT_SEED = [
  { id: "msg_seed_1", village: "v_reyes", author: "village", kind: "nudge", text: "Marco, you're on tonight until 9:30.", refs: [{ kind: "rota", id: "2026-10-16" }], source: { kind: "system", ref: "watcher" }, at: "2026-10-16T15:00:00-04:00" },
  { id: "msg_seed_2", village: "v_reyes", author: "m_marco", kind: "chat", text: "On it. Bringing soup.", refs: [], source: { kind: "app", ref: "m_marco" }, at: "2026-10-16T15:04:00-04:00" }
];

export interface SeqFrame { t: string; client: string; dir: "s2c" | "c2s"; msg: any }
export function sequence(name: string): SeqFrame[] {
  return ((wsScam as any).sequences[name] ?? []) as SeqFrame[];
}

/** West 147th (block_spec.json) control snapshot: no live data offline, the regions show the blueprint and empty phones. */
export function blockControlSnapshot() {
  const identity = { member_id: null, name: "Control Room", role: "control", village_name: (blockSpec as any).village.name, lang: "en" };
  return { type: "snapshot", contract_version: "1.2.2", rev: (blockSpec as any).rev, village: (blockSpec as any).village.id, role: "control", member_id: null, spec: blockSpec, data: {}, now: SNAPSHOT_NOW, identity };
}

/** Villages the offline fake knows (Control Room switcher). */
export const FAKE_VILLAGES = ["v_reyes", "v_w147"];
