"""Apply the founding conversation to the draft spec: the founder's words become
blueprint.description (spans index into them), household needs + life areas, per-person days and
areas, outsiders (neighbor, super, doctor) as phone-less contacts, and checklist elements so the
apps reflect them (Ana's dashboard across every area; the helpers' week)."""
from __future__ import annotations

import re
from typing import Any

from .conversation import ConversationState, facts, intake_needs, person_assignments

AREA_LABELS = {"home": ("Home: stairs, keys", "Casa"), "daily_living": ("Daily life: groceries, visits", "Vida diaria"), "people": ("People: whose turn", "Personas"), "money": ("Money: scams, bills", "Dinero"), "health": ("Health: pills", "Salud"), "information": ("Information", "Información")}
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _outsider(pid: str, name: str, relation: str, role: str, template: dict[str, Any]) -> dict[str, Any]:
    prof = {k: template["profile"][k] for k in ("script", "dir") if k in template["profile"]}
    prof.update({"lang": "en", "script": prof.get("script", "Latn"), "reading_level": "standard", "vision": "typical", "hearing": "typical", "memory": "typical", "mobility": "typical", "tech_comfort": "phone", "availability": []})
    return {"id": pid, "name": name, "relation": relation, "role": role, "view": None, "notes": "Named by the founder; not invited. Village never calls them without asking.", "profile": prof, "consent": {"ai_calls": None, "app_prompts": None, "recorded_on": "2026-10-16", "recorded_by": "not asked (named during founding)"}}


def apply_intake(spec: dict[str, Any], conv: ConversationState) -> dict[str, Any]:
    """Mutates spec; returns a summary of what the conversation added."""
    bp = spec["blueprint"]
    text = conv.text[:2000]
    f = facts(conv)
    center = spec["village"].get("care_recipient_id")
    people = bp["people"]
    by_first = {p["name"].split()[0]: p for p in people}
    added: dict[str, Any] = {"needs": [], "people": [], "areas": {}}
    # household needs with spans into the founder's words
    existing = {n["id"] for n in bp["needs"]}
    for need in intake_needs(text, center):
        if need["id"] in existing:
            continue
        bp["needs"].append(need)
        added["needs"].append(need["id"])
    # per-person days + areas
    assign = person_assignments(text, {first: p["id"] for first, p in by_first.items()})
    for p in people:
        a = assign.get(p["id"])
        if not a:
            continue
        if a["days"] and p["id"] != center:
            avail = p["profile"].get("availability") or []
            window = avail[0]["window"] if avail else "09:00-18:00"
            p["profile"]["availability"] = [{"days": a["days"], "window": window, "note": "from the founding conversation"}]
        if a["areas"]:
            p["life_areas"] = sorted(set(p.get("life_areas", [])) | set(a["areas"]))
        added["areas"][p["id"]] = {"days": a["days"], "areas": a["areas"], "refill": a["refill"]}
    if f.get("quiet_hours") and center:
        cp = next(p for p in people if p["id"] == center)
        cp["profile"]["quiet_hours"] = f["quiet_hours"]
    # outsiders: phone-less contacts (no view, no channels)
    ft = text.lower()
    tmpl = people[0]
    outsiders = []
    m = re.search(r"(Mrs?\.|Ms\.) ([A-Z][a-z]+) next door", text)
    if m:
        outsiders.append(_outsider(f"m_{m.group(2).lower()}", f"{m.group(1)} {m.group(2)}", "neighbor (next door)", "peer", tmpl))
    if re.search(r"\bthe super\b", ft):
        outsiders.append(_outsider("m_super", "Building super", "building super (has keys)", "peer", tmpl))
    d = re.search(r"Dr\.? ([A-Z][a-z]+)(?: at ([A-Z][a-z]+))?", text)
    if d:
        outsiders.append(_outsider(f"m_dr_{d.group(1).lower()}", f"Dr. {d.group(1)}", f"doctor{' at ' + d.group(2) if d.group(2) else ''}", "professional_caregiver", tmpl))
    ids = {p["id"] for p in people}
    for o in outsiders:
        if o["id"] not in ids:
            people.append(o)
            spec["channels"][o["id"]] = []
            added["people"].append(o["id"])
    # apps reflect the household: Ana's dashboard checklist + the helpers' week
    new_needs = [n for n in bp["needs"] if n["id"] in added["needs"]]
    if new_needs and "coordinator" in spec["views"]:
        view = spec["views"]["coordinator"]
        owners = []
        items = []
        for n in new_needs[:8]:
            owner = next((pid for pid, a in added["areas"].items() if n["life_area"] in a["areas"] and pid != center), "")
            items.append(n["text"].split(":")[0][:80])
            owners.append(owner)
        view["elements"]["household"] = {"type": "Checklist", "props": {"title": "Household", "items": items, "owners": owners, "recurring": True}}
        view["elements"]["s"]["children"].append("household")
        view.setdefault("needs_served", {})["household"] = [n["id"] for n in new_needs[:8]]
    helpers = [p for p in people if p.get("view") == "helper" and p["id"] in added["areas"]]
    if helpers and "helper" in spec["views"]:
        view = spec["views"]["helper"]
        items, owners, served = [], [], {"n_turns"} & {n["id"] for n in bp["needs"]}
        for p in helpers:
            a = added["areas"][p["id"]]
            bits = []
            if a["days"]:
                bits.append("/".join(a["days"]) + " visits")
            if a["refill"]:
                bits.append("refill day")
            labels = {"money": "insurance & bills", "daily_living": "groceries", "home": "home", "people": "check-ins"}
            bits += [labels[x] for x in a["areas"] if x in labels]
            if bits:
                items.append(f"{p['name'].split()[0]}: {', '.join(bits)}"[:80])
                owners.append(p["id"])
                served |= {n["id"] for n in new_needs if n["life_area"] in a["areas"]}
        if items and served:
            view["elements"]["week"] = {"type": "Checklist", "props": {"title": "Who does what", "items": items, "owners": owners, "recurring": True}}
            view["elements"]["s"]["children"].insert(1, "week")
            view.setdefault("needs_served", {})["week"] = sorted(served)
    # every need lives in a life area
    for n in new_needs:
        area = next((a for a in bp["life_areas"] if a["id"] == n["life_area"]), None)
        if area is None:
            label, es = AREA_LABELS.get(n["life_area"], (n["life_area"], n["life_area"]))
            area = {"id": n["life_area"], "label": label, "label_i18n": {"en": label.split(":")[0], "es": es}, "need_ids": [], "modules": ["coordinator:household"] if "household" in spec["views"].get("coordinator", {}).get("elements", {}) else [], "rules": []}
            bp["life_areas"].append(area)
        area["need_ids"].append(n["id"])
        if "household" in spec["views"].get("coordinator", {}).get("elements", {}) and "coordinator:household" not in area["modules"]:
            area["modules"].append("coordinator:household")
    return added
