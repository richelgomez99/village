// Non-elder member app: Home + life-area tabs + Chat (docs/UX-UPGRADE.md, "Village-agnostic by construction").
// Everything here is composed from the view's own elements and its bound data; no village, person or element id is named.
import { useMemo, useRef, useState, type ReactNode } from "react";
import { Ctx, type RenderCtx } from "../renderer/context";
import { Node, collectInvalid, collectUnknown } from "../renderer/Renderer";
import { text } from "../renderer/view";
import { Bi, Card, ReadAloud, memberName } from "../components/shared";
import { ChatPreview } from "../components/generic";
import { fmtTime } from "../util/time";
import { planTabs } from "./tabs";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const isEmpty = (v: unknown) => v == null || (Array.isArray(v) && v.length === 0);

function boundEmpty(ctx: RenderCtx, id: string): boolean {
  if (ctx.results[id]) return false; // keep a just-answered prompt on screen for its thanks line
  const bind = ctx.view.elements[id]?.props.bind;
  return typeof bind === "string" && isEmpty(ctx.data[bind]);
}

function todayIso(nowMs: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date(nowMs));
}

interface Person { member_id?: string; name?: string }

/** "Right now": who's on tonight · pills today · the last thing that happened. Each line only when its bind is in the snapshot. */
export function rightNowLines(data: Record<string, unknown>, nowMs: number, lang: string): { key: string; text: string }[] {
  const out: { key: string; text: string }[] = [];
  const today = todayIso(nowMs);
  let onDuty: string | undefined;
  const p = data["rota:current.on_duty"] as Person | null | undefined;
  if (p?.name) onDuty = p.name;
  const me = data["rota:current?member=me"] as { on_duty?: Person } | null | undefined;
  if (!onDuty && me?.on_duty?.name) onDuty = me.on_duty.name;
  for (const key of ["rota:current", "rota:week"]) {
    if (onDuty) break;
    const d = arr<{ date: string; on_duty: string }>(data[key]).find((r) => r.date === today);
    if (d?.on_duty) onDuty = memberName(d.on_duty, data);
  }
  if (onDuty) out.push({ key: "tonight", text: `Tonight: ${onDuty}` });

  const doseKey = Object.keys(data).find((k) => k.startsWith("facts:dose_event") && k.includes("valid_at=today"));
  const dose = doseKey ? (data[doseKey] as { slots?: { slot: string; status: string }[] } | null) : null;
  if (dose?.slots?.length) {
    const taken = dose.slots.filter((s) => s.status === "taken").length;
    const open = dose.slots.find((s) => s.status !== "taken");
    out.push({ key: "pills", text: `Pills today: ${taken} of ${dose.slots.length} taken${open ? ` · ${open.slot} ${open.status === "upcoming" ? "still to come" : open.status}` : ""}` });
  }

  const tlKey = Object.keys(data).find((k) => k.startsWith("timeline:"));
  const last = arr<{ at: string; text: unknown; superseded?: boolean }>(tlKey ? data[tlKey] : null)
    .filter((r) => !r.superseded)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
  if (last) out.push({ key: "last", text: `Last: ${text(last.text, lang)} · ${fmtTime(last.at, lang)}` });
  return out;
}

interface Rounds { counts?: Record<string, number>; did_alone?: number; alone?: number; asked?: number; asked_person?: number; refused?: number; rows?: { text?: unknown; line?: unknown; summary?: unknown; role?: string; actor?: string }[] }

/** rounds:latest (core-glue): three counts + rows in words. Absent = hidden. */
export function WhatVillageDid({ data }: { data: Record<string, unknown> }) {
  const r = data["rounds:latest"] as Rounds | null | undefined;
  if (!r || typeof r !== "object") return null;
  const c = r.counts ?? {};
  const alone = c.did_alone ?? c.alone ?? r.did_alone ?? r.alone ?? 0;
  const asked = c.asked ?? c.asked_person ?? r.asked ?? r.asked_person ?? 0;
  const refused = c.refused ?? r.refused ?? 0;
  const rows = arr<NonNullable<Rounds["rows"]>[number]>(r.rows);
  return (
    <Card test="what-village-did" title="What Village did">
      <p className="wvd-counts" data-test="wvd-counts">
        Did {alone} {alone === 1 ? "thing" : "things"} on its own · asked a person {asked} · refused itself {refused}
      </p>
      {rows.length ? (
        <ul className="wvd-rows">
          {rows.slice(0, 6).map((row, i) => (
            <li key={i} data-test="wvd-row">
              {row.role || row.actor ? <span className="chip chip-gray">{row.role ?? row.actor}</span> : null} {text(row.text ?? row.line ?? row.summary ?? "", "en")}
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

export function TabbedApp({ ctx, blueprint }: { ctx: RenderCtx; blueprint?: { life_areas?: any[] } | null }) {
  const [tab, setTab] = useState("home");
  const [draft, setDraft] = useState<string | undefined>();
  const ref = useRef<HTMLElement | null>(null);
  const plan = useMemo(() => planTabs(ctx.view, ctx.data, ctx.lang, blueprint), [ctx.view, ctx.data, ctx.lang, blueprint]);
  const unknown = useMemo(() => collectUnknown(ctx.view), [ctx.view]);
  const invalid = useMemo(() => collectInvalid(ctx.view), [ctx.view]);
  const openChat = (prefill?: string) => {
    if (prefill) setDraft(prefill);
    setTab("chat");
  };
  const c: RenderCtx = { ...ctx, openChat: plan.chat ? openChat : undefined, chatDraft: draft };
  const root = ctx.view.elements[ctx.view.root];
  const es = ctx.lang === "es";

  const yesItems = plan.attention.filter((id) => ctx.view.elements[id].type !== "Alert");
  const needsYes = yesItems.filter((id) => !boundEmpty(ctx, id));
  const alerts = plan.attention.filter((id) => ctx.view.elements[id].type === "Alert");
  const lines = rightNowLines(ctx.data, ctx.nowMs(), ctx.lang);
  const tabs: { id: string; label: string }[] = [
    { id: "home", label: es ? "Inicio" : "Home" },
    ...plan.areas.map((a) => ({ id: a.id, label: a.label })),
    ...(plan.chat ? [{ id: "chat", label: "Chat" }] : [])
  ];
  const panel = (id: string, children: ReactNode) => (
    <section key={id} className="tab-panel" data-test={`tab-${id}`} data-tab={id} hidden={tab !== id}>
      {children}
    </section>
  );

  return (
    <Ctx.Provider value={c}>
      <div className="el" data-id={ctx.view.root} data-type="Screen">
      <main className="screen screen-tabbed" data-test="screen" ref={ref} data-tab={tab}>
        <header className="screen-head">
          <h1 className="screen-title"><Bi value={root?.props.title ?? ""} /></h1>
          {root?.props.subtitle ? <p className="screen-sub"><Bi value={root.props.subtitle} /></p> : null}
          <ReadAloud target={ref} />
        </header>
        <div className="screen-body">
          {panel(
            "home",
            <>
              {lines.length >= 2 ? (
                <Card test="right-now" title={es ? "Ahora" : "Right now"}>
                  <ul className="right-now">
                    {lines.map((l) => <li key={l.key} data-test="right-now-line" data-line={l.key}>{l.text}</li>)}
                  </ul>
                </Card>
              ) : null}
              {alerts.map((id) => <Node key={id} id={id} />)}
              {yesItems.length ? (
                <div className="needs-yes" data-test="needs-your-yes" hidden={needsYes.length === 0}>
                  <h2 className="group-title">{es ? "Necesita tu sí" : "Needs your yes"}</h2>
                  {yesItems.map((id) => <div key={id} hidden={!needsYes.includes(id)}><Node id={id} /></div>)}
                </div>
              ) : null}
              {plan.headline ? <div className="headline" data-test="headline"><Node id={plan.headline} /></div> : null}
              <WhatVillageDid data={ctx.data} />
              {plan.homeRest.map((id) => <Node key={id} id={id} />)}
              {plan.chat ? <ChatPreview chatId={plan.chat} onOpen={() => setTab("chat")} /> : null}
            </>
          )}
          {plan.areas.map((a) => panel(a.id, a.elements.map((id) => <Node key={id} id={id} />)))}
          {plan.chat ? panel("chat", <Ctx.Provider value={{ ...c, chatFull: true }}><div className="chat-panel"><Node id={plan.chat} /></div></Ctx.Provider>) : null}
        </div>
      </main>
      </div>
      {tabs.length > 1 ? (
        <nav className="bottom-nav" data-test="bottom-nav" aria-label="Sections">
          {tabs.map((t) => (
            <button key={t.id} type="button" className={`nav-tab${tab === t.id ? " active" : ""}`} data-test="nav-tab" data-tab={t.id} aria-current={tab === t.id ? "page" : undefined} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      ) : null}
      <span data-test="unknown-types" data-count={unknown.length} data-types={unknown.join(",")} hidden />
      <span data-test="invalid-props" data-count={invalid.length} data-ids={invalid.join(",")} hidden />
    </Ctx.Provider>
  );
}
