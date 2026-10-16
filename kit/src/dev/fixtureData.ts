// Fake "Core" data for offline demo/tests. Shapes follow ws_messages.schema.json bv_* defs.
// Values not present in contracts/fixtures are marked FAKE and listed in LANE-REPORT (LD-6).
import reyesSpec from "../../../contracts/fixtures/reyes_spec.json";
import wsScam from "../../../contracts/fixtures/ws_sequence_scam.json";
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

/** D22 refill checklist (kit-extension bind, not in contract 1.1.0). lisinopril change is from events_reyes_seed ev_1003_1740_med_change; other doses FAKE. */
export const PRESCRIPTIONS = {
  day: "Sunday",
  owner: "Marco",
  items: [
    { med: "lisinopril", dose: "10 mg", changed: { at: "Oct 3", by: "Dr. Lee", was: "5 mg" } },
    { med: "metformin", dose: "500" },
    { med: "atorvastatin", dose: "20" },
    { med: "apixaban", dose: "5" }
  ],
  source_label: "Ana's call, Oct 3 (Dr. Lee's change)"
};

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
  { event_id: "ev_1016_0811_dose_morning", kind: "dose", at: "2026-10-16T08:11:04-04:00", text: { en: "Morning pills taken", es: "Pastillas de la mañana tomadas" }, source: { kind: "scan", ref: "st_reyes_morning" }, source_label: { en: "Organizer, morning" }, superseded: false },
  { event_id: "ev_1012_0900_shift_1016", kind: "shift", at: "2026-10-12T09:00:00-04:00", text: { en: "Friday: Marco on duty, Ana backup" }, source: { kind: "system", ref: "seed" }, superseded: false },
  { event_id: "ev_1009_1922_incident", kind: "incident", at: "2026-10-09T19:22:15-04:00", text: { en: "Couldn't confirm a $1,500 gift-card request in Marco's name" }, source: { kind: "system", ref: "gate" }, rule_id: "R-MONEY-DEFAULT", superseded: false },
  { event_id: "ev_1003_1740_med_change", kind: "med_change", at: "2026-10-03T17:40:00-04:00", text: { en: "Lisinopril 10 mg (Dr. Lee)" }, source: { kind: "call", ref: "conv_setup_0003", secs: 41 }, source_label: { en: "Ana's call, Oct 3 at 0:41" }, superseded: false },
  { event_id: "ev_0901_med_lisinopril_5", kind: "med_change", at: "2026-09-01T10:00:00-04:00", text: { en: "Lisinopril 5 mg" }, source: { kind: "system", ref: "seed" }, source_label: { en: "Prescription on file (FAKE seed)" }, superseded: true }
];

const lifeAreas = [
  { id: "health", label: "Health: pills", status: { en: "1/2 today", es: "1/2 hoy" } },
  { id: "money", label: "Money: scam calls", status: { en: "Marco verifies money calls", es: "Marco confirma llamadas de dinero" }, rules: ["R-MONEY-VERIFY", "R-MONEY-DEFAULT"], trusted_contacts: ["m_marco", "m_ana"] },
  { id: "people", label: "People: whose turn", status: { en: "Marco on duty", es: "Marco de turno" } }
];

export function baseData(client: FakeClient): Record<string, unknown> {
  switch (client) {
    case "carmen":
      return {
        "alerts:active": [],
        "facts:dose_event?subject=m_carmen&valid_at=today": doseToday(false),
        "rota:current.on_duty": marcoPerson
      };
    case "ana":
      return {
        "alerts:active": [],
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
      const data = { ...(snap?.data ?? {}) } as Record<string, unknown>;
      if (client === "lucia") {
        data["rota:current?member=me"] = {
          is_my_turn: false, date: "2026-10-16", on_duty: marcoPerson, backup: anaPerson, until: null, next_shift: "2026-10-17",
          answer: { en: "No. Marco is on tonight; you're next on Saturday." }
        };
      }
      data["prescriptions:current"] = PRESCRIPTIONS;
      return data;
    }
    default:
      return {};
  }
}

function connectSnapshot(): any {
  return (wsScam as any).sequences.connect.find((f: any) => f.dir === "s2c" && f.msg.type === "snapshot")?.msg;
}

/** D22 overlay the fake Core applies to the rev-4 fixture: elder loses the "Ya me la tomé" log_dose button and the
 *  dose tracker (the organizer is the tool), gains "Llamar a Village" + TonightCard; helper/coordinator gain RefillCard. */
export function d22Overlay(view: View, role: string): View {
  const v = structuredClone(view);
  const screen = v.elements.s;
  if (role === "elder") {
    v.elements.b_pill = {
      type: "BigButton",
      props: { label: "Llamar a Village", icon: "phone", tone: "ok", action: "call_number", action_arg: "village", confirm: false, speak: "Llamando a Village" }
    };
    delete v.elements.hoy;
    v.elements.tonight = { type: "TonightCard", props: { bind: "rota:current.on_duty" } };
    screen.children = ["al", "tonight", "b_pill", "b_call", "b_help", "e911"];
    if (v.needs_served) {
      delete v.needs_served.hoy;
      v.needs_served.tonight = ["n_turns"];
      v.needs_served.b_pill = ["n_safety"];
    }
  }
  if (role === "helper" || role === "coordinator") return withRefill(v, role);
  return v;
}

export function withRefill(view: View, role: string): View {
  const v = structuredClone(view);
  if (v.elements.refill) return v;
  v.elements.refill = { type: "RefillCard", props: { bind: "prescriptions:current", owner: "Marco", day: "Sunday" } };
  const kids = v.elements.s.children ?? [];
  const at = role === "coordinator" ? Math.max(1, kids.indexOf("dose") + 1) : Math.min(kids.length, 3);
  kids.splice(at, 0, "refill");
  v.elements.s.children = kids;
  if (v.needs_served) v.needs_served.refill = ["n_dose_change"];
  return v;
}

export function fakeSnapshot(client: FakeClient, rev = 4) {
  const meta = FAKE_CLIENTS[client];
  if (client === "control") {
    return { type: "snapshot", contract_version: "1.2.0", rev, village: "v_reyes", role: "control", member_id: null, spec: reyesSpec, data: {}, now: SNAPSHOT_NOW };
  }
  const view = d22Overlay((reyesSpec as any).views[meta.role] as View, meta.role);
  return { type: "snapshot", contract_version: "1.2.0", rev, village: "v_reyes", role: meta.role, member_id: meta.member_id, spec: view, data: baseData(client), now: SNAPSHOT_NOW };
}

export interface SeqFrame { t: string; client: string; dir: "s2c" | "c2s"; msg: any }
export function sequence(name: string): SeqFrame[] {
  return ((wsScam as any).sequences[name] ?? []) as SeqFrame[];
}
