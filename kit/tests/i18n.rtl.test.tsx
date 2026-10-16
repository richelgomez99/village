import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Renderer } from "../src/renderer/Renderer";
import type { View } from "../src/renderer/view";
import "../src/theme/floor.css";

describe("RTL and long labels", () => {
  it("renders long labels without dropping floor size", () => {
    const view: View = {
      lang: "ar",
      dir: "rtl",
      theme: "elder",
      root: "s",
      elements: {
        s: { type: "Screen", props: { title: "مرحبا", read_aloud: true }, children: ["b"] },
        b: { type: "BigButton", props: { label: "هذا نص طويل جدا جدا جدا جدا جدا داخل الزر", action: "call_member", tone: "info", confirm: false } }
      }
    };
    render(<div data-theme="elder" dir="rtl"><Renderer view={view} data={{}} lang="ar" role="elder" send={() => {}} /></div>);
    const button = screen.getByTestId("bigbutton");
    expect(button).toHaveTextContent("هذا نص طويل");
    expect(parseFloat(getComputedStyle(button).minHeight)).toBeGreaterThanOrEqual(88);
  });
});
