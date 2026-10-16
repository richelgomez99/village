import { render } from "@testing-library/react";
import { Renderer } from "../src/renderer/Renderer";
import { defaultCtx, type RenderCtx } from "../src/renderer/context";
import { viewSchema, type View } from "../src/renderer/view";

export function renderView(rawView: unknown, data: Record<string, unknown> = {}, over: Partial<RenderCtx> = {}) {
  const view: View = viewSchema.parse(rawView);
  const ctx: RenderCtx = { ...defaultCtx, view, data, lang: view.lang, ...over };
  return render(
    <div className="app" data-test="app" data-theme={view.theme}>
      <Renderer ctx={ctx} />
    </div>
  );
}

export function unknownCount(container: HTMLElement) {
  return Number(container.querySelector("[data-test='unknown-types']")?.getAttribute("data-count"));
}
