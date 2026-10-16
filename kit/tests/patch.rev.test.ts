import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { applyViewPatch, viewSchema } from "../src/renderer/view";

describe("applyViewPatch", () => {
  it("applies valid RFC6902 patches to a clone", () => {
    const view = viewSchema.parse((reyes as any).views.elder);
    const next = applyViewPatch(view, [
      { op: "add", path: "/elements/scam", value: { type: "ScamCheck", props: { label: "¿Es de verdad?", choices_member_ids: ["m_marco"], bind: "verifications:mine" } } },
      { op: "add", path: "/elements/s/children/6", value: "scam" }
    ]);
    expect(Object.keys(next.elements)).toHaveLength(8);
    expect(view.elements.scam).toBeUndefined();
  });

  it("throws on bad paths and leaves the source unchanged", () => {
    const view = viewSchema.parse((reyes as any).views.elder);
    expect(() => applyViewPatch(view, [{ op: "replace", path: "/elements/nope/type", value: "Text" }])).toThrow();
    expect(view.elements.s.type).toBe("Screen");
  });
});
