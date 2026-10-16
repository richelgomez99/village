import { describe, expect, it } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { d22Overlay, baseData } from "../src/dev/fixtureData";
import { viewSchema } from "../src/renderer/view";
import { renderView } from "./helpers";
import "../src/theme/floor.css";

describe("elder floor (D8/D17)", () => {
  it("BigButtons ≥ 88px tall with ≥ 28px labels on paper #FBF6EE, read-aloud present", () => {
    const view = d22Overlay(viewSchema.parse((reyes as any).views.elder), "elder");
    const { container } = renderView(view, baseData("carmen"));
    const buttons = Array.from(container.querySelectorAll<HTMLElement>("[data-test='bigbutton']"));
    expect(buttons).toHaveLength(3);
    for (const b of buttons) {
      const st = getComputedStyle(b);
      expect(parseFloat(st.minHeight)).toBeGreaterThanOrEqual(88);
      expect(parseFloat(st.fontSize)).toBeGreaterThanOrEqual(28);
    }
    expect(getComputedStyle(container.querySelector("[data-test='app']")!).backgroundColor).toBe("rgb(251, 246, 238)");
    expect(container.querySelector("[data-test='read-aloud']")).not.toBeNull();
    expect(getComputedStyle(container.querySelector("[data-test='app']")!).fontSize).toBe("22px");
  });

  it("never shows med names on the elder view even if data carries them", () => {
    const view = viewSchema.parse((reyes as any).views.elder);
    const data = { "facts:dose_event?subject=m_carmen&valid_at=today": { date: "2026-10-16", slots: [{ slot: "morning", status: "taken", taken_at: null, via: null, meds: ["lisinopril 10 mg"] }] } };
    const { container } = renderView(view, data);
    expect(container.textContent).not.toContain("lisinopril");
  });
});
