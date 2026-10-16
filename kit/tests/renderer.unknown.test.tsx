import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Renderer } from "../src/renderer/Renderer";
import type { View } from "../src/renderer/view";

describe("Renderer", () => {
  it("renders siblings when a component type is unknown and counts it", () => {
    const unknown = new Set<string>();
    const view: View = {
      lang: "en",
      theme: "family",
      root: "s",
      elements: {
        s: { type: "Screen", props: { title: "Root" }, children: ["a", "bad", "b"] },
        a: { type: "Text", props: { text: "Before" } },
        bad: { type: "CustomFoo", props: {} },
        b: { type: "Text", props: { text: "After" } }
      }
    };
    render(<Renderer view={view} data={{}} lang="en" role="helper" send={() => {}} unknown={unknown} />);
    expect(screen.getByText("Before")).toBeInTheDocument();
    expect(screen.getByText("After")).toBeInTheDocument();
    expect(screen.getByTestId("unknown-types")).toHaveAttribute("data-count", "1");
  });
});
