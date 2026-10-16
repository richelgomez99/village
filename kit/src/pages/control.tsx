// Control Room (T020–T026, T042, T045): one dark projector page, a scene reducer fed by every WS frame.
// /control.html?t=<control token>  ·  offline: /control.html?fake=control&seq=founding|scam|release|evolve
// Every region keys on the selected village: each village has its own control socket and its own scene, and the room
// remounts on switch, so nothing from one village shows under the other. No village yet = the founding (transcript ·
// work log · blueprint with coverage meter · phone skeletons).
import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { useSocketState } from "../app/MemberApp";
import { answerFollowUp, apiConfig, createVillage, warpClock, type ApiConfig } from "../control/api";
import { AskWhyRegion, BlueprintRegion, CaptionsLayer, GateRegion, Header, KnowsRegion, LedgerRegion, LiveMomentRegion, NEW_VILLAGE, PhonesRegion, TranscriptRegion, type VillageTab } from "../control/regions";
import { displayName, initialScene, nameCtx, sceneReducer, type SceneState } from "../control/scene";
import { FAKE_VILLAGES } from "../dev/fixtureData";
import { addCaption } from "../i18n/captions";
import { liveConfig, makeSocket, type LiveConfig } from "../live/useLive";
import type { VillageSocket } from "../live/ws";
import "../theme/fonts.css";
import "../theme/floor.css";
import "../theme/a.css";

/** Scene for one village's socket: reduce every validated frame (replayed from the socket's log on mount). */
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

/** ?hero=1: screenshot mode, dev chrome hidden (connection banner, clock warp, view-as bar). */
const HERO = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("hero") === "1";

export function isFounding(scene: SceneState): boolean {
  return !scene.spec || (!scene.blueprint.done && (Object.keys(scene.blueprint.stages).length > 0 || scene.transcript.length > 0));
}

export interface ControlRoomProps {
  socket: VillageSocket;
  cfg?: LiveConfig;
  api?: ApiConfig;
  /** villages on the switcher (default: ?villages=a,b · offline: the fake's villages · else the home village) */
  villages?: string[];
  /** factory for secondary sockets (view-as, other village); defaults to makeSocket(cfg). */
  spawn?: (opts: { village: string; viewAs?: string; founding?: boolean }) => VillageSocket;
}

function defaultVillages(home: string, cfg?: LiveConfig): string[] {
  const p = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("villages") : null;
  const list = p ? p.split(",").filter(Boolean) : cfg?.fake ? FAKE_VILLAGES : [];
  return [home, ...list.filter((v) => v !== home)].filter(Boolean);
}

export function ControlRoom({ socket, cfg, api, villages, spawn }: ControlRoomProps) {
  const apiCfg = useMemo<ApiConfig>(() => api ?? (typeof window !== "undefined" ? apiConfig() : { base: "", token: "", fake: true }), [api]);
  const make = useCallback(
    (o: { village: string; viewAs?: string; founding?: boolean }) =>
      spawn
        ? spawn(o)
        : makeSocket({ ...(cfg ?? liveConfig("control")), village: o.village }, undefined, {
            viewAs: o.viewAs,
            fakeOverrides: { start: "off", seq: o.founding ? "founding" : null, quiet: true }
          }),
    [spawn, cfg]
  );
  const home = useRef(socket.state.village || cfg?.village || "").current;
  const [list, setList] = useState<string[]>(() => villages ?? defaultVillages(home, cfg));
  const [tab, setTab] = useState(home || NEW_VILLAGE);
  // one control socket per village, opened up front (names for the switcher) and kept: switching never reconnects
  const [sockets, setSockets] = useState<Record<string, VillageSocket>>(() => (home ? { [home]: socket } : {}));
  useEffect(() => {
    const missing = list.filter((v) => !sockets[v]);
    if (!missing.length) return;
    const add: Record<string, VillageSocket> = {};
    for (const v of missing) {
      add[v] = make({ village: v });
      add[v].connect();
    }
    setSockets((m) => ({ ...m, ...add }));
  }, [list, sockets, make]);
  useEffect(() => () => Object.entries(sockets).forEach(([v, s]) => v !== home && s.close()), []); // eslint-disable-line react-hooks/exhaustive-deps
  const names = useVillageNames(sockets);
  const tabs: VillageTab[] = list.map((id) => ({ id, label: names[id] ?? id.replace(/^v_/, "") }));

  const startVillage = async (description: string) => {
    const r = await createVillage(apiCfg, description);
    const s = make({ village: r.village_id, founding: true });
    s.connect();
    setSockets((m) => ({ ...m, [r.village_id]: s }));
    setList((l) => (l.includes(r.village_id) ? l : [...l, r.village_id]));
    setTab(r.village_id);
  };

  const active = tab === NEW_VILLAGE ? null : sockets[tab];
  if (!active) {
    return (
      <main className="control founding" data-test="control" data-village="" data-mode="founding">
        <Header tabs={tabs} tab={NEW_VILLAGE} onTab={setTab} onNew={() => setTab(NEW_VILLAGE)} phones={null} clock={null} nowMs={() => Date.now()} onWarp={() => {}} warpState="idle" />
        <div className="cr-grid">
          <TranscriptRegion lines={[]} onSend={startVillage} />
          <LedgerRegion rows={[]} nowMs={() => Date.now()} />
          <BlueprintRegion spec={null} scene={initialScene("")} />
        </div>
      </main>
    );
  }
  return <VillageRoom key={tab} village={tab} socket={active} tabs={tabs} onTab={setTab} onNew={() => setTab(NEW_VILLAGE)} make={make} api={apiCfg} />;
}

/** village.name from each socket's control snapshot (spec), for the switcher pills. */
function useVillageNames(sockets: Record<string, VillageSocket>): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>({});
  useEffect(() => {
    const unsubs = Object.entries(sockets).map(([id, s]) =>
      s.subscribe((st) => {
        const n = (st.spec as any)?.village?.name ?? st.identity?.village_name;
        if (n) setNames((m) => (m[id] === n ? m : { ...m, [id]: n }));
      })
    );
    return () => unsubs.forEach((u) => u());
  }, [sockets]);
  return names;
}

function VillageRoom({ village, socket, tabs, onTab, onNew, make, api }: {
  village: string; socket: VillageSocket; tabs: VillageTab[]; onTab: (v: string) => void; onNew: () => void;
  make: (o: { village: string; viewAs?: string }) => VillageSocket; api: ApiConfig;
}) {
  const state = useSocketState(socket);
  const scene = useScene(socket, village);
  const founding = isFounding(scene);

  // View as (D21): a read-only socket that asks Core for that member's snapshot; the main stream keeps flowing
  const [viewAs, setViewAs] = useState<string | null>(null);
  const [asSocket, setAsSocket] = useState<VillageSocket | null>(null);
  useEffect(() => {
    if (!viewAs) {
      setAsSocket(null);
      return;
    }
    const s = make({ village, viewAs });
    s.connect();
    setAsSocket(s);
    return () => s.close();
  }, [viewAs, village, make]);
  const asState = useSocketState(asSocket ?? socket);
  const liveView = asSocket && asState.viewAs ? { role: asState.role, view: asState.view, data: asState.data } : null;

  const [warpState, setWarpState] = useState<"idle" | "busy" | "failed">("idle");
  const onWarp = async () => {
    setWarpState("busy");
    try {
      await warpClock(api, 30);
      setWarpState("idle");
    } catch {
      setWarpState("failed");
    }
  };

  // the caption bar never covers content: pad the room by its height
  const capRef = useRef<HTMLDivElement | null>(null);
  const [capH, setCapH] = useState(0);
  useLayoutEffect(() => {
    const el = capRef.current;
    if (!el) {
      setCapH(0);
      return;
    }
    const measure = () => setCapH(el.getBoundingClientRect().height);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [scene.captions.length]);

  const lastQuestion = [...scene.transcript].reverse().find((l) => l.who === "village")?.text ?? "";
  const onAnswer = async (text: string) => {
    await answerFollowUp(api, village, lastQuestion, text);
  };
  const spec = scene.spec;
  const people = scene.blueprint.stages.people ?? spec?.blueprint?.people ?? [];
  const coordP = people.find((p: any) => p.role === "coordinator");
  const coordinator = coordP ? displayName(coordP, nameCtx(scene)) : "Coordinator";
  return (
    <main className={`control${founding ? " founding" : ""}${HERO ? " hero" : ""}`} data-test="control" data-status={state.status} data-village={village} data-mode={founding ? "founding" : "live"} data-frames={scene.frames} style={{ paddingBottom: `${Math.round(capH) + 32}px` }}>
      <Header tabs={tabs} tab={village} onTab={onTab} onNew={onNew} phones={scene.phones} clock={scene.clock} nowMs={socket.nowMs} onWarp={onWarp} warpState={warpState} />
      {state.status !== "live" && state.status !== "idle" ? (
        <p className="ws-banner" data-test="ws-banner">{state.status === "reconnecting" ? `Reconnecting to Core… (try ${state.attempt})` : state.status === "closed" ? `Not connected: ${state.closedReason ?? "closed"}` : "Connecting to Core…"}</p>
      ) : null}
      {founding ? (
        <div className="cr-grid">
          <TranscriptRegion lines={scene.transcript} onSend={onAnswer} speakerName={coordinator} />
          <LedgerRegion rows={scene.ledger} nowMs={socket.nowMs} />
          <BlueprintRegion spec={spec} scene={scene} />
          {scene.data["prescriptions:current"] ? <KnowsRegion api={api} village={village} data={scene.data} spec={spec} /> : null}
          <PhonesRegion spec={spec} data={scene.data} village={village} nowMs={socket.nowMs} viewAs={null} onViewAs={() => {}} live={null} cfg={api} people={people} villageName={scene.villageName} />
        </div>
      ) : (
        <div className="cr-grid">
          <BlueprintRegion spec={spec} scene={scene} />
          <LedgerRegion rows={scene.ledger} nowMs={socket.nowMs} />
          <LiveMomentRegion live={scene.live} nowMs={socket.nowMs} spec={spec} data={scene.data} />
          <KnowsRegion api={api} village={village} data={scene.data} spec={spec} />
          <PhonesRegion spec={spec} data={scene.data} village={village} nowMs={socket.nowMs} viewAs={viewAs} onViewAs={setViewAs} live={liveView} cfg={api} />
          <GateRegion gate={scene.gate} decisions={scene.decisions} autonomy={scene.autonomy} />
          <AskWhyRegion cfg={api} village={village} />
        </div>
      )}
      <CaptionsLayer ref={capRef} captions={scene.captions} />
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
