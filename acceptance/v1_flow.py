"""V1 core acceptance: the headline scam flow over real sockets against a running Core.

usage: uv run python acceptance/v1_flow.py --url http://127.0.0.1:8792 [--dump frames.json]
Checks (contracts/fixtures/ws_sequence_scam.json + scam_call_tool_requests.json):
  money_request via POST /tools/report_money_request (variant `denied` body) -> Marco gets `prompt`
  -> POST /verifications/{vid}/answer no -> frames on carmen/ana/marco/control match `start` + `denied`
  (ordered per client; type, event kind / control kind, prompt.closed, data keys)
  -> await_verification returns the verbatim gate `say` for denied; duplicate webhook -> identical body;
  timeout path: second request + POST /clock/warp -> money_timeout say + prompt{closed}.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "contracts" / "fixtures"
VERSION = (ROOT / "contracts" / "VERSION").read_text().strip()
TOKENS = {"carmen": "mt_carmen_accept_v1_0001", "ana": "mt_ana_accept_v1_00001", "marco": "mt_marco_accept_v1_0001", "control": "control"}
# Fixture frames Core does not produce yet (documented in LANE-REPORT LD-n): narrative reasoning lines,
# the gate's possible_fraud_pattern event, and the c2s/result pair (this flow answers over HTTP).
SKIP = {("control", "reasoning")}  # Core emits one reasoning line per gate decision; the fixture narrates two


def sig(msg: dict) -> tuple:
    t = msg.get("type")
    if t == "event":
        return (t, msg["event"]["kind"])
    if t == "control":
        return (t, msg.get("kind"))
    if t == "prompt":
        return (t, bool(msg.get("closed")))
    return (t, None)


def expected(seq: str, client: str) -> list[dict]:
    frames = json.loads((FIX / "ws_sequence_scam.json").read_text())["sequences"][seq]
    out = []
    for f in frames:
        if f["client"] != client or f["dir"] != "s2c":
            continue
        m = f["msg"]
        if m["type"] == "result" or sig(m) in SKIP:
            continue
        out.append(m)
    return out


def match(exp: list[dict], got: list[dict], client: str, binds: set[str]) -> list[str]:
    errs = []
    i = 0
    for e in exp:
        while i < len(got) and sig(got[i]) != sig(e):
            i += 1
        if i == len(got):
            errs.append(f"{client}: missing {sig(e)}")
            return errs
        want = {k for k in (e.get("data") or {}) if k in binds or not binds}
        have = set((got[i].get("data") or {}).keys())
        if not want <= have:
            errs.append(f"{client}: {sig(e)} data keys {sorted(have)} lack {sorted(want - have)}")
        i += 1
    return errs


class Sock:
    def __init__(self, name: str, url: str):
        self.name, self.url, self.frames, self.snapshot = name, url, [], None

    async def open(self):
        self.ws = await websockets.connect(f"{self.url}/ws?village=v_reyes&m={TOKENS[self.name]}")
        await self.ws.send(json.dumps({"type": "hello", "contract_version": VERSION, "village": "v_reyes", "member_token": TOKENS[self.name], "client": "test"}))
        self.snapshot = json.loads(await self.ws.recv())
        assert self.snapshot["type"] == "snapshot", self.snapshot
        self.task = asyncio.create_task(self._pump())

    async def _pump(self):
        try:
            async for raw in self.ws:
                self.frames.append(json.loads(raw))
        except websockets.ConnectionClosed:
            pass

    def mark(self) -> int:
        return len(self.frames)

    async def close(self):
        await self.ws.close()


def binds_of(snapshot: dict) -> set[str]:
    if snapshot["role"] == "control":
        return set()
    return {el.get("props", {}).get("bind") for el in snapshot["spec"].get("elements", {}).values() if el.get("props", {}).get("bind")}


async def wait_for(pred, timeout=5.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if pred():
            return True
        await asyncio.sleep(0.05)
    return pred()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8792")
    ap.add_argument("--dump")
    args = ap.parse_args()
    http = httpx.AsyncClient(base_url=args.url, timeout=40)
    wsurl = args.url.replace("http", "ws", 1)
    errs: list[str] = []
    scam = json.loads((FIX / "scam_call_tool_requests.json").read_text())["variants"]
    denied_req = scam["denied"]["exchanges"][0]["request"]
    denied_await = scam["denied"]["exchanges"][1]
    timeout_await = scam["timeout"]["exchanges"][1]

    r = await http.post("/admin/reset", json={"scopes": ["events_today", "verifications", "proposals", "tokens", "counters"]}, headers={"X-Admin-Key": args_admin_key()})
    assert r.status_code == 200, r.text
    socks = {n: Sock(n, wsurl) for n in TOKENS}
    for s in socks.values():
        await s.open()
    # identity + prescriptions on snapshots (contract 1.2.0)
    for n, s in socks.items():
        ident = s.snapshot.get("identity") or {}
        if not {"member_id", "name", "role", "village_name"} <= set(ident):
            errs.append(f"{n}: snapshot.identity incomplete {ident}")
    if "prescriptions:current" not in socks["marco"].snapshot["data"]:
        errs.append("marco: snapshot lacks prescriptions:current")
    if "prescriptions:current" in socks["carmen"].snapshot["data"]:
        errs.append("carmen (elder) must not get prescriptions:current")

    # --- start
    tool = await http.post("/tools/report_money_request", json=denied_req)
    assert tool.status_code == 200, tool.text
    body = tool.json()
    vid = body["data"]["verification_id"]
    if body["say_key"] != "money_hold" or body["say"] != scam["denied"]["exchanges"][0]["response"]["say"]:
        errs.append(f"report_money_request say mismatch: {body['say']!r}")
    if not await wait_for(lambda: any(f["type"] == "prompt" and f["verification_id"] == vid for f in socks["marco"].frames)):
        errs.append("marco never got a prompt")
    dup = await http.post("/tools/report_money_request", json=denied_req)
    if dup.json() != body:
        errs.append("duplicate webhook body differs")
    await asyncio.sleep(0.3)
    start_marks = {n: s.mark() for n, s in socks.items()}
    for n, s in socks.items():
        errs += match(expected("start", n), s.frames[:start_marks[n]], n, binds_of(s.snapshot))

    # --- denied
    ans = await http.post(f"/verifications/{vid}/answer", json={"verification_answer": "no", "member_id": "m_marco", "via": "app_prompt"})
    assert ans.status_code == 200, ans.text
    await wait_for(lambda: any(f.get("kind") == "counter" for f in socks["control"].frames[start_marks["control"]:]))
    await asyncio.sleep(0.3)
    incident_ev = next(f["event"]["id"] for f in socks["ana"].frames if f["type"] == "event" and f["event"]["kind"] == "incident")
    await socks["ana"].ws.send(json.dumps({"type": "ack", "event_id": incident_ev, "status": "got_it", "req_id": "r_ana_ack_1"}))
    await wait_for(lambda: any(f["type"] == "event" and f["event"]["kind"] == "ack" for f in socks["control"].frames))
    await asyncio.sleep(0.2)
    for n, s in socks.items():
        errs += match(expected("denied", n), s.frames[start_marks[n]:], n, binds_of(s.snapshot))
    aw = await http.post("/tools/await_verification", json={**denied_await["request"], "verification_id": vid})
    awb = aw.json()
    if awb.get("say") != denied_await["response"]["say"] or awb.get("say_key") != "money_denied" or awb["data"]["status"] != "denied":
        errs.append(f"await_verification denied: {awb}")
    chat_incident = [f for f in socks["ana"].frames if f["type"] == "chat" and f["message"]["kind"] == "incident"]
    if not chat_incident:
        errs.append("ana got no chat{kind incident} after the denied incident")
    if any(f["type"] == "chat" for f in socks["carmen"].frames):
        errs.append("carmen (elder) received a chat frame")

    # --- timeout path (second scam call, nobody answers)
    t_req = {**denied_req, "conversation_id": "conv_accept_v1_timeout", "tool_call_id": "toolu_t1"}
    tb = (await http.post("/tools/report_money_request", json=t_req)).json()
    vid2 = tb["data"]["verification_id"]
    if vid2 == vid:
        errs.append("second money request reused the verification id")
    await wait_for(lambda: any(f["type"] == "prompt" and f["verification_id"] == vid2 for f in socks["marco"].frames))
    marks = {n: s.mark() for n, s in socks.items()}
    w = await http.post("/clock/warp", json={"minutes": 2})
    assert w.status_code == 200, w.text
    await wait_for(lambda: any(f["type"] == "prompt" and f.get("closed") and f["verification_id"] == vid2 for f in socks["marco"].frames))
    await asyncio.sleep(0.3)
    for n, s in socks.items():
        got = {sig(f) for f in s.frames[marks[n]:]}
        for e in expected("timeout_tail", n):
            if sig(e) not in got:
                errs.append(f"timeout {n}: missing {sig(e)}")
    ta = (await http.post("/tools/await_verification", json={**timeout_await["request"], "conversation_id": "conv_accept_v1_timeout", "verification_id": vid2})).json()
    if ta.get("say") != timeout_await["response"]["say"] or ta.get("say_key") != "money_timeout":
        errs.append(f"await_verification timeout: {ta}")

    validator = frame_validator()
    for n, s in socks.items():
        for f in [s.snapshot, *s.frames]:
            for e in validator.iter_errors(f):
                from jsonschema.exceptions import best_match

                bm = best_match(list(e.context) or [e])
                errs.append(f"schema {n} {sig(f)} {list(e.path)}{list(bm.path)}: {bm.message[:140]}")
                break
    if args.dump:
        Path(args.dump).write_text(json.dumps({n: s.frames for n, s in socks.items()}, indent=1, ensure_ascii=False))
    for n, s in socks.items():
        print(f"{n:8s} " + " ".join(f"{a}:{b}" if b not in (None, False) else a for a, b in (sig(f) for f in s.frames)))
    for s in socks.values():
        await s.close()
    await http.aclose()
    if errs:
        print("FAIL")
        for e in errs:
            print("  -", e)
        return 1
    print("V1 core acceptance: OK")
    return 0


def frame_validator():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    resources = []
    root = None
    for p in (ROOT / "contracts" / "schemas").glob("*.schema.json"):
        doc = json.loads(p.read_text())
        res = Resource.from_contents(doc, default_specification=__import__("referencing.jsonschema").jsonschema.DRAFT202012)
        resources.append((doc.get("$id", p.name), res))
        if p.name == "ws_messages.schema.json":
            root = doc
    registry = Registry().with_resources(resources)
    validators = {t: Draft202012Validator({"$ref": root["$id"] + f"#/$defs/{t}"}, registry=registry) for t in ("snapshot", "event", "control", "prompt", "result", "chat", "error", "pong")}

    class ByType:
        def iter_errors(self, frame):
            v = validators.get(frame.get("type"))
            return iter([]) if v is None else v.iter_errors(frame)

    return ByType()


def args_admin_key() -> str:
    import os

    try:
        from core.settings import get_settings

        return get_settings().admin_key
    except Exception:
        return os.getenv("ADMIN_KEY", "change-me-admin-key")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
