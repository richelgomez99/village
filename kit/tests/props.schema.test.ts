import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import block from "../../contracts/fixtures/block_spec.json";
import { parseProps } from "../src/renderer/props";

describe("props schemas", () => {
  it("parses every fixture element", () => {
    for (const fixture of [reyes, block] as any[]) {
      for (const view of Object.values(fixture.views) as any[]) {
        for (const element of Object.values(view.elements) as any[]) {
          expect(parseProps(element.type, element.props), element.type).not.toBeNull();
        }
      }
    }
  });

  it("rejects danger BigButton without confirmation", () => {
    expect(parseProps("BigButton", { label: "Help", tone: "danger", action: "need_help" })).toBeNull();
  });
});
