// Control Room (T020–T026, T042, T045): one dark projector page, a scene reducer fed by every WS frame.
// /control.html?t=<control token>  ·  offline: /control.html?fake=control&seq=founding|scam|release|evolve
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { useSocketState } from "../app/MemberApp";
import { apiConfig, warpClock, type ApiConfig } from "../control/api";
import { AskWhyRegion, BlueprintRegion, CaptionsLayer, GateRegion, Header, JoinQrRegion, LedgerRegion, LiveMomentRegion, PhonesRegion } from "../control/regions";
import { initialScene, sceneReducer, type SceneState } from "../control/scene";
import { addCaption } from "../i18n/captions";
import { liveConfig, makeSocket, type LiveConfig } from "../live/useLive";
import type { VillageSocket } from "../live/ws";
import "../theme/fonts.css";
import "../theme/floor.css";
import "../theme/a.css";

/** Scene for one socket: reduce every validated frame; captions feed the D18 glossary. */
export function useScene(socket: VillageSocket, village: string): SceneState {
  const [scene, dispatch] = useReducer(sceneReducer, village, initialScene);
  useEffect(
    () =>
      socket.onFrame((f) => {
        if (f.type === "control" && f.kind === "caption") addCaption(String((f.payload as any).es ?? ""), String((f.payload as any).en ?? ""));
        dispatch(f);
      }),
    [socket]
  );
  return scene;
}

export interface ControlRoomProps {
  socket: VillageSocket;
  cfg?: LiveConfig;
  api?: ApiConfig;
  /** factory for secondary sockets (view-as, other village tab); defaults to makeSocket(cfg). */
  spawn?: (opts: { village: string; viewAs?: string }) => VillageSocket;
}

export function ControlRoom({ socket, cfg, api, spawn }: ControlRoomProps) {
  const apiCfg = useMemo<ApiConfig>(() => api ?? (typeof window !== "undefined" ? apiConfig() : { base: "", token: "", fake: true }), [api]);
  const make = useCallback(
    (o: { village: string; viewAs?: string }) =>
      spawn ? spawn(o) : makeSocket({ ...(cfg ?? liveConfig("control")), village: o.village }, undefined, { viewAs: o.viewAs, fakeOverrides: { start: "off", seq: null, quiet: true } }),
    [spawn, cfg]
  );
  const mainState = useSocketState(socket);
  const [tab, setTab] = useState(mainState.village || "v_reyes");
  const homeVillage = useRef(mainState.village || "v_reyes");

  // second village (tab) gets its own control socket, opened once and kept (no reconnect on switch)
  const [other, setOther] = useState<VillageSocket | null>(null);
  useEffect(() => {
    if (tab === homeVillage.current || other) return;
    const s = make({ village: tab });
    s.connect();
    setOther(s);
  }, [tab, other, make]);
  useEffect(() => () => other?.close(), [other]);

  const active = tab === homeVillage.current || !other ? socket : other;
  const homeScene = useScene(socket, homeVillage.current);
  const otherScene = useScene(other ?? socket, tab);
  const scene = active === socket ? homeScene : otherScene;

  // View as (D21): a read-only socket that asks Core for that member's snapshot; the main stream keeps flowing
  const [viewAs, setViewAs] = useState<string | null>(null);
  const [asSocket, setAsSocket] = useState<VillageSocket | null>(null);
  useEffect(() => {
    if (!viewAs) {
      setAsSocket(null);
      return;
    }
    const s = make({ village: tab, viewAs });
    s.connect();
    setAsSocket(s);
    return () => s.close();
  }, [viewAs, tab, make]);
  const asState = useSocketState(asSocket ?? socket);
  const liveView = asSocket && asState.viewAs ? { role: asState.role, view: asState.view, data: asState.data } : null;

  const [warpState, setWarpState] = useState<"idle" | "busy" | "failed">("idle");
  const onWarp = async () => {
    setWarpState("busy");
    try {
      await warpClock(apiCfg, 30);
      setWarpState("idle");
    } catch {
      setWarpState("failed");
    }
  };

  const spec = scene.spec;
  return (
    <main className="control" data-test="control" data-status={mainState.status} data-village={tab} data-frames={scene.frames}>
      <Header tab={tab} onTab={(t) => { setViewAs(null); setTab(t); }} phones={scene.phones} clock={scene.clock} nowMs={active.nowMs} onWarp={onWarp} warpState={warpState} />
      {mainState.status !== "live" && mainState.status !== "idle" ? (
        <p className="ws-banner" data-test="ws-banner">{mainState.status === "reconnecting" ? `Reconnecting to Core… (try ${mainState.attempt})` : mainState.status === "closed" ? `Not connected: ${mainState.closedReason ?? "closed"}` : "Connecting to Core…"}</p>
      ) : null}
      <div className="cr-grid">
        <BlueprintRegion spec={spec} scene={scene} />
        <LedgerRegion rows={scene.ledger} nowMs={active.nowMs} />
        <LiveMomentRegion live={scene.live} nowMs={active.nowMs} spec={spec} />
        <PhonesRegion spec={spec} data={scene.data} village={tab} nowMs={active.nowMs} viewAs={viewAs} onViewAs={setViewAs} live={liveView} />
        <GateRegion gate={scene.gate} decisions={scene.decisions} autonomy={scene.autonomy} />
        <AskWhyRegion cfg={apiCfg} village={tab} />
        <JoinQrRegion cfg={apiCfg} village={tab} />
      </div>
      <CaptionsLayer captions={scene.captions} />
    </main>
  );
}

if (typeof document !== "undefined" && document.getElementById("root")) {
  const cfg = liveConfig("control");
  const socket = makeSocket(cfg);
  socket.connect();
  (window as any).__village = socket;
  createRoot(document.getElementById("root")!).render(<ControlRoom socket={socket} cfg={cfg} />);
}
