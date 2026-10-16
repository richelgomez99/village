"""Founding intake (docs/FOUNDING-INTAKE.md, D29): ten topics from data/intake/plan.json. After every
answer: `record_answer` extraction (model tool call, or the rules extractor model-off) → coverage meter
→ side effects (founding.py) → the next highest-risk question (plan order: money and meds before home).
"I don't know" marks the field `unknown`: shown as a gap, never guessed, never re-asked."""
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .paths import DATA

UNKNOWN = "unknown"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_WORDS = {"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun"}
MED_WORDS = {"eliquis": "apixaban", "apixaban": "apixaban", "lisinopril": "lisinopril", "metformin": "metformin", "atorvastatin": "atorvastatin", "lipitor": "atorvastatin", "warfarin": "warfarin", "insulin": "insulin", "amlodipine": "amlodipine"}
NUMBER_WORDS = {"seventy": 70, "eighty": 80, "ninety": 90, "sixty": 60}
ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
DONT_KNOW = re.compile(r"\b(i don'?t know|not sure|no idea|no s[eé])\b", re.I)

RECORD_ANSWER_TOOL = {
    "name": "record_answer",
    "description": "Extract the structured intake fields stated in the founder's answer. Only what was said; omit anything not stated; use 'unknown' when they say they don't know.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["fields"],
        "properties": {
            "fields": {
                "type": "object",
                "description": "topic id → {field: value}. Topics/fields from the intake plan.",
                "additionalProperties": {"type": "object"},
            },
            "now_i_know": {"type": "string", "maxLength": 160},
        },
    },
}


def fold(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c))


@lru_cache
def plan(kind: str = "care") -> dict[str, Any]:
    from .registry import path

    return json.loads(path(kind, "plan").read_text(encoding="utf-8"))


def topics(kind: str = "care") -> list[dict[str, Any]]:
    return plan(kind)["topics"]


@dataclass
class Question:
    topic: str
    field: str
    text: str
    n: int


@dataclass
class Review:
    text: str


@dataclass
class IntakeState:
    opener: str = ""
    kind: str = "care"
    speaker: str = "you"
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    asked: list[str] = field(default_factory=list)  # "topic.field"
    transcript: list[dict[str, str]] = field(default_factory=list)  # {who, text, topic?}
    family_word: str | None = None  # never in frames, traces or the description

    def __post_init__(self) -> None:
        for t in topics(self.kind):
            self.fields.setdefault(t["id"], {})

    @property
    def topics(self) -> list[dict[str, Any]]:
        return topics(self.kind)

    def covered(self) -> list[str]:
        out = []
        for t in self.topics:
            f = self.fields[t["id"]]
            if all(f.get(r) not in (None, "", [], UNKNOWN) for r in t["required"]):
                out.append(t["id"])
        return out

    def gaps(self) -> list[str]:
        cov = set(self.covered())
        return [t["title"] for t in self.topics if t["id"] not in cov]

    def meter(self) -> str:
        n = len(self.covered())
        g = len(self.topics) - n
        return f"{n} of {len(self.topics)} covered · {g} gap{'s' if g != 1 else ''}"

    def answers_text(self, *, exclude_topics: tuple[str, ...] = ("money.family_word",)) -> str:
        return "\n".join(t["text"] for t in self.transcript if t["who"] == "founder" and t.get("ask") not in exclude_topics)

    def to_dict(self) -> dict[str, Any]:
        return {"fields": self.fields, "asked": self.asked, "covered": self.covered(), "meter": self.meter(), "gaps": self.gaps(), "family_word_set": bool(self.family_word)}


# ---- next question -----------------------------------------------------------------------------
def helper_name(state: IntakeState) -> str:
    members = state.fields.get("members", {}).get("members") or []
    if not isinstance(members, list):
        return "the main helper"
    local = [m for m in members if m.get("relation") != "self" and not m.get("remote")]
    return local[0]["name"] if local else "the main helper"


def next_question(state: IntakeState) -> Question | Review:
    for t in state.topics:
        for q in t["questions"]:
            key = f"{t['id']}.{q['field']}"
            val = state.fields[t["id"]].get(q["field"])
            if key in state.asked or val not in (None, "", []):
                continue
            if t["id"] == "center" and t["id"] in state.covered():
                continue
            return Question(t["id"], q["field"], q["text"].format(helper=helper_name(state)), len(state.asked) + 1)
    return Review(plan(state.kind)["review"]["text"])


# ---- rules extractor (model-off record_answer) -------------------------------------------------
def _days(text: str) -> list[str]:
    ft = fold(text)
    found = {DAY_WORDS[w] for w in re.findall(r"[a-z]+?(?=s?\b)", ft) if w in DAY_WORDS}
    return [d for d in DAYS if d in found]


def _sentences(text: str) -> list[str]:
    safe = re.sub(r"\b(Dr|Mr|Mrs|Ms|St)\. ", r"\1~ ", text)
    return [s.replace("~ ", ". ") for s in re.split(r"(?<=[.!?])\s+", safe) if s.strip()]


def extract(answer: str, q: Question | None, state: IntakeState) -> dict[str, dict[str, Any]]:
    """Plan-driven extraction: per-field `detect` regexes (any kind), the care extractors, then the
    asked field gets the founder's own words when nothing more specific matched."""
    out = _extract_care(answer, q, state) if state.kind == "care" else {}
    if q is not None and out.get(q.topic, {}).get(q.field) == UNKNOWN:
        return out
    for t in state.topics:
        for fld, rx in (t.get("detect") or {}).items():
            if state.fields[t["id"]].get(fld) or out.get(t["id"], {}).get(fld):
                continue
            m = re.search(rx, answer, re.I)
            if m:
                sent = next((x for x in _sentences(answer) if re.search(rx, x, re.I)), m.group(0))
                out.setdefault(t["id"], {})[fld] = sent.strip()[:160]
    if q is not None and not (q.topic == "money" and q.field == "family_word"):
        if DONT_KNOW.search(answer) and len(answer) < 60:
            out.setdefault(q.topic, {})[q.field] = UNKNOWN
        elif not out.get(q.topic, {}).get(q.field) and state.kind != "care":
            out.setdefault(q.topic, {})[q.field] = answer.strip()[:160]
    return out


def _extract_care(answer: str, q: Question | None, state: IntakeState) -> dict[str, dict[str, Any]]:
    """Fields stated in `answer` (any topic). The asked field gets `unknown` on 'I don't know'."""
    out: dict[str, dict[str, Any]] = {}
    ft = fold(answer)

    def put(topic: str, key: str, value: Any) -> None:
        if value not in (None, "", []):
            out.setdefault(topic, {})[key] = value

    if q is not None and DONT_KNOW.search(answer) and len(answer) < 60:
        put(q.topic, q.field, UNKNOWN)
        return out
    # 1 center
    age = re.search(r"\b(sixty|seventy|eighty|ninety)(?:-(\w+))?\b|\b([6-9]\d)\b", ft)
    if age and (q is None or q.topic == "center"):
        put("center", "age", NUMBER_WORDS[age.group(1)] + ONES.get(age.group(2) or "", 0) if age.group(1) else int(age.group(3)))
    lives = re.search(r"\b(?:alone|lives) in (Queens|Brooklyn|the Bronx|Manhattan|Staten Island|[A-Z][a-z]+ Heights)", answer)
    if lives:
        put("center", "lives", lives.group(1))
    probs = [p for p, rx in (("pills", r"pill|medic"), ("money", r"money|wired|pretending"), ("visits", r"nobody went|each thought")) if re.search(rx, ft)]
    if probs and (q is None or q.topic == "center"):
        put("center", "problems", probs)
    # 2 members
    if q is None or q.topic == "members" or re.search(r"\bsister\b|\bbrother\b", ft):
        members = []
        for rel, name in re.findall(r"\b(?:our|my) (sister|brother|son|daughter) ([A-ZÁÉÍÓÚ][a-zá-ú]+)", answer):
            members.append({"name": name, "relation": rel})
        named = re.findall(r"\b([A-ZÁÉÍÓÚ][a-zá-ú]+)(?:'s| is) in ([A-Z][a-z]+(?: [A-Z][a-z]+)?)", answer)
        for name, where in named:
            m = next((x for x in members if x["name"] == name), None) or {"name": name, "relation": "family"}
            m["lives"] = where
            if m not in members:
                members.append(m)
        for m in members:
            sent = next((s for s in _sentences(answer) if m["name"] in s), "")
            dist = re.search(r"(\w+(?:-\w+)?) minutes", sent)
            if dist:
                m["distance"] = f"{dist.group(1)} minutes"
            if re.search(r"in ([A-Z][a-z]+ [A-Z][a-z]+)", sent) and not m.get("lives"):
                m["lives"] = re.search(r"in ([A-Z][a-z]+ [A-Z][a-z]+)", sent).group(1)
        for s in _sentences(answer):
            for m in members:
                if m["name"] in s and re.search(r"refill|insurance|money|doctor", fold(s)):
                    m["takes_on"] = [w for w in ("refills", "insurance", "money", "doctor visits") if w.split()[0][:5] in fold(s)]
                if re.search(r"can'?t come|short notice", fold(s)) and m["name"] in s:
                    m["remote"] = True
        me = re.search(r"\bI'?m in ([A-Z][a-z]+)[^.]*?(\w+(?:-\w+)?) minutes", answer)
        if me:
            members.append({"name": state.speaker, "relation": "self", "lives": me.group(1), "distance": f"{me.group(2)} minutes"})
        if len([m for m in members if m["relation"] != "self"]) >= 1 and (q is None or q.topic == "members"):
            prior = state.fields["members"].get("members") or []
            names = {m["name"] for m in prior}
            put("members", "members", prior + [m for m in members if m["name"] not in names])
    # 3 availability
    if q is not None and q.topic == "availability":
        avail_sent = [s for s in _sentences(answer) if re.search(r"can do|evenings|after|mornings|\bI go\b", s, re.I)] or _sentences(answer)
        days = _days(" ".join(avail_sent)) if q.field == "helper_days" else _days(answer)
        rec: dict[str, Any] = {"days": days}
        c = re.search(r"works nights|leave by [\w-]+|sleeps until [\w ]+?(?=\.)", answer)
        if c:
            rec["constraints"] = [m.group(0) for m in re.finditer(r"works nights|has to leave by [\w-]+|sleeps until [\w ]+?(?=\.)", answer)]
        rem = re.search(r"text at (\w+)", answer)
        if rem:
            rec["reminder"] = f"text at {rem.group(1)}"
        window = re.search(r"after (\w+)", answer)
        if window:
            rec["after"] = window.group(1)
        if re.search(r"evenings", ft):
            rec["window"] = "evenings"
        if days:
            put("availability", q.field, rec)
        if re.search(r"doctor visits", ft):
            put("availability", "speaker_does", ["doctor visits"] + (["fills the organizer Sunday"] if "organizer" in ft else []))
    # 4 meds
    meds = []
    for w in re.findall(r"[a-z]+", ft):
        if w in MED_WORDS and MED_WORDS[w] not in [m["name"] for m in meds]:
            meds.append({"name": MED_WORDS[w], "said": w})
    if meds:
        for m in meds:
            sent = next((s for s in _sentences(answer) if m["said"] in fold(s)), "")
            fs = fold(sent)
            m["slots"] = [s for s in ("morning", "night", "evening") if s in fs] or (["morning", "night"] if "twice a day" in fs else [])
            ch = re.search(r"(doubled|bumped|changed)[^.]*?to (\w+) milligrams(?: on the (\w+))?", sent)
            if ch:
                nums = {"five": "5", "ten": "10", "twenty": "20", "two": "2", "forty": "40"}
                m["change"] = {"to": nums.get(ch.group(2), ch.group(2)), "when": ch.group(3) or "", "words": sent.strip()[:160]}
        put("meds", "meds", meds)
        dr = re.search(r"Dr\.? ([A-Z][a-z]+)", answer)
        put("meds", "prescriber", f"Dr. {dr.group(1)}" if dr else None)
        ph = re.search(r"(Farmacia [A-Z][\w ]+?|[A-Z]\w+ Pharmacy)(?: on (\w+))?(?= fills|[.,])", answer)
        put("meds", "pharmacy", (ph.group(1) + (f" on {ph.group(2)}" if ph.group(2) else "")) if ph else None)
        if re.search(r"old [\w ]*bottle", ft):
            put("meds", "risk", "old bottle still in the cabinet")
    # 5 routine
    if re.search(r"organizer|pastillero", ft) and (q is None or q.topic == "routine"):
        put("routine", "how_taken", "weekly organizer" + (" (yellow lid morning, blue lid evening)" if "yellow" in ft else ""))
    fails = re.search(r"[^.]*(calls me asking|took them twice|forgets)[^.]*", answer)
    if fails and (q is None or q.topic == "routine"):
        put("routine", "what_fails", fails.group(0).strip()[:160])
        if re.search(r"calls me", ft):
            put("routine", "who_called", state.speaker)
    # 6 money
    if q is not None and q.topic == "money" and q.field == "family_word":
        w = re.match(r"\s*[\"'“]?([A-Za-zÁÉÍÓÚáéíóúñÑ]+)", answer)
        if w:
            put("money", "family_word", "set")
            state.family_word = w.group(1)
        return out
    if re.search(r"saying he was|pretending|gift cards|wire", ft) and q is not None and q.topic == "money":
        amt = re.search(r"(fifteen hundred|two thousand|\$[\d,]+)", ft)
        put("money", "incident", ("caller claimed to be family" + (f", asked {amt.group(1)}" if amt else "") + (" in gift cards" if "gift card" in ft else ""))[:160])
    hd = re.search(r"([A-Z][a-z]+) handles her money", answer)
    put("money", "handler", hd.group(1) if hd else None)
    acc = re.search(r"(one checking account|checking account|savings account|one account)", ft)
    put("money", "accounts", acc.group(1) if acc else None)
    # 7 home
    if q is not None and q.topic == "home":
        times = re.findall(r"at (eight|eleven|seven(?:-thirty)?|nine|noon|\d{1,2}(?::\d\d)?)", ft)
        put("home", "routine", times and f"{len(times)} fixed times a day" or None)
        nearby = []
        nb = re.search(r"(Doña [A-Z][a-z]+|Mrs?\. [A-Z][a-z]+)?,? ?(?:her )?neighbou?r(?: on the (\w+) floor)?", answer)
        if nb:
            nearby.append(f"neighbor{' (' + nb.group(2) + ' floor)' if nb.group(2) else ''}")
        if re.search(r"\bsuper\b", ft):
            nearby.append("building super")
        put("home", "nearby", nearby)
        if re.search(r"walk-up|no elevator", ft):
            put("home", "building", "walk-up, no elevator")
        if re.search(r"blood pressure", ft):
            put("home", "bp_log", _days(answer))
    # 8 emergencies
    if "911" in answer:
        mem = state.fields.get("members", {}).get("members")
        names = [m["name"] for m in mem if isinstance(m, dict)] if isinstance(mem, list) else []
        alts = "|".join(re.escape(n) for n in names + [state.speaker] if n)
        order = re.findall(rf"911|\bme\b{'|' + alts if alts else ''}", answer)
        put("emergencies", "first", " → ".join(o if o != "me" else state.speaker for o in dict.fromkeys(order)))
    hosp = re.search(r"([A-Z][a-z]+) Hospital", answer)
    put("emergencies", "hospital", f"{hosp.group(1)} Hospital" if hosp else None)
    # 9 channels
    if q is not None and q.topic == "channels" or re.search(r"won'?t use apps?|regular phone|flip phone", ft):
        if re.search(r"spanish only|solo espanol|only spanish", ft):
            put("channels", "center_lang", "es")
        elif re.search(r"spanish", ft):
            put("channels", "center_lang", "es")
        if re.search(r"won'?t use apps?|regular phone|flip phone|answer a call", ft):
            put("channels", "center_channel", "phone")
        if re.search(r"big letters", ft):
            put("channels", "large_text", True)
        if re.search(r"won'?t read a text", ft):
            put("channels", "no_sms", True)
    # 10 consent
    if q is not None and q.topic == "consent":
        wc = re.search(r"(one-thirty|1:30)", ft) or re.search(r"(two o'?clock|after lunch|morning)", ft)
        put("consent", "welcome_call", "13:30" if wc and wc.group(1) in ("one-thirty", "1:30") else (wc.group(1) if wc else None))
        if re.search(r"calls at night|late|night", ft):
            put("consent", "center_rules", "pending her words (dislikes calls at night)")
    return out


def merge(state: IntakeState, found: dict[str, dict[str, Any]]) -> list[str]:
    """Merge extracted fields; returns topics newly covered."""
    before = set(state.covered())
    for topic, vals in found.items():
        if topic not in state.fields:
            continue
        for k, v in vals.items():
            if k == "family_word" and v not in ("set", UNKNOWN):
                state.family_word, v = str(v), "set"
            state.fields[topic][k] = deepcopy(v)
    return [t for t in state.covered() if t not in before]


def now_i_know(state: IntakeState, found: dict[str, dict[str, Any]], q: Question | None) -> str:
    f = state.fields
    bits: list[str] = []
    if state.kind != "care":
        return _generic_know(state, found, q)
    if "center" in found:
        c = f["center"]
        bits.append(", ".join(str(x) for x in (c.get("age") and f"{c['age']}", c.get("lives") and f"alone in {c['lives']}") if x) + (" · " + ", ".join(c.get("problems", [])) if c.get("problems") else ""))
    if "members" in found:
        bits.append("cards: " + " · ".join(m["name"] + (f" ({', '.join(m['takes_on'])})" if m.get("takes_on") else "") for m in found["members"].get("members", [])))
    if "availability" in found:
        for k, v in found["availability"].items():
            if isinstance(v, dict) and v.get("days"):
                who = helper_name(state) if k == "helper_days" else "you"
                bits.append(f"{who}: {'/'.join(v['days'])}" + (f" ({v['reminder']})" if v.get("reminder") else ""))
    if "meds" in found and found["meds"].get("meds"):
        ms = found["meds"]["meds"]
        ch = next((m for m in ms if m.get("change")), None)
        bits.append(f"{len(ms)} medications" + (f", {ch['name']} now {ch['change']['to']} mg" if ch else "") + (f", {f['meds'].get('prescriber')}" if f["meds"].get("prescriber") else ""))
    if "routine" in found:
        bits.append(f"organizer; unsure nights call {state.speaker}")
    if "money" in found:
        if found["money"].get("family_word"):
            bits.append("family word · set")
        else:
            bits.append(f"verifier: {f['money'].get('handler') or 'unknown'}" + (f", {f['money']['accounts']}" if f["money"].get("accounts") else ""))
    if "home" in found:
        bits.append("contacts: " + ", ".join(f["home"].get("nearby", [])))
    if "emergencies" in found:
        bits.append(f"{f['emergencies'].get('first', '')} · {f['emergencies'].get('hospital', '')}")
    if "channels" in found:
        bits.append(f"phone only, {'Spanish' if f['channels'].get('center_lang') == 'es' else f['channels'].get('center_lang', '')}")
    if "consent" in found:
        bits.append(f"welcome call {f['consent'].get('welcome_call', '?')} · quiet hours pending her words")
    if q is not None and found.get(q.topic, {}).get(q.field) == UNKNOWN:
        bits.append(f"{q.field.replace('_', ' ')}: unknown (a gap; I won't guess)")
    return "Now I know: " + "; ".join(b for b in bits if b) if bits else "Noted."


def _generic_know(state: IntakeState, found: dict[str, dict[str, Any]], q: Question | None) -> str:
    titles = {t["id"]: t["title"] for t in state.topics}
    bits = []
    for t, vals in found.items():
        for k, v in vals.items():
            bits.append(f"{titles.get(t, t).lower()}: {'unknown (a gap; I won’t guess)' if v == UNKNOWN else str(v)[:70]}")
    return "Now I know: " + "; ".join(bits) if bits else "Noted."


def med_names(state: IntakeState) -> list[str]:
    meds = state.fields.get("meds", {}).get("meds")
    if isinstance(meds, list) and meds:
        return [m["name"] for m in meds]
    if state.kind == "care":
        return []
    text = fold(state.opener + " " + " ".join(t["text"] for t in state.transcript))
    return sorted({MED_WORDS[w] for w in re.findall(r"[a-z]+", text) if w in MED_WORDS})


def load_intake(path: Any = None, kind: str = "care") -> list[dict[str, Any]]:
    from .registry import path as kpath

    return [json.loads(l) for l in open(path or kpath(kind, "intake"), encoding="utf-8") if l.strip()]


async def record_answer(answer: str, q: Question | None, state: IntakeState, llm: Any | None = None) -> dict[str, dict[str, Any]]:
    """Structured extraction: the model's `record_answer` when on (merged over the rules), rules otherwise."""
    rules = extract(answer, q, state)
    if llm is None:
        return rules
    try:
        out = await llm.tool_call(
            system="Extract intake fields from the founder's answer. Plan: " + json.dumps([{"id": t["id"], "required": t["required"], "optional": t.get("optional", [])} for t in state.topics]),
            messages=[{"role": "user", "content": json.dumps({"asked": q.text if q else None, "topic": q.topic if q else None, "answer": answer}, ensure_ascii=False)}],
            tool=RECORD_ANSWER_TOOL,
            max_tokens=1200,
        )
        model_fields = out.get("fields", {}) if isinstance(out, dict) else {}
        merged = deepcopy(rules)
        for t, vals in model_fields.items():
            if t in state.fields and isinstance(vals, dict):
                for k, v in vals.items():
                    merged.setdefault(t, {}).setdefault(k, v)
        return merged
    except Exception:
        return rules
