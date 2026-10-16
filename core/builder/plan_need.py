"""CORE-GLUE-7 (D39): a need that is not a night cover becomes an open plan item + an ask in the thread.

"take mom to the doctor's on friday" → extract {what, when, needs_on_site, is_night_cover} (LLM tool call,
deterministic fallback), add an open PlanBoard item on `plan:needs` (and any PlanBoard bind the views have),
ask the people who can do it, and on a yes set the owner and post the one-line outcome. The rota is untouched."""
from __future__ import annotations

import re
import uuid
from datetime import timedelta
from typing import Any

NEED_TOOL = {
    "name": "extract_need",
    "description": "Extract the need exactly as said in one group-chat message. Never invent people, places or times.",
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["what", "needs_on_site", "is_night_cover"],
        "properties": {
            "what": {"type": "string", "maxLength": 80, "description": "short phrase as said, e.g. 'take mom to the doctor'"},
            "weekday": {"type": "string", "description": "weekday name if said (English)"},
            "relative_day": {"enum": ["today", "tonight", "tomorrow", ""]},
            "date": {"type": "string", "description": "ISO date only if an explicit date was said"},
            "time": {"type": "string", "description": "time if said, e.g. '10:30 AM'"},
            "where": {"type": "string"},
            "needs_on_site": {"type": "boolean", "description": "true for drive/take/visit/pick up/bring; false for calls, reads, video, paperwork, ordering"},
            "is_night_cover": {"type": "boolean", "description": "only when about tonight's/tomorrow's check-in, night shift, cover or a swap"},
            "candidates": {"type": "array", "items": {"type": "string"}, "description": "names of people asked, only if named"},
        },
    },
}
WEEKDAYS = {"monday": 0, "mon": 0, "lunes": 0, "tuesday": 1, "tue": 1, "tues": 1, "martes": 1, "wednesday": 2, "wed": 2, "miercoles": 2, "miércoles": 2,
            "thursday": 3, "thu": 3, "thurs": 3, "jueves": 3, "friday": 4, "fri": 4, "viernes": 4, "saturday": 5, "sat": 5, "sabado": 5, "sábado": 5,
            "sunday": 6, "sun": 6, "domingo": 6}
WD_RE = re.compile(r"\b(" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r")\b", re.I)
REL_RE = re.compile(r"\b(tomorrow|tonight|today|mañana|hoy)\b", re.I)
ON_SITE_RE = re.compile(r"\b(take|drive|visit|pick(ing)? (her|him|them|up)|pick up|bring|go with|accompany|sit with|stay with|llevar|visitar|recoger|acompañar)\b", re.I)
REMOTE_RE = re.compile(r"\b(call|phone|ring|read|video|paperwork|forms?|order|book|schedule|email|refill|llamar)\b", re.I)
COVER_RE = re.compile(r"\b(take care|cover|covering|swap|shift|check-?in|night|fill in|on duty)\b", re.I)
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", re.I)
WHAT_RE = re.compile(r"\b(?:someone|somebody|anyone|anybody|alguien|help)\s+(?:to\s+|que\s+)?(.+)$", re.I)
KIN_RE = re.compile(r"\b(mom|mum|mother|mama|mamá|dad|father|papa|papá|grandma|grandpa|abuela|abuelo)\b", re.I)
FAR_RE = re.compile(r"\b(far|remote|lives (in|out|away)|hours? away|out of state|another (city|state|country))\b", re.I)
KIND = (("appointment", r"doctor|dentist|clinic|hospital|appointment|cita|médico|medico"), ("call", r"\bcall|phone|video\b"),
        ("visit", r"visit|sit with|stay with|visitar"), ("errand", r"."))


def resolve_day(weekday: str | None, relative: str | None, today: Any) -> tuple[str | None, str | None]:
    """(ISO date, day label) relative to core.clock's today; same weekday = today."""
    if weekday and weekday.lower().strip() in WEEKDAYS:
        d = today + timedelta(days=(WEEKDAYS[weekday.lower().strip()] - today.weekday()) % 7)
        return d.isoformat(), d.strftime("%A")
    rel = (relative or "").lower()
    if rel in ("tomorrow", "mañana"):
        d = today + timedelta(days=1)
        return d.isoformat(), d.strftime("%A")
    if rel in ("today", "tonight", "hoy"):
        return today.isoformat(), today.strftime("%A")
    return None, None


def extract_rules(text: str) -> dict[str, Any]:
    from .chat_intent import strip_mention

    t = strip_mention(text)
    wd, rel, tm = WD_RE.search(t), REL_RE.search(t), TIME_RE.search(t)
    m = WHAT_RE.search(t)
    what = ""
    if m:
        what = m.group(1)
        what = re.split(r"\s+(?:on|this|next|el|este)\s+(?=" + WD_RE.pattern[2:-2] + r")|\s+(?:" + WD_RE.pattern[2:-2] + r"|tomorrow|tonight|today|mañana|hoy|at \d)\b", what, flags=re.I)[0]
        what = re.sub(r"\b(\w+)'s\b(?=\s*[.!?]?$)", r"\1", what).strip(" .!?,")
    on_site = bool(ON_SITE_RE.search(what or t))
    remote = bool(REMOTE_RE.search(what or t)) and not on_site
    cover = bool(COVER_RE.search(t)) or not (on_site or remote)
    time = None
    if tm:
        time = f"{int(tm.group(1))}:{tm.group(2) or '00'} {tm.group(3).upper()}M"
    return {"what": what[:80], "weekday": wd.group(1) if wd else "", "relative_day": rel.group(1).lower() if rel else "", "time": time or "",
            "needs_on_site": on_site, "is_night_cover": cover and not wd, "candidates": []}


async def extract(text: str, llm: Any | None = None) -> dict[str, Any]:
    rules = extract_rules(text)
    if llm is None:
        return rules
    try:
        from .chat_intent import strip_mention

        out = await llm.tool_call(system="Extract the need exactly as said in this group-chat message. Only what was said: never invent people, places or times. "
                                         "is_night_cover only for tonight's/tomorrow's check-in, night shift, cover or a swap.",
                                  messages=[{"role": "user", "content": strip_mention(text)}], tool=NEED_TOOL, max_tokens=300)
        got = {k: v for k, v in out.items() if v not in (None, "", [])}
        # never accept an invented time: keep a time only if digits from it appear in the message
        if got.get("time") and not re.search(re.escape(str(got["time"]).split(":")[0].split()[0]), text):
            got.pop("time")
        return {**rules, **got}
    except Exception:
        return rules


def _kind(what: str) -> str:
    return next(k for k, pat in KIND if re.search(pat, what, re.I))


def _far(p: dict[str, Any]) -> bool:
    prof = p.get("profile") or {}
    return bool(p.get("remote") or prof.get("remote") or prof.get("distance") or FAR_RE.search(str(prof.get("notes") or "")) or FAR_RE.search(str(p.get("notes") or "")))


def candidates(village_id: str, author: str | None, on_site: bool) -> tuple[list[str], list[str]]:
    """(near, far) members with a phone/app, never the author or the care recipient."""
    from core import village as villages

    center = villages.care_recipient_id(village_id)
    near, far = [], []
    for p in villages.people(village_id):
        if p["id"] in (author, center) or p.get("role") in ("care_recipient", "elder") or not (p.get("view") or p.get("phone")):
            continue
        (far if on_site and _far(p) else near).append(p["id"])
    coord = villages.coordinator_id(village_id)
    near.sort(key=lambda m: m == coord)
    return near, far


def _phrase(village_id: str, what: str) -> str:
    """'take mom to the doctor' → 'take Mamá to the doctor' using the village's own word for the care recipient."""
    from core import village as villages

    center = villages.care_recipient_id(village_id)
    if not center:
        return what
    word = villages.relationship_word(village_id, center, "en") or villages.first_name(village_id, center)
    return KIN_RE.sub(word[:1].upper() + word[1:] if word else r"\1", what, count=1) if word else what


def plan_binds(village_id: str) -> list[str]:
    from core import village as villages

    binds = {"needs"}
    for view in (villages.spec(village_id).get("views") or {}).values():
        for el in (view.get("elements") or {}).values():
            b = str((el.get("props") or {}).get("bind") or "")
            if el.get("type") == "PlanBoard" and b.startswith("plan:"):
                binds.add(b.split(":", 1)[1])
    return sorted(binds)


async def start_plan_need(village_id: str, message: dict[str, Any], need: dict[str, Any]) -> dict[str, Any]:
    from core import village as villages
    from core.bindings_v3 import PLANS, plan
    from core.clock import clock
    from core.ws_hub import hub
    from . import asks

    text, author = message.get("text", ""), message.get("author")
    date, day = (need.get("date"), None) if need.get("date") else resolve_day(need.get("weekday"), need.get("relative_day"), clock.now().date())
    if need.get("date") and not day:
        try:
            from datetime import date as _d

            day = _d.fromisoformat(need["date"]).strftime("%A")
        except ValueError:
            date = None
    what = _phrase(village_id, need.get("what") or "help")
    time = need.get("time") or ""
    when = " · ".join(x for x in (date or "", time) if x)
    item = {"text": what[:1].upper() + what[1:], "kind": _kind(what), "owner": "", "when": when, "status": "open", "note": "who?"}
    if need.get("where"):
        item["text"] = f"{item['text']} ({need['where']})"[:80]
    refs_plan = []
    for pid in plan_binds(village_id):
        cur = plan(village_id, pid)
        items = [dict(i) for i in cur.get("items", [])] + [item]
        PLANS[(village_id, pid)] = {**cur, "items": items}
        refs_plan.append((pid, len(items) - 1))
    try:
        await hub.push_binds(village_id, {f"plan:{p}" for p, _ in refs_plan})
    except Exception:
        pass
    near, far = candidates(village_id, author, bool(need.get("needs_on_site")))
    named = {villages.first_name(village_id, m).lower(): m for m in near + far}
    picked = [named[c.split()[0].lower()] for c in need.get("candidates") or [] if c and c.split()[0].lower() in named]
    asked = picked or near[:3] or far[:2]
    names = {m: villages.first_name(village_id, m) for m in asked}
    gid = f"ask_{uuid.uuid4().hex[:8]}"
    pronoun = "her" if re.search(r"\b(mom|mum|mother|mam[aá]|grandma|abuela)\b", need.get("what") or "", re.I) else ("him" if KIN_RE.search(need.get("what") or "") else None)
    verb = re.match(r"(take|drive|pick up|bring|visit)\b", what, re.I)
    short = f"{verb.group(1).lower()} {pronoun}" if verb and pronoun else what
    questions = {m: f"{names[m]}, can you {short}?" for m in asked}
    label = day or "Soon"
    head = f"{label}{', ' + time if time else ''}: {villages.first_name(village_id, author, 'someone')} needs someone to {what}."
    body = " ".join([head] + [questions[m] for m in asked]) if asked else f"{head} Nobody else has the app yet."
    ask = {"id": gid, "type": "plan", "village": village_id, "date": date, "day": label, "time": time, "what": what, "on_duty": None, "on_duty_out": True,
           "asker": author, "asked": asked, "names": names, "questions": questions, "answers": {}, "status": "open", "plans": refs_plan, "item": item,
           "member_ask": {m: f"{gid}_{m}" for m in asked}, "message_id": None, "reply_to": message.get("id")}
    for m in asked:
        asks.BY_MEMBER_ASK[ask["member_ask"][m]] = (gid, m)
    asks.ASKS[gid] = ask
    msg = await asks.post(village_id, kind="answer", text=body, refs=[asks._ref(gid, m, ask) for m in asked] or [{"kind": "member", "id": author, "label": villages.first_name(village_id, author)}], reply_to=message.get("id"))
    ask["message_id"] = msg["id"]
    for m in asked:
        await asks.push_prompt(village_id, m, ask["member_ask"][m], questions[m])
    try:
        from .actors import on_ask

        for m in asked:
            on_ask(village_id, ask["member_ask"][m], m, role="plan")
    except Exception:
        pass
    if asked:
        asks._spawn(asks._window(gid))
    return ask


async def resolve_plan(ask: dict[str, Any], *, final: bool) -> None:
    from core import village as villages
    from core.bindings_v3 import set_plan_item
    from . import asks

    a = {m: v["answer"] for m, v in ask["answers"].items()}
    yes = next((m for m in ask["asked"] if a.get(m) == "yes"), None)
    vid = ask["village"]
    if yes:
        ask["status"] = "resolved"
        for pid, idx in ask["plans"]:
            try:
                await set_plan_item(vid, pid, idx, status="claimed", owner=yes)
            except Exception:
                pass
        ask["item"]["owner"], ask["item"]["status"] = yes, "claimed"
        what = ask["what"]
        verb = what.split()[0].lower() if what else ""
        conj = {"take": "takes", "drive": "drives", "bring": "brings", "visit": "visits", "call": "calls", "pick": "picks", "go": "goes", "do": "does"}.get(verb)
        line = f"{names_or(ask, yes)} {conj} {what.split(' ', 1)[1] if ' ' in what else ''}".strip() if conj else f"{names_or(ask, yes)}: {what}"
        text = f"{ask['day']}: {line}" + (f" · {ask['time']}" if ask.get("time") else "")
        await asks.post(vid, kind="answer", text=text, refs=[{"kind": "member", "id": yes, "label": names_or(ask, yes)}])
        try:
            from core.db import db
            from .decisions import builder_decision

            await db.create_decision({**builder_decision(vid, text, mode="asked_human"), "id": f"dc_{ask['id']}_claimed", "actor": "builder", "rule_id": "R-SPEC"})
        except Exception:
            pass
        return
    if final or all(a.get(m) == "no" for m in ask["asked"]):
        ask["status"] = "escalated"
        coord = villages.coordinator_id(vid)
        cname = villages.first_name(vid, coord, "the leader")
        silent = [ask["names"][m] for m in ask["asked"] if m not in ask["answers"]]
        lead = f"No answer from {' or '.join(silent)}." if silent else f"{' and '.join(ask['names'][m] for m in ask['asked'])} can't."
        await asks.post(vid, kind="nudge", text=f"{lead} {cname}, want me to ask someone else for {ask['day']}?", refs=[{"kind": "member", "id": coord, "label": cname}])


def names_or(ask: dict[str, Any], m: str) -> str:
    return ask["names"].get(m) or m
