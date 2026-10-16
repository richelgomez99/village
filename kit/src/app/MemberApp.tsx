import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IdentityChip, PromptOverlay, StatusStrip, ViewAs, ViewingAsBanner, type ViewAsOption } from "../components/chrome";
import { memberName } from "../components/shared";
import { k } from "../i18n/strings";
import { PHONE_LINE, type LiveState, type VillageSocket } from "../live/ws";
import { makePhoneFor, type RenderCtx } from "../renderer/context";
import type { ApiConfig } from "../control/api";
import { Renderer } from "../renderer/Renderer";
import { TabbedApp } from "./TabbedApp";

/** View-as options from the coordinator's own data: member:<id> records, then everyone on the rota. */
export function viewAsOptions(data: Record<string, unknown>): ViewAsOption[] {
  const out = new Map<string, string>();
  for (const [k, v] of Object.entries(data)) {
    if (k.startsWith("member:")) out.set(k.slice(7), (v as { name?: string } | null)?.name ?? memberName(k.slice(7)));
  }
  const rota = data["rota:week"];
  if (Array.isArray(rota)) for (const d of rota as { on_duty?: string; backup?: string }[]) for (const m of [d.on_duty, d.backup]) if (m && !out.has(m)) out.set(m, memberName(m, data));
  return [...out].map(([member_id, name]) => ({ member_id, name }));
}

/** Display name for a phone-line member: their member record, else identity.name unless it is only an honorific ("Mrs."), else from the id. */
export function phoneLineName(id: string | null, idName: string | undefined, data: Record<string, unknown>): string {
  const rec = (data[`member:${id}`] as { name?: string } | undefined)?.name;
  if (rec) return rec;
  if (idName && !idName.endsWith(".")) return idName;
  return memberName(id);
}

export function useSocketState(socket: VillageSocket): LiveState {
  const [state, setState] = useState<LiveState>(socket.state);
  useEffect(() => socket.subscribe(setState), [socket]);
  return state;
}

export function MemberApp({ socket, captions = false, api }: { socket: VillageSocket; captions?: boolean; api?: ApiConfig }) {
  const state = useSocketState(socket);
  const lang = state.view?.lang ?? "en";
  const dir = state.view?.dir ?? "ltr";
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const view = state.view;
  const data = state.data;

  const send = useCallback((a: Parameters<RenderCtx["send"]>[0]) => socket.action(a), [socket]);
  const ack = useCallback((id: string) => socket.ack(id), [socket]);
  const disabled = state.viewAs !== null;
  const highlight = useMemo(() => new Set(state.highlight), [state.highlight]);
  const phoneFor = useMemo(() => makePhoneFor(data, state.identity?.village_number), [data, state.identity]);

  const ctx: RenderCtx | null = view
    ? { view, data, lang, role: state.role, memberId: state.memberId, village: state.village, nowMs: socket.nowMs, disabled, highlight, results: state.results, send, ack, captions, phoneFor, api }
    : null;

  // options come from my own snapshot; keep them while viewing as someone else
  const optsRef = useRef<ViewAsOption[]>([]);
  if (!state.viewAs) {
    const o = viewAsOptions(data);
    if (o.length) optsRef.current = o;
  }
  const viewOpts = optsRef.current;
  const selfRole = state.self?.role ?? state.role;
  const canViewAs = selfRole === "coordinator" || selfRole === "control";
  const prompt = state.prompt;

  return (
    <div className="app" data-test="app" data-role={state.role} data-theme={view?.theme ?? "family"} data-lang={lang} data-dir={dir} data-rev={state.rev} data-status={state.status} data-view-as={state.viewAs ?? ""}>
      <StatusStrip state={state} lang={lang} />
      <div className="topbar">
        {canViewAs ? <ViewAs options={viewOpts} current={state.viewAs} self={state.self?.memberId ?? null} onPick={(m) => socket.viewAs(m)} lang={state.self?.role === "elder" ? "es" : "en"} /> : null}
        <IdentityChip memberId={state.memberId} role={state.role} village={state.village} lang={lang} identity={state.identity} />
      </div>
      {state.viewAs ? <ViewingAsBanner name={viewOpts.find((o) => o.member_id === state.viewAs)?.name ?? memberName(state.viewAs, data)} onBack={() => socket.viewAs(null)} lang={state.self?.role === "elder" ? "es" : "en"} /> : null}
      {ctx ? (
        ctx.view.theme === "elder" ? <Renderer ctx={ctx} /> : <TabbedApp ctx={ctx} blueprint={(state.spec as { blueprint?: { life_areas?: any[] } } | null)?.blueprint ?? null} />
      ) : state.role === PHONE_LINE ? (
        <section className="card" data-test="phone-line-card">
          <h2 className="card-title">{k("phone_uses", lang, { who: phoneLineName(state.memberId, state.identity?.name, data) })}</h2>
          <p>{state.identity?.village_number ? k("phone_call_n", lang, { n: state.identity.village_number }) : k("phone_call", lang)}</p>
          <p className="muted">{k("phone_shows", lang)}</p>
        </section>
      ) : (
        <p className="skeleton" data-test="skeleton">{memberName(state.memberId) ? k("building", lang, { who: memberName(state.memberId) }) : k("building_you", lang)}</p>
      )}
      {state.ask && !disabled ? (
        <div className="ask-sheet" data-test="ask-sheet" role="dialog" aria-label="Village asks">
          <p className="ask-from"><span className="village-mark" aria-hidden="true">V</span> Village asks</p>
          <p className="ask-q" data-test="ask-question">{typeof state.ask.question === "string" ? state.ask.question : (state.ask.question as Record<string, string>)?.[lang] ?? (state.ask.question as Record<string, string>)?.en}</p>
          <div className="row">
            {(state.ask.options?.length ? state.ask.options : [{ id: "yes", label: "Yes" }, { id: "no", label: "Can't" }]).map((o) => (
              <button key={o.id} type="button" className={`btn ${o.id === "yes" ? "btn-primary" : "btn-soft"}`} data-test={`ask-${o.id}`}
                onClick={() => { socket.action({ name: "answer_ask", arg: state.ask!.ask_id, element_id: "ask", payload: { ask_id: state.ask!.ask_id, answer: o.id } }); socket.clearAsk(); }}>
                {typeof o.label === "string" ? o.label : (o.label as Record<string, string>)?.[lang] ?? (o.label as Record<string, string>)?.en}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {prompt && !disabled ? (
        <PromptOverlay
          prompt={prompt}
          lang={lang}
          nowMs={socket.nowMs}
          result={state.results.answer_verification}
          onAnswer={(answer) => socket.action({ name: "answer_verification", element_id: "prompt", payload: { verification_id: prompt.verification_id, answer } })}
        />
      ) : null}
    </div>
  );
}
