import { useMemo, type ReactNode } from "react";
import { CATALOG } from "./catalog";
import { Ctx, useCtx, type RenderCtx } from "./context";
import { parseProps } from "./props";
import { reachable, type View } from "./view";

/** Reachable element types the catalog doesn't know (they render nothing). */
export function collectUnknown(view: View): string[] {
  return [...new Set(reachable(view).map((id) => view.elements[id].type).filter((t) => !CATALOG[t]))];
}

/** Reachable element ids whose props fail their zod schema (they render nothing). */
export function collectInvalid(view: View): string[] {
  return reachable(view).filter((id) => {
    const el = view.elements[id];
    return CATALOG[el.type] && !parseProps(el.type, el.props).ok;
  });
}

export function Renderer({ ctx }: { ctx: RenderCtx }) {
  const unknown = useMemo(() => collectUnknown(ctx.view), [ctx.view]);
  const invalid = useMemo(() => collectInvalid(ctx.view), [ctx.view]);
  return (
    <Ctx.Provider value={ctx}>
      <Node id={ctx.view.root} />
      <span data-test="unknown-types" data-count={unknown.length} data-types={unknown.join(",")} hidden />
      <span data-test="invalid-props" data-count={invalid.length} data-ids={invalid.join(",")} hidden />
    </Ctx.Provider>
  );
}

export function Node({ id }: { id: string }) {
  const ctx = useCtx();
  const el = ctx.view.elements[id];
  if (!el) return null;
  const Comp = CATALOG[el.type];
  if (!Comp) return null;
  const parsed = parseProps(el.type, el.props);
  if (!parsed.ok) return null;
  let children: ReactNode = null;
  if (el.type === "Screen" || el.type === "Stack") {
    children = (el.children ?? []).map((c) => <Node key={c} id={c} />);
  }
  const isNew = ctx.highlight.has(id);
  return (
    <div className="el" data-id={id} data-type={el.type} data-new={isNew ? "true" : undefined}>
      {isNew ? <span className="new-tag">{ctx.lang === "es" ? "NUEVO" : "NEW"}</span> : null}
      <Comp id={id} props={parsed.data}>
        {children}
      </Comp>
    </div>
  );
}
