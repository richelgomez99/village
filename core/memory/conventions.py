"""Agent Memory conventions (data-model.md §1): entities, scopes, labels, fact ids.

Pure functions only. One place decides how a village thing maps to an Agent Memory
entity so writes, history reads and the Fact view agree.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.settings import ROOT

ET = ZoneInfo("America/New_York")
DATA = ROOT / "data" / "villages"
FIXTURES = ROOT / "contracts" / "fixtures"

_MEMBER_RE = re.compile(r"^[a-z]_[a-z0-9_]{1,40}$")
_ID_SUFFIX = re.compile(r"\(([a-z]_[a-z0-9_]{1,40})\)\s*$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,60}$")


@lru_cache
def member_names() -> dict[str, str]:
    """member_id -> display name, read from every data/villages/*.json and the spec fixture."""
    names: dict[str, str] = {}
    for path in sorted(DATA.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for m in data.get("members", []) or []:
            if isinstance(m, dict) and m.get("id") and m.get("name"):
                names.setdefault(m["id"], m["name"])
    return names


def is_member(entity: str) -> bool:
    return bool(_MEMBER_RE.match(entity))


def am_entity(entity: str, village: str) -> dict[str, str]:
    """Village entity id -> Agent Memory entity {type, name} (closed type list)."""
    if entity == "village":
        return {"type": "organisation", "name": f"Village {village}"}
    if is_member(entity):
        name = member_names().get(entity, entity)
        return {"type": "person", "name": f"{name} ({entity})"}
    if entity.startswith("med_"):
        return {"type": "product", "name": entity}
    return {"type": "concept", "name": entity}


def entity_from_am(ref: str | None, village: str | None = None) -> str:
    """'entity:person/carmen_reyes_(m_carmen)' or a name -> village entity id."""
    if not ref:
        return "village"
    m = _ID_SUFFIX.search(ref)
    if m:
        return m.group(1)
    tail = ref.split("/")[-1].strip()
    if ref.startswith("entity:organisation") or tail.startswith("village_"):
        return "village"
    tail = re.sub(r"[^a-z0-9_]", "_", tail.lower()).strip("_")[:41] or "village"
    if not re.match(r"^[a-z]", tail):
        tail = "x_" + tail
    return tail


def village_scope(village: str) -> str:
    return f"village/{village}"


def member_scope(village: str, member: str) -> str:
    return f"village/{village}/{member}"


def scope_for(entity: str, village: str) -> str:
    return member_scope(village, entity) if is_member(entity) else village_scope(village)


def scope_chain(entity: str, village: str) -> list[str]:
    chain = ["village", village_scope(village)]
    if is_member(entity):
        chain.append(member_scope(village, entity))
    return chain


def make_labels(*, source: dict[str, Any], village: str, agent: str, event_id: str | None = None,
                rule_id: str | None = None, extra: dict[str, str] | None = None) -> list[str]:
    """Provenance labels: src=<kind>:<ref>, secs=, url=, agent=, village=, event=, rule=, quote=."""
    kind = source.get("kind", "system")
    ref = str(source.get("ref", "unknown"))
    labels = [f"src={kind}:{ref}"[:200]]
    if source.get("secs") is not None:
        labels.append(f"secs={_num(source['secs'])}")
    if source.get("url"):
        labels.append(f"url={source['url']}"[:200])
    labels += [f"agent={agent}", f"village={village}"]
    if event_id:
        labels.append(f"event={event_id}")
    if rule_id:
        labels.append(f"rule={rule_id}")
    if source.get("quote"):
        labels.append(("quote=" + str(source["quote"]).replace("\n", " "))[:126])
    for k, v in (extra or {}).items():
        labels.append(f"{k}={v}"[:200])
    return labels


def parse_labels(labels: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in labels or []:
        if isinstance(item, str) and "=" in item:
            k, v = item.split("=", 1)
            out.setdefault(k, v)
    return out


def source_from_labels(lab: dict[str, str]) -> dict[str, Any]:
    """Labels -> contract source{kind, ref, secs|url, quote}."""
    kind, _, ref = lab.get("src", "system:memory").partition(":")
    if kind not in {"call", "app", "scan", "url", "system"}:
        kind, ref = "system", ref or kind
    src: dict[str, Any] = {"kind": kind, "ref": (ref or "memory")[:200]}
    if kind == "call":
        try:
            src["secs"] = float(lab.get("secs", "0"))
            if src["secs"].is_integer():
                src["secs"] = int(src["secs"])
        except ValueError:
            src["secs"] = 0
    if kind == "url":
        src["url"] = lab.get("url") or "https://example.invalid/"
    if lab.get("quote"):
        src["quote"] = lab["quote"][:600]
    return src


def norm_key(key: str) -> str:
    k = re.sub(r"[^a-z0-9_]", "_", key.lower()).strip("_")
    if not re.match(r"^[a-z]", k):
        k = "k_" + k
    k = k[:61]
    return k if _KEY_RE.match(k) else "fact_key"


def to_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if len(s) == 10:
            s += "T00:00:00"
        s = s.replace("Z", "+00:00")
        m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", s)
        if m:  # trim nanoseconds to micro
            frac = (m.group(2) or "")[:7]
            s = m.group(1) + frac + m.group(3)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    return dt


def iso(value: Any, default: datetime | None = None) -> str:
    dt = to_dt(value) or default or datetime.now(timezone.utc)
    return dt.astimezone(ET).isoformat(timespec="seconds")


def utc_iso(value: Any) -> str:
    dt = to_dt(value) or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fact_id(key: str, entity: str, observed_at: Any) -> str:
    """Fact ref format: fact:<key>:<entity>:<YYYY-MM-DD> (ET date)."""
    day = (to_dt(observed_at) or datetime.now(ET)).astimezone(ET).date().isoformat()
    return f"fact:{key}:{entity}:{day}"[:200]


def _num(v: Any) -> str:
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)
