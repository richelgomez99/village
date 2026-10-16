"""Group-village binds from the village data file + ledger (core-glue 5). Generic: any registered village whose
data has members/resources/rumors/demo_calls gets these; nothing names a village or a person.

needs:open · resources:available · checkins:village · calls:line=<line> · claims:topic=<t>
`seed_checkins(village)` writes door-knock check-ins (ack events) for residents without an urgent need, so a reset
shows "N of M residents checked" and the urgent ones still open."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

_URGENT = 2  # need priority <= 2 = urgent (oxygen, insulin)


def _data(vid: str) -> dict[str, Any]:
    return villages.village_data(vid) or {}


def _name(vid: str, mid: str | None) -> str:
    p = villages.person(vid, mid) or next((m for m in _data(vid).get("members", []) if m.get("id") == mid), None) or {}
    words = [w for w in str(p.get("name") or mid or "").split() if w.rstrip(".").lower() not in {"mr", "mrs", "ms", "dr", "the"}]
    title = str(p.get("name") or "").split()[0] if str(p.get("name") or "").split()[0].rstrip(".").lower() in {"mr", "mrs", "ms", "dr"} else ""
    if str(p.get("name") or "").lower().startswith("the ") and len(words) >= 2:
        return " ".join(words[:2])  # "The Okafor family" -> "Okafor family"
    return f"{title} {words[-1]}".strip() if title and words else (words[0] if words else str(mid or ""))


def _residents(vid: str) -> list[dict[str, Any]]:
    return [m for m in _data(vid).get("members", []) if m.get("role") in {"resident", "care_recipient", "elder"}]


def _urgent(member: dict[str, Any]) -> bool:
    return any(int(n.get("priority", 9)) <= _URGENT for n in member.get("needs", []) or [])


def _checked_ids(vid: str) -> dict[str, str]:
    today = clock.now().date().isoformat()
    out: dict[str, str] = {}
    for ev in db.events:
        if ev.get("village") == vid and ev["kind"] == "ack" and str(ev.get("at", ""))[:10] == today:
            mid = ev.get("payload", {}).get("member_id") or ev.get("actor")
            if mid:
                out[mid] = ev["at"]
    return out


async def seed_checkins(vid: str) -> int:
    residents = _residents(vid)
    if not residents or not _data(vid).get("resources"):
        return 0
    coord = villages.coordinator_id(vid)
    now = clock.now()
    n = 0
    for i, m in enumerate(r for r in residents if not _urgent(r)):
        await db.create_event({
            "id": f"ev_{vid[2:]}_checkin_{m['id'][2:]}"[:60], "village": vid, "kind": "ack",
            "payload": {"member_id": m["id"], "status": "got_it", "via": "door_knock"},
            "actor": coord or m["id"], "source": {"kind": "app", "ref": coord or m["id"]},
            "at": (now - timedelta(minutes=40 - 7 * i)).isoformat(),
        })
        n += 1
    return n


def checkins(vid: str) -> list[dict[str, Any]]:
    seen = _checked_ids(vid)
    rows = []
    for m in sorted(_residents(vid), key=lambda r: (r["id"] in seen, not _urgent(r))):
        nm = _name(vid, m["id"])
        if m["id"] in seen:
            t = clock.now().fromisoformat(seen[m["id"]]).strftime("%-I:%M")
            rows.append({"id": m["id"], "member_id": m["id"], "status": "ok", "at": seen[m["id"]], "text": {"en": f"{nm} · checked {t}", "es": f"{nm} · visitado {t}"}})
        else:
            urgent = _urgent(m)
            rows.append({"id": m["id"], "member_id": m["id"], "status": "urgent" if urgent else "open",
                         "text": {"en": f"{nm} · {'urgent · ' if urgent else ''}not checked yet", "es": f"{nm} · {'urgente · ' if urgent else ''}sin visitar"}})
    return rows


def needs_open(vid: str) -> list[dict[str, Any]]:
    seen = _checked_ids(vid)
    rows = []
    for n in sorted(villages.spec(vid).get("blueprint", {}).get("needs", []), key=lambda n: n.get("priority", 9)):
        subjects = n.get("subject_member_ids") or []
        if subjects and all(s in seen for s in subjects) and int(n.get("priority", 9)) > _URGENT:
            continue
        who = ", ".join(_name(vid, s) for s in subjects)
        urgent = int(n.get("priority", 9)) <= _URGENT
        txt = f"{'Urgent · ' if urgent else ''}{n.get('text', '')}" + (f" · {who}" if who else "")
        rows.append({"id": n["id"], "priority": n.get("priority"), "life_area": n.get("life_area"), "subject_member_ids": subjects,
                     "status": "open", "text": {"en": txt[:200]}})
    return rows


def resources(vid: str) -> list[dict[str, Any]]:
    rows = []
    for r in _data(vid).get("resources", []):
        owner = r.get("owner")
        who = "Official" if owner == "official" else _name(vid, owner)
        what = str(r.get("type", "")).replace("_", " ")
        detail = r.get("capacity") or r.get("detail") or ""
        cons = "; ".join(r.get("constraints") or [])
        txt = f"{who} · {what}" + (f" · {detail}" if detail else "") + (f" ({cons})" if cons else "")
        row = {"id": r["id"], "owner": owner, "type": r.get("type"), "text": {"en": txt[:200]}}
        if r.get("source_url"):
            row["url"] = r["source_url"]
        rows.append(row)
    for m in _data(vid).get("members", []):  # a business on the block: phone + what it offers
        if m.get("role") == "business" and m.get("phone"):
            offer = m.get("offers") or m.get("notes") or "phone"
            rows.append({"id": f"res_{m['id']}", "owner": m["id"], "type": "business", "phone": m["phone"],
                         "text": {"en": f"{m.get('name', m['id'])} · {m['phone']} · {str(offer)[:80]}"}})
    return rows


def calls(vid: str, line: str) -> list[dict[str, Any]]:
    want = line.replace("-", "_")
    rows = []
    for c in _data(vid).get("demo_calls", []):
        if str(c.get("line", "")).replace("-", "_") != want:
            continue
        first = next((t.get("gloss") or t.get("text") for t in c.get("turns", []) if t.get("speaker") != "agent"), "")
        rows.append({"id": c["id"], "caller": c.get("caller"), "at": c.get("time"),
                     "text": {"en": f"{_name(vid, c.get('caller'))} called · {str(first)[:140]}"}})
    return rows


def claims(vid: str, topic: str = "all") -> list[dict[str, Any]]:
    rows = []
    for r in _data(vid).get("rumors", []):
        src = (r.get("official_source") or {}).get("name", "the official source")
        verdict = r.get("expected_verdict") or "check"
        rows.append({"id": r["id"], "claim": r.get("claim"), "verdict": verdict, "url": (r.get("official_source") or {}).get("url"),
                     "text": {"en": f"Heard: {r.get('claim')} · Check: {src}"}})
    return rows


def resolve(bind: str, vid: str) -> tuple[bool, Any]:
    if not _data(vid).get("members"):
        return False, None
    if bind == "needs:open":
        return True, needs_open(vid)
    if bind == "needs:open?count":
        return True, len(needs_open(vid))
    if bind == "resources:available":
        return True, resources(vid)
    if bind in {"checkins:village", "checkins:overdue"}:
        rows = checkins(vid)
        return True, rows if bind.endswith("village") else [r for r in rows if r["status"] != "ok"]
    if bind.startswith("calls:line="):
        return True, calls(vid, bind.split("=", 1)[1])
    if bind.startswith("claims:topic="):
        return True, claims(vid, bind.split("=", 1)[1])
    return False, None
