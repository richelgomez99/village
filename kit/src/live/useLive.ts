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
  const village = p.get("village") ?? env0.VITE_VILLAGE ?? (fake ? FAKE_VILLAGES[0] : "");
  let stored: string | null = null;
  try {
    stored = localStorage.getItem("village_member_token");
  } catch {
    stored = null;
  }
  const token = (client === "control" ? p.get("t") ?? p.get("m") : p.get("m")) ?? stored ?? `mt_${fake ?? "anonymous"}_offline_demo`;
  const env = (import.meta as any).env ?? {};
  const core: string =
    env.VITE_CORE_WS ??
    (env.DEV ? "ws://localhost:8787/ws" : `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/ws`);
  const url = fake ? `ws://fake/${fake}` : `${core}?village=${encodeURIComponent(village)}&m=${encodeURIComponent(token)}`;
  return { url, village, token, client, fake };
}

export function makeSocket(cfg: LiveConfig, search = typeof window !== "undefined" ? window.location.search : "", extra: { viewAs?: string; fakeOverrides?: Partial<ReturnType<typeof parseFakeOptions>> } = {}): VillageSocket {
  const WebSocketImpl = isFakeClient(cfg.fake) ? createFakeWebSocket(cfg.fake, { ...parseFakeOptions(search), ...(extra.fakeOverrides ?? {}) }) : undefined;
  return new VillageSocket({ url: cfg.url, village: cfg.village, token: cfg.token, client: cfg.client, WebSocketImpl, viewAs: extra.viewAs });
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
