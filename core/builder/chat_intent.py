"""@Village chat routing (T024, D36): classify `why | change | other`; a change request becomes an
Evolve proposal with per-role ops (existing catalog, right place per D35) that the leader approves
from the same card; the release gate runs on approve (core.evolve.proposals.approve)."""
from __future__ import annotations

import copy
import re
from typing import Any

from .decisions import builder_decision

INTENT_TOOL = {
    "name": "classify_intent",
    "description": "Classify an @Village message.",
    "input_schema": {"type": "object", "additionalProperties": False, "required": ["intent", "reason"],
                     "properties": {"intent": {"enum": ["why", "change", "other"]}, "reason": {"type": "string", "maxLength": 200}}},
}
CHANGE_TOOL = {
    "name": "extract_change",
    "description": "Extract a new plan the group wants Village to keep (only what was said).",
    "input_schema": {
        "type": "object", "additionalProperties": False, "required": ["event"],
        "properties": {
            "event": {"type": "string"}, "date_day": {"type": "integer"}, "month": {"type": "string"}, "place": {"type": "string"},
            "people_count": {"type": "integer"},
            "brings": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["who", "what"], "properties": {"who": {"type": "string"}, "what": {"type": "string"}}}},
            "arrivals": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["who"], "properties": {"who": {"type": "string"}, "train": {"type": "string"}, "pickup_at": {"type": "string"}, "pickup_place": {"type": "string"}}}},
            "dietary": {"type": "array", "items": {"type": "string"}},
            "rule": {"type": "string"},
        },
    },
}
WHY_RE = re.compile(r"^\s*(@village[\s,:]*)?(why|por qu[eé]|how come|what does|who decided|explain)", re.I)
CHANGE_RE = re.compile(r"\b(we'?re doing|we are doing|add|switch(ed)?|change|from now on|starting|can you (set|add|make)|please (add|set)|is coming|are coming|brings?|pick (her|him|them) up)\b", re.I)
WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20}
MONTH_OF = {"thanksgiving": "Nov", "christmas": "Dec", "new year": "Jan"}
ES_MONTH = {"Nov": "noviembre", "Dec": "diciembre", "Jan": "enero"}


def strip_mention(text: str) -> str:
    s = text.lstrip()
    return s[len("@village"):].strip(" ,:") if s.lower().startswith("@village") else s


async def classify(text: str, llm: Any | None = None) -> str:
    if llm is not None:
        try:
            out = await llm.tool_call(system="Classify a family chat message addressed to Village: why = asks for an explanation; change = asks Village to add/change something in the village; other.",
                                      messages=[{"role": "user", "content": text}], tool=INTENT_TOOL, max_tokens=200)
            if out.get("intent") in ("why", "change", "other"):
                return out["intent"]
        except Exception:
            pass
    if WHY_RE.search(text):
        return "why"
    return "change" if CHANGE_RE.search(text) else "other"


def extract_rules(text: str) -> dict[str, Any]:
    """Deterministic extractor (model off): event, day, count, who brings what, trains/pickups, diets, a rule."""
    t = strip_mention(text)
    out: dict[str, Any] = {}
    ev = re.search(r"\b(Thanksgiving|Christmas|Easter|a birthday|New Year'?s?)\b", t, re.I)
    out["event"] = ev.group(1) if ev else "the plan"
    day = re.search(r"\bon the (\d{1,2})(?:st|nd|rd|th)\b", t)
    if day:
        out["date_day"] = int(day.group(1))
    out["month"] = MONTH_OF.get(out["event"].lower(), "")
    pl = re.search(r"\bat ((?:Mom|Mamá|Dad|Grandma)'?s)\b", t)
    if pl:
        out["place"] = pl.group(1)
    cnt = re.search(r"\b(\w+) of us\b", t, re.I)
    if cnt:
        w = cnt.group(1).lower()
        out["people_count"] = WORD_NUM.get(w) or (int(w) if w.isdigit() else None)
    out["brings"] = [{"who": w, "what": what.strip()} for w, what in re.findall(r"\b([A-ZÁÉÍÓÚ][a-zá-ú]+) brings (the [a-z ]+?)(?= and |[.,]|$)", t)]
    arrivals = []
    for who, train in re.findall(r"\b([A-ZÁÉÍÓÚ][a-zá-ú]+) (?:brings [a-z ]+ and )?comes in on the (\d{1,2}:\d{2}) train", t):
        arrivals.append({"who": who, "train": train})
    pk = re.search(r"pick (?:her|him|them) up at ([A-Z][\w ]+?) at (\d{1,2}(?::\d{2})?)", t)
    if pk and arrivals:
        arrivals[-1].update(pickup_place=pk.group(1).strip(), pickup_at=pk.group(2))
    out["arrivals"] = arrivals
    out["dietary"] = [m.group(0).strip(" .") for m in re.finditer(r"[A-Z][a-z]+ needs a [a-z-]+ plate", t)]
    rule = re.search(r"\b(no [a-z ]+? at the table)\b", t, re.I)
    if rule:
        out["rule"] = rule.group(1)
    return out


async def extract_change(text: str, llm: Any | None = None) -> dict[str, Any]:
    rules = extract_rules(text)
    if llm is None:
        return rules
    try:
        out = await llm.tool_call(system="Extract only what was said; never invent people, times or dishes.", messages=[{"role": "user", "content": strip_mention(text)}], tool=CHANGE_TOOL, max_tokens=800)
        return {**rules, **{k: v for k, v in out.items() if v not in (None, "", [])}}
    except Exception:
        return rules


def _first(spec: dict[str, Any], pid: str | None) -> str:
    p = next((x for x in spec["blueprint"]["people"] if x["id"] == pid), None)
    return p["name"].split()[0] if p else ""


def plan_lines(ch: dict[str, Any], *, pickup_by: str | None) -> list[str]:
    lines = []
    if ch.get("people_count"):
        lines.append(f"{ch['people_count']} people at {ch.get('place', 'home')}")
    lines += [f"{b['who']} brings {b['what']}" for b in ch.get("brings", [])]
    for a in ch.get("arrivals", []):
        if a.get("train"):
            lines.append(f"{a['who']}: {a['train']} train")
        if a.get("pickup_place"):
            lines.append(f"Pick up {a['who']} at {a['pickup_place']}, {a.get('pickup_at', '')} PM" + (f" ({pickup_by})" if pickup_by else " (who?)"))
    lines += [d.replace("needs a", ":").replace(" : ", ": ") for d in ch.get("dietary", [])]
    if ch.get("rule"):
        lines.append(f"Rule: {ch['rule']}")
    return [l[:80] for l in lines][:12]


PLANS: dict[str, dict[str, dict[str, Any]]] = {}  # village → plan_id → {id, title, items}; core serves `plan:<id>` from here


def plan_id_for(ch: dict[str, Any]) -> str:
    ev = re.sub(r"[^a-z0-9]+", "_", str(ch.get("event", "plan")).lower()).strip("_")[:20] or "plan"
    month_n = {"Jan": "01", "Nov": "11", "Dec": "12"}.get(ch.get("month", ""), "")
    day = f"{int(ch['date_day']):02d}" if ch.get("date_day") else ""
    return f"{ev}_{month_n}{day}" if day else ev


def plan_items(ch: dict[str, Any], spec: dict[str, Any], *, pickup_by: str | None) -> list[dict[str, Any]]:
    """bv items for PlanBoard: {text, kind, owner (member id), when, status, note} — only what was said."""
    ids = {p["name"].split()[0]: p["id"] for p in spec["blueprint"]["people"]}
    out: list[dict[str, Any]] = []
    for b in ch.get("brings", []):
        out.append({"text": f"{b['who']}: {b['what'].replace('the ', '')}", "kind": "brings", "owner": ids.get(b["who"], ""), "when": "", "status": "claimed", "note": ""})
    for a in ch.get("arrivals", []):
        if a.get("train"):
            out.append({"text": f"{a['who']}: {a['train']} train", "kind": "travel", "owner": ids.get(a["who"], ""), "when": a["train"], "status": "planned", "note": ""})
        if a.get("pickup_place"):
            out.append({"text": f"Pick up {a['who']} at {a['pickup_place']}", "kind": "pickup", "owner": ids.get(pickup_by or "", ""), "when": f"{a.get('pickup_at', '')}:00 PM".replace("::", ":") if a.get("pickup_at") and ":" not in a["pickup_at"] else a.get("pickup_at", ""), "status": "claimed" if pickup_by else "open", "note": "" if pickup_by else "who?"})
    for d in ch.get("dietary", []):
        who = d.split()[0]
        out.append({"text": f"{who}: {d.split('needs a ', 1)[-1]}", "kind": "constraint", "owner": "", "when": "", "status": "noted", "note": ""})
    if ch.get("rule"):
        out.append({"text": f"Rule: {ch['rule']}", "kind": "rule", "owner": "", "when": "", "status": "noted", "note": ""})
    if ch.get("people_count"):
        out.insert(0, {"text": f"{ch['people_count']} people at {ch.get('place', 'home')}", "kind": "headcount", "owner": "", "when": "", "status": "noted", "note": ""})
    return out[:24]


def plan_data(village_id: str, plan_id: str) -> dict[str, Any] | None:
    """Core's `plan:<id>` binding value."""
    return copy.deepcopy(PLANS.get(village_id, {}).get(plan_id))


def build_change_ops(spec: dict[str, Any], ch: dict[str, Any]) -> dict[str, Any]:
    """Per-role ops in the right place (D35), ≤ 12 root children, existing catalog only."""
    from .patch import apply_ops, apply_to_copy

    event = ch.get("event", "The plan")
    day = ch.get("date_day")
    month = ch.get("month") or ""
    when = f"{month} {day}".strip() if day else ""
    title = f"{event} plan" + (f" · {when}" if when else "")
    coord = spec["village"].get("coordinator_id")
    center = spec["village"].get("care_recipient_id")
    by_first = {p["name"].split()[0]: p for p in spec["blueprint"]["people"]}
    brings = {b["who"]: b["what"] for b in ch.get("brings", [])}
    # who could pick up: a local helper who isn't the one arriving (the one bringing the main dish, by default)
    arriving = {a["who"] for a in ch.get("arrivals", [])}
    pickup_by = next((w for w in brings if w not in arriving and w in by_first), None)
    lines = plan_lines(ch, pickup_by=pickup_by)
    plan_id = plan_id_for(ch)
    items = plan_items(ch, spec, pickup_by=pickup_by)
    need = next((n["id"] for n in spec["blueprint"]["needs"] if n.get("domain") == "scheduling"), "n_safety")
    ops: dict[str, list[dict[str, Any]]] = {}
    served: dict[str, dict[str, list[str]]] = {}
    highlight: dict[str, list[str]] = {}
    changes: list[dict[str, str]] = []
    cand = copy.deepcopy(spec)
    for role, view in spec["views"].items():
        els = view["elements"]
        kids = list(els["s"].get("children", []))
        if len(kids) + 1 > 12 or "plan_event" in els:
            continue

        def after(t: str) -> int | None:
            return next((i + 1 for i, e in enumerate(kids) if els.get(e, {}).get("type") == t), None)

        members = [p for p in spec["blueprint"]["people"] if p.get("view") == role]
        if view.get("theme") == "elder":
            at = after("TonightCard") or 1
            dia = f"El jueves {day} vienen todos." if day else "Vienen todos."
            main = next(iter(brings.items()), None)
            text = dia + (f" {main[0]} trae el {'pavo' if 'turkey' in main[1] else main[1].replace('the ', '')}." if main else "")
            el = {"type": "Text", "props": {"text": text, "size": "l", "tone": "info"}}
            for p in members:
                changes.append({"en": f"{p.get('short_name') or p['name'].split()[0]}: one line in Spanish under tonight: \"{text}\"", "es": f"{p.get('short_name') or p['name'].split()[0]}: una línea: \"{text}\""})
        elif after("LifeAreas") is not None:
            at = after("LifeAreas")
            el = {"type": "PlanBoard", "props": {"title": (f"{event} · {when}" if when else event)[:60], "bind": f"plan:{plan_id}", "date": (f"Thu {when}" if event.lower() == "thanksgiving" and when else when)[:40], "allow_claim": True}}
            changes.append({"en": f"{_first(spec, coord)}: a '{title}' card under her life areas (who brings what, pickups, the plate, the rule)", "es": f"{_first(spec, coord)}: tarjeta '{title}'"})
        elif after("HelperAnswer") is not None:
            at = after("HelperAnswer")
            if len(members) == 1:
                me = members[0]["name"].split()[0]
                bits = [f"you bring {brings[me]}"] if me in brings else []
                bits += [f"pick up {a['who']} at {a['pickup_place']}, {a.get('pickup_at')} PM" for a in ch.get("arrivals", []) if a.get("pickup_place") and pickup_by == me]
                text = f"{event}: " + " · ".join(bits or lines[:2])
            else:  # shared view: say it in third person so nobody reads someone else's line as theirs
                bits = []
                for who, what in brings.items():
                    arr = next((a for a in ch.get("arrivals", []) if a["who"] == who and a.get("train")), None)
                    bits.append(f"{who} brings {what.replace('the ', 'the ')}" + (f", {arr['train']} train" if arr else ""))
                text = f"{event}: " + " · ".join(bits)
            el = {"type": "Text", "props": {"text": text[:200], "size": "m", "tone": "info"}}
            for p in members:
                changes.append({"en": f"{p['name'].split()[0]}: under 'Is it my turn?': \"{text[:120]}\"", "es": f"{p['name'].split()[0]}: \"{text[:120]}\""})
        else:
            continue
        role_ops = [{"op": "add", "path": "/elements/plan_event", "value": el}, {"op": "add", "path": f"/elements/s/children/{at}", "value": "plan_event"}]
        srv = {} if el["type"] == "Text" else {"plan_event": [need]}  # PlanBoard serves the scheduling need
        nxt, errs = apply_to_copy(cand, role, {"ops": role_ops, "needs_served": srv})
        if nxt is None:
            continue
        cand, ops[role], served[role], highlight[role] = nxt, role_ops, srv, ["plan_event"]
    # the new life area (blueprint) — applied with the views on approve (rec voice_ops path)
    bp_ops = []
    used = {a["id"] for a in spec["blueprint"]["life_areas"]}
    area_id = next((a for a in ("daily_living", "home", "information") if a not in used), None)
    if area_id and "coordinator" in ops:
        nid = "n_" + re.sub(r"[^a-z0-9]+", "_", event.lower()).strip("_")[:30]
        bp_ops = [
            {"op": "add", "path": "/blueprint/needs/-", "value": {"id": nid, "text": f"{event}: {', '.join(lines[:3])}"[:160], "priority": 3, "domain": "scheduling", "life_area": area_id, "subject_member_ids": [p for p in (center, coord) if p], "source_span": None, "origin": "evolve"}},
            {"op": "add", "path": "/blueprint/life_areas/-", "value": {"id": area_id, "label": f"{event} · {when}"[:40] if when else event[:40], "label_i18n": {"en": f"{event} · {when}"[:60], "es": f"{'Acción de Gracias' if event.lower() == 'thanksgiving' else event} · {day or ''} {ES_MONTH.get(month, '')}".strip()[:60]}, "need_ids": [nid], "modules": ["coordinator:plan_event"], "rules": []}},
        ]
        try:
            from .validate import validate_spec

            if not validate_spec(apply_ops(cand, bp_ops)).ok:
                bp_ops = []
        except Exception:
            bp_ops = []
    return {"ops": ops, "needs_served": served, "highlight": highlight, "blueprint_ops": bp_ops, "changes": changes[:6], "title": title, "lines": lines,
            "plan": {"id": plan_id, "title": title, "items": items}}


async def propose_change(village_id: str, text: str, author: str | None, *, llm: Any | None = None) -> dict[str, Any]:
    """Change request → Evolve proposal record (same STORE/approve/release path as core.evolve.proposals)."""
    from core import services
    from core import village as villages
    from core.db import db
    from core.evolve import proposals as ev

    spec = copy.deepcopy(villages.spec(village_id))
    ch = await extract_change(text, llm)
    built = build_change_ops(spec, ch)
    if not built["ops"]:
        raise ValueError("nothing to change")
    coord = villages.coordinator_id(village_id)
    coord_name = villages.first_name(village_id, coord, "the coordinator")
    asker = villages.first_name(village_id, author, coord_name) if author else coord_name
    ev._SEQ[village_id] = ev._SEQ.get(village_id, 0) + 1
    slug = re.sub(r"[^a-z0-9]+", "_", ch.get("event", "plan").lower()).strip("_")[:20] or "plan"
    pid = f"prop_{ev._slug(village_id)}_{slug}_{ev._SEQ[village_id]}"
    event = ch.get("event", "the plan")
    count = ch.get("people_count")
    day = ch.get("date_day")
    rel_en = villages.relationship_word(village_id, villages.care_recipient_id(village_id), "en") or "home"
    rationale_en = f"{asker} asked in the chat: " + (f"{_num_word(count)} people at {rel_en}'s" if count else event) + (f" on {ch.get('month', '')} {day}".rstrip() if day else "") + "."
    proposal: dict[str, Any] = {
        "id": pid, "village": village_id,
        "detected_by": "memory_pattern",  # contract enum has no chat_request yet (LD-11); rec["detected_by"] says chat_request
        "title": {"en": f"Add {event} to the village", "es": f"Agregar {'Acción de Gracias' if event.lower() == 'thanksgiving' else event} a la village"},
        "rationale": {"en": rationale_en, "es": f"{asker} lo pidió en el chat."},
        "changes": built["changes"],
        "evidence": [{"kind": "fact", "ref": f"chat:{author or 'member'}", "label": f"{asker}'s message in the chat"}],
        "ops": built["ops"], "needs_served": built["needs_served"], "spec_ops": [],
        "status": "proposed", "base_rev": int(spec.get("rev", 0)), "created_at": ev._now(),
    }
    errs = ev.validate(proposal)
    if errs:
        raise ValueError(f"proposal invalid: {errs[:2]}")
    stays = "Nothing else changes; the plan is the family's, Village only keeps it in one place."
    rec = {"proposal": proposal, "options": None, "voice_ops": built["blueprint_ops"], "highlight": built["highlight"],
           "key": f"chat:{slug}", "detected_by": "chat_request", "evidence_meta": {"text": text},
           "evidence_labels": [f"{asker}'s message"], "what_happened": proposal["rationale"],
           "stays_the_same": {"en": stays, "es": "Nada más cambia; el plan es de la familia, Village solo lo guarda en un lugar."}, "checked": []}
    rec["plan"] = built["plan"]  # PlanBoard data (bind plan:<id>) for core's binding
    PLANS.setdefault(village_id, {})[built["plan"]["id"]] = copy.deepcopy(built["plan"])
    ev.STORE.setdefault(village_id, {})[pid] = rec
    await db.create_decision({**builder_decision(village_id, f"Proposed: {proposal['title']['en']} ({asker}'s chat request). Waiting for {coord_name}.", mode="asked_human"),
                              "id": f"dc_{pid}_proposed", "at": ev._now(), "actor": "evolve", "rule_id": "R-SPEC", "rev": proposal["base_rev"]})
    lines = "; ".join(c["en"] for c in built["changes"][:4])
    msg = await services.post_message(village_id, author="village", kind="proposal",
                                      text=f"{proposal['title']['en']}? {rationale_en} {lines}. {stays}"[:2000],
                                      refs=[{"kind": "proposal", "id": pid, "label": "proposal"}], source={"kind": "system", "ref": "evolve"})
    proposal["message_id"] = msg["id"]
    await ev._announce(village_id, rec)
    await services.ledger(village_id, f"prop:{pid}", "queued", f"Proposal · {proposal['title']['en']}", result="waiting for approval", decision_id=f"dc_{pid}_proposed", role="Builder")
    await services.reasoning(village_id, f"{asker} asked for a change → proposed '{proposal['title']['en']}'. Nothing changes until {coord_name} says yes.", source="builder", kind="decision", mode="asked_human")
    return copy.deepcopy(proposal)


def _num_word(n: int | None) -> str:
    words = {v: k for k, v in WORD_NUM.items()}
    return words.get(n or 0, str(n)).capitalize() if n else ""


async def route_chat(village_id: str, text: str, author: str | None = None, *, llm: Any | None = None, services: Any = None) -> dict[str, Any]:
    """Core's @Village hook (`core.builder.ask(village_id, text)`): returns {text, refs, trace_id}."""
    from .ask import ask

    intent = await classify(text, llm)
    if intent == "change":
        try:
            p = await propose_change(village_id, text, author, llm=llm)
            return {"text": f"I drafted '{p['title']['en']}'. Nothing changes until it's approved: tap Approve on the card.", "refs": [{"kind": "proposal", "id": p["id"], "label": "proposal"}], "intent": "change"}
        except Exception as exc:  # fall back to an answer, never a crash in the chat
            return {"text": f"I couldn't turn that into a change yet ({type(exc).__name__}). Want me to try again?", "refs": [], "intent": "change"}
    if services is None:
        from .routes import services as route_services

        services = route_services()
    res = await ask(village_id, strip_mention(text), services=services, llm=llm, channel="chat")
    refs = [{"kind": c["kind"], "id": c["id"], "label": (c.get("label") or c["kind"])[:80]} for c in res.citations]
    return {"text": res.answer, "refs": refs, "trace_id": res.trace_id, "intent": intent}
