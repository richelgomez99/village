import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import proposal from "../../contracts/schemas/proposal.schema.json";
import { applyViewPatch, viewSchema } from "../src/renderer/view";

const elder = () => viewSchema.parse((reyes as any).views.elder);

describe("applyViewPatch", () => {
  it("applies the fixture proposal ops to the elder view (ScamCheck added, 8 elements)", () => {
    const before = elder();
    const ops = (proposal as any).examples[0].ops.elder;
    const after = applyViewPatch(before, ops);
    expect(Object.keys(after.elements)).toHaveLength(Object.keys(before.elements).length + 1);
    expect(after.elements.scam.type).toBe("ScamCheck");
    expect(after.elements.s.children?.[3]).toBe("scam");
    expect(before.elements.scam).toBeUndefined();
  });

  it("throws on a bad op and leaves the view unchanged", () => {
    const before = elder();
    const snapshot = JSON.stringify(before);
    expect(() => applyViewPatch(before, [{ op: "replace", path: "/elements/nope/props/x", value: 1 }])).toThrow();
    expect(() => applyViewPatch(before, [{ op: "add", path: "/elements/s/children/-", value: "ghost" }])).toThrow();
    expect(JSON.stringify(before)).toBe(snapshot);
  });
});
