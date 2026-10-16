import { useCallback, useEffect, useMemo, useState } from "react";
import { IdentityChip, PromptOverlay, StatusStrip, ViewAs, ViewingAsBanner, type ViewAsOption } from "../components/chrome";
import { memberName } from "../components/shared";
import { PRESCRIPTIONS, withRefill } from "../dev/fixtureData";
import { k } from "../i18n/strings";
import type { LiveState, VillageSocket } from "../live/ws";
import type { RenderCtx } from "../renderer/context";
import { Renderer } from "../renderer/Renderer";

export const REYES_MEMBERS: ViewAsOption[] = [
  { member_id: "m_carmen", name: "Carmen" },
  { member_id: "m_ana", name: "Ana" },
  { member_id: "m_marco", name: "Marco" },
  { member_id: "m_lucia", name: "Lucía" }
];

export function useSocketState(socket: VillageSocket): LiveState {
  const [state, setState] = useState<LiveState>(socket.state);
  useEffect(() => socket.subscribe(setState), [socket]);
  return state;
}

export function MemberApp({ socket, demo = null, captions = false }: { socket: VillageSocket; demo?: string | null; captions?: boolean }) {
  const state = useSocketState(socket);
  const lang = state.view?.lang ?? "en";
  const dir = state.view?.dir ?? "ltr";
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const { view, data } = useMemo(() => {
    let v = state.view;
    let d = state.data;
    if (demo === "refill" && v && (state.role === "helper" || state.role === "coordinator")) {
      v = withRefill(v, state.role);
      if (!("prescriptions:current" in d)) d = { ...d, "prescriptions:current": PRESCRIPTIONS };
    }
    return { view: v, data: d };
  }, [state.view, state.data, state.role, demo]);

  const send = useCallback((a: Parameters<RenderCtx["send"]>[0]) => socket.action(a), [socket]);
  const ack = useCallback((id: string) => socket.ack(id), [socket]);
  const disabled = state.viewAs !== null;
  const highlight = useMemo(() => new Set(state.highlight), [state.highlight]);

  const ctx: RenderCtx | null = view
    ? { view, data, lang, role: state.role, memberId: state.memberId, village: state.village, nowMs: socket.nowMs, disabled, highlight, results: state.results, send, ack, captions }
    : null;

  const selfRole = state.self?.role ?? state.role;
  const canViewAs = selfRole === "coordinator" || selfRole === "control";
  const prompt = state.prompt;

  return (
    <div className="app" data-test="app" data-role={state.role} data-theme={view?.theme ?? "family"} data-lang={lang} data-dir={dir} data-rev={state.rev} data-status={state.status} data-view-as={state.viewAs ?? ""}>
      <StatusStrip state={state} lang={lang} />
      <div className="topbar">
        {canViewAs ? <ViewAs options={REYES_MEMBERS} current={state.viewAs} self={state.self?.memberId ?? null} onPick={(m) => socket.viewAs(m)} lang={state.self?.role === "elder" ? "es" : "en"} /> : null}
        <IdentityChip memberId={state.memberId} role={state.role} village={state.village} lang={lang} />
      </div>
      {state.viewAs ? <ViewingAsBanner name={memberName(state.viewAs)} onBack={() => socket.viewAs(null)} lang="en" /> : null}
      {ctx ? (
        <Renderer ctx={ctx} />
      ) : (
        <p className="skeleton" data-test="skeleton">{k("building", lang, { who: memberName(state.memberId) || "your" })}</p>
      )}
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
