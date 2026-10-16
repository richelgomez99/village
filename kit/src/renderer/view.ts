import { applyPatch, type Operation } from "fast-json-patch";
import { z } from "zod";

export const localizedSchema = z.record(z.string(), z.string()).or(z.string());
export type Localized = z.infer<typeof localizedSchema>;

export const elementSchema = z.object({
  type: z.string(),
  props: z.record(z.string(), z.unknown()).default({}),
  children: z.array(z.string()).optional()
});

export const viewSchema = z.object({
  lang: z.string().default("en"),
  dir: z.enum(["ltr", "rtl"]).optional(),
  theme: z.string().default("family"),
  root: z.string().default("s"),
  elements: z.record(z.string(), elementSchema),
  needs_served: z.record(z.string(), z.array(z.string())).optional()
});

export type ElementNode = z.infer<typeof elementSchema>;
export type View = z.infer<typeof viewSchema>;

export function applyViewPatch(view: View, ops: Operation[]): View {
  const clone = structuredClone(view);
  const result = applyPatch(clone, ops, true, false).newDocument;
  return viewSchema.parse(result);
}

export function text(value: unknown, lang = "en"): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const direct = obj[lang] ?? obj.en ?? Object.values(obj)[0];
    return typeof direct === "string" ? direct : "";
  }
  return "";
}

export function normalizeReyesView(view: View, role: string): View {
  const next = structuredClone(view);
  if (role === "elder") {
    next.elements.tonight = {
      type: "Text",
      props: { text: "Esta noche cuida Marco", size: "xl", tone: "ok" }
    };
    next.elements.b_pill = {
      type: "BigButton",
      props: {
        label: "Llamar a Village",
        icon: "phone",
        tone: "info",
        action: "call_village",
        confirm: false,
        speak: "Llamar a Village"
      }
    };
    const screen = next.elements[next.root];
    screen.children = ["al", "tonight", "b_pill", "b_call", "b_help", "e911"].filter((id) => next.elements[id]);
  }
  if (role === "coordinator" || role === "helper") {
    next.elements.refill = {
      type: "RefillCard",
      props: { bind: "prescriptions:current", owner: "Marco" }
    };
    const screen = next.elements[next.root];
    if (screen?.children && !screen.children.includes("refill")) {
      const after = role === "helper" ? 2 : screen.children.indexOf("dose") + 1;
      screen.children.splice(Math.max(1, after), 0, "refill");
    }
  }
  return next;
}
