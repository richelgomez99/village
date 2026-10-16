// Control Room (T020–T026, T042, T045): one dark projector page, a scene reducer fed by every WS frame.
// /control.html?t=<control token>  ·  offline: /control.html?fake=control&seq=founding|scam|release|evolve
// Every region keys on the selected village: each village has its own control socket and its own scene, and the room
// remounts on switch, so nothing from one village shows under the other. No village yet = the founding (transcript ·
// work log · blueprint with coverage meter · phone skeletons).
import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { useSocketState } from "../app/MemberApp";
import { answerFollowUp, apiConfig, apiRequest, createVillage, getQr, listDecisions, listVillages, warpClock, type ApiConfig } from "../control/api";
import { ArcStrip, AutonomyHeadline, ChatMirror, type ArcBeat, AskWhyRegion, BlueprintRegion, CaptionsLayer, FoundingWorkRegion, GateRegion, Header, KnowsRegion, ProposalRegion, LedgerRegion, LiveMomentRegion, NEW_VILLAGE, PhonesRegion, TranscriptRegion, resolveAs, type VillageTab } from "../control/regions";
import { displayName, initialScene, nameCtx, sceneReducer, type SceneState } from "../control/scene";
import { FAKE_VILLAGES } from "../dev/fixtureData";
import { addCaption } from "../i18n/captions";
import { TransportBar } from "../control/transport";
import { PresenterLayer } from "../control/PresenterLayer";
import { KEY_MAP_7, coordinatorTokenFromQr, coverLine, demoCast, moneyCallBody, thanksgivingLine } from "../control/presenter";
import { ReceiptOverlay } from "../control/regions";
import { BuildSection, RebuildSection, useProposals, type Section } from "../control/sections";
import type { Transport } from "../dev/transport";
import { liveConfig, makeSocket, type LiveConfig } from "../live/useLive";
import type { VillageSocket } from "../live/ws";
import "../theme/fonts.css";
import "../theme/floor.css";
import "../theme/a.css";

/** Scene for one village's socket: reduce every validated frame (replayed from the socket's log on mount). */
export function useScene(socket: VillageSocket, village: string): SceneState {
  return useSceneWithDispatch(socket, village)[0];
}

export function useSceneWithDispatch(socket: VillageSocket, village: string) {
  const [scene, dispatch] = useReducer(sceneReducer, village, initialScene);
  useEffect(
    () =>
      socket.onFrame((f) => {
        if (f.type === "control" && f.kind === "caption") addCaption(String((f.payload as any).es ?? ""), String((f.payload as any).en ?? ""));
        dispatch(f);
      }),
    [socket]
  );
  // offline replays: stepping back rebuilds the scene from frame 0 (reset → hello snapshot → prefix); the reducer is pure
  useEffect(() => {
    const tr = typeof window !== "undefined" ? ((window as any).__fake?.transport as Transport | null | undefined) : null;
    if (!tr) return;
    return tr.subscribe((e) => {
      if (e.type !== "rewind" || (tr.village && tr.village !== village)) return;
      dispatch({ type: "reset", village });
      if (e.initial) dispatch(e.initial);
      e.frames.forEach((f) => dispatch(f));
    });
  }, [village]);
  return [scene, dispatch] as const;
}

/** ?presenter=1: live stage mode — keys drive Core, no demo chrome (clock in words, no transport/details/banners). */
const PRESENTER = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("presenter") === "1";

/** "Friday · 8:50 PM · <on-duty name>'s night" from the room clock and the rota. */
export function villageTimeWords(nowIso: string, data: Record<string, unknown>): string {
  const d = new Date(nowIso);
  if (Number.isNaN(d.getTime())) return "";
  const day = d.toLocaleDateString("en-US", { weekday: "long", timeZone: "America/New_York" });
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
  const onDuty = data["rota:current.on_duty"] as { name?: string } | null | undefined;
  let who = onDuty?.name ?? "";
  if (!who && Array.isArray(data["rota:week"])) {
    const ymd = d.toLocaleDateString("en-CA", { timeZone: "America/New_York" });
    const row = (data["rota:week"] as { date: string; on_duty: string }[]).find((r) => r.date === ymd);
    const m = row ? (data[`member:${row.on_duty}`] as { name?: string } | undefined) : undefined;
    who = m?.name ?? "";
  }
  return [day, time, who ? `${who}'s night` : ""].filter(Boolean).join(" · ");
}

/** ?hero=1: screenshot mode, dev chrome hidden (connection banner, clock warp, view-as bar). */
const HERO = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("hero") === "1";

const QS = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
const ADMIN_KEY = QS.get("admin") ?? "";
const SECRET = QS.get("secret") ?? "";
const COORD_TOKEN = QS.get("ana") ?? QS.get("coord") ?? "";

/** first proposal waiting for a yes (proposals:pending, else the room's latest proposal frame) */
function firstPending(scene: SceneState): string | null {
  const p = scene.data["proposals:pending"];
  if (Array.isArray(p) && p.length) return String((p[0] as { proposal_id?: string; id?: string }).proposal_id ?? (p[0] as { id?: string }).id ?? "") || null;
  return scene.proposal && ["proposed", "ready"].includes(scene.proposal.status) ? scene.proposal.id : null;
}

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
  // a village is always selected once one is known; only "+ New village" opens the empty founding room
  const urlVillage = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("village") : null;
  const [tab, setTabRaw] = useState(home || urlVillage || list[0] || "");
  const [wantNew, setWantNew] = useState(false);
  const setTab = (v: string) => {
    setWantNew(v === NEW_VILLAGE);
    setTabRaw(v);
  };
  useEffect(() => {
    if (villages || apiCfg.fake) return;
    let live = true;
    listVillages(apiCfg).then(
      (rows) => {
        if (!live || !rows.length) return;
        const ids = rows.map((r) => r.id);
        setList((l) => [...ids, ...l.filter((v) => !ids.includes(v))]);
      },
      () => undefined
    );
    return () => {
      live = false;
    };
  }, [apiCfg, villages]);
  useEffect(() => {
    if (!wantNew && (!tab || tab === NEW_VILLAGE) && list.length) setTabRaw(urlVillage && list.includes(urlVillage) ? urlVillage : list[0]);
  }, [list, tab, wantNew]); // eslint-disable-line react-hooks/exhaustive-deps
  const [details, setDetails] = useState(false);
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
  if (typeof window !== "undefined") (window as any).__villages = sockets;
  const names = useVillageNames(sockets);
  const people = useVillagePeople(sockets);
  const asMe = resolveAs(typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("as") : null, people);
  const tabs: VillageTab[] = list.map((id) => ({ id, label: names[id] ?? id.replace(/^v_/, ""), role: asMe?.roles[id] }));
  const owner = asMe?.first || undefined;

  // presenter B / X: a replay socket (offline fake + transport) shown in place of the live room; Esc / X returns
  const [override, setOverride] = useState<{ socket: VillageSocket; village: string; kind: "b" | "x" } | null>(null);
  const exitReplay = () => {
    if (!override) return;
    override.socket.close();
    override.socket = null as any;
    try {
      delete (window as any).__fake;
    } catch {
      /* ignore */
    }
    setOverride(null);
  };
  const startVillage = async (description: string) => {
    const r = await createVillage(apiCfg, description);
    const s = make({ village: r.village_id, founding: true });
    s.connect();
    setSockets((m) => ({ ...m, [r.village_id]: s }));
    setList((l) => (l.includes(r.village_id) ? l : [...l, r.village_id]));
    setTab(r.village_id);
  };
  const startReplay = (kind: "b" | "x", beatNow: ArcBeat) => {
    if (override) {
      exitReplay();
      if (override.kind === kind) return;
    }
    const block = kind === "b" || (tab === FAKE_VILLAGES[1] && beatNow !== "run" && beatNow !== "rebuild");
    const village = block ? FAKE_VILLAGES[1] : FAKE_VILLAGES[0];
    const seq = kind === "b" || beatNow === "build" || beatNow === "anyone" ? "founding" : beatNow === "run" ? "scam" : "evolve";
    const search = `?seq=${seq}${seq === "founding" && block ? "&audio=1" : ""}${seq === "scam" ? "&tail=denied" : ""}`;
    const s = makeSocket({ url: "ws://fake/control", village, token: "ct_replay_offline_demo", client: "control", fake: "control" }, search);
    s.connect();
    setOverride({ socket: s, village, kind });
  };
  if (override) {
    return <VillageRoom key={`replay:${override.kind}:${override.village}`} village={override.village} socket={override.socket} tabs={tabs} onTab={(v) => { exitReplay(); setTab(v); }} onNew={() => { exitReplay(); setTab(NEW_VILLAGE); }} make={make} api={{ ...apiCfg, fake: true }} details={details} onDetails={setDetails} replay onReplay={startReplay} onExitReplay={exitReplay} owner={owner} />;
  }
  const active = tab === NEW_VILLAGE || !tab ? null : sockets[tab];
  if (!active && !wantNew && list.length) {
    return <main className="control" data-test="control" data-village={tab} data-mode="loading"><p className="ws-banner" data-test="ws-banner">Connecting to Core…</p></main>;
  }
  if (!active) {
    return (
      <main className="control founding" data-test="control" data-village="" data-mode="founding">
        <Header tabs={tabs} tab={NEW_VILLAGE} onTab={setTab} onNew={() => setTab(NEW_VILLAGE)} phones={null} clock={null} nowMs={() => Date.now()} onWarp={() => {}} warpState="idle" owner={owner} />
        <div className="cr-grid">
          <TranscriptRegion lines={[]} onSend={startVillage} />
          <LedgerRegion rows={[]} nowMs={() => Date.now()} />
          <BlueprintRegion spec={null} scene={initialScene("")} />
        </div>
      </main>
    );
  }
  // arc strip: offline it jumps between the fake scenes; "Anyone" switches to the next village either way
  const jump = (b: ArcBeat) => {
    if (b === "anyone") {
      const next = list.find((v) => v !== tab) ?? tab;
      setTab(next);
      return;
    }
    if (!cfg?.fake || typeof window === "undefined") return;
    const seq = b === "build" ? "founding" : b === "run" ? "scam" : "evolve";
    const p = new URLSearchParams(window.location.search);
    p.set("seq", seq);
    if (b !== "build") p.delete("village");
    window.location.search = p.toString();
  };
  const reselect = () => {
    const old = sockets[tab];
    const s = make({ village: tab });
    s.connect();
    setSockets((m) => ({ ...m, [tab]: s }));
    old?.close();
  };
  const nextVillage = () => setTab(list[(list.indexOf(tab) + 1) % list.length] ?? tab);
  return <VillageRoom key={`${tab}:${roomEpoch(sockets[tab])}`} village={tab} socket={active} tabs={tabs} onTab={setTab} onNew={() => setTab(NEW_VILLAGE)} make={make} api={apiCfg} details={details} onDetails={setDetails} onJump={jump} anyone={!!(home || list[0]) && tab !== (home || list[0])} onReselect={reselect} onNextVillage={nextVillage} onReplay={startReplay} owner={owner} />;
}

const EPOCHS = new WeakMap<object, number>();
let epochSeq = 0;
/** a stable number per socket object, so re-opening a village's socket remounts its room */
function roomEpoch(s: object | undefined): number {
  if (!s) return 0;
  if (!EPOCHS.has(s)) EPOCHS.set(s, ++epochSeq);
  return EPOCHS.get(s)!;
}

/** blueprint.people from each socket's spec, for `?as=` role words on the switcher pills. */
function useVillagePeople(sockets: Record<string, VillageSocket>): Record<string, any[]> {
  const [people, setPeople] = useState<Record<string, any[]>>({});
  useEffect(() => {
    const unsubs = Object.entries(sockets).map(([id, s]) =>
      s.subscribe((st) => {
        const p = (st.spec as any)?.blueprint?.people;
        if (Array.isArray(p)) setPeople((m) => (m[id] === p ? m : { ...m, [id]: p }));
      })
    );
    return () => unsubs.forEach((u) => u());
  }, [sockets]);
  return people;
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

function VillageRoom({ village, socket, tabs, onTab, onNew, make, api, details = false, onDetails, onJump, anyone = false, onReselect, onNextVillage, replay = false, onReplay, onExitReplay, owner }: {
  owner?: string;
  onReselect?: () => void; onNextVillage?: () => void;
  /** presenter B/X replay in place of the live room: transport bar shown even in presenter mode */
  replay?: boolean; onReplay?: (kind: "b" | "x", beat: ArcBeat) => void; onExitReplay?: () => void;
  village: string; socket: VillageSocket; tabs: VillageTab[]; onTab: (v: string) => void; onNew: () => void;
  make: (o: { village: string; viewAs?: string }) => VillageSocket; api: ApiConfig;
  details?: boolean; onDetails?: (on: boolean) => void; onJump?: (b: ArcBeat) => void; anyone?: boolean;
}) {
  const state = useSocketState(socket);
  const [scene, dispatch] = useSceneWithDispatch(socket, village);
  const founding = isFounding(scene);
  const beat: ArcBeat = anyone ? "anyone" : founding ? "build" : scene.beat ?? "run";
  // ROOM-10: the pills navigate (Build = intake · Run = today · Rebuild = suggestions); null = follow the live beat
  const [section, setSection] = useState<Section | null>(null);
  const shown: Section = section ?? (founding ? "build" : "run");
  const proposals = useProposals(api, village, `${scene.proposal?.id ?? ""}:${scene.proposal?.status ?? ""}:${JSON.stringify(scene.data["proposals:pending"] ?? null).length}:${shown}`);
  const transport = typeof window !== "undefined" ? ((window as any).__fake?.transport as Transport | null | undefined) ?? null : null;
  // presenter ROOM-7 keys: real Core calls built from the spec (names never hard-coded)
  const [receipt, setReceipt] = useState<any>(null);
  const real: ApiConfig = { ...api, fake: false };
  const coordinatorToken = async (): Promise<string> => {
    if (COORD_TOKEN) return COORD_TOKEN;
    const qr = await getQr(real, village);
    const t = coordinatorTokenFromQr(qr as any, spec?.village?.coordinator_id);
    if (!t) throw new Error("no coordinator token");
    return t;
  };
  const openReceipt = async (releaseId?: string) => {
    let r = releaseId && scene.release?.id === releaseId ? scene.release : null;
    if (!r) {
      const res = (await apiRequest(real, "GET" as any, `/villages/${encodeURIComponent(village)}/releases`).catch(() => [])) as { receipts?: any[] } | any[];
      const all = Array.isArray(res) ? res : res?.receipts ?? [];
      r = all.find((x: any) => x.id === releaseId) ?? null;
    }
    if (r) setReceipt(r);
  };
  const presenterExtras: Record<string, () => Promise<string | void> | string | void> = {
    m: async () => {
      await apiRequest(real, "POST", "/tools/report_money_request", moneyCallBody(spec, village), SECRET ? { "X-Village-Secret": SECRET } : undefined);
      return `${demoCast(spec).centerName || "She"} reported the call`;
    },
    s: async () => {
      await apiRequest({ ...real, token: await coordinatorToken() }, "POST", `/villages/${encodeURIComponent(village)}/messages`, { text: coverLine(spec) });
      return `${demoCast(spec).coordName || "The coordinator"} asked the chat for cover`;
    },
    t: async () => {
      await apiRequest({ ...real, token: await coordinatorToken() }, "POST", `/villages/${encodeURIComponent(village)}/messages`, { text: thanksgivingLine(spec), mention: "village" });
      return `${demoCast(spec).coordName || "The coordinator"} posted the Thanksgiving plan`;
    },
    w: async () => {
      try {
        await apiRequest(real, "POST", "/admin/warm");
      } catch {
        await apiRequest(real, "GET", "/health").catch(() => undefined);
        await listVillages(real).catch(() => undefined);
      }
      return "warm";
    },
    l: async () => {
      let r = scene.release;
      if (!r) {
        const res = (await apiRequest(real, "GET" as any, `/villages/${encodeURIComponent(village)}/releases`)) as { receipts?: any[] } | any[];
        const list = Array.isArray(res) ? res : res?.receipts ?? [];
        r = [...list].sort((a, b) => Date.parse(b.created_at ?? "") - Date.parse(a.created_at ?? ""))[0] ?? null;
      }
      if (!r) return "No receipt yet";
      setReceipt(r);
      return `Receipt · rev ${r.rev}`;
    },
    b: () => {
      onReplay?.("b", beat);
      return replay ? "Back to live" : "The block's founding call";
    },
    x: () => {
      onReplay?.("x", beat);
      return replay ? "Back to live" : "Replay with controls";
    }
  };
  // presenter: a connection banner only after 5 s down
  const [downLong, setDownLong] = useState(false);
  useEffect(() => {
    if (state.status === "live" || state.status === "idle") {
      setDownLong(false);
      return;
    }
    const t = setTimeout(() => setDownLong(true), 5000);
    return () => clearTimeout(t);
  }, [state.status]);
  // decisions log backfill from Core (then control{gate|reasoning} frames keep it live)
  useEffect(() => {
    let live = true;
    listDecisions(api, village).then((rows) => live && rows.length && dispatch({ type: "decisions", rows }), () => undefined);
    return () => {
      live = false;
    };
  }, [api, village]);

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

  // block founding with a recorded call: browsers block autoplay, so the first click starts the call (fake replay)
  const [audioBlocked, setAudioBlocked] = useState(() => typeof window !== "undefined" && (window as any).__fake?.audioState === "blocked");
  useEffect(() => {
    const on = (e: Event) => setAudioBlocked((e as CustomEvent).detail === "blocked");
    window.addEventListener("village-audio", on);
    return () => window.removeEventListener("village-audio", on);
  }, []);
  const playAudio = () => {
    setAudioBlocked(false);
    (window as any).__fake?.startAudio?.();
  };
  const lastQuestion = [...scene.transcript].reverse().find((l) => l.who === "village")?.text ?? "";
  const onAnswer = async (text: string) => {
    await answerFollowUp(api, village, lastQuestion, text);
  };
  const spec = scene.spec;
  const people = scene.blueprint.stages.people ?? spec?.blueprint?.people ?? [];
  const coordP = people.find((p: any) => p.role === "coordinator") ?? (spec?.blueprint?.people ?? []).find((p: any) => p.role === "coordinator");
  const coordinator = coordP ? displayName(coordP, nameCtx(scene)) : "Coordinator";
  return (
    <main className={`control${founding ? " founding" : ""}${HERO ? " hero" : ""}${transport && !HERO ? " has-transport" : ""}`} data-test="control" data-status={state.status} data-village={village} data-mode={founding ? "founding" : "live"} data-frames={scene.frames} style={{ paddingBottom: `${Math.round(capH) + 32 + (transport && !HERO ? 56 : 0)}px` }}>
      <Header owner={owner} tabs={tabs} tab={village} onTab={onTab} onNew={onNew} phones={scene.phones} clock={scene.clock} nowMs={socket.nowMs} onWarp={onWarp} warpState={warpState} details={details} onDetails={onDetails} villageTime={PRESENTER ? villageTimeWords(scene.clock?.now ?? new Date(socket.nowMs()).toISOString(), scene.data) || " " : undefined} />
      <ArcStrip beat={beat} selected={shown} onJump={(b) => (b === "anyone" ? onJump?.(b) : setSection(b))} />
      {state.status !== "live" && state.status !== "idle" && (!PRESENTER || downLong) ? (
        <p className="ws-banner" data-test="ws-banner">{state.status === "reconnecting" ? `Reconnecting to Core… (try ${state.attempt})` : state.status === "closed" ? `Not connected: ${state.closedReason ?? "closed"}` : "Connecting to Core…"}</p>
      ) : null}
      {!scene.spec && scene.frames === 0 ? (
        <p className="empty loading" data-test="room-loading">Opening {tabs.find((t) => t.id === village)?.label ?? "the village"}…</p>
      ) : shown === "rebuild" ? (
        <RebuildSection
          spec={spec}
          rows={proposals.rows}
          options={proposals.options}
          error={proposals.error}
          onDecide={async (pid, a) => {
            await apiRequest(real, "POST", `/villages/${encodeURIComponent(village)}/proposals/${encodeURIComponent(pid)}/${a}`);
            proposals.reload();
          }}
          onReceipt={openReceipt}
          onSuggest={async (t) => {
            await apiRequest({ ...real, token: await coordinatorToken() }, "POST", `/villages/${encodeURIComponent(village)}/messages`, { text: t, mention: "village" });
          }}
        />
      ) : shown === "build" && !founding ? (
        <BuildSection scene={scene} live={false} onAddDetail={(t) => answerFollowUp(api, village, lastQuestion, t)} />
      ) : shown === "build" ? (
        <div className="cr-grid">
          <TranscriptRegion lines={scene.transcript} onSend={onAnswer} speakerName={coordinator} onPlayAudio={audioBlocked ? playAudio : undefined} />
          <FoundingWorkRegion blocks={scene.blocks} ledger={scene.ledger} nowMs={socket.nowMs} />
          <BlueprintRegion spec={spec} scene={scene} />
          <PhonesRegion spec={spec} data={scene.data} village={village} nowMs={socket.nowMs} viewAs={null} onViewAs={() => {}} live={null} cfg={api} people={people} villageName={scene.villageName} drafts={scene.drafts} draftNew={scene.draftNew} />
        </div>
      ) : (
        <div className="cr-live">
          <div className="cr-main">
            <BlueprintRegion spec={spec} scene={scene} />
            <div className="cr-stack">
              <LedgerRegion rows={scene.ledger} nowMs={socket.nowMs} details={details} />
              <ChatMirror chat={scene.chat} data={scene.data} />
            </div>
            <PhonesRegion spec={spec} data={scene.data} village={village} nowMs={socket.nowMs} viewAs={viewAs} onViewAs={setViewAs} live={liveView} cfg={api} />
          </div>
          <aside className="cr-side">
            <AutonomyHeadline rounds={scene.rounds} />
            {scene.live ? <LiveMomentRegion live={scene.live} nowMs={socket.nowMs} spec={spec} data={scene.data} /> : null}
            {scene.proposal ? <ProposalRegion proposal={scene.proposal} release={scene.release} spec={spec} details={details} /> : null}
            <KnowsRegion api={api} village={village} data={scene.data} spec={spec} />
            <GateRegion gate={scene.gate} decisions={scene.decisions} autonomy={scene.autonomy} details={details} />
            <AskWhyRegion cfg={api} village={village} />
          </aside>
        </div>
      )}
      {transport && !HERO && (!PRESENTER || replay) ? <TransportBar transport={transport} beat={beat} villages={tabs} /> : null}
      {receipt ? <ReceiptOverlay receipt={receipt} spec={spec} data={scene.data} onClose={() => setReceipt(null)} /> : null}
      {PRESENTER ? (
        <PresenterLayer
          api={api}
          ctx={{ village, description: String(spec?.blueprint?.description?.text ?? ""), pendingProposal: firstPending(scene), coordinatorName: coordinator, adminKey: ADMIN_KEY }}
          onNextVillage={() => onNextVillage?.()}
          onDetails={() => onDetails?.(!details)}
          onReselect={() => onReselect?.()}
          extraKeys={presenterExtras}
          extraMap={KEY_MAP_7}
          onEscape={() => {
            if (receipt) setReceipt(null);
            else if (replay) onExitReplay?.();
          }}
        />
      ) : null}
      <CaptionsLayer ref={capRef} captions={scene.captions} />
    </main>
  );
}

if (typeof document !== "undefined" && document.getElementById("root")) {
  const cfg = liveConfig("control");
  const socket = makeSocket(cfg);
  // without ?village the room asks Core for its villages (GET /villages) and opens one socket per village itself
  if (cfg.village) socket.connect();
  (window as any).__village = socket;
  createRoot(document.getElementById("root")!).render(<ControlRoom socket={socket} cfg={cfg} />);
}
