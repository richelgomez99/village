import { createRoot } from "react-dom/client";
import { MemberApp } from "./app/MemberApp";
import { liveConfig, makeSocket } from "./live/useLive";
import { apiConfig } from "./control/api";
import "./theme/fonts.css";
import "./theme/floor.css";
import "./theme/village.css";

const params = new URLSearchParams(window.location.search);
const cfg = liveConfig("kit");
const socket = makeSocket(cfg);
const api = { ...apiConfig(), token: cfg.token, fake: !!cfg.fake };
socket.connect();
(window as any).__village = socket;
createRoot(document.getElementById("root")!).render(<MemberApp socket={socket} captions={params.get("captions") === "1"} api={api} />);
