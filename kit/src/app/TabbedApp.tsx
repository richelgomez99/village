// Non-elder member app: Home + life-area tabs + Chat (docs/UX-UPGRADE.md, "Village-agnostic by construction").
// Everything here is composed from the view's own elements and its bound data; no village, person or element id is named.
import { useMemo, useRef, useState, type ReactNode } from "react";
import { Ctx, type RenderCtx } from "../renderer/context";
import { Node, collectInvalid, collectUnknown } from "../renderer/Renderer";
import { text } from "../renderer/view";
import { Bi, Card, ReadAloud, memberName } from "../components/shared";
import { ChatPreview } from "../components/generic";
import { planTabs, tabKey } from "./tabs";
import { SinceLastTurn, WhatVillageDid, rightNowLines } from "../components/brief";
export { rightNowLines } from "../components/brief";

const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const isEmpty = (v: unknown) => v == null || (Array.isArray(v) && v.length === 0);

function boundEmpty(ctx: RenderCtx, id: string, openOnly = true): boolean {
  if (ctx.results[id]) return false; // keep a just-answered prompt on screen for its thanks line
  if (!openOnly) return isEmpty(ctx.data[ctx.view.elements[id]?.props.bind as string]);
  const el = ctx.view.elements[id];
  const bind = el?.props.bind;
  if (typeof bind !== "string") return false;
  const v = ctx.data[bind];
  // an incident needs a yes only while it is open; acknowledged ones are history (area tab)
  if (el.type === "IncidentCard") return !Array.isArray(v) || !(v as { status?: string }[]).some((i) => i.status === "open");
  return isEmpty(v);
}

export function TabbedApp({ ctx, blueprint }: { ctx: RenderCtx; blueprint?: { life_areas?: any[] } | null }) {
  const [tab, setTab] = useState("home");
  const [draft, setDraft] = useState<string | undefined>();
  const ref = useRef<HTMLElement | null>(null);
  // one tab set per snapshot: depends on the view and the life-area rows only, never on which tab is open or on live rows
  // live event frames may resend life-area rows without need_ids: keep the last rows that had them
  const rowsNow = ctx.data["blueprint:life_areas"];
  const stableRows = useRef<unknown>(null);
  if (Array.isArray(rowsNow) && (rowsNow.some((r: { need_ids?: unknown[] }) => r?.need_ids?.length) || !stableRows.current)) stableRows.current = rowsNow;
  const tabData = useMemo(() => ({ "blueprint:life_areas": stableRows.current }), [stableRows.current]); // eslint-disable-line react-hooks/exhaustive-deps
  const tk = tabKey(tabData);
  const plan = useMemo(() => planTabs(ctx.view, tabData, ctx.lang, blueprint), [ctx.view, tk, ctx.lang, blueprint]); // eslint-disable-line react-hooks/exhaustive-deps
  const inHistory = new Set(plan.areas.flatMap((a) => a.elements));
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
  const needsYes = yesItems.filter((id) => !boundEmpty(ctx, id, true));
  // acknowledged incidents with no area tab to live on stay on Home, below the headline, outside "Needs your yes"
  const homeHistory = yesItems.filter((id) => !inHistory.has(id) && !needsYes.includes(id) && !boundEmpty(ctx, id, false));
  const alerts = plan.attention.filter((id) => ctx.view.elements[id].type === "Alert");
  const has = (t: string) => Object.values(ctx.view.elements).some((e) => e.type === t);
  // the shell composes a block only when the view doesn't already carry its 1.3.3 element
  // a one-glance strip leads (above alerts); any other headline follows the asks
  const heroFirst = !!plan.headline && ctx.view.elements[plan.headline]?.type === "RightNow";
  const lines = has("RightNow") ? [] : rightNowLines(ctx.data, ctx.nowMs(), ctx.lang);
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
              {heroFirst ? <div className="headline" data-test="headline"><Node id={plan.headline!} /></div> : null}
              {alerts.map((id) => <Node key={id} id={id} />)}
              {yesItems.length ? (
                <div className="needs-yes" data-test="needs-your-yes" hidden={needsYes.length === 0}>
                  <h2 className="group-title">{es ? "Necesita tu sí" : "Needs your yes"}</h2>
                  {yesItems.map((id) => (
                    <Ctx.Provider key={id} value={{ ...c, openOnly: inHistory.has(id) }}>
                      {homeHistory.includes(id) ? null : <div hidden={!needsYes.includes(id)}><Node id={id} /></div>}
                    </Ctx.Provider>
                  ))}
                </div>
              ) : null}
              {plan.headline && !heroFirst ? <div className="headline" data-test="headline"><Node id={plan.headline} /></div> : null}
              {homeHistory.map((id) => <Node key={id} id={id} />)}
              {has("SinceYourTurn") ? null : <SinceLastTurn data={ctx.data} lang={ctx.lang} />}
              {has("WhatVillageDid") ? null : <WhatVillageDid data={ctx.data} nowMs={ctx.nowMs()} />}
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
