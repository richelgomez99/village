import { useEffect, useMemo, useState } from "react";
import { createFakeWebSocket, isFakeClient, parseFakeOptions } from "../dev/fakeWs";
import { FAKE_VILLAGES } from "../dev/fixtureData";
import type { ClientName } from "./messages";
import { VillageSocket, type LiveState } from "./ws";

export interface LiveConfig {
  url: string;
  village: string;
  token: string;
  client: ClientName;
  fake: string | null;
}

/** Resolve socket config from the page URL: ?fake=<client> (offline), ?m=<token> or stored token, CORE_WS / same-origin /ws. */
export function liveConfig(client: ClientName, loc: Location = window.location): LiveConfig {
  const p = new URLSearchParams(loc.search);
  const fake = p.get("fake");
  const env0 = (import.meta as any).env ?? {};
  const stored = readStored();
  const token =
    client === "control"
      ? p.get("t") ?? p.get("m") ?? (fake ? "ct_control_offline_demo" : "control")
      : p.get("m") ?? stored.token ?? `mt_${fake ?? "anonymous"}_offline_demo`;
  // the village travels with the token: URL, else what we stored next to this token, else env, else (offline) the fake's
  const village = p.get("village") || (client !== "control" && stored.token === token ? stored.village : null) || env0.VITE_VILLAGE || (fake ? FAKE_VILLAGES[0] : "");
  const env = (import.meta as any).env ?? {};
  const core: string =
    env.VITE_CORE_WS ??
    (env.DEV ? "ws://localhost:8787/ws" : `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/ws`);
  const url = fake ? `ws://fake/${fake}` : `${core}?village=${encodeURIComponent(village)}&m=${encodeURIComponent(token)}`;
  return { url, village, token, client, fake };
}

export const TOKEN_KEY = "village_member_token";
export const VILLAGE_KEY = "village_id";

function readStored(): { token: string | null; village: string | null } {
  try {
    return { token: localStorage.getItem(TOKEN_KEY), village: localStorage.getItem(VILLAGE_KEY) };
  } catch {
    return { token: null, village: null };
  }
}

/** Keep the member token and its village together (storage) and the village in the address bar, so a reload,
 *  a service-worker update or a reconnect never comes back with an empty village. */
export function persistMember(token: string, village: string) {
  if (!village) return;
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(VILLAGE_KEY, village);
  } catch {
    /* private mode: the URL still carries it */
  }
  if (typeof window !== "undefined" && typeof history !== "undefined") {
    const u = new URL(window.location.href);
    if (u.searchParams.get("village") !== village) {
      u.searchParams.set("village", village);
      history.replaceState(history.state, "", u.pathname + u.search + u.hash);
    }
  }
}

export function makeSocket(cfg: LiveConfig, search = typeof window !== "undefined" ? window.location.search : "", extra: { viewAs?: string; fakeOverrides?: Partial<ReturnType<typeof parseFakeOptions>> } = {}): VillageSocket {
  const WebSocketImpl = isFakeClient(cfg.fake) ? createFakeWebSocket(cfg.fake, { ...parseFakeOptions(search), ...(extra.fakeOverrides ?? {}) }) : undefined;
  const socket = new VillageSocket({ url: cfg.url, village: cfg.village, token: cfg.token, client: cfg.client, WebSocketImpl, viewAs: extra.viewAs });
  if (cfg.client === "kit" && !cfg.fake && !extra.viewAs) {
    let last = "";
    socket.subscribe((st) => {
      // learn the village from the snapshot if we didn't have one, then persist it with the token
      if (st.village && st.village !== last && !st.viewAs) {
        last = st.village;
        persistMember(cfg.token, st.village);
      }
    });
  }
  return socket;
}

export function useLive(client: ClientName = "kit") {
  const socket = useMemo(() => makeSocket(liveConfig(client)), [client]);
  const [state, setState] = useState<LiveState>(socket.state);
  useEffect(() => {
    const unsub = socket.subscribe(setState);
    socket.connect();
    return () => {
      unsub();
      socket.close();
    };
  }, [socket]);
  return { state, socket };
}
