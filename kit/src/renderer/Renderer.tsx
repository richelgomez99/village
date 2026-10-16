import { useLayoutEffect, useRef, useState } from "react";
import type { View } from "./view";
import { Node } from "./catalog";

export interface RenderContext {
  view: View;
  data: Record<string, unknown>;
  lang: string;
  role: string;
  disabled?: boolean;
  highlight?: Set<string>;
  unknown: Set<string>;
  send: (name: string, payload?: Record<string, unknown>, elementId?: string, arg?: unknown) => void;
}

export function Renderer(props: Omit<RenderContext, "unknown"> & { unknown?: Set<string>; onUnknown?: (types: Set<string>) => void }) {
  const fallback = useRef(new Set<string>());
  fallback.current.clear();
  const unknown = props.unknown ?? fallback.current;
  unknown.clear();
  const [types, setTypes] = useState<Set<string>>(new Set());
  const ctx = { ...props, unknown };
  useLayoutEffect(() => {
    const next = new Set(unknown);
    setTypes((prev) => ([...prev].join(",") === [...next].join(",") ? prev : next));
    props.onUnknown?.(next);
  });
  return (
    <>
      <Node id={props.view.root} ctx={ctx} />
      <span data-test="unknown-types" data-count={types.size} data-types={[...types].join(",")} hidden />
    </>
  );
}
