import { useEffect, useMemo, useState } from "react";
import { installFakeWs } from "../dev/fakeWs";
import { VillageSocket, type LiveSnapshot } from "./ws";

export function useLive(client: "kit" | "control" = "kit") {
  const params = new URLSearchParams(window.location.search);
  const fake = params.get("fake");
  if (fake) installFakeWs(fake);
  const token = params.get("m") ?? localStorage.getItem("member_token") ?? `mt_${fake ?? "carmen"}`;
  const core = import.meta.env.VITE_CORE_WS ?? `${import.meta.env.VITE_CORE_URL ?? "ws://localhost:8787"}`.replace(/^http/, "ws") + "/ws";
  const url = fake ? "ws://fake/ws" : `${core}?village=v_reyes&m=${encodeURIComponent(token)}`;
  const socket = useMemo(() => new VillageSocket({ url, village: "v_reyes", token, client, fakeRole: fake ?? undefined }), [url, token, client, fake]);
  const [state, setState] = useState<LiveSnapshot>(() => ({
    status: "idle",
    attempt: 0,
    role: String(fake ?? "elder"),
    member_id: null,
    rev: 0,
    view: null,
    data: {},
    now: new Date().toISOString(),
    prompt: null,
    lastError: null,
    sent: []
  }));

  useEffect(() => {
    const unsub = socket.subscribe(setState);
    socket.connect();
    return () => {
      unsub();
      socket.close();
    };
  }, [socket]);

  return { ...state, send: socket.action.bind(socket) };
}
