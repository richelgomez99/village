"""V2 core acceptance (specs/003-founding-generation/tasks.md A2-1..A2-11, core part) against a running Core.

usage: uv run python acceptance/v2_flow.py --url http://127.0.0.1:8795 [--token control]
Village-agnostic (D30): member ids come from the draft, the description from the registry's data file."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = (ROOT / "contracts" / "VERSION").read_text().strip()
RESULTS: list[tuple[str, bool, str]] = []


def check(step: str, ok: bool, note: str = "") -> bool:
    RESULTS.append((step, bool(ok), note))
    print(f"{'PASS' if ok else 'FAIL'} {step} {note}", flush=True)
    return bool(ok)


def description() -> str:
    reg = json.loads((ROOT / "data/villages/index.json").read_text())
    data = json.loads((ROOT / reg["villages"][reg["default"]]["data"]).read_text())
    d = data.get("demo_spoken_description")
    return d.get("text") if isinstance(d, dict) else str(d)


async def ws_open(base: str, village: str, token: str):
    ws = await websockets.connect(base.replace("http", "ws", 1) + f"/ws?village={village}&m={token}")
    await ws.send(json.dumps({"type": "hello", "contract_version": VERSION, "village": village, "member_token": token}))
    return ws


async def collect(ws, frames: list, stop: asyncio.Event) -> None:
    try:
        while not stop.is_set():
            frames.append(json.loads(await ws.recv()))
    except Exception:
        pass


async def main(url: str, token: str) -> int:
    H = {"Authorization": f"Bearer {token}"}
    vid = f"v_acc{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(base_url=url, headers=H, timeout=60) as c:
        room = await ws_open(url, vid, token)
        frames: list[dict] = []
        stop = asyncio.Event()
        tail = asyncio.create_task(collect(room, frames, stop))
        t0 = time.monotonic()
        r = await c.post("/villages", json={"description": description(), "language": "en", "village_id": vid,
                                            "clarify_wait_s": 4, "dailymed": "fixture"})
        check("A2-1 found by text -> 202", r.status_code == 202 and r.json().get("village_id") == vid, f"{r.status_code}")
        # A2-2: >=5 reasoning frames within 8 s on this village's control socket
        while time.monotonic() - t0 < 8 and sum(f.get("kind") == "reasoning" for f in frames) < 5:
            await asyncio.sleep(0.2)
        n = sum(f.get("kind") == "reasoning" for f in frames)
        check("A2-2 reasoning frames (>=5 in 8 s)", n >= 5, f"{n} in {time.monotonic() - t0:.1f}s")
        # answer one question so the founding frames fire after an answer
        for _ in range(40):
            b = (await c.get(f"/villages/{vid}")).json().get("builder", {})
            if b.get("waiting_for_answer"):
                await c.post(f"/villages/{vid}/answers", json={"text": "Marco goes Tuesdays and Thursdays; I go weekends."})
                break
            await asyncio.sleep(0.25)
        # A2-3: draft with 3 views
        spec: dict = {}
        for _ in range(120):
            spec = (await c.get(f"/villages/{vid}")).json()
            if len(spec.get("views") or {}) == 3 and spec.get("village", {}).get("status") == "draft" and spec.get("builder", {}).get("state") in (None, "review", "done", "draft"):
                break
            await asyncio.sleep(1)
        views = spec.get("views") or {}
        check("A2-3 draft with 3 views", {"elder", "coordinator", "helper"} <= set(views), f"views={sorted(views)} t={time.monotonic() - t0:.0f}s state={spec.get('builder', {}).get('state')}")
        cov = [f for f in frames if f.get("kind") == "counter" and f["payload"].get("name") == "intake_coverage"]
        qs = [f for f in frames if f.get("kind") == "blueprint" and f["payload"].get("stage") == "questions" and any(i.get("gap") for i in f["payload"]["items"])]
        check("T3 founding frames (intake_coverage + blueprint questions/gaps)", bool(cov) and bool(qs), f"coverage={len(cov)} gap_frames={len(qs)}")
        foreign = [f for f in frames if f.get("type") == "control" and f["payload"].get("village") not in (None, vid)]
        check("T2 control frames keyed to this village only", not foreign, f"foreign={len(foreign)}")
        # A2-4
        from core.builder.validate import validate_spec

        clean = {k: v for k, v in spec.items() if k != "builder"}
        rep = validate_spec(clean)
        check("A2-4 validates (contract oracle)", rep.ok, "" if rep.ok else str(rep.errors[:3]))
        # A2-5 template fallback with the model off (server runs VILLAGE_LLM=off)
        r5 = await c.post("/villages", json={"description": "Mom forgets her pills", "mode": "full", "clarify_wait_s": 1, "dailymed": "fixture"})
        check("A2-5 model-off found -> village_id", r5.status_code == 202 and bool(r5.json().get("village_id")))
        # T4 village list
        rows = (await c.get("/villages")).json()
        check("T4 GET /villages lists the new village", any(r.get("id") == vid for r in rows), f"{len(rows)} villages")
        # A2-6
        q = await c.get(f"/villages/{vid}/qr", params={"kind": "join", "format": "json"})
        check("A2-6a no join codes before activation", q.status_code == 409 or q.json() == [], f"{q.status_code} {q.text[:60]}")
        act = await c.post(f"/villages/{vid}/activate")
        inv = act.json().get("invites", []) if act.status_code == 200 else []
        check("A2-6b activate -> >=2 invites", len(inv) >= 2, f"{act.status_code} {len(inv)}")
        again = await c.post(f"/villages/{vid}/activate")
        check("A2-6c second activate 409", again.status_code == 409)
        roles = {i["role"]: i for i in inv}
        tok = lambda i: i["url"].split("i=", 1)[1]
        # A2-7 redeem through core's /auth/redeem (builder handoff), judge phone becomes the call target
        helper = roles.get("helper") or inv[0]
        rr = await c.post("/auth/redeem", json={"invite": tok(helper), "first_name": "Judge", "phone": "+15550109999",
                                                "consent": {"ai_calls": True, "text_version": "join_v1"}}, headers={})
        out = rr.json() if rr.status_code == 200 else {}
        check("A2-7 redeem -> member_token + consent event", bool(out.get("member_token")) and (out.get("consent_event") or {}).get("kind") == "consent" and out.get("village") == vid, f"{rr.status_code}")
        if out.get("member_token"):
            ws = await ws_open(url, vid, out["member_token"])
            snap = json.loads(await asyncio.wait_for(ws.recv(), 5))
            await ws.close()
            recs = {k: v for k, v in snap.get("data", {}).items() if k.startswith("member:")}
            check("T1 member snapshot carries member:<id> phones + village line", snap.get("village") == vid and any(v.get("phone") for v in recs.values()),
                  f"role={snap.get('role')} members={list(recs)} village_number={'village_number' in snap.get('identity', {})}")
        fr = await c.get(f"/villages/{vid}/print/fridge")
        check("T7 fridge card", fr.status_code == 200 and "911" in fr.text, f"{fr.status_code}")
        # A2-8
        a = await c.post(f"/villages/{vid}/ask", json={"question": "Why does the person at the center get a phone line and not an app?", "lang": "en"})
        aj = a.json() if a.status_code == 200 else {}
        check("A2-8 ask why -> answer + citations", bool(aj.get("answer")) and len(aj.get("citations") or []) >= 1, f"{a.status_code} cites={len(aj.get('citations') or [])}")
        # A2-9
        def chats(role: str) -> int:
            return sum(e.get("type") == "VillageChat" for e in (views.get(role) or {}).get("elements", {}).values())
        check("A2-9 chat in coordinator+helper, absent in elder", chats("coordinator") == 1 and chats("helper") == 1 and chats("elder") == 0,
              f"coord={chats('coordinator')} helper={chats('helper')} elder={chats('elder')}")
        print("SKIP A2-10 incident into chat (needs a seeded incident in the new village)", flush=True)
        # A2-11 @Village why from the coordinator
        coord = roles.get("coordinator")
        if coord:
            rc = await c.post("/auth/redeem", json={"invite": tok(coord), "first_name": "Coord", "consent": {"ai_calls": True, "text_version": "join_v1"}}, headers={})
            mt = rc.json().get("member_token") if rc.status_code == 200 else None
            ok = False
            note = f"redeem {rc.status_code}"
            if mt:
                ws = await ws_open(url, vid, mt)
                await asyncio.wait_for(ws.recv(), 5)
                pm = await c.post(f"/villages/{vid}/messages", json={"text": "@Village why does the person at the center get a phone line?", "mention": "village"},
                                  headers={"Authorization": f"Bearer {mt}"})
                routed = pm.json().get("routed") if pm.status_code == 201 else None
                end = time.monotonic() + 15
                got = None
                while time.monotonic() < end and got is None:
                    try:
                        f = json.loads(await asyncio.wait_for(ws.recv(), end - time.monotonic()))
                    except Exception:
                        break
                    if f.get("type") == "chat" and f.get("message", {}).get("kind") == "answer":
                        got = f["message"]
                await ws.close()
                ok = routed == "ask" and got is not None and bool(got.get("refs"))
                note = f"routed={routed} answer={'yes' if got else 'no'} refs={len((got or {}).get('refs') or [])}"
            check("A2-11 @Village why -> answer with refs", ok, note)
        else:
            check("A2-11 @Village why -> answer with refs", False, "no coordinator invite")
        stop.set()
        await room.close()
        tail.cancel()
    failed = [s for s, ok, _ in RESULTS if not ok]
    print(f"V2 core acceptance: {len(RESULTS) - len(failed)}/{len(RESULTS)} PASS" + (f"; FAIL: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8795")
    ap.add_argument("--token", default="control")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.url, args.token)))
