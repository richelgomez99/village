// Tabs from life areas (docs/UX-UPGRADE.md "Village-agnostic by construction" #2). Pure: no village names, no member ids.
// A non-elder view's bottom nav = Home + the life areas its elements serve (needs_served → life area, spec order) + Chat.
import { text, type View } from "../renderer/view";

export const ATTENTION_TYPES = new Set(["Alert", "Proposal", "VerificationPrompt", "IncidentCard"]);
const LAYOUT = new Set(["Screen", "Header", "Text", "Stack"]);
/** one-tap actions (Call Mamá, 911) never move off Home */
const PINNED = new Set(["BigButton", "ContactCard"]);
/** below this many tab-able elements one screen is enough (Marco: Home · Chat) */
const MIN_FOR_TABS = 4;

export interface Tab { id: string; label: string; elements: string[] }
export interface TabPlan {
  /** attention items (alerts, needs-your-yes, prompts) in view order */
  attention: string[];
  /** the person's headline element: the first non-attention, non-chat element */
  headline: string | null;
  /** everything Home shows after the headline (elements no life area claims, or all of them when there are < 2 area tabs) */
  homeRest: string[];
  /** life-area tabs (never Home / Chat) */
  areas: Tab[];
  /** the VillageChat element, if the view has one */
  chat: string | null;
}

interface AreaRow { id: string; label?: string; label_i18n?: Record<string, string>; need_ids?: string[] }

/** need id → life area id. Sources, best first: a full spec's blueprint (control / view-as), then bv_life_area.need_ids. */
export function needAreaMap(data: Record<string, unknown>, blueprint?: { life_areas?: AreaRow[] } | null): Map<string, string> {
  const out = new Map<string, string>();
  const rows: AreaRow[] = [...(blueprint?.life_areas ?? []), ...(Array.isArray(data["blueprint:life_areas"]) ? (data["blueprint:life_areas"] as AreaRow[]) : [])];
  for (const a of rows) for (const n of a.need_ids ?? []) if (!out.has(n)) out.set(n, a.id);
  return out;
}

/** Area order + labels: blueprint first, then the live rows. Label = label_i18n[lang], else the word before ":" ("Health: pills" → "Health"). */
export function areaLabels(data: Record<string, unknown>, lang: string, blueprint?: { life_areas?: AreaRow[] } | null): Map<string, string> {
  const out = new Map<string, string>();
  const rows: AreaRow[] = [...(blueprint?.life_areas ?? []), ...(Array.isArray(data["blueprint:life_areas"]) ? (data["blueprint:life_areas"] as AreaRow[]) : [])];
  for (const a of rows) {
    if (out.has(a.id)) continue;
    const l = a.label_i18n ? text(a.label_i18n, lang) : "";
    out.set(a.id, l || String(a.label ?? a.id).split(":")[0].trim() || a.id);
  }
  return out;
}

export function planTabs(view: View, data: Record<string, unknown>, lang: string, blueprint?: { life_areas?: AreaRow[] } | null): TabPlan {
  const root = view.elements[view.root];
  const top = (root?.children ?? []).filter((id) => view.elements[id]);
  const attention = top.filter((id) => ATTENTION_TYPES.has(view.elements[id].type));
  const chat = top.find((id) => view.elements[id].type === "VillageChat") ?? null;
  const rest = top.filter((id) => !attention.includes(id) && id !== chat);
  const headline = rest.find((id) => !LAYOUT.has(view.elements[id].type)) ?? rest[0] ?? null;
  const others = rest.filter((id) => id !== headline);

  const needArea = needAreaMap(data, blueprint);
  const labels = areaLabels(data, lang, blueprint);
  const order = [...labels.keys()];
  const byArea = new Map<string, string[]>();
  const unassigned: string[] = [];
  const pinned = others.filter((id) => PINNED.has(view.elements[id].type));
  const movable = others.filter((id) => !PINNED.has(view.elements[id].type));
  for (const id of movable) {
    const needs = view.needs_served?.[id] ?? [];
    const area = needs.map((n) => needArea.get(n)).find(Boolean);
    if (area) byArea.set(area, [...(byArea.get(area) ?? []), id]);
    else unassigned.push(id);
  }
  const areas: Tab[] = order.filter((a) => byArea.has(a)).map((a) => ({ id: a, label: labels.get(a) ?? a, elements: byArea.get(a)! }));
  // one area is not a choice: keep it on Home (Marco: Home · Chat; Lucía: Home · Chat)
  if (areas.length < 2 || movable.length < MIN_FOR_TABS) return { attention, headline, homeRest: others, areas: [], chat };
  return { attention, headline, homeRest: others.filter((id) => pinned.includes(id) || unassigned.includes(id)), areas, chat };
}
