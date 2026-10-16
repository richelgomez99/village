// KIT-MEMBERS-5: Marco / Lucía homes answer "is it me?" with one-tap Done / Can't, and suggest other ways to help from data only.
import { describe, expect, it, vi } from "vitest";
import { act } from "@testing-library/react";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { renderView } from "./helpers";
import { helpSuggestions } from "../src/components/help";

const NOW = Date.parse("2026-10-14T12:00:00-04:00");
const week = [
  { date: "2026-10-14", on_duty: "m_ana" }, { date: "2026-10-15", on_duty: "m_ana" }, { date: "2026-10-16", on_duty: "m_marco" },
  { date: "2026-10-17", on_duty: null }, { date: "2026-10-18", on_duty: "m_ana" }
];

describe("Other ways you could help", () => {
  it("open plan items, nobody-on nights and an uneven week; nothing invented when the data has none", () => {
    const s = helpSuggestions({ "rota:week": week, "plan:thanksgiving": { items: [{ id: "pi_pie", text: "Bring the pie", status: "open" }, { id: "pi_turkey", text: "Turkey", owner: "m_marco" }] }, "member:m_ana": { name: "Ana" } }, "m_marco", NOW);
    expect(s.map((x) => x.text)).toEqual(["Bring the pie", "Saturday: nobody on yet", "Ana has 3 of the nights left this week · take Thursday?"]);
    expect(s[0].claim).toBe("pi_pie");
    expect(helpSuggestions({ "rota:week": week.map((d) => ({ ...d, on_duty: d.on_duty ?? "m_marco" })).slice(2) }, "m_marco", NOW)).toEqual([]);
  });
  it("remote-only drops on-site items", () => {
    const s = helpSuggestions({ "plan:x": { items: [{ id: "a", text: "Pick up at the station", kind: "pickup", status: "open" }, { id: "b", text: "Call the pharmacy", kind: "call", status: "open" }] } }, "m_lucia", NOW, { remoteOnly: true });
    expect(s.map((x) => x.claim)).toEqual(["b"]);
  });
});

describe("Your turn: Done / Can't", () => {
  it("on my night, two one-tap answers that go to the chat (D39)", () => {
    const openChat = vi.fn();
    const { container } = renderView((reyes as any).views.helper, { "rota:current?member=me": { is_my_turn: true, date: "2026-10-16", next_shift: null, answer: { en: "Yes. Tonight." } } }, { memberId: "m_marco", openChat });
    act(() => (container.querySelector("[data-test='turn-cant']") as HTMLButtonElement).click());
    expect(openChat).toHaveBeenCalledWith(expect.stringMatching(/^@Village I can't do .*can someone cover\?$/), { send: true });
    expect(container.querySelector("[data-test='turn-done']")).not.toBeNull();
  });
});
