import { createRoot } from "react-dom/client";
import { MemberApp } from "./app/MemberApp";
import { liveConfig, makeSocket } from "./live/useLive";
import "./theme/fonts.css";
import "./theme/floor.css";
import "./theme/village.css";

const params = new URLSearchParams(window.location.search);
const socket = makeSocket(liveConfig("kit"));
socket.connect();
(window as any).__village = socket;
createRoot(document.getElementById("root")!).render(<MemberApp socket={socket} captions={params.get("captions") === "1"} />);
