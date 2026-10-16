import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { Renderer } from "../src/renderer/Renderer";
import { normalizeReyesView, viewSchema } from "../src/renderer/view";
import "../src/theme/floor.css";

describe("elder floor", () => {
  it("keeps BigButtons large on the elder surface", () => {
    const view = normalizeReyesView(viewSchema.parse((reyes as any).views.elder), "elder");
    render(<div data-test="app" data-theme="elder" style={{ backgroundColor: "#FBF6EE" }}><Renderer view={view} data={{ "alerts:active": [] }} lang="es" role="elder" send={() => {}} /></div>);
    const button = screen.getAllByTestId("bigbutton")[0];
    const style = getComputedStyle(button);
    expect(parseFloat(style.minHeight)).toBeGreaterThanOrEqual(88);
    expect(Number(button.getAttribute("data-font-floor"))).toBeGreaterThanOrEqual(28);
    expect(getComputedStyle(document.querySelector("[data-test='app']")!).backgroundColor).toBe("rgb(251, 246, 238)");
  });
});
