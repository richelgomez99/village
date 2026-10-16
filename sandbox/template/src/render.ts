// Catalog-only renderer. Unknown types render nothing. Components never call the network:
// actions are handed to the host (Core's WebSocket client) through window.villageAction.
import { createElement as h, type ReactNode } from "react";
import { isCatalogType, secondaryPx, styleFor, type Props, type ThemeName } from "./catalog";

export interface Element { type: string; props: Props; children?: string[] }
export interface View { lang: string; theme: ThemeName; dir?: "ltr" | "rtl"; root: string; elements: Record<string, Element> }

const ICONS: Record<string, string> = { pill: "💊", phone: "📞", sos: "🆘", check: "✓", alert: "!", home: "⌂" };

function act(action: string, arg?: unknown) {
  const w = globalThis as unknown as { villageAction?: (a: string, b?: unknown) => void };
  w.villageAction?.(action, arg);
}

function textOf(type: string, p: Props): string {
  return String(p.label ?? p.title ?? p.text ?? p.name ?? p.question ?? type);
}

export function renderElement(view: View, id: string): ReactNode {
  const el = view.elements[id];
  if (!el || !isCatalogType(el.type)) return null;
  const p = el.props ?? {};
  const s = styleFor(el.type, p, view.theme);
  const base = {
    key: id,
    "data-id": id,
    "data-type": el.type,
    "data-tone": String(p.tone ?? ""),
  };
  const kids = (el.children ?? []).map((c) => renderElement(view, c));
  switch (el.type) {
    case "Screen":
      return h("main", { ...base, style: { padding: 16, display: "flex", flexDirection: "column", gap: 16 } },
        h("h1", { style: { fontSize: s.fontSize, color: s.color, margin: 0, fontWeight: 700 } }, textOf(el.type, p)),
        ...kids);
    case "Stack":
      return h("section", { ...base, style: { display: "flex", flexDirection: "column", gap: 12 } }, ...kids);
    case "Header":
      return h("h2", { ...base, style: { fontSize: s.fontSize, color: s.color, margin: 0 } }, textOf(el.type, p));
    case "Text":
      return h("p", { ...base, style: { fontSize: s.fontSize, color: s.color, margin: 0 } }, textOf(el.type, p));
    case "Alert":
      // Live alerts arrive over the WebSocket binding; nothing to show in a static render.
      return h("div", { ...base, role: "status", "aria-live": "assertive", style: { display: "none" } });
    case "BigButton":
      return h("button", {
        ...base,
        type: "button",
        "aria-label": textOf(el.type, p),
        onClick: () => act(String(p.action), p.action_arg),
        style: {
          minHeight: s.minHeight, fontSize: s.fontSize, color: s.color, background: s.background,
          border: `2px solid ${s.color}`, borderLeft: `14px solid ${s.bar}`, borderRadius: 16,
          fontWeight: 700, textAlign: "start", padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, width: "100%",
        },
      }, h("span", { "aria-hidden": true }, ICONS[String(p.icon)] ?? ""), textOf(el.type, p));
    case "ContactCard":
      return h("a", {
        ...base,
        href: p.phone ? `tel:${String(p.phone)}` : undefined,
        style: {
          minHeight: s.minHeight, fontSize: s.fontSize, color: s.color, background: s.background,
          border: `2px solid ${s.color}`, borderLeft: `14px solid ${s.bar}`, borderRadius: 16, fontWeight: 700,
          display: "flex", flexDirection: "column", justifyContent: "center", padding: "8px 16px", textDecoration: "none",
        },
      }, h("span", null, String(p.label ?? p.name)),
        p.phone ? h("span", { style: { fontSize: secondaryPx(view.theme), fontWeight: 400 } }, String(p.phone)) : null);
    default:
      return h("section", {
        ...base,
        style: { minHeight: s.minHeight, fontSize: s.fontSize, color: s.color, background: s.background, borderLeft: `8px solid ${s.bar}`, borderRadius: 12, padding: 12 },
      }, textOf(el.type, p));
  }
}

export function renderView(view: View): ReactNode {
  return h("div", { dir: view.dir ?? "ltr", lang: view.lang, "data-theme": view.theme, style: { background: "#FBF6EE", minHeight: "100vh", fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif" } },
    renderElement(view, view.root));
}
