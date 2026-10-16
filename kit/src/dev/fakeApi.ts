// Offline answers for the Control Room REST calls (?fake=…). Reyes-fixture wording lives here, never in kit/src outside dev/.
import type { AskAnswer, FactHistory, FactsAsOf, QrEntry } from "../control/api";

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

export async function fakeAsk(question: string): Promise<AskAnswer> {
  await new Promise((r) => setTimeout(r, 400));
  const hit = FAKE_ANSWERS.find(([re]) => re.test(question));
  return hit ? hit[1] : { answer: "Village has no decision on record about that yet.", lang: "en", degraded: true, citations: [] };
}

const MEMBERS: Record<string, string[]> = { v_reyes: ["m_carmen", "m_ana", "m_marco"] };

export async function fakeQr(village: string): Promise<QrEntry[]> {
  const ids = MEMBERS[village];
  if (!ids) throw new Error("409");
  const here = typeof window !== "undefined" ? `${window.location.origin}${window.location.pathname.replace(/control\.html$/, "")}` : "/";
  return ids.map((m) => ({ member_id: m, kind: "app" as const, url: `${here}?fake=${m.slice(2)}` }));
}

/** New village offline: the founding replay plays on a fresh village id. */
export const FAKE_NEW_VILLAGE = "v_new";
export async function fakeCreateVillage(_description: string): Promise<{ village_id: string; plan: string }> {
  await new Promise((r) => setTimeout(r, 200));
  return { village_id: FAKE_NEW_VILLAGE, plan: "Intake: ten topics, one question at a time." };
}

/** Agent Memory offline: the lisinopril chain as core/memory/ledger_subscriber.py writes it (prior + change). */
const HISTORY: Record<string, Omit<FactHistory, "village">> = {
  "m_carmen/lisinopril_dose": {
    entity: "m_carmen", key: "lisinopril_dose", degraded: false,
    versions: [
      { id: "fact:lisinopril_dose:m_carmen:2", value: "10 mg", text: "Lisinopril is 10 mg since Oct 3 (Dr. Park).", observed_at: "2026-10-03T17:40:00-04:00", recorded_at: "2026-10-03T17:41:12-04:00", superseded: false,
        source: { kind: "call", ref: "conv_setup_0003", secs: 88, quote: "The doctor changed her lisinopril from five to ten on October third." }, event_id: "ev_1003_1740_med_change" },
      { id: "fact:lisinopril_dose:m_carmen:1", value: "5 mg", text: "Lisinopril was 5 mg.", observed_at: "2026-09-01T10:00:00-04:00", recorded_at: "2026-10-03T17:41:12-04:00", superseded: true,
        source: { kind: "system", ref: "prescription on file" } }
    ]
  }
};

export async function fakeFactHistory(village: string, entity: string, key: string): Promise<FactHistory> {
  await new Promise((r) => setTimeout(r, 120));
  const h = HISTORY[`${entity}/${key}`];
  if (!h || village !== "v_reyes") throw new Error("404");
  return { village, ...h };
}

export async function fakeFactsAsOf(village: string, entity: string, key: string, asOf: string): Promise<FactsAsOf> {
  const h = await fakeFactHistory(village, entity, key);
  const t = Date.parse(asOf);
  const v = h.versions.filter((x) => Date.parse(x.observed_at) <= t).sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))[0];
  return { village, as_of: asOf, degraded: false, facts: v ? [{ ...v, entity, key, superseded: false }] : [] };
}
