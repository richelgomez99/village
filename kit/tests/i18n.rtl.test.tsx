import { describe, expect, it } from "vitest";
import { k } from "../src/i18n/strings";
import { renderView } from "./helpers";
import "../src/theme/floor.css";

describe("i18n", () => {
  it("kit strings exist in es and en with fallback", () => {
    expect(k("tonight", "es", { name: "Marco" })).toBe("Esta noche cuida Marco");
    expect(k("tonight", "en", { name: "Marco" })).toBe("Tonight: Marco");
    expect(k("tonight", "zh", { name: "Marco" })).toBe("Tonight: Marco");
  });

  it("long elder labels keep the 88px floor", () => {
    const label = "Necesito ayuda ahora mismo por favor con algo importante hoy".slice(0, 60);
    const { container } = renderView({
      lang: "ar", dir: "rtl", theme: "elder", root: "s",
      elements: { s: { type: "Screen", props: { title: "مرحبا" }, children: ["b"] }, b: { type: "BigButton", props: { label, action: "call_member", action_arg: "m_ana" } } }
    });
    const b = container.querySelector<HTMLElement>("[data-test='bigbutton']")!;
    expect(b.textContent).toContain(label);
    expect(parseFloat(getComputedStyle(b).minHeight)).toBeGreaterThanOrEqual(88);
  });
});
