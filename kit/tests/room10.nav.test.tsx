import { act, fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ArcStrip } from "../src/control/regions";
import { BuildSection, RebuildSection, useProposals } from "../src/control/sections";
import { initialScene } from "../src/control/scene";
import reyes from "../../contracts/fixtures/reyes_spec.json";

const scene = () => ({
  ...initialScene("v_reyes"), spec: reyes as any,
  coverage: { value: 7, of: 10 }, gaps: ["pharmacy", "quiet hours"],
  transcript: [{ id: "t1", at: "", who: "village", text: "Who refills the pills?" }, { id: "t2", at: "", who: "ana", text: "Whoever is on duty, Fridays." }],
  blocks: [{ id: "b1", at: "", heard: "Whoever is on duty, Fridays.", knows: "refill day", doing: [], willBuild: [{ person: "Marco", component: "Refill checklist", reason: "he's on duty Friday" }] }]
});

describe("ROOM-10 arc pills navigate", () => {
  it("click selects a section; the live beat stays lit; Anyone still jumps", () => {
    const onJump = vi.fn();
    const { container } = render(<ArcStrip beat="run" selected="rebuild" onJump={onJump} />);
    const pill = (b: string) => container.querySelector<HTMLElement>(`[data-test='arc-beat'][data-beat='${b}']`)!;
    expect(pill("run").className).toContain("lit");
    expect(pill("rebuild").className).toContain("selected");
    expect(pill("rebuild").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(pill("build"));
    expect(onJump).toHaveBeenCalledWith("build");
  });
});

describe("ROOM-10 Build = the intake", () => {
  it("shows Ana's words, coverage, gaps, transcript, will-build, needs; Add a detail posts", async () => {
    const add = vi.fn(async () => ({ accepted: true, next_question: "Which pharmacy?" }));
    const { container } = render(<BuildSection scene={scene()} live={false} onAddDetail={add} />);
    const q = (t: string) => container.querySelector(`[data-test='${t}']`);
    expect(q("intake-description")?.textContent).toContain((reyes as any).blueprint.description.text);
    expect(q("intake-coverage")?.textContent).toBe("7 of 10 covered");
    expect(q("intake-gaps")?.textContent).toContain("pharmacy, quiet hours");
    expect(container.querySelectorAll("[data-test='intake-line']").length).toBe(2);
    expect(q("will-build")?.textContent).toContain("Refill checklist");
    expect(container.querySelectorAll("[data-test='intake-need']").length).toBe((reyes as any).blueprint.needs.length);
    fireEvent.change(q("add-detail-input")!, { target: { value: "Pharmacy is on 37th Ave" } });
    await act(async () => { fireEvent.submit(q("add-detail")!); });
    expect(add).toHaveBeenCalledWith("Pharmacy is on 37th Ave");
    expect(q("add-detail-result")?.textContent).toContain("Which pharmacy?");
  });
  it("says Core's no when the founding is closed", async () => {
    const { container } = render(<BuildSection scene={scene()} live={false} onAddDetail={async () => { throw new Error("404"); }} />);
    fireEvent.change(container.querySelector("[data-test='add-detail-input']")!, { target: { value: "x" } });
    await act(async () => { fireEvent.submit(container.querySelector("[data-test='add-detail']")!); });
    expect(container.querySelector("[data-test='add-detail-result']")?.textContent).toContain("404");
  });
});

const rows = [
  { id: "p1", status: "proposed", title: { en: "Village answers unknown callers" }, rationale: { en: "2nd money request in 30 days" } },
  { id: "p2", status: "applied", title: { en: "Thursday cover" }, approved_by: "m_ana", approved_at: "2026-10-16T18:00:00Z", release_id: "rel_1", target_rev: 8 },
  { id: "p3", status: "rejected", title: { en: "Move the visit" }, rejected_by: "m_ana" }
];
const options = { p1: { candidates: [{ key: "receptionist", name: "Receptionist", what_changes: "Village answers first", reason: "stops the call", chosen: true }, { key: "button", name: "Panic button", reason: "relies on memory" }], reasons: "A button relies on her memory." } };

describe("ROOM-10 Rebuild = suggestions and history", () => {
  it("groups pending / applied / declined, shows what was weighed, decides and suggests through callbacks", async () => {
    const decide = vi.fn(async () => undefined), receipt = vi.fn(), suggest = vi.fn(async () => undefined);
    const { container } = render(<RebuildSection spec={reyes} rows={rows} options={options} error={null} onDecide={decide} onReceipt={receipt} onSuggest={suggest} />);
    const q = (t: string) => container.querySelector<HTMLElement>(`[data-test='${t}']`)!;
    expect(q("pending-proposal").textContent).toContain("unknown callers");
    expect(q("applied-proposal").textContent).toMatch(/approved by Ana/);
    expect(q("declined-proposal").textContent).toContain("declined");
    const opts = container.querySelectorAll<HTMLElement>("[data-test='weighed-option']");
    expect(opts.length).toBe(2);
    expect(opts[0].dataset.chosen).toBe("1");
    await act(async () => { fireEvent.click(q("proposal-approve")); });
    expect(decide).toHaveBeenCalledWith("p1", "approve");
    await act(async () => { fireEvent.click(q("proposal-reject")); });
    expect(decide).toHaveBeenCalledWith("p1", "reject");
    fireEvent.click(q("applied-receipt"));
    expect(receipt).toHaveBeenCalledWith("rel_1");
    fireEvent.change(q("suggest-change-input"), { target: { value: "Marco can't do Thursdays" } });
    await act(async () => { fireEvent.submit(q("suggest-change")); });
    expect(suggest).toHaveBeenCalledWith("Marco can't do Thursdays");
  });
  it("useProposals reads GET /proposals then each proposal's options", async () => {
    const fetchImpl = vi.fn(async (url: string) => ({ ok: true, json: async () => (url.endsWith("/proposals") ? { proposals: [rows[0]] } : { proposal: rows[0], options: options.p1 }) })) as any;
    let out: any = null;
    const cfg = { base: "http://core", token: "control", fake: false, fetchImpl };
    function Probe() { out = useProposals(cfg, "v_w147", 0); return null; }
    render(<Probe />);
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    expect(fetchImpl.mock.calls[0][0]).toBe("http://core/villages/v_w147/proposals");
    expect(out.rows.length).toBe(1);
    expect(out.options.p1.candidates.length).toBe(2);
  });
});
