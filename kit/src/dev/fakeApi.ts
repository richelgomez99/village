// Offline answers for the Control Room REST calls (?fake=…). Reyes-fixture wording lives here, never in kit/src outside dev/.
import type { AskAnswer, QrEntry } from "../control/api";

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
