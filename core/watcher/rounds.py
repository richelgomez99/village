"""Village's rounds (D23 #1, Watcher): one nightly autonomous pass per village.

run_round(village_id, clock, services, memory, budget, ports) looks at tonight's state
and, within an action budget, acts alone, asks a human, or is refused by code. Every
action writes a decision row with `mode: acted_alone | asked_human | refused` and a
control{kind: reasoning} frame. Counts are measured from the data, never stored.

Steps (priority order, the budget is spent top-down):
  1. evening check-in call (if the village has a check-in routine and none happened) -> Dialer
     (quiet hours P-QH-01 are checked first: refused rows cite the member's own words)
  2. evening pills not logged -> nudge the on-duty member
  3. "you're on tomorrow" nudge -> chat
  4. refill due within 3 days (prescriptions + village meds) -> nudge the refill owner
  5. open Agent Memory uncertainties -> ask the coordinator (asked_human)
  6. scam eval set re-run (evals port)                          -> acted_alone
  7. pattern detection -> proposal (evals port / local fallback) -> asked_human
  8. carer load (D24 #2): nights per member over 14 days; one > 60% and an eligible
     member < 20% -> asked_human, never acts alone (outside the budget).
Over-budget autonomous candidates are downgraded to asked_human.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol
from zoneinfo import ZoneInfo

from core.settings import ROOT

ET = ZoneInfo("America/New_York")
DATA = ROOT / "data" / "villages"
HISTORY = Path(__file__).resolve().parent / "fixtures"
ROUNDS_AT = "21:40"  # after the evening dose window (19:30 + 90 min call + 15 min backup)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday",
             "Sat": "Saturday", "Sun": "Sunday"}


# ------------------------------------------------------------------ ports
class Dialer(Protocol):
    async def schedule_call(self, village: str, member_id: str, at: datetime, purpose: str) -> dict[str, Any]: ...


class Chat(Protocol):
    async def post(self, village: str, text: str, *, to: str, refs: list[dict[str, Any]]) -> dict[str, Any]: ...


class Evals(Protocol):
    async def rerun_scam_set(self, village: str) -> dict[str, Any] | None: ...
    async def detect_patterns(self, village: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


@dataclass
class Budget:
    max_actions: int = 3


@dataclass
class Ports:
    dialer: Any = None
    chat: Any = None
    evals: Any = None
    write_decision: Callable[[dict[str, Any]], Awaitable[Any]] | None = None
    broadcast: Callable[[str, str, dict[str, Any]], Awaitable[Any]] | None = None


class RecordingDialer:
    """Default dialer: records the scheduled call (the voice lane owns real outbound calls)."""
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def schedule_call(self, village, member_id, at, purpose):
        row = {"village": village, "member_id": member_id, "at": at.isoformat(), "purpose": purpose, "status": "scheduled"}
        self.calls.append(row)
        return row


class RecordingChat:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def post(self, village, text, *, to, refs):
        row = {"village": village, "text": text, "to": to, "refs": refs}
        self.messages.append(row)
        return row


# ------------------------------------------------------------------ services (read side)
@dataclass
class Services:
    events: Callable[[str], list[dict[str, Any]]]
    prescriptions: Callable[[str], list[dict[str, Any]]] = lambda v: []
    village: Callable[[str], dict[str, Any]] = lambda v: load_village(v)
    include_history: bool = True


def load_village(village_id: str) -> dict[str, Any]:
    for p in sorted(DATA.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if d.get("village_id") == village_id:
            return d
    return {"village_id": village_id, "members": []}


def history_events(village_id: str) -> list[dict[str, Any]]:
    out = []
    for p in sorted(HISTORY.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if d.get("village") == village_id:
            out += d.get("events", [])
    return out


def _dt(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=ET)


def _hm(s: str) -> time:
    h, m = s.strip().split(":")[:2]
    return time(int(h), int(m[:2]))


def first(name: str) -> str:
    return name.split()[0] if name else name


# ------------------------------------------------------------------ pure checks
def quiet_hours_block(village: dict[str, Any], member_id: str, at: datetime) -> dict[str, Any] | None:
    """P-QH-01: the member's own quiet-hours rule. Returns the refusal (rule, words, source) or None."""
    for rule in village.get("rules_from_members", []):
        if rule.get("member_id") != member_id or "quiet_hours" not in (rule.get("params") or {}):
            continue
        start_s, end_s = rule["params"]["quiet_hours"].split("-")
        start, end, t = _hm(start_s), _hm(end_s), at.astimezone(ET).time()
        inside = (start <= t or t < end) if start > end else (start <= t < end)
        if inside:
            return {"rule_id": rule.get("rule_id", "P-QH-01"), "window": rule["params"]["quiet_hours"],
                    "words": rule.get("words"), "words_en": rule.get("words_en"), "source": rule.get("source")}
    return None


def rota_days(village: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for k, v in (village.get("care_rota") or {}).items():
        if k.startswith("week_of_") and isinstance(v, list):
            for d in v:
                out[d["date"]] = d
    return out


def night_owner(day: str, events: list[dict[str, Any]], rota: dict[str, dict[str, Any]]) -> str | None:
    """Who covered the evening: last assigned/swapped shift row for that date, else the rota."""
    rows = [e for e in events if e.get("kind") == "shift" and (e.get("payload") or {}).get("date") == day
            and (e.get("payload") or {}).get("change") in ("assigned", "swapped")]
    if rows:
        rows.sort(key=lambda e: (_dt(e.get("at")) or datetime.min.replace(tzinfo=ET), e["payload"]["change"] == "swapped"))
        return rows[-1]["payload"].get("on_duty")
    return (rota.get(day) or {}).get("on_duty")


def nights_by_member(events: list[dict[str, Any]], rota: dict[str, dict[str, Any]], today: date, days: int = 14) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    covered = []
    for i in range(days, 0, -1):
        d = (today - timedelta(days=i)).isoformat()
        who = night_owner(d, events, rota)
        if who:
            counts[who] += 1
            covered.append(d)
    return counts, covered


def carer_load(village: dict[str, Any], events: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    rota = rota_days(village)
    counts, covered = nights_by_member(events, rota, today)
    total = sum(counts.values())
    if not total:
        return None
    members = {m["id"]: m for m in village.get("members", [])}
    carers = [mid for mid, m in members.items() if m.get("role") not in ("care_recipient",)]
    heavy = max(carers, key=lambda m: counts.get(m, 0), default=None)
    if heavy is None or counts.get(heavy, 0) / total <= 0.60:
        return None
    prefs = (village.get("care_rota") or {}).get("preferences", {})
    eligible = [m for m in carers if m != heavy and (prefs.get(m, {}).get("available") or members[m].get("consent", {}).get("app_prompts"))]
    light = sorted([m for m in eligible if counts.get(m, 0) / total < 0.20], key=lambda m: (counts.get(m, 0), carers.index(m)))
    if not light:
        return None
    lm = light[0]
    # next night the heavy member is on, from tomorrow
    nxt = None
    for i in range(1, 8):
        d = (today + timedelta(days=i)).isoformat()
        if (rota.get(d) or {}).get("on_duty") == heavy:
            nxt = rota[d]
            break
    day_name = DAY_NAMES.get((nxt or {}).get("day", ""), "next") if nxt else "next"
    avail = prefs.get(lm, {}).get("window", "")
    what = "call" if "phone" in avail else "evening"
    hn, ln = first(members[heavy]["name"]), first(members[lm]["name"])
    return {"heavy": heavy, "light": lm, "nights": counts.get(heavy, 0), "total": total,
            "counts": dict(counts), "covered": covered, "date": (nxt or {}).get("date"),
            "text": f"{hn} has taken {counts.get(heavy, 0)} of the last {total} nights. Ask {ln} to take the {day_name} {what}?"}


def refills_due(village: dict[str, Any], prescriptions: list[dict[str, Any]], today: date, within_days: int = 3) -> list[dict[str, Any]]:
    meds = {m.get("id") or m.get("med_id"): m for m in village.get("medications", [])}
    for rx in prescriptions:
        key = rx.get("med_id") or rx.get("id")
        meds[key] = {**meds.get(key, {}), **rx}
    out = []
    for mid, m in meds.items():
        r = m.get("refill") or {}
        due = r.get("next_due")
        if not due or m.get("valid_until") or m.get("status") == "superseded":
            continue
        dd = date.fromisoformat(due)
        if today <= dd <= today + timedelta(days=within_days):
            out.append({"med_id": mid, "name": m.get("name", mid), "dose": m.get("dose"), "due": due,
                        "owner": r.get("owner_id") or village.get("coordinator_id")})
    return sorted(out, key=lambda x: x["due"])


def local_patterns(events: list[dict[str, Any]], now: datetime, window_days: int = 30) -> list[dict[str, Any]]:
    """Fallback detector: >= 2 money requests in one member's name within 30 days."""
    by: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if e.get("kind") == "money_request":
            at = _dt(e.get("at"))
            if at and now - at <= timedelta(days=window_days):
                by.setdefault((e.get("payload") or {}).get("claimed_member_id") or "unknown", []).append(e)
    return [{"pattern": "repeat_money_request", "claimed_member_id": k, "event_ids": [e["id"] for e in v], "count": len(v)}
            for k, v in by.items() if len(v) >= 2]


# ------------------------------------------------------------------ the round
class _Round:
    def __init__(self, village_id: str, at: datetime, budget: Budget, ports: Ports) -> None:
        self.v, self.at, self.budget, self.ports = village_id, at, budget, ports
        self.rows: list[dict[str, Any]] = []
        self.acted = 0
        self.rid = f"{at.strftime('%m%d')}"

    def can_act(self) -> bool:
        return self.acted < self.budget.max_actions

    async def record(self, mode: str, text: str, *, refs: list[dict[str, Any]], step: str,
                     rule_id: str | None = None, source: dict[str, Any] | None = None, detail: dict[str, Any] | None = None) -> dict[str, Any]:
        n = len(self.rows) + 1
        row = {"id": f"dc_round_{self.rid}_{n:02d}", "village_id": self.v, "at": self.at.isoformat(timespec="seconds"),
               "actor": "gate" if mode == "refused" else "evolve", "kind": "decision", "text": text[:400],
               "refs": refs[:12], "source": source or {"kind": "system", "ref": "evolve"}, "mode": mode}
        if rule_id:
            row["rule_id"] = rule_id
        self.rows.append({**row, "_step": step, "_detail": detail or {}})
        if mode == "acted_alone":
            self.acted += 1
        if self.ports.write_decision:
            try:
                await self.ports.write_decision(row)
            except Exception:  # noqa: BLE001
                pass
        if self.ports.broadcast:
            try:
                await self.ports.broadcast(self.v, "reasoning", {"source": "evolve", "kind": "decision",
                                                                 "text": f"[rounds · {mode}] {text}"[:400], "village": self.v})
            except Exception:  # noqa: BLE001
                pass
        return row

    async def autonomous(self, text: str, do: Callable[[], Awaitable[Any]], *, refs, step, ask_whom: str, ask_name: str) -> None:
        if self.can_act():
            res = await do()
            await self.record("acted_alone", text, refs=refs, step=step, detail={"result": res})
        else:
            await self.record("asked_human", f"Over tonight's budget ({self.budget.max_actions}); asking {ask_name} instead: {text}",
                              refs=refs + [{"kind": "member", "id": ask_whom}], step=step)


async def run_round(village_id: str, clock: Any, services: Services, memory: Any = None,
                    budget: Budget | None = None, ports: Ports | None = None, *, at: datetime | None = None) -> dict[str, Any]:
    budget = budget or Budget()
    ports = ports or Ports(dialer=RecordingDialer(), chat=RecordingChat())
    now = clock.now().astimezone(ET)
    if at is None:
        at = datetime.combine(now.date(), _hm(ROUNDS_AT), tzinfo=ET)
    today = at.date()
    village = services.village(village_id)
    events = list(services.events(village_id))
    if services.include_history:
        known = {e.get("id") for e in events}
        events = [e for e in history_events(village_id) if e.get("id") not in known] + events
    members = {m["id"]: m for m in village.get("members", [])}
    name = lambda mid: first(members.get(mid, {}).get("name", mid))  # noqa: E731
    recipient = village.get("care_recipient_id", "m_carmen")
    coord = village.get("coordinator_id", "m_ana")
    rota = rota_days(village)
    tonight_on = night_owner(today.isoformat(), events, rota)
    r = _Round(village_id, at, budget, ports)
    today_events = [e for e in events if (_dt(e.get("at")) or datetime.min.replace(tzinfo=ET)).astimezone(ET).date() == today]
    evening_logged = any(e.get("kind") == "dose" and (e.get("payload") or {}).get("slot") == "evening" for e in today_events)

    # 1. evening check-in call
    checkin = next((x for x in village.get("routines", []) if "checkin" in x.get("id", "")), None)
    if checkin and not evening_logged and ports.dialer is not None:
        block = quiet_hours_block(village, recipient, at)
        if block:
            src = dict(block["source"] or {"kind": "system", "ref": "gate"})
            if block.get("words"):
                src["quote"] = block["words"]
            await r.record("refused", f"Wanted to call {name(recipient)} for the evening check-in at {at.strftime('%-I:%M %p')}. "
                                      f"Blocked by code: {name(recipient)}'s rule, no calls after "
                                      f"{_hm(block['window'].split('-')[0]).strftime('%-I:%M %p')}.",
                           refs=[{"kind": "policy", "id": block["rule_id"]}, {"kind": "member", "id": recipient}],
                           step="checkin_call", rule_id=block["rule_id"], source=src, detail={"window": block["window"]})
        else:
            await r.autonomous(f"Called {name(recipient)} for the evening check-in.",
                               lambda: ports.dialer.schedule_call(village_id, recipient, at, "evening_checkin"),
                               refs=[{"kind": "member", "id": recipient}], step="checkin_call", ask_whom=coord, ask_name=name(coord))

    # 2. evening pills not logged -> tell tonight's on-duty member
    if not evening_logged and tonight_on and ports.chat is not None and at.time() >= _hm(village.get("escalation_policy", {}).get("evening_slot_time", "19:30")):
        txt = f"{name(recipient)}'s evening pills aren't logged yet. {name(tonight_on)} is on tonight; sent a nudge."
        await r.autonomous(txt, lambda: ports.chat.post(village_id, f"{name(recipient)}'s evening pills (blue lid) aren't logged yet. Can you check with her?",
                                                        to=tonight_on, refs=[{"kind": "member", "id": recipient}]),
                           refs=[{"kind": "member", "id": tonight_on}, {"kind": "member", "id": recipient}], step="missed_dose_nudge",
                           ask_whom=coord, ask_name=name(coord))

    # 3. you're on tomorrow
    tomorrow = (today + timedelta(days=1)).isoformat()
    tm = night_owner(tomorrow, events, rota)
    if tm and ports.chat is not None:
        await r.autonomous(f"Reminded {name(tm)}: you're on for {name(recipient)} tomorrow.",
                           lambda: ports.chat.post(village_id, f"You're on for {members.get(recipient, {}).get('short_name', name(recipient))} tomorrow ({tomorrow}).",
                                                   to=tm, refs=[{"kind": "member", "id": tm}]),
                           refs=[{"kind": "member", "id": tm}], step="tomorrow_nudge", ask_whom=coord, ask_name=name(coord))

    # 4. refills due
    for rf in refills_due(village, services.prescriptions(village_id), today):
        owner = rf["owner"]
        await r.autonomous(f"Reminded {name(owner)}: {rf['name']} {rf['dose'] or ''} refill is due {rf['due']}.".replace("  ", " "),
                           lambda rf=rf, owner=owner: ports.chat.post(village_id, f"{rf['name'].capitalize()} refill is due {rf['due']}. You're on refills.",
                                                                      to=owner, refs=[{"kind": "fact", "id": f"{rf['name']}_refill_due"}]),
                           refs=[{"kind": "member", "id": owner}, {"kind": "fact", "id": f"{rf['name']}_refill_due"}],
                           step="refill_nudge", ask_whom=coord, ask_name=name(coord))

    # 5. open uncertainties -> ask the coordinator
    if memory is not None:
        try:
            u = await memory.uncertainties(village_id)
        except Exception:  # noqa: BLE001
            u = {"degraded": True, "uncertainties": []}
        for item in (u.get("uncertainties") or [])[:2]:
            key = str(item.get("key", "a fact")).replace("_", " ")
            await r.record("asked_human", f"Two sources disagree about {key}. Asked {name(coord)} which is right.",
                           refs=[{"kind": "fact", "id": str(item.get("key", "fact"))[:128]}, {"kind": "member", "id": coord}],
                           step="uncertainty_reask")

    # 6. scam eval re-run
    if ports.evals is not None and hasattr(ports.evals, "rerun_scam_set"):
        res = None
        if r.can_act():
            try:
                res = await ports.evals.rerun_scam_set(village_id)
            except Exception:  # noqa: BLE001
                res = None
            if res:
                caught, total = res.get("caught"), res.get("total")
                await r.record("acted_alone", f"Re-ran the scam eval set: {caught}/{total} caught." if total else "Re-ran the scam eval set.",
                               refs=[{"kind": "policy", "id": "R-MONEY-VERIFY"}], step="scam_evals", detail={"result": res})
        else:
            await r.record("asked_human", f"Over tonight's budget ({budget.max_actions}); scam eval re-run left for {name(coord)} to start.",
                           refs=[{"kind": "member", "id": coord}], step="scam_evals")

    # 7. patterns -> proposal (asked_human)
    try:
        pats = await ports.evals.detect_patterns(village_id, events) if ports.evals is not None and hasattr(ports.evals, "detect_patterns") \
            else local_patterns(events, at)
    except Exception:  # noqa: BLE001
        pats = local_patterns(events, at)
    for p in (pats or [])[:1]:
        cm = p.get("claimed_member_id") or p.get("subject")
        await r.record("asked_human", p.get("text") or f"{p.get('count', 2)} money requests in {name(cm)}'s name this month. "
                                                      f"Proposed a change to the app; waiting for {name(coord)}.",
                       refs=[{"kind": "event", "id": e} for e in p.get("event_ids", [])[:4]] + [{"kind": "member", "id": coord}],
                       step="pattern_proposal", detail={"pattern": p})

    # 8. carer load (never acts alone; outside the budget)
    load = carer_load(village, events, today)
    if load:
        await r.record("asked_human", load["text"],
                       refs=[{"kind": "member", "id": load["heavy"]}, {"kind": "member", "id": load["light"]}],
                       step="carer_load", detail=load)

    counts = Counter(row["mode"] for row in r.rows)
    result = {"village": village_id, "round_at": at.isoformat(timespec="seconds"), "ran_at": now.isoformat(timespec="seconds"),
              "budget": {"max_actions": budget.max_actions, "used": r.acted},
              "counts": {"acted_alone": counts.get("acted_alone", 0), "asked_human": counts.get("asked_human", 0),
                         "refused": counts.get("refused", 0)},
              "rows": [{k: v for k, v in row.items() if not k.startswith("_")} | {"step": row["_step"]} for row in r.rows],
              "details": {row["id"]: row["_detail"] for row in r.rows if row["_detail"]}}
    c = result["counts"]
    result["summary"] = (f"Tonight Village did {c['acted_alone']} things on its own, asked you about {c['asked_human']}"
                         f" and was stopped by a family rule {c['refused']} time{'s' if c['refused'] != 1 else ''}.")
    return result
