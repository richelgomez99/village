import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderView, unknownCount } from "./helpers";

describe("Renderer", () => {
  it("renders nothing for unknown types, counts them, and still renders siblings", () => {
    const { container } = renderView({
      lang: "en", theme: "family", root: "s",
      elements: {
        s: { type: "Screen", props: { title: "Home" }, children: ["foo", "t", "bar"] },
        foo: { type: "CustomFoo", props: {} },
        bar: { type: "Marquee", props: {} },
        t: { type: "Text", props: { text: "Still here" } }
      }
    });
    expect(screen.getByText("Still here")).toBeInTheDocument();
    expect(unknownCount(container)).toBe(2);
    expect(container.querySelector("[data-id='foo']")).toBeNull();
    expect(container.querySelector("[data-id='t']")?.getAttribute("data-type")).toBe("Text");
  });

  it("only Screen/Stack render children; invalid props render nothing", () => {
    const { container } = renderView({
      lang: "en", theme: "family", root: "s",
      elements: {
        s: { type: "Screen", props: { title: "Home" }, children: ["h", "bad"] },
        h: { type: "Header", props: { text: "Head" }, children: ["x"] },
        x: { type: "Text", props: { text: "never" } },
        bad: { type: "BigButton", props: { label: "Help", action: "need_help", tone: "danger" } }
      }
    });
    expect(screen.queryByText("never")).toBeNull();
    expect(container.querySelector("[data-id='bad']")).toBeNull();
    expect(container.querySelector("[data-test='invalid-props']")?.getAttribute("data-count")).toBe("1");
  });
});
