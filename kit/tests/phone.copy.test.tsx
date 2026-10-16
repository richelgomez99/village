import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { MemberApp } from "../src/app/MemberApp";
import { authorName, oneLine } from "../src/components/generic";
import { plural } from "../src/i18n/plural";
import { makeSocket } from "../src/live/useLive";
import { renderView } from "./helpers";
import "../src/theme/floor.css";

afterEach(() => vi.useRealTimers());

const WALL = "Village proposes answering unknown callers for Mamá first. Options weighed: a ¿Es de verdad? button (relies on her remembering), blocking unknown numbers (blocks the pharmacy), a receptionist (checks before she picks up). Chosen: the receptionist, because it works before the call reaches her. Evidence: 2 calls in 30 days.";
const card = { proposal_id: "prop_reyes_receptionist_1", title: { en: "Village answers unknown callers for Mamá" }, changes: [{ en: "+ Village answers unknown callers first" }], evidence_labels: ["Oct 9 call", "Oct 16 call"], status: "proposed" };
const chat = [
  { id: "msg_1", village: "v_reyes", author: "m_marco", kind: "member", text: "I'm on tonight.", refs: [], source: { kind: "app", ref: "m_marco" }, at: "2026-10-16T14:00:00-04:00" },
  { id: "msg_2", village: "v_reyes", author: "village", kind: "proposal", text: WALL, refs: [{ kind: "proposal", id: card.proposal_id, label: "proposal" }], source: { kind: "system", ref: "evolve" }, at: "2026-10-16T14:01:00-04:00" }
];

describe("family-phone copy (DEMO-NOTES)", () => {
  it("chat shows member names, never raw ids; Village for village posts", () => {
    const { container } = renderView((reyes as any).views.coordinator, { "chat:village": chat, "proposals:pending": [card], "member:m_marco": { member_id: "m_marco", name: "Marco" } }, { role: "coordinator" });
    const authors = Array.from(container.querySelectorAll("[data-test='chat-author']")).map((a) => a.textContent);
    expect(authors).toEqual(["Marco", "Village"]);
    expect(container.querySelector("[data-test='village-chat']")?.textContent).not.toContain("m_marco");
    expect(authorName("m_lucia", {})).toBe("Lucia");
  });

  it("a proposal post is title + one line + Approve · Not now; the details live on the Proposal card", () => {
    const { container } = renderView((reyes as any).views.coordinator, { "chat:village": chat, "proposals:pending": [card] }, { role: "coordinator" });
    const post = container.querySelector("[data-test='chat-proposal']")!;
    expect(post.textContent).toBe("Village answers unknown callers for MamáVillage proposes answering unknown callers for Mamá first.");
    expect(post.textContent).not.toContain("Options weighed");
    expect(container.querySelector("[data-test='chat-proposal-approve']")).not.toBeNull();
    expect(container.querySelector("[data-test='proposal'] [data-test='pb-changes']")?.textContent).toContain("Village answers unknown callers first");
    expect(oneLine("x".repeat(200))).toHaveLength(141); // 140 + "…" (no word boundary to cut at)
    expect(oneLine(`${"word ".repeat(40)}end`)).toMatch(/word…$/); // never mid-word
  });

  it("family phones show no rule ids; life areas are plain words", async () => {
    vi.useFakeTimers();
    for (const who of ["ana", "marco"]) {
      const socket = makeSocket({ url: `ws://fake/${who}`, village: "v_reyes", token: `mt_${who}_offline_demo`, client: "kit", fake: who }, "?start=off");
      const { container, unmount } = render(<MemberApp socket={socket} />);
      act(() => socket.connect());
      await act(async () => { vi.advanceTimersByTime(10); });
      expect(container.textContent).not.toMatch(/\b[RP]-[A-Z0-9]+(-[A-Z0-9]+)*\b/);
      if (who === "ana") {
        const lines = Array.from(container.querySelectorAll("[data-test='life-area-status']")).map((l) => l.textContent);
        expect(lines).toContain("Money: 1 scam stopped · Marco checks money calls");
        expect(lines).toContain("Pills: morning pills taken · refill Friday · Marco");
      }
      expect(container.textContent).not.toMatch(/\blids?\b|scanned/i);
      unmount();
    }
  });

  it("counts agree with their noun", () => {
    expect(plural(1, "call")).toBe("1 call");
    expect(plural(2, "call")).toBe("2 calls");
    expect(plural(0, "gap")).toBe("0 gaps");
  });
});
