import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Header, resolveAs } from "../src/control/regions";
import reyes from "../../contracts/fixtures/reyes_spec.json";
import block from "../../contracts/fixtures/block_spec.json";

describe("ROOM-9 ?as=<member>: the room belongs to a person", () => {
  it("names the owner and her role per village, from the specs; no ?as= changes nothing", () => {
    const people = { v_reyes: (reyes as any).blueprint.people, v_w147: (block as any).blueprint.people };
    const coord = people.v_reyes.find((p: any) => p.role === "coordinator");
    const me = resolveAs(coord.id, people)!;
    expect(me.first).toBe(String(coord.name).split(" ")[0]);
    expect(me.roles.v_reyes).toBe("you coordinate");
    // a name match in another village with a different id still resolves; a non-member gets no words
    const other = { ...people, v_x: [{ id: "m_other", name: `${me.first} Smith`, role: "volunteer" }], v_none: [{ id: "m_z", name: "Zed Q", role: "helper" }] };
    const r2 = resolveAs(coord.id, other)!;
    expect(r2.roles.v_x).toBe("you volunteer");
    expect(r2.roles.v_none).toBeUndefined();
    expect(resolveAs(null, people)).toBeNull();
    expect(resolveAs("m_nobody", people)).toBeNull();

    const tabs = [{ id: "v_reyes", label: "Familia Reyes", role: me.roles.v_reyes }, { id: "v_w147", label: "Block" }];
    const base = { tab: "v_reyes", onTab: () => {}, onNew: () => {}, phones: 0, clock: null, nowMs: () => 0, onWarp: () => {}, warpState: "idle" as const };
    const { container, rerender } = render(<Header {...base} tabs={tabs} owner={me.first} />);
    expect(container.querySelector("[data-test='brand']")?.textContent).toBe(`${me.first}'s villages`);
    const roles = Array.from(container.querySelectorAll("[data-test='tab-role']")).map((e) => e.textContent);
    expect(roles).toEqual([" · you coordinate"]);
    rerender(<Header {...base} tabs={[{ id: "v_reyes", label: "Familia Reyes" }]} />);
    expect(container.querySelector("[data-test='brand']")?.textContent).toBe("Village");
    expect(container.querySelector("[data-test='tab-role']")).toBeNull();
  });
});
