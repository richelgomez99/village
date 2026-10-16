import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IdentityChip, PromptOverlay, StatusStrip, ViewAs, ViewingAsBanner, type ViewAsOption } from "../components/chrome";
import { memberName } from "../components/shared";
import { k } from "../i18n/strings";
import type { LiveState, VillageSocket } from "../live/ws";
import type { RenderCtx } from "../renderer/context";
import { Renderer } from "../renderer/Renderer";

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

export function useSocketState(socket: VillageSocket): LiveState {
  const [state, setState] = useState<LiveState>(socket.state);
  useEffect(() => socket.subscribe(setState), [socket]);
  return state;
}

export function MemberApp({ socket, captions = false }: { socket: VillageSocket; captions?: boolean }) {
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

  const ctx: RenderCtx | null = view
    ? { view, data, lang, role: state.role, memberId: state.memberId, village: state.village, nowMs: socket.nowMs, disabled, highlight, results: state.results, send, ack, captions }
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
