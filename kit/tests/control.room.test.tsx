import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import block from "../../contracts/fixtures/block_spec.json";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import { BlueprintRegion } from "../src/control/regions";
import { initialScene } from "../src/control/scene";
import type { ApiConfig } from "../src/control/api";
import { makeSocket, type LiveConfig } from "../src/live/useLive";
import { ControlRoom } from "../src/pages/control";
import "../src/theme/floor.css";
import "../src/theme/a.css";

const cfg: LiveConfig = { url: "ws://fake/control", village: "v_reyes", token: "ct_control_offline_demo", client: "control", fake: "control" };
const api: ApiConfig = { base: "", token: "", fake: true };

function mount(search: string, apiCfg: ApiConfig = api) {
  const socket = makeSocket(cfg, search);
  const utils = render(<ControlRoom socket={socket} cfg={cfg} api={apiCfg} />);
  act(() => socket.connect());
  return { socket, ...utils };
}

const q = (c: HTMLElement, sel: string) => c.querySelector<HTMLElement>(sel);
const tick = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

afterEach(() => vi.useRealTimers());

describe("Control Room", () => {
  it("renders header + every region from the control snapshot", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    for (const t of ["cr-header", "tagline", "new-village", "phones-counter", "demo-clock", "blueprint", "ledger", "live-moment", "phones", "gate-feed", "decisions-log", "ask-why", "qr-tile"]) {
      expect(q(container, `[data-test='${t}']`), t).not.toBeNull();
    }
    const tabs = Array.from(container.querySelectorAll("[data-test='village-tab']")).map((t) => t.textContent);
    expect(tabs).toEqual([reyes.village.name, block.village.name]);
    expect(q(container, "[data-test='tagline']")?.textContent).toBe("Village builds an app for each person in a group, runs their week, and rebuilds itself when their life changes.");
  });

  it("phones region renders 3 roles read-only under the shared URL, elder light inside the dark frame", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    const phones = Array.from(container.querySelectorAll<HTMLElement>("[data-test='phone']"));
    expect(phones.map((p) => p.dataset.role)).toEqual(["elder", "coordinator", "helper"]);
    expect(q(container, "[data-test='shared-url']")?.textContent).toBe("village.app/v/reyes · one site · three people");
    for (const p of phones) expect(p.querySelector("[data-test='unknown-types']")?.getAttribute("data-count")).toBe("0");
    const elder = phones[0].querySelector<HTMLElement>(".phone")!;
    expect(getComputedStyle(elder).backgroundColor).toBe("rgb(251, 246, 238)");
    expect(Array.from(phones[0].querySelectorAll<HTMLButtonElement>("[data-test='bigbutton']")).every((b) => b.disabled)).toBe(true);
    expect(phones[1].querySelector("[data-test='refill-card']")).not.toBeNull();
  });

  it("captions: every Spanish node on the elder mirror has its English line under it (D18)", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    const elder = q(container, "[data-test='phone'][data-role='elder']")!;
    const spoken = Array.from(elder.querySelectorAll<HTMLElement>("[data-say]")).filter((n) => n.textContent?.trim());
    expect(spoken.length).toBeGreaterThanOrEqual(5);
    for (const n of spoken) {
      const cap = n.nextElementSibling;
      expect(cap?.getAttribute("data-test"), n.textContent!).toBe("caption");
      expect(cap?.textContent?.length).toBeGreaterThan(0);
    }
    expect(elder.textContent).toContain("Call Village");
    expect(elder.textContent).toContain("I need help");
  });

  it("scam replay: gate rows newest first, mode counts, live ring then collapse, captions layer, counter follows frames", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(10);
    expect(q(container, "[data-test='phones-counter']")?.dataset.count).toBe("4");
    expect(container.querySelectorAll("[data-test='phone-dot']")).toHaveLength(4);
    await tick(2000);
    const live = q(container, "[data-test='live-moment']")!;
    expect(live.dataset.state).toBe("pending");
    expect(q(container, "[data-test='countdown-ring']")).not.toBeNull();
    expect(live.querySelector("[data-test='caption']")?.textContent).toContain("Marco called me crying");
    await tick(15000);
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
    expect(q(container, "[data-test='countdown-ring']")).toBeNull();
    expect(q(container, "[data-test='live-outcome']")?.textContent).toContain("Scam stopped");
    const rules = Array.from(container.querySelectorAll<HTMLElement>("[data-test='gate-row']")).map((r) => r.dataset.rule);
    expect(rules).toEqual(["R-MONEY-DEFAULT", "R-MONEY-VERIFY"]);
    expect(q(container, "[data-test='count-refused']")?.dataset.count).toBe("1");
    expect(Number(q(container, "[data-test='count-asked_human']")?.dataset.count)).toBeGreaterThanOrEqual(1);
    const layer = q(container, "[data-test='captions-layer']")!;
    for (const line of Array.from(layer.querySelectorAll("[data-test='caption-line']"))) {
      if (line.querySelector("[lang='es']")) expect(line.querySelector("[data-test='caption']")).not.toBeNull();
    }
    // Spanish gate say on the feed carries English
    const say = q(container, "[data-test='gate-row'] .say")!;
    expect(say.querySelector("[data-test='caption']")?.textContent).toContain("Don't send any money");
  });

  it("founding replay fills the ledger with Founder rows and the counter ticks up", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=founding");
    await tick(10);
    expect(q(container, "[data-test='founding-empty']")?.textContent).toBe("No village yet. Describe your people.");
    await tick(40000);
    const rows = Array.from(container.querySelectorAll<HTMLElement>("[data-test='ledger-row']"));
    expect(rows.length).toBeGreaterThanOrEqual(8);
    expect(rows.every((r) => ["queued", "running", "done", "retrying", "fallback", "refused"].includes(r.dataset.status!))).toBe(true);
    expect(rows.some((r) => r.textContent?.includes("DailyMed: apixaban"))).toBe(true);
    expect(q(container, "[data-test='phones-counter']")?.dataset.count).toBe("4");
    // the founding finished: the spec arrived and the room switched to the live layout
    expect(q(container, "[data-test='control']")?.dataset.mode).toBe("live");
  });

  it("ask why: empty question ignored, disabled in flight, answer + citation chips", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    const btn = q(container, "[data-test='ask-submit']") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(q(container, "[data-test='ask-input']")!, { target: { value: "Why did you call Marco?" } });
    expect(btn.disabled).toBe(false);
    act(() => btn.click());
    expect((q(container, "[data-test='ask-submit']") as HTMLButtonElement).disabled).toBe(true);
    expect(q(container, "[data-test='ask-busy']")).not.toBeNull();
    await tick(500);
    expect(q(container, "[data-test='ask-answer']")?.textContent).toContain("Marco agreed to calls");
    expect(container.querySelectorAll("[data-test='citation']").length).toBe(3);
  });

  it("ask why against Core: posts the contract body; failure shows plain words", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn(async () => new Response("{}", { status: 503 }));
    const { container } = mount("?start=off", { base: "http://core", token: "ct_x", fake: false, fetchImpl: fetchImpl as any });
    await tick(10);
    fireEvent.change(q(container, "[data-test='ask-input']")!, { target: { value: "why?" } });
    await act(async () => { q(container, "[data-test='ask-submit']")!.click(); });
    await tick(10);
    const askCall = (fetchImpl.mock.calls as any[]).find((c) => String(c[0]).endsWith("/villages/v_reyes/ask"))!;
    expect(JSON.parse(askCall[1].body)).toEqual({ question: "why?", lang: "en" });
    expect(askCall[1].headers.Authorization).toBe("Bearer ct_x");
    expect(q(container, "[data-test='ask-error']")?.textContent).toContain("Core didn't reply");
    expect(q(container, "[data-test='qr-empty']")).not.toBeNull();
  });

  it("phone mirrors are labelled from the member record with a join QR under each; Be Marco highlighted sage", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    const labels = Array.from(container.querySelectorAll("[data-test='phone-label']")).map((l) => l.textContent);
    expect(labels).toEqual(["Carmen's phone · right now", "Ana's phone", "Marco's phone"]);
    const tiles = Array.from(container.querySelectorAll<HTMLElement>("[data-test='phone'] [data-test='qr-tile']"));
    expect(tiles.map((t) => t.dataset.member)).toEqual(["m_carmen", "m_ana", "m_marco"]);
    expect(tiles[2].className).toContain("sage");
    expect(tiles[2].textContent).toContain("Be Marco");
    expect(tiles[0].className).not.toContain("sage");
    expect(tiles[2].querySelector("svg")).not.toBeNull();
  });

  it("switching village re-keys every region: the Reyes scam never shows under West 147th", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=denied");
    await tick(17000);
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
    expect(q(container, "[data-test='captions-layer']")).not.toBeNull();
    act(() => q(container, "[data-test='village-tab'][data-village='v_w147']")!.click());
    await tick(10);
    expect(q(container, "[data-test='control']")?.dataset.village).toBe("v_w147");
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("idle");
    expect(container.querySelectorAll("[data-test='ledger-row']")).toHaveLength(0);
    expect(container.querySelectorAll("[data-test='gate-row']")).toHaveLength(0);
    expect(container.querySelectorAll("[data-test='decision-row']")).toHaveLength(0);
    expect(q(container, "[data-test='captions-layer']")).toBeNull();
    expect(q(container, "[data-test='phones-counter']")?.dataset.count).toBe("0");
    expect(container.textContent).not.toMatch(/Carmen|Marco/);
    // back to Reyes: its scene is rebuilt from the socket's own frames
    act(() => q(container, "[data-test='village-tab'][data-village='v_reyes']")!.click());
    await tick(10);
    expect(q(container, "[data-test='live-moment']")!.dataset.state).toBe("denied");
  });

  it("live headline uses the proper-cased member name", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam&tail=timeout");
    await tick(60000);
    const out = q(container, "[data-test='live-outcome']")?.textContent ?? "";
    expect(out).toContain("No answer from Marco");
    expect(out).not.toContain("marco");
  });

  it("captions bar pads the room so it never covers the last safety rule", async () => {
    vi.useFakeTimers();
    const { container } = mount("?seq=scam");
    await tick(1000);
    expect(q(container, "[data-test='captions-layer']")).not.toBeNull();
    expect(parseInt(q(container, "[data-test='control']")!.style.paddingBottom)).toBeGreaterThanOrEqual(32);
  });

  it("New village opens the founding empty state and posts the description to POST /villages", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn(async (url: string) => new Response(JSON.stringify(String(url).endsWith("/villages") ? { village_id: "v_x", ws_url: "/ws" } : []), { status: 202 }));
    const spawn = vi.fn((o: any) => makeSocket({ ...cfg, village: o.village }, "", { fakeOverrides: { start: "off", seq: o.founding ? "founding" : null, quiet: true } }));
    const socket = makeSocket(cfg, "?start=off");
    const { container } = render(<ControlRoom socket={socket} cfg={cfg} api={{ base: "http://core", token: "ct", fake: false, fetchImpl: fetchImpl as any }} spawn={spawn} villages={["v_reyes"]} />);
    act(() => socket.connect());
    await tick(10);
    act(() => q(container, "[data-test='new-village']")!.click());
    expect(q(container, "[data-test='founding-empty']")?.textContent).toBe("No village yet. Describe your people.");
    fireEvent.change(q(container, "[data-test='founding-input']")!, { target: { value: "My dad lives alone." } });
    await act(async () => { q(container, "[data-test='founding-submit']")!.click(); });
    await tick(10);
    const post = (fetchImpl.mock.calls as any[]).find((c) => String(c[0]) === "http://core/villages")!;
    expect(JSON.parse(post[1].body)).toMatchObject({ description: "My dad lives alone." });
    expect(spawn).toHaveBeenCalledWith(expect.objectContaining({ village: "v_x", founding: true }));
    expect(q(container, "[data-test='control']")?.dataset.village).toBe("v_x");
    expect(q(container, "[data-test='control']")?.dataset.mode).toBe("founding");
    // the founding replay fills transcript, ledger and the coverage meter
    await tick(4000);
    expect(container.querySelectorAll("[data-test='transcript-line']").length).toBeGreaterThan(2);
    expect(q(container, "[data-test='coverage']")?.textContent).toMatch(/\d+ of 10 covered · \d+ gaps/);
    expect(container.querySelectorAll("[data-test='gap']").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("[data-test='phone-skeleton']").length).toBeGreaterThan(0);
  });

  it("view as Carmen morphs the elder phone into her live snapshot, others dim", async () => {
    vi.useFakeTimers();
    const { container } = mount("?start=off");
    await tick(10);
    act(() => q(container, "[data-test='view-as-option'][data-member='m_carmen']")!.click());
    await tick(10);
    expect(q(container, "[data-test='phones']")?.dataset.viewAs).toBe("m_carmen");
    expect(q(container, "[data-test='phone'][data-role='elder']")?.className).toContain("focused");
    expect(q(container, "[data-test='phone'][data-role='helper']")?.className).toContain("dim");
    expect(q(container, "[data-test='phone'][data-role='elder'] [data-test='tonight-card']")?.textContent).toContain("Esta noche cuida Marco");
  });

  it("village tab switches to West 147th without reconnecting the main socket", async () => {
    vi.useFakeTimers();
    const { container, socket } = mount("?start=off");
    await tick(10);
    act(() => q(container, "[data-test='village-tab'][data-village='v_w147']")!.click());
    await tick(10);
    expect(q(container, "[data-test='blueprint']")?.dataset.village).toBe("v_w147");
    expect(Array.from(container.querySelectorAll<HTMLElement>("[data-test='phone']")).map((p) => p.dataset.role)).toEqual(["coordinator", "resident", "volunteer"]);
    expect(socket.state.status).toBe("live");
  });
});

describe("Blueprint region", () => {
  it.each([
    ["reyes", reyes, ["Carmen", "Ana", "Marco", "Lucía"], "family · aging parent at home"],
    ["block", block, ["Tanya Brooks", "Mrs. Gloria Alvarez", "Mr. Wei Chen", "The Okafor family (Ngozi & Daniel)", "Darnell Price"], "block · neighbors in an emergency"]
  ])("renders %s_spec.json without code changes", (_n, spec: any, firstNames, kind) => {
    const { container } = render(<div className="control"><BlueprintRegion spec={spec} scene={initialScene(spec.village.id)} /></div>);
    const people = Array.from(container.querySelectorAll("[data-test='bp-person'] .person-name")).map((n) => n.textContent);
    for (const n of firstNames) expect(people).toContain(n);
    expect(people).toHaveLength(spec.blueprint.people.length);
    expect(container.querySelector("[data-test='group-type']")?.textContent).toContain(kind);
    expect(container.querySelectorAll("[data-test='bp-area']")).toHaveLength(spec.blueprint.life_areas.length);
    expect(container.querySelectorAll("[data-test='quote-highlight']").length).toBeGreaterThanOrEqual(3);
    expect(container.querySelectorAll("[data-test='bp-channel']").length).toBeGreaterThan(0);
    expect(container.querySelector("[data-test='bp-rules']")).not.toBeNull();
  });

  it("shows plain-words empty state with no spec", () => {
    const { container } = render(<BlueprintRegion spec={null} scene={initialScene()} />);
    expect(container.querySelector("[data-test='blueprint-empty']")?.textContent).toMatch(/^Nothing heard yet/);
  });
});
