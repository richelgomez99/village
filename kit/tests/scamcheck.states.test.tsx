import { act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderView } from "./helpers";

const view = {
  lang: "es", theme: "elder", root: "s",
  elements: {
    s: { type: "Screen", props: { title: "Hola" }, children: ["scam"] },
    scam: { type: "ScamCheck", props: { label: "¿Es de verdad?", choices_member_ids: ["m_marco", "m_ana"], other_label: "Otra persona", bind: "verifications:mine", big: true } }
  }
};
const v = (status: string, say: any) => ({ "verifications:mine": { verification_id: "ver_x1", claimed_member_id: "m_marco", claimed_name: "Marco", status, state: status, deadline: "2026-10-16T14:02:54-04:00", say } });

describe("ScamCheck states", () => {
  it("idle → choosing → start_verification with the chosen member", () => {
    const send = vi.fn(() => "r");
    const { container } = renderView(view, { "verifications:mine": null }, { send });
    act(() => container.querySelector<HTMLButtonElement>("[data-test='scam-check']")!.click());
    expect(container.querySelector("[data-state='choosing']")).not.toBeNull();
    act(() => container.querySelector<HTMLButtonElement>("[data-member='m_marco']")!.click());
    expect(send).toHaveBeenCalledWith({ name: "start_verification", arg: "m_marco", element_id: "scam" });
  });

  it.each([
    ["pending", null, "checking", "Confirmando con Marco"],
    ["denied", { es: "Ese no era Marco. No mande dinero.", en: "x" }, "denied", "Ese no era Marco. No mande dinero."],
    ["timeout", { es: "No pudimos confirmar. No mande dinero.", en: "x" }, "timeout", "No pudimos confirmar"],
    ["confirmed", { es: "Marco confirmó.", en: "x" }, "confirmed", "Marco confirmó."]
  ])("%s renders gate text only", (status, say, state, textPart) => {
    const { container } = renderView(view, v(status, say), { nowMs: () => Date.parse("2026-10-16T14:02:20-04:00") });
    const el = container.querySelector(`[data-state='${state}']`)!;
    expect(el.textContent).toContain(textPart);
  });
});
