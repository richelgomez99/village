"""V4 evolve acceptance over real sockets against a running Core.

usage: uv run python acceptance/v4_flow.py --url http://127.0.0.1:8793 [--village v_reyes] [--timeout 120]
  1. sockets: control + elder + coordinator + helper (tokens from the spec's people)
  2. today's scam call (report_money_request) -> claimed member answers no -> (auto trigger) or POST /evolve/trigger
  3. control frames: options (2 losers refused + winner "testing"), reasoning, proposal{proposed}
  4. approve with the control token -> release frames (6 stages, released, tests stage "Scored on N calls")
     -> `patch` frame on each member socket; measures "yes -> every phone patched" (ms)
  5. control snapshot spec: R-MONEY-UNKNOWN.params.receptionist_mode == true
  6. POST /tools/screen_caller (unknown caller claiming the verifier) -> held -> answer no -> refusal say
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "contracts" / "VERSION").read_text().strip()
CTRL = {"Authorization": "Bearer control"}


class Sock:
    def __init__(self, name: str, token: str) -> None:
        self.name, self.token, self.frames, self.ws = name, token, [], None
        self.cond = asyncio.Condition()

    async def open(self, ws_url: str, village: str) -> None:
        self.ws = await websockets.connect(f"{ws_url}/ws?village={village}&m={self.token}", max_size=8_000_000)
        await self.ws.send(json.dumps({"type": "hello", "contract_version": VERSION, "village": village, "member_token": self.token}))
        asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self.ws:
                f = json.loads(raw)
                f["_t"] = time.perf_counter()
                async with self.cond:
                    self.frames.append(f)
                    self.cond.notify_all()
        except Exception:
            pass

    async def wait(self, pred, timeout: float, start: int = 0):
        end = time.perf_counter() + timeout
        async with self.cond:
            while True:
                for f in self.frames[start:]:
                    if pred(f):
                        return f
                left = end - time.perf_counter()
                if left <= 0:
                    return None
                try:
                    await asyncio.wait_for(self.cond.wait(), left)
                except asyncio.TimeoutError:
                    return None


def ok(cond: bool, what: str, fails: list[str]) -> None:
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8793")
    ap.add_argument("--village", default="v_reyes")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--auto-wait", type=float, default=8.0, help="seconds to wait for the automatic Watcher trigger")
    a = ap.parse_args()
    fails: list[str] = []
    timings: dict[str, object] = {}
    vid = a.village
    ws_url = a.url.replace("http", "ws", 1)
    async with httpx.AsyncClient(base_url=a.url, timeout=60) as http:
        ctl = Sock("control", "control")
        await ctl.open(ws_url, vid)
        snap = await ctl.wait(lambda f: f.get("type") == "snapshot", 10)
        spec = snap["spec"]
        people = spec["blueprint"]["people"]
        recipient = spec["village"].get("care_recipient_id")
        verifier = next(p["params"]["trusted_contacts"][0] for p in spec["policies"] if p["rule_id"] == "R-MONEY-VERIFY")
        socks: dict[str, Sock] = {}
        for p in people:
            if p.get("view") and p["view"] not in {s_role for s_role in [x.get("view") for x in people if x["id"] in socks]}:
                s = Sock(p["view"], p["id"])
                await s.open(ws_url, vid)
                socks[p["id"]] = s
        for s in socks.values():
            ok(await s.wait(lambda f: f.get("type") == "snapshot", 10) is not None, f"snapshot on {s.name} ({s.token})", fails)
        base_rev = spec["rev"]
        mark = len(ctl.frames)

        # 2. today's scam call -> the real member says no -> Watcher trigger
        r = await http.post("/tools/report_money_request", json={
            "conversation_id": f"conv_v4_scam_{int(time.time())}", "caller_id": next(p.get("phone", "") for p in people if p["id"] == recipient),
            "call_secs": 9, "utterance": "Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.",
            "claimed_member": verifier, "claimed_identity": "Marco", "amount": 2000, "currency": "USD", "method": "gift_card",
            "urgency": "now", "red_flags": ["urgency", "claimed_family_member", "gift_card"]})
        ok(r.status_code == 200, f"report_money_request {r.status_code}", fails)
        ver = r.json().get("data", {}).get("verification_id")
        if ver:
            r = await http.post(f"/verifications/{ver}/answer", json={"verification_answer": "no", "member_id": verifier})
            ok(r.status_code == 200, "claimed member answered no", fails)
        t_trig = time.perf_counter()
        prop_frame = await ctl.wait(lambda f: f.get("type") == "control" and f.get("kind") == "proposal", a.auto_wait, mark)
        if prop_frame is not None:
            timings["trigger"] = "auto (verification resolved)"
            timings["resolved_to_proposal_ms"] = int((prop_frame["_t"] - t_trig) * 1000)
        else:
            t_trig = time.perf_counter()
            r = await http.post(f"/villages/{vid}/evolve/trigger", headers=CTRL)
            ok(r.status_code == 200, f"POST /evolve/trigger {r.status_code} {r.text[:200]}", fails)
            prop_frame = await ctl.wait(lambda f: f.get("type") == "control" and f.get("kind") == "proposal", 15, mark)
            timings["trigger"] = "control endpoint"
            timings["trigger_to_proposal_ms"] = int((time.perf_counter() - t_trig) * 1000)
        ok(prop_frame is not None and prop_frame["payload"]["proposal"]["status"] == "proposed", "control{proposal} proposed", fails)
        if prop_frame is None:
            print(json.dumps({"fails": fails}, indent=2))
            return 1
        prop = prop_frame["payload"]["proposal"]
        pid = prop["id"]
        led = [f["payload"] for f in ctl.frames[mark:] if f.get("type") == "control" and f.get("kind") == "ledger" and str(f["payload"].get("id", "")).startswith("opt:")]
        ok(sum(1 for x in led if x["status"] == "refused") == 2 and any(x["status"] == "running" and x.get("result") == "testing" for x in led),
           f"options ledger: 2 losers refused + winner testing ({[(x['what'], x['status']) for x in led]})", fails)
        ok(any(f.get("type") == "control" and f.get("kind") == "reasoning" and f["payload"].get("source") == "evolve" for f in ctl.frames[mark:]),
           "control{reasoning source=evolve}", fails)
        ok(len(prop["evidence"]) >= 3 and set(prop["ops"]) >= {"coordinator"}, f"proposal evidence {len(prop['evidence'])} rows, ops {sorted(prop['ops'])}", fails)
        chat = [f for s in socks.values() for f in s.frames if f.get("type") == "chat" and f["message"]["kind"] == "proposal"]
        ok(bool(chat), "chat{kind: proposal} reached the family", fails)

        # 4. approve -> release -> patch frames
        mark2 = {k: len(s.frames) for k, s in socks.items()}
        cmark = len(ctl.frames)
        t0 = time.perf_counter()
        r = await http.post(f"/villages/{vid}/proposals/{pid}/approve", headers=CTRL)
        ok(r.status_code == 202, f"approve {r.status_code} {r.text[:160]}", fails)
        patched = {}
        for k, s in socks.items():
            f = await s.wait(lambda f: f.get("type") == "patch", a.timeout, mark2[k])
            ok(f is not None and f.get("base_rev") == base_rev and f.get("proposal_id") == pid,
               f"patch on {s.name} ({k}) base_rev {f and f.get('base_rev')} -> rev {f and f.get('rev')}", fails)
            if f:
                patched[k] = f["_t"]
        if patched:
            timings["yes_to_every_phone_patched_ms"] = int((max(patched.values()) - t0) * 1000)
        rel = [f["payload"]["receipt"] for f in ctl.frames[cmark:] if f.get("type") == "control" and f.get("kind") == "release"]
        final = rel[-1] if rel else {}
        ok(final.get("result") == "released" and len(final.get("stages", [])) == 6, f"release frames: {len(rel)}, final {final.get('result')} ({final.get('id')})", fails)
        tests = next((st for st in final.get("stages", []) if st["name"] == "tests"), {})
        ok("Scored on" in (tests.get("details") or {}).get("summary", ""), f"tests stage: {(tests.get('details') or {}).get('summary')}", fails)
        timings["stages_ms"] = {st["name"]: (st.get("details") or {}).get("duration_ms") for st in final.get("stages", [])}
        snap2 = await ctl.wait(lambda f: f.get("type") == "snapshot" and f.get("rev", 0) > base_rev, 10, cmark)
        pol = next((p for p in (snap2 or {}).get("spec", {}).get("policies", []) if p["rule_id"] == "R-MONEY-UNKNOWN"), {})
        ok(pol.get("params", {}).get("receptionist_mode") is True, "spec R-MONEY-UNKNOWN.params.receptionist_mode == true", fails)
        got = (await http.get(f"/villages/{vid}/proposals")).json()
        ok(any(p["id"] == pid and p["status"] == "applied" for p in got["proposals"]), "proposal applied", fails)
        timings["server"] = got.get("timings")

        # 6. receptionist screens an unknown caller claiming the verifier
        conv = f"conv_v4_screen_{int(time.time())}"
        r = await http.post("/tools/screen_caller", json={"conversation_id": conv, "caller_id": "+12025550199", "call_secs": 5,
                                                          "utterance": "Hi, it's Marco. Put me through to my mom, I need money for bail.",
                                                          "claimed_identity": "Marco", "tool_call_id": "screen_1"})
        held = r.json()
        ok(held.get("data", {}).get("status") == "held", f"screen_caller held: {held.get('say')}", fails)
        sv = held.get("data", {}).get("verification_id")
        mk = mark2.get(verifier, 0)
        pr = await socks[verifier].wait(lambda f: f.get("type") == "prompt" and f.get("verification_id", f.get("prompt", {}).get("verification_id")) == sv, 10, mk) if verifier in socks else None
        ok(pr is not None or verifier not in socks, "verification prompt on the real member's phone", fails)
        await http.post(f"/verifications/{sv}/answer", json={"verification_answer": "no", "member_id": verifier})
        r = await http.post("/tools/screen_caller", json={"conversation_id": conv, "caller_id": "+12025550199", "call_secs": 18,
                                                          "utterance": "Hello?", "verification_id": sv, "tool_call_id": "screen_2"})
        out = r.json()
        ok(out.get("data", {}).get("status") == "refused" and "won't put you through" in out.get("say", ""), f"screen_caller refuses: {out.get('say')}", fails)
    print(json.dumps({"timings": timings, "fails": fails}, indent=2, ensure_ascii=False))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
