import { applyPatch, type Operation } from "fast-json-patch";
import { z } from "zod";

const elementId = z.string().regex(/^[a-z][a-z0-9_]{0,23}$/);

export const elementSchema = z.object({
  type: z.string().min(1),
  props: z.record(z.string(), z.unknown()),
  children: z.array(elementId).max(12).optional()
});

export const viewSchema = z
  .object({
    lang: z.string().regex(/^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/),
    theme: z.enum(["elder", "family", "dashboard"]),
    dir: z.enum(["ltr", "rtl"]).optional(),
    root: z.literal("s"),
    elements: z.record(elementId, elementSchema),
    needs_served: z.record(z.string(), z.array(z.string()).min(1)).optional()
  })
  .superRefine((view, ctx) => {
    const root = view.elements[view.root];
    if (!root || root.type !== "Screen") ctx.addIssue({ code: "custom", message: "root s must be a Screen" });
    for (const [id, el] of Object.entries(view.elements)) {
      for (const child of el.children ?? []) {
        if (!view.elements[child]) ctx.addIssue({ code: "custom", message: `${id} references missing child ${child}` });
      }
    }
  });

export type ElementNode = z.infer<typeof elementSchema>;
export type View = z.infer<typeof viewSchema>;
export type Localized = string | Record<string, string>;

/** Apply RFC 6902 ops to a clone. Throws on a bad op or an invalid result; the input view is never touched. */
export function applyViewPatch(view: View, ops: Operation[]): View {
  const clone = structuredClone(view);
  const next = applyPatch(clone, ops, true, true).newDocument;
  return viewSchema.parse(next);
}

/** Pick a localized string for lang with en / first-value fallback. */
export function text(value: unknown, lang = "en"): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const direct = obj[lang] ?? obj[lang.split("-")[0]] ?? obj.en ?? Object.values(obj)[0];
    return typeof direct === "string" ? direct : "";
  }
  return "";
}

/** Element ids reachable from root (children only on Screen/Stack). */
export function reachable(view: View): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const walk = (id: string) => {
    if (seen.has(id)) return;
    seen.add(id);
    const el = view.elements[id];
    if (!el) return;
    out.push(id);
    if (el.type === "Screen" || el.type === "Stack") (el.children ?? []).forEach(walk);
  };
  walk(view.root);
  return out;
}
