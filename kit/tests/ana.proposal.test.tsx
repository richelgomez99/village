import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { renderView, unknownCount } from "./helpers";

const card = {
  proposal_id: "prop_reyes_receptionist_1",
  title: { en: "Village answers unknown callers for Mamá", es: "Village contesta a desconocidos por Mamá" },
  changes: [{ en: "+ Village answers unknown callers on Mamá's line first", es: "+ Village contesta primero" }],
  evidence_labels: ["Call 1: 'Soy Marco'", "Call 2"],
  status: "proposed"
};
const chat = [
  { id: "msg_1", village: "v_reyes", author: "village", kind: "proposal", text: "Village proposes a change · needs your yes.", refs: [{ kind: "proposal", id: card.proposal_id, label: "proposal" }], source: { kind: "system", ref: "evolve" }, at: "2026-10-16T14:00:00-04:00" }
];

describe("Ana's coordinator view: Proposal card + VillageChat inline approve", () => {
  it("renders bv_proposal and sends approve_proposal / reject_proposal with arg = proposal_id", () => {
    const send = vi.fn(() => "rq_1");
    const { container } = renderView((reyes as any).views.coordinator, { "proposals:pending": [card], "chat:village": chat }, { send, role: "coordinator" });
    expect(unknownCount(container)).toBe(0);
    expect(container.querySelector("[data-test='invalid-props']")?.getAttribute("data-count")).toBe("0");
    const prop = container.querySelector("[data-test='proposal']")!;
    expect(prop.textContent).toContain("Village answers unknown callers for Mamá");
    expect(prop.textContent).toContain("Call 1");
    fireEvent.click(prop.querySelector("[data-test='proposal-approve']")!);
    expect(send).toHaveBeenLastCalledWith({ name: "approve_proposal", arg: card.proposal_id, element_id: "prop" });
    fireEvent.click(container.querySelector("[data-test='chat-proposal-approve']")!);
    expect(send).toHaveBeenLastCalledWith({ name: "approve_proposal", arg: card.proposal_id, element_id: "chat" });
    fireEvent.click(container.querySelector("[data-test='chat-proposal-reject']")!);
    expect(send).toHaveBeenLastCalledWith({ name: "reject_proposal", arg: card.proposal_id, element_id: "chat" });
  });

  it("chat drops the buttons once the proposal leaves proposals:pending; helper chat never shows them", () => {
    const { container } = renderView((reyes as any).views.coordinator, { "proposals:pending": [], "chat:village": chat }, { role: "coordinator" });
    expect(container.querySelector("[data-test='proposal']")).toBeNull();
    expect(container.querySelector("[data-test='chat-proposal-approve']")).toBeNull();
    const helper = renderView((reyes as any).views.helper, { "chat:village": chat });
    expect(helper.container.querySelector("[data-test='village-chat']")).not.toBeNull();
    expect(helper.container.querySelector("[data-test='chat-proposal-approve']")).toBeNull();
  });
});
