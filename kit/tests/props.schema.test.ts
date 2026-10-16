import { describe, expect, it } from "vitest";
import block from "../../contracts/fixtures/block_spec.json";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import schema from "../../contracts/schemas/village_spec.schema.json";
import { CONTRACT_TYPES, parseProps } from "../src/renderer/props";

describe("catalog props", () => {
  for (const [name, spec] of [["reyes", reyes], ["block", block]] as const) {
    it(`every element of ${name}_spec.json parses`, () => {
      const failures: string[] = [];
      for (const [role, view] of Object.entries((spec as any).views)) {
        for (const [id, el] of Object.entries((view as any).elements)) {
          const r = parseProps((el as any).type, (el as any).props);
          if (!r.ok) failures.push(`${role}.${id} (${(el as any).type}): ${r.error}`);
        }
      }
      expect(failures).toEqual([]);
    });
  }

  it("rejects a danger BigButton without confirm", () => {
    expect(parseProps("BigButton", { label: "Help", action: "need_help", tone: "danger" }).ok).toBe(false);
    expect(parseProps("BigButton", { label: "Help", action: "need_help", tone: "danger", confirm: true, confirm_text: "Sure?" }).ok).toBe(true);
  });

  it("rejects unknown props and bad actions", () => {
    expect(parseProps("Text", { text: "x", colour: "red" }).ok).toBe(false);
    expect(parseProps("BigButton", { label: "x", action: "transfer_money" }).ok).toBe(false);
  });

  it("covers every catalog type in the contract", () => {
    expect([...CONTRACT_TYPES].sort()).toEqual([...(schema as any).$defs.catalog_type.enum].sort());
  });
});
