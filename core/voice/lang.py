"""Bilingual tool responses: Core's services speak Spanish; the presenter playing Carmen may speak English.

`bilingual(response, lang, body)` rebuilds the gate template (`say_key`) in both languages with the village's names.
It switches `say` to English only when the rebuilt Spanish line equals Core's original `say` (so the English line is
the same template, never a paraphrase); otherwise `say` stays exactly as Core returned it. Both lines land in
`data.say_es` / `data.say_en` for the projector captions (D18).
"""
from __future__ import annotations

import copy
from typing import Any

from core import village


def _vars(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    vid = body.get("village_id") or village.default_village_id()
    data = response.get("data") or {}
    claimed = data.get("claimed_member_id") or body.get("claimed_member_id") or village.default_verifier(vid)
    coordinator = village.first_name(vid, village.coordinator_id(vid))
    return {
        "claimed_name": village.first_name(vid, claimed) if claimed else "",
        "pronoun": village.pronoun(village.person(vid, claimed)) if claimed else "",
        "coordinator_name": coordinator,
        "on_duty_name": coordinator,
        "recipient_name": village.first_name(vid, village.care_recipient_id(vid)),
    }


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def bilingual(response: dict[str, Any], lang: str | None, body: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or not response.get("say"):
        return response
    out = copy.deepcopy(response)
    data = out.setdefault("data", {}) if isinstance(out.get("data", {}), dict) else {}
    es, en = (out["say"], "") if out.get("lang", "es") == "es" else ("", out["say"])
    key = out.get("say_key")
    if data.get("say_es") or data.get("say_en"):  # handler already returned both lines
        es, en, key = data.get("say_es", ""), data.get("say_en", ""), None
    if key:
        try:
            from core.gate.say import say as gate_say

            pair = gate_say(key, **_vars(body, out))
            if _norm(pair["es"]) == _norm(out["say"]) or _norm(pair["en"]) == _norm(out["say"]):
                es, en = pair["es"], pair["en"]
        except Exception:
            pass
    data["say_es"], data["say_en"] = es, en
    out["data"] = data
    want = "en" if str(lang or "").lower().startswith("en") else "es"
    if want == "en" and en:
        out["say"], out["lang"] = en, "en"
    elif want == "es" and es:
        out["say"], out["lang"] = es, "es"
    return out
