import { act, fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JoinPage } from "../src/pages/join";

describe("join page", () => {
  it("disables submit without a name; redeems and stores the token", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ member_token: "mt_marco_9Qe2vLx7Rk3pZ0aB" }), { status: 200 }));
    const go = vi.fn();
    const { container } = render(<JoinPage search="" hash="#i=inv_abc123" fetchImpl={fetchImpl as any} go={go} />);
    const submit = container.querySelector<HTMLButtonElement>("[data-test='join-submit']")!;
    expect(submit.disabled).toBe(true);
    fireEvent.change(container.querySelector("[data-test='join-name']")!, { target: { value: "Marco" } });
    fireEvent.click(container.querySelector("[data-test='join-consent']")!);
    await act(async () => { fireEvent.submit(container.querySelector("form")!); });
    const body = JSON.parse((fetchImpl.mock.calls[0] as any)[1].body);
    expect(body).toEqual({ invite: "inv_abc123", first_name: "Marco", consent: { ai_calls: true, text_version: "join_v1" } });
        expect(go).toHaveBeenCalledWith("./");
  });

  it("fake mode goes straight to the fake app", async () => {
    const go = vi.fn();
    const { container } = render(<JoinPage search="?fake=marco" hash="" go={go} />);
    await act(async () => { fireEvent.submit(container.querySelector("form")!); });
    expect(go).toHaveBeenCalledWith("./?fake=marco");
  });
});
