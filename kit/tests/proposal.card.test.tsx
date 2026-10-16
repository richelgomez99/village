import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { proposalBlocks } from "../src/components/proposal";
import { Renderer } from "../src/renderer/Renderer";
import { defaultCtx } from "../src/renderer/context";
import { viewSchema } from "../src/renderer/view";
import { renderView } from "./helpers";
import "../src/theme/floor.css";

afterEach(() => vi.useRealTimers());

const NEW = {
  proposal_id: "prop_reyes_receptionist_1",
  title: { en: "Village answers unknown callers for Mamá" },
  rationale: { en: "Two calls in 30 days used Marco's name to ask Mamá for money." },
  changes: [
    { en: "Mamá: unknown callers hear Village first; family rings straight through" },
    { en: "Ana: a card lists the calls Village screened" },
    { en: "Nothing changes for known numbers" },
    { en: "Her rules stay hers: she can turn it off by asking Village" }
  ],
  checked: ["Oct 9 · a caller said he was Marco and asked for $1,500", "Oct 16 · a caller said he was Marco and asked for $2,000"],
  evidence_labels: ["trace 4bf92f3577b34da6", "src=call:conv_demo secs=9"],
  status: "proposed",
  allow_ask_other: true,
  ask_other: "m_marco"
};
const OLD = {
  proposal_id: "prop_old", title: { en: "Village answers unknown callers for Mamá" },
  changes: [{ en: "+ Village answers unknown callers on Mamá's line first" }, { en: "= Nothing changes for known numbers" }],
  evidence_labels: ["Oct 9 call · claimed_member=m_marco", "trace abc", "Oct 16 · call at 0:09 · \"Marco\" asked for $2,000"],
  status: "proposed"
};
const members = { "member:m_marco": { member_id: "m_marco", name: "Marco" }, "member:m_ana": { member_id: "m_ana", name: "Ana" }, "member:m_carmen": { member_id: "m_carmen", name: "Mamá" } };
const coord = (reyes as any).views.coordinator;

describe("Proposal card (INTERACTIONS §3 Options)", () => {
  it("four labelled blocks in order, plain words, names bold, no ids; Approve · Not now · Ask Marco first", () => {
    const send = vi.fn(() => "r");
    const { container } = renderView(coord, { ...members, "proposals:pending": [NEW] }, { send, role: "coordinator" });
    const card = container.querySelector("[data-test='proposals']")!;
    expect(card.querySelector(".card-title")?.textContent).toBe("Village proposes a change · needs your yes");
    const heads = Array.from(card.querySelectorAll(".pb h4")).map((h) => h.textContent);
    expect(heads).toEqual(["What happened", "What changes", "What stays the same", "Village checked"]);
    expect(card.querySelector("[data-test='pb-happened']")?.textContent).toContain("Two calls in 30 days");
    expect(Array.from(card.querySelectorAll("[data-test='pb-changes'] li")).map((l) => l.textContent)).toEqual([
      "Mamá: unknown callers hear Village first; family rings straight through", "Ana: a card lists the calls Village screened"
    ]);
    expect(card.querySelector("[data-test='pb-changes'] li strong")?.textContent).toBe("Mamá");
    expect(card.querySelectorAll("[data-test='pb-stays'] li")).toHaveLength(2);
    const checked = Array.from(card.querySelectorAll("[data-test='pb-checked'] li"));
    expect(checked).toHaveLength(2);
    expect(checked[0].querySelector("svg")).not.toBeNull();
    expect(card.textContent).not.toMatch(/src=|trace|claimed_member|prop_|m_marco/);
    const buttons = Array.from(card.querySelectorAll(".proposal-actions button")).map((b) => b.textContent);
    expect(buttons).toEqual(["Approve", "Not now", "Ask Marco first"]);
    fireEvent.click(card.querySelector("[data-test='proposal-approve']")!);
    expect(send).toHaveBeenLastCalledWith({ name: "approve_proposal", arg: NEW.proposal_id, element_id: "prop" });
  });

  it("old content still reads cleanly: + / = prefixes dropped, id-like evidence filtered, no Ask button", () => {
    const b = proposalBlocks(OLD, "en");
    expect(b.happened).toBe("");
    expect(b.changes).toEqual(["Village answers unknown callers on Mamá's line first"]);
    expect(b.stays).toEqual(["Nothing changes for known numbers"]);
    expect(b.checked).toEqual(["Oct 16 · call at 0:09 · \"Marco\" asked for $2,000"]);
    const { container } = renderView(coord, { "proposals:pending": [OLD] }, { role: "coordinator" });
    expect(container.querySelector("[data-test='pb-happened']")).toBeNull();
    expect(container.querySelector("[data-test='proposal-ask-other']")).toBeNull();
  });

  it("verifying: buttons become the release stepper in words; applied/left: Done · every phone updated for 10 s with Undo", () => {
    vi.useFakeTimers();
    const view = viewSchema.parse(coord);
    const ctx = (data: any) => ({ ...defaultCtx, view, data, lang: "en", role: "coordinator", api: { base: "", token: "", fake: true } });
    const { container, rerender } = render(<div className="app"><Renderer ctx={ctx({ "proposals:pending": [{ ...NEW, status: "verifying", release_stage: "tests" }] })} /></div>);
    expect(container.querySelector("[data-test='proposal-approve']")).toBeNull();
    const steps = Array.from(container.querySelectorAll("[data-test='release-stepper'] li")).map((l) => l.textContent);
    expect(steps).toEqual(["✓ Checking the change", "✓ Building", "Testing…", "Trying it on a phone…", "Scoring…", "Publishing"]);
    // the proposal leaves proposals:pending once applied → done banner with Undo, gone after 10 s
    rerender(<div className="app"><Renderer ctx={ctx({ "proposals:pending": [] })} /></div>);
    expect(container.querySelector("[data-test='proposal-done']")?.textContent).toContain("Done · every phone updated");
    expect(container.querySelector("[data-test='proposal-undo']")).not.toBeNull();
    act(() => { vi.advanceTimersByTime(10_001); });
    expect(container.querySelector("[data-test='proposal-done']")).toBeNull();
  });
});

describe("Control Room proposal frame", () => {
  it("same block order; verifying shows the stepper at the running release stage", async () => {
    const { ProposalRegion } = await import("../src/control/regions");
    const { container } = render(<div className="control"><ProposalRegion proposal={{ ...NEW, status: "verifying" }} release={{ stages: [{ name: "spec", status: "passed" }, { name: "daytona_build", status: "running" }] }} spec={reyes} /></div>);
    expect(Array.from(container.querySelectorAll(".pb h4")).map((h) => h.textContent)).toEqual(["What happened", "What changes", "What stays the same", "Village checked"]);
    // with a receipt, the six tiles name the tool that did each stage
    expect(Array.from(container.querySelectorAll("[data-test='release-tile']")).map((t) => t.getAttribute("data-stage"))).toEqual(["daytona_build"]);
    const { container: c2 } = render(<div className="control"><ProposalRegion proposal={{ ...NEW, status: "verifying" }} release={null} spec={reyes} /></div>);
    expect(c2.querySelector("[data-test='release-stepper']")).not.toBeNull();
    expect(container.textContent).not.toMatch(/src=|trace/);
  });
});
