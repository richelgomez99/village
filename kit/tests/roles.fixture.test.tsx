import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { MemberApp } from "../src/app/MemberApp";
import { makeSocket } from "../src/live/useLive";
import "../src/theme/floor.css";
import { makePhoneFor } from "../src/renderer/context";
import { renderView } from "./helpers";

function mount(fake: string, search = "?start=off") {
  const socket = makeSocket({ url: `ws://fake/${fake}`, village: "v_reyes", token: `mt_${fake}_offline_demo`, client: "kit", fake }, search);
  const utils = render(<MemberApp socket={socket} />);
  act(() => socket.connect());
  return { socket, ...utils };
}

afterEach(() => vi.useRealTimers());

describe("fixture roles via the fake server", () => {
  it.each([
    ["carmen", "elder"],
    ["ana", "coordinator"],
    ["marco", "helper"]
  ])("%s renders the %s view with unknown-types=0", async (fake, role) => {
    vi.useFakeTimers();
    const { container } = mount(fake);
    await act(async () => { vi.advanceTimersByTime(10); });
    const app = container.querySelector("[data-test='app']")!;
    expect(app.getAttribute("data-role")).toBe(role);
    expect(container.querySelector("[data-test='unknown-types']")?.getAttribute("data-count")).toBe("0");
    expect(container.querySelector("[data-test='invalid-props']")?.getAttribute("data-count")).toBe("0");
    expect(container.querySelector("[data-test='identity-chip']")).not.toBeNull();
    if (role !== "elder") {
      for (const id of Object.keys((reyes as any).views[role].elements)) {
        expect(container.querySelector(`[data-id='${id}']`), id).not.toBeNull();
      }
      expect(container.querySelector("[data-test='refill-card']")).not.toBeNull();
    }
  });

  it("carmen: 3 big buttons + 911 + Esta noche cuida Marco", async () => {
    vi.useFakeTimers();
    const { container } = mount("carmen");
    await act(async () => { vi.advanceTimersByTime(10); });
    const labels = Array.from(container.querySelectorAll("[data-test='bigbutton']")).map((b) => b.textContent);
    expect(labels).toEqual(["Llamar a Village", "Llamar a Ana", "Necesito ayuda"]);
    expect(container.querySelector("[data-test='contact-card'][data-kind='emergency']")?.getAttribute("href")).toBe("tel:911");
    expect(container.querySelector("[data-test='tonight-card']")?.textContent).toContain("Esta noche cuida Marco");
    expect(container.querySelector("[data-test='identity-chip']")?.textContent).toBe("Eres Carmen · Familia Reyes");
  });

  it("refill card shows lisinopril 10 mg with the superseded 5 mg struck through", async () => {
    vi.useFakeTimers();
    const { container } = mount("marco");
    await act(async () => { vi.advanceTimersByTime(10); });
    const card = container.querySelector("[data-test='refill-card']")!;
    expect(card.textContent).toContain("Refill checklist");
    expect(card.textContent).toContain("Friday refill · Marco");
    expect(card.textContent).toContain("lisinopril 10 mg (changed Oct 3, Dr. Park; was 5 mg)");
    expect(card.querySelectorAll("[data-test='refill-item']")).toHaveLength(4);
    expect(card.querySelector("s[data-test='refill-superseded']")?.textContent).toBe("5 mg");
  });

  it("danger button opens a confirm sheet before sending", async () => {
    vi.useFakeTimers();
    const { container } = mount("carmen");
    await act(async () => { vi.advanceTimersByTime(10); });
    (window as any).__frames = [];
    const help = container.querySelector<HTMLButtonElement>("[data-action='need_help']")!;
    act(() => help.click());
    expect(container.querySelector("[data-test='confirm-sheet']")).not.toBeNull();
    expect((window as any).__frames.filter((f: any) => f.type === "action")).toHaveLength(0);
    act(() => container.querySelector<HTMLButtonElement>("[data-test='confirm-yes']")!.click());
    expect((window as any).__frames.filter((f: any) => f.type === "action")[0]).toMatchObject({ name: "need_help", element_id: "b_help" });
  });
});

describe("call affordances are real tel: links (iOS Safari)", () => {
  it("marco: Call Mamá is <a href=tel:> with Carmen's number from her member record", async () => {
    vi.useFakeTimers();
    const { container } = mount("marco");
    await act(async () => { vi.advanceTimersByTime(10); });
    const call = container.querySelector<HTMLAnchorElement>("[data-action='call_member']")!;
    expect(call.tagName).toBe("A");
    expect(call.getAttribute("href")).toBe("tel:+18482579221");
  });

  it("carmen: Llamar a Village + Llamar a Ana + 911 are tel: anchors", async () => {
    vi.useFakeTimers();
    const { container } = mount("carmen");
    await act(async () => { vi.advanceTimersByTime(10); });
    expect(container.querySelector("[data-action='call_number']")?.getAttribute("href")).toBe("tel:+18482579221");
    expect(container.querySelector("[data-action='call_member']")?.getAttribute("href")).toBe("tel:+15555550102");
    expect(container.querySelector("[data-test='contact-card'][data-kind='emergency']")?.getAttribute("href")).toBe("tel:911");
  });

  it("a missing number renders a disabled button that says so", () => {
    const view = { lang: "en", theme: "family", root: "s", elements: { s: { type: "Screen", props: { title: "x" }, children: ["b"] }, b: { type: "BigButton", props: { label: "Call Lee", action: "call_member", action_arg: "m_lee" } } } };
    const { container } = renderView(view, {}, { phoneFor: makePhoneFor({}) });
    const b = container.querySelector<HTMLButtonElement>("[data-action='call_member']")!;
    expect(b.tagName).toBe("BUTTON");
    expect(b.disabled).toBe(true);
    expect(b.textContent).toContain("no number");
  });
});
