import { createRoot } from "react-dom/client";
import spec from "./village/spec.json";
import { renderView, type View } from "./render";

const params = new URLSearchParams(location.search);
const views = (spec as unknown as { views: Record<string, View> }).views;
const role = params.get("role") ?? "elder";
const view = views[role] ?? views[Object.keys(views)[0]];
document.documentElement.lang = view.lang;
createRoot(document.getElementById("root")!).render(renderView(view));
