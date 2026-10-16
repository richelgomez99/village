// KIT-MEMBERS-5: "Other ways you could help" — suggestions derived only from bound data (open plan items, unassigned
// rota nights, an uneven week), never invented; one tap claims (claim_plan_item) or asks Village in the chat (D39).
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { Card, memberName } from "./shared";
import { todayIso } from "./brief";
import { weekdayName } from "./care";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
/** plan item kinds that need a body on site; everything else can be done from a distance */
const ON_SITE = new Set(["pickup", "bring", "visit", "drive", "cook", "errand"]);

export interface Suggestion { key: string; text: string; claim?: string; chat?: string }

export function helpSuggestions(data: Record<string, unknown>, me: string | null, nowMs: number, opts: { remoteOnly?: boolean } = {}): Suggestion[] {
  const out: Suggestion[] = [];
  const today = todayIso(nowMs);
  // 1. open, unowned plan items (PlanBoard binds carry { items: [...] })
  for (const [key, v] of Object.entries(data)) {
    const items = arr<{ id?: string; item_id?: string; text: unknown; owner?: string | null; status?: string; kind?: string; when?: string; remote?: boolean }>((v as { items?: unknown } | null)?.items);
    for (const it of items) {
      if (it.owner || (it.status && it.status !== "open")) continue;
      if (opts.remoteOnly && (it.remote === false || (it.kind && ON_SITE.has(it.kind) && it.remote !== true))) continue;
      const id = it.id ?? it.item_id;
      const words = `${text(it.text, "en")}${it.when ? ` · ${it.when}` : ""}`;
      out.push({ key: `${key}:${id ?? words}`, text: words, ...(id ? { claim: id } : { chat: `@Village I can take "${text(it.text, "en")}"` }) });
    }
  }
  // 2. nights this week nobody has yet
  const week = arr<{ date: string; on_duty?: string | null }>(data["rota:week"]).filter((d) => d.date >= today);
  for (const d of week) if (!d.on_duty) out.push({ key: `rota:${d.date}`, text: `${weekdayName(d.date)}: nobody on yet`, chat: `@Village I can take ${weekdayName(d.date)}` });
  // 3. an uneven week: someone carries 2+ more of the remaining nights than me → offer their next one
  if (me && week.length) {
    const n = new Map<string, number>();
    for (const d of week) if (d.on_duty) n.set(d.on_duty, (n.get(d.on_duty) ?? 0) + 1);
    const mine = n.get(me) ?? 0;
    const [heavy, count] = [...n.entries()].filter(([m]) => m !== me).sort((a, b) => b[1] - a[1])[0] ?? [];
    if (heavy && count! - mine >= 2) {
      const next = week.find((d) => d.on_duty === heavy && d.date > today);
      if (next) out.push({ key: `even:${next.date}`, text: `${memberName(heavy, data)} has ${count} of the nights left this week · take ${weekdayName(next.date)}?`, chat: `@Village I can take ${weekdayName(next.date)} for ${memberName(heavy, data)}` });
    }
  }
  return out.slice(0, 3);
}

export function WaysToHelp({ remoteOnly }: { remoteOnly?: boolean }) {
  const ctx = useCtx();
  const items = helpSuggestions(ctx.data, ctx.memberId, ctx.nowMs(), { remoteOnly });
  if (!items.length) return null;
  return (
    <Card test="ways-to-help" title="Other ways you could help">
      <ul className="plan-rows">
        {items.map((s) => (
          <li key={s.key} data-test="help-item">
            {s.text}{" "}
            <button type="button" className="btn btn-soft" data-test="help-take" disabled={ctx.disabled}
              onClick={() => (s.claim ? ctx.send({ name: "claim_plan_item", arg: s.claim }) : ctx.openChat?.(s.chat, { send: true }))}>
              I'll take it
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
