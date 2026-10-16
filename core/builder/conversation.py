"""Founding intake dialogue (operator LD-6/LD-7). A deterministic turn policy over blueprint gaps:
people → roles/contact → health → money/scams → coordination → household → rules/consent.
Village reflects back what it heard, asks one short question at a time, never asks what it already
knows, and stops when the picture is complete (`fast` = opener + 2 questions; `full` ≤ 12).
The same policy serves text founding (POST /villages/{id}/answers) and the voice Setup agent."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .paths import DATA

WEEKDAYS = {"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
            "lunes": "Mon", "martes": "Tue", "miercoles": "Wed", "jueves": "Thu", "viernes": "Fri", "sabado": "Sat", "domingo": "Sun"}
MED_WORDS = {"eliquis": "apixaban", "apixaban": "apixaban", "lisinopril": "lisinopril", "metformin": "metformin", "atorvastatin": "atorvastatin",
             "lipitor": "atorvastatin", "warfarin": "warfarin", "insulin": "insulin", "amlodipine": "amlodipine", "levothyroxine": "levothyroxine"}
HOUSEHOLD = {
    "groceries": r"grocer|bodega|shop(s|ping)?\b|bags|meals|comida|mercado",
    "insurance": r"medicare|medicaid|insurance|seguro|paperwork|bills|autopay",
    "appointments": r"appointment|cita|ride to|transport|doctor visits",
    "home": r"stairs|floors|stove|heat|escalera|fall\b",
    "keys": r"\bkeys\b|llaves|\bsuper\b",
    "social": r"lonely|sola\b|company|checks on her",
}


def fold(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c))


@dataclass(frozen=True)
class Slot:
    id: str
    category: str
    question: str  # {name} = center's first name or "your mom"


SLOTS = [
    Slot("center", "people", "What's {name_or_mom}'s name, and which language is easiest for her?"),
    Slot("people", "people", "Besides you{and_known}, who else is part of this — family, a neighbor, an aide?"),
    Slot("contact", "roles", "How does {name} like to be reached — phone, or would she use an app? And everyone else?"),
    Slot("health", "health", "What medications does {name} take, and who's her doctor?"),
    Slot("money", "money", "Has anyone tried to get money from {name} — calls, texts, someone pretending to be family?"),
    Slot("coordination", "coordination", "Who goes to see {name} on which days?"),
    Slot("household", "household", "And the rest of her week — groceries, bills, getting around, the apartment? Who has keys?"),
    Slot("worry", "rules", "Of all that, what worries you most?"),
    Slot("rules", "rules", "Any rules {name} would set herself — times not to call, things she doesn't want?"),
    Slot("consent", "consent", "Is it OK for Village to call you and the others to check things, like when someone asks her for money?"),
]
SLOT_IDS = [s.id for s in SLOTS]
MAX_QUESTIONS = {"fast": 2, "full": 12}


@dataclass
class Question:
    slot: str
    category: str
    reflection: str
    text: str
    n: int

    @property
    def say(self) -> str:
        return f"{self.reflection} {self.text}".strip()


@dataclass
class Done:
    reason: str
    gaps: list[str] = field(default_factory=list)


@dataclass
class ConversationState:
    opener: str
    mode: str = "full"
    turns: list[dict[str, str]] = field(default_factory=list)  # {slot, question, answer}
    asked: list[str] = field(default_factory=list)

    @property
    def answers_text(self) -> str:
        return "\n".join(t["answer"] for t in self.turns if t.get("answer"))

    @property
    def text(self) -> str:
        return self.opener + ("\n" + self.answers_text if self.answers_text else "")

    def answer_for(self, slot: str) -> str:
        return next((t["answer"] for t in self.turns if t["slot"] == slot and t.get("answer")), "")

    def add(self, slot: str, question: str, answer: str) -> None:
        self.turns.append({"slot": slot, "question": question, "answer": answer.strip()})

    def to_dict(self) -> dict[str, Any]:
        return {"opener": self.opener, "mode": self.mode, "turns": self.turns, "asked": self.asked}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConversationState":
        return cls(opener=d["opener"], mode=d.get("mode", "full"), turns=list(d.get("turns", [])), asked=list(d.get("asked", [])))


# ---- what Village knows ------------------------------------------------------------------------
def facts(state: ConversationState) -> dict[str, Any]:
    text = state.text
    f: dict[str, Any] = {}
    center_ans = state.answer_for("center")
    m = re.search(r"\b(?:se llama|her name is|mom'?s name is|named|mother,|mom,)\s+([A-Z][a-zá-ú]+)", text)
    if center_ans:
        nm = re.search(r"[A-ZÁÉÍÓÚ][a-zá-ú]+", center_ans)
        f["name"] = nm.group(0) if nm else None
    elif m:
        f["name"] = m.group(1)
    age = re.search(r"\b(seventy|eighty|ninety)(-\w+)?\b|\b([6-9]\d)\b(?= ?(?:years|y/o|,| and))", text, re.I)
    if age:
        words = {"seventy": 70, "eighty": 80, "ninety": 90}
        ones = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
        if age.group(1):
            f["age"] = words[age.group(1).lower()] + ones.get((age.group(2) or "-").strip("-").lower(), 0)
        else:
            f["age"] = int(age.group(3))
    place = re.search(r"\bin (Queens|Brooklyn|the Bronx|Manhattan|Staten Island|[A-Z][a-z]+ Heights)\b", text)
    if place:
        f["place"] = place.group(1)
    ft = fold(text)
    if re.search(r"spanish|espanol", ft):
        f["lang"] = "es"
    f["meds"] = sorted({MED_WORDS[w] for w in re.findall(r"[a-z]+", ft) if w in MED_WORDS})
    doc = re.search(r"\bDr\.? ([A-Z][a-z]+)(?: at ([A-Z][a-z]+))?", text)
    if doc:
        f["doctor"] = f"Dr. {doc.group(1)}" + (f" at {doc.group(2)}" if doc.group(2) else "")
    f["days"] = sorted({WEEKDAYS[w] for w in re.findall(r"[a-z]+?(?=s?\b)", ft) if w in WEEKDAYS}, key=list(WEEKDAYS.values()).index)
    f["household"] = [k for k, rx in HOUSEHOLD.items() if re.search(rx, ft)]
    f["phone_only"] = bool(re.search(r"won'?t use an app|flip phone|answer the phone|no apps?\b|doesn'?t do apps", ft))
    qh = re.search(r"(nueve y media|nine-?thirty|9:30|after (nine|9))", ft)
    if qh:
        f["quiet_hours"] = "21:30-07:00"
    f["outsiders"] = [o for o, rx in (("Mrs. Ortiz next door" if "ortiz" in ft else "a neighbor", r"neighbou?r|next door|vecin"), ("the super", r"\bsuper\b"), (f.get("doctor") or "her doctor", r"\bdr\.? "), ("the bodega", r"bodega")) if re.search(rx, ft)]
    return f


def known(state: ConversationState) -> dict[str, bool]:
    """Which slots are already covered — by an answer or by what was said anywhere."""
    t = fold(state.text)
    f = facts(state)
    answered = {x["slot"] for x in state.turns if x.get("answer")}
    k = {
        "center": bool(f.get("name")),
        "people": len(re.findall(r"\bmy (brother|sister|son|daughter|husband|wife|cousin|aunt|uncle)\b|neighbou?r|\baide\b|next door", t)) >= 2,
        "contact": f["phone_only"] or bool(re.search(r"smartphone|uses? the app|has the app", t)),
        "health": bool(f["meds"]) or bool(re.search(r"\b\d+\s?mg\b", t)),
        "money": bool(re.search(r"money|wired?|dinero|scam|pretending|gift card", t)),
        "coordination": len(f["days"]) >= 2,
        "household": len(f["household"]) >= 2 and bool({"home", "keys"} & set(f["household"])),
        "worry": bool(re.search(r"worr|scared|afraid|preocup|miedo|biggest", t)) or _domains(t) >= 3,
        "rules": bool(f.get("quiet_hours")) or bool(re.search(r"don'?t call|no calls after|quiet hours|never call", t)),
        "consent": bool(re.search(r"call me anytime|ok(ay)? to call|fine to call|it'?s fine to call|said it'?s fine|agreed to calls|prefers? texts|can call (me|him|her)", t)),
    }
    for s in answered:
        k[s] = True
    return k


def _domains(t: str) -> int:
    return sum(bool(re.search(rx, t)) for rx in (r"pill|medic|pastill", r"money|wired|dinero|scam", r"nobody went|turn|visit", r"lonely|alone|sola"))


def reflect(state: ConversationState) -> str:
    f = facts(state)
    name = f.get("name") or "She"
    if not state.turns:
        heard = []
        t = fold(state.opener)
        if re.search(r"pill|medic|pastill", t):
            heard.append("the pills")
        if re.search(r"money|wired|scam|pretending", t):
            m = re.search(r"pretending to be ([A-Z][a-z]+)", state.opener)
            heard.append(f"a money call in {m.group(1)}'s name" if m else "a money call")
        if re.search(r"nobody went|whose turn|each thought", t):
            heard.append("a missed visit")
        return ("I heard " + ", ".join(heard[:-1]) + (" and " if len(heard) > 1 else "") + heard[-1] + ".") if heard else "Got it."
    last = state.turns[-1]["slot"]
    if last == "center":
        bits = [b for b in (name, f.get("age") and str(f["age"]), f.get("place") and f"in {f['place']}") if b]
        return ", ".join(bits) + (", Spanish first." if f.get("lang") == "es" else ".")
    if last == "people":
        found = [n for n in re.findall(r"\b(?:brother|sister|son|daughter) ([A-Z][a-zá-ú]+)", state.answer_for("people"))]
        extra = [o for o in f["outsiders"] if "next door" in o or "neighbor" in o]
        return "So: you, " + ", ".join(found + extra) + "." if found or extra else "Got it."
    if last == "contact":
        return f"{name} by phone, no app; the rest of you on the app." if f["phone_only"] else "Got it."
    if last == "health":
        n = len(f["meds"])
        return f"{name} takes {n} medication{'s' if n != 1 else ''}; I'm checking them on DailyMed while we talk." if n else "Noted."
    if last == "money":
        return "That's exactly what Village checks before a dollar moves."
    if last == "coordination":
        return f"Got the days{'; Friday is refill day' if 'refill' in fold(state.answer_for('coordination')) else ''}."
    if last == "household":
        labels = {"groceries": "groceries", "insurance": "paperwork", "appointments": "appointments", "home": "the stairs", "keys": "keys", "social": "company"}
        return ", ".join(labels[h] for h in f["household"]).capitalize() + " — noted." if f["household"] else "Noted."
    if last == "rules":
        return f"No calls after 9:30 — {name}'s rule." if f.get("quiet_hours") else "Noted."
    return "Thanks."


def next_turn(state: ConversationState) -> Question | Done:
    k = known(state)
    gaps = [s for s in SLOTS if not k[s.id] and s.id not in state.asked]
    limit = MAX_QUESTIONS.get(state.mode, 12)
    if not gaps:
        return Done("complete")
    if len(state.asked) >= limit:
        return Done("enough for a first draft", [g.id for g in gaps])
    slot = gaps[0]
    f = facts(state)
    name = f.get("name") or "her"
    known_people = re.findall(r"pretending to be ([A-Z][a-z]+)|([A-Z][a-z]+) and I\b", state.opener)
    first_known = next((a or b for a, b in known_people), None)
    q = slot.question.format(name=name, name_or_mom="your mom" if not f.get("name") else name, and_known=f" and {first_known}" if first_known else "")
    return Question(slot.id, slot.category, reflect(state), q, len(state.asked) + 1)


def mark_asked(state: ConversationState, q: Question) -> None:
    state.asked.append(q.slot)


# ---- intake → needs (with spans into the founder's words) ------------------------------------
NEED_RULES = [
    ("n_groceries", r"bodega[^.]*|groceries[^.]*|can'?t carry bags[^.]*", "Groceries: shopping and carrying bags up the stairs", "logistics", "daily_living"),
    ("n_insurance", r"Medicare paperwork[^.]*|insurance[^.]*|Bills are on autopay[^.]*", "Insurance, Medicare paperwork and bills", "money", "money"),
    ("n_appointments", r"Dr\.? [A-Z][a-z]+ at [A-Z][a-z]+[^.]*|appointments?[^.]*", "Doctor appointments and getting there", "logistics", "daily_living"),
    ("n_home_safety", r"three floors|stairs[^.]*|stove[^.]*", "Home safety: three flights of stairs", "safety", "home"),
    ("n_keys", r"[Tt]he super has keys|keys[^.]*", "Who has keys (the super)", "safety", "home"),
    ("n_social", r"checks on her[^.]*|lonely[^.]*", "Company and check-ins from neighbors", "social", "people"),
]


def intake_needs(text: str, center_id: str | None) -> list[dict[str, Any]]:
    out, seen = [], set()
    for nid, rx, label, domain, area in NEED_RULES:
        m = re.search(rx, text)
        if not m or nid in seen:
            continue
        seen.add(nid)
        quote = m.group(0)[:80]
        out.append({"id": nid, "text": f"{label}: \"{quote}\""[:160], "priority": 4, "domain": domain, "life_area": area, "subject_member_ids": [center_id] if center_id else [], "source_span": {"start": m.start(), "end": m.start() + len(quote)}, "origin": "follow_up"})
    return out


def person_assignments(text: str, first_names: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Per person: weekdays and household areas named in the same sentence as their first name."""
    out: dict[str, dict[str, Any]] = {}
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        fs = fold(sentence)
        for first, pid in first_names.items():
            if re.search(rf"\b{fold(first)}\b", fs):
                rec = out.setdefault(pid, {"days": [], "areas": set(), "refill": False})
                if not re.search(rf"\b{fold(first)} (and I|thought)\b|pretending to be {fold(first)}", fs):
                    rec["days"] += [WEEKDAYS[w] for w in re.findall(r"[a-z]+?(?=s?\b)", fs) if w in WEEKDAYS]
                for k, rx in HOUSEHOLD.items():
                    if re.search(rx, fs):
                        rec["areas"].add({"groceries": "daily_living", "insurance": "money", "appointments": "daily_living", "home": "home", "keys": "home", "social": "people"}[k])
                rec["refill"] = rec["refill"] or "refill" in fs
    for rec in out.values():
        rec["days"] = sorted(set(rec["days"]), key=list(WEEKDAYS.values()).index)
        rec["areas"] = sorted(rec["areas"])
    return out


def load_transcript(path: Any = None) -> tuple[str, dict[str, str]]:
    """(opener, {slot: answer}) from a recorded founding transcript (jsonl)."""
    p = path or DATA / "builder" / "reyes_founding_transcript.jsonl"
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    opener = next(r["text"] for r in rows if r["slot"] == "opener")
    return opener, {r["slot"]: r["text"] for r in rows if r["slot"] != "opener"}
