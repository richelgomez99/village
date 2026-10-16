"""Extraction step: a call utterance -> a `report_money_request` request (or none).

Model path: core.llm.llm("haiku") with forced tool use (report_money_request |
not_a_money_request). Model-off path: a deterministic keyword extractor. Both return
the same shape so the gate step never knows which one ran.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from evals.reyes import ROOT, fold

SCHEMAS = ROOT / "contracts" / "schemas"


def _common_defs() -> dict[str, Any]:
    return json.loads((SCHEMAS / "common.schema.json").read_text())["$defs"]


METHODS = _common_defs()["money_method"]["enum"]
URGENCIES = _common_defs()["money_urgency"]["enum"]
RED_FLAGS = _common_defs()["money_red_flag"]["enum"]


@dataclass
class Extraction:
    tool: str  # report_money_request | not_a_money_request
    request: dict[str, Any] | None
    extractor: str  # model:<id> | rules
    ms: float
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- model path

SYSTEM = """You are the listening step of Village's Mom line for Carmen Reyes (78, Queens).
Family members in her village: Ana (daughter, coordinator), Marco (son), Lucía (daughter). Carmen is the care recipient.
Carmen is telling the line about a call, text or voicemail she got. Decide which tool to call:
- report_money_request: someone is asking Carmen to give, send, pay, lend, wire, move, buy gift cards/crypto for, or hand over money, OR to share card/bank/account/Social Security/Medicare numbers. Also when someone asks Village itself to send money for her.
- not_a_money_request: anything else (money coming TO her, bills already handled, reminders, appointments, offers of help, information).
For report_money_request:
- claimed_member: the family member (marco, ana, lucia) the requester claimed to be, or spoke for or about (a lawyer, hospital or police officer calling about Marco => marco). Omit it when the requester is anyone outside the village (grandchildren, friends, companies, government, bank, pharmacy).
- claimed_identity: who the requester said they were, in her words.
- red_flags: only values from the enum. Use asks_village_to_pay when she asks Village (Luz) itself to send money.
Never judge whether it is a scam; just extract."""


def _tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "name": "report_money_request",
            "description": "Report a request for money or account details made to Carmen. Core and the safety gate decide what to do.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "claimed_member": {"type": "string", "enum": ["marco", "ana", "lucia"]},
                    "claimed_identity": {"type": "string"},
                    "amount": {"type": "number", "minimum": 0},
                    "currency": {"type": "string"},
                    "method": {"type": "string", "enum": METHODS},
                    "urgency": {"type": "string", "enum": URGENCIES},
                    "red_flags": {"type": "array", "items": {"type": "string", "enum": RED_FLAGS}},
                },
                "required": ["urgency", "claimed_identity"],
            },
        },
        {
            "name": "not_a_money_request",
            "description": "Nothing is being asked of Carmen involving money or account details.",
            "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
        },
    ]


def model_client():
    """Return (client, model_id) or (None, reason) when the model is off/unavailable."""
    try:
        from core.llm import llm
        from core.settings import get_settings
    except Exception as exc:  # pragma: no cover
        return None, f"import:{type(exc).__name__}"
    client = llm("haiku")
    provider = getattr(client, "village_provider", getattr(client, "provider", "off"))
    if provider == "off":
        return None, "off"
    model = getattr(client, "village_model", None)
    if provider == "bedrock":
        model = get_settings().bedrock_haiku_model  # llm('haiku') maps to the sonnet slot; pin haiku
    return client, model


def extract_with_model(utterance: str, client: Any, model: str, timeout_s: float = 30.0) -> Extraction:
    t0 = time.perf_counter()
    msg = client.messages.create(
        model=model,
        max_tokens=400,
        system=SYSTEM,
        tools=_tool_defs(),
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": f"Carmen says: “{utterance}”"}],
        timeout=timeout_s,
    )
    ms = (time.perf_counter() - t0) * 1000
    block = next((b for b in msg.content if getattr(b, "type", "") == "tool_use"), None)
    if block is None:
        return Extraction("not_a_money_request", None, f"model:{model}", ms, error="no_tool_use")
    args = dict(block.input or {})
    if block.name != "report_money_request":
        return Extraction("not_a_money_request", None, f"model:{model}", ms, raw=args)
    return Extraction("report_money_request", _clean(args), f"model:{model}", ms, raw=args)


def _clean(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"urgency": args.get("urgency") if args.get("urgency") in URGENCIES else "unspecified"}
    if args.get("claimed_member"):
        out["claimed_member"] = fold(str(args["claimed_member"]))
    if args.get("claimed_identity"):
        out["claimed_identity"] = str(args["claimed_identity"])[:120]
    if isinstance(args.get("amount"), (int, float)) and args["amount"] >= 0:
        out["amount"] = args["amount"]
    out["currency"] = args.get("currency") if re.fullmatch(r"[A-Z]{3}", str(args.get("currency", ""))) else "USD"
    out["method"] = args.get("method") if args.get("method") in METHODS else "unknown"
    out["red_flags"] = sorted({f for f in args.get("red_flags", []) or [] if f in RED_FLAGS})
    return out


# ---------------------------------------------------------------- rules path

FAMILY = {"marco": "marco", "ana": "ana", "lucia": "lucia"}
ASK_VILLAGE = re.compile(r"\b(usted|luz|village)\b.*\b(mandar|mande|send|pay|pagar|transfer)\b.*\b(cuenta|account)\b")
MONEY = re.compile(
    r"d[oó]lar|dollar|dinero|money|\bcash\b|efectivo|tarjetas? de regalo|gift ?cards?|prepaid card|bitcoin|crypto|"
    r"zelle|cash app|western union|venmo|bail|fianza|savings|ahorros|\brenta\b|\brent\b|"
    r"mi tarjeta|my card|by card|con mi tarjeta|n[uú]mero|number|\bbank\b|cuenta|account|"
    r"cien|doscientos|quinientos|ochocientos|novecientos|mil\b|hundred|thousand|cincuenta|prestad|preste|"
    r"\bpague\b|\bpay\b"
)
ASK = re.compile(
    r"necesita|needs?\b|\bpide|pidi[oó]|asked me|have to pay|tengo que|i have to|i need to|unless i pay|"
    r"\bpague\b|\bmande\b|\bpase\b|compre|preste|prestados|regresarles|\blea\b|read (her|him|them)|"
    r"confirme|confirm my|take my cash|move my|double my|pasar mi|darles|courier|pick up the cash|"
    r"zelle|cash app|western union|mandar|send"
)
NOT_ASK = re.compile(
    r"paid me back|me paga|me debe|ya pag[oó]|pays it online|copay|mailed me|give him the .* back|"
    r"llegó mi tarjeta|bake sale|building pays|no compre nada|para recordarme|refill is ready|está lista|gratis"
)
NON_FAMILY_SPEAKER = re.compile(r"\b(nieto|nieta|grandson|granddaughter|danny|robert|friend|amigo|amiga)\b")
NUM_WORDS = {
    "cien": 100, "cincuenta": 50, "doscientos": 200, "trescientos": 300, "quinientos": 500, "ochocientos": 800,
    "novecientos": 900, "mil": 1000, "dos mil": 2000, "tres mil": 3000, "cuatro mil": 4000, "cinco mil": 5000,
    "mil quinientos": 1500, "hundred": 100, "four hundred": 400, "seven hundred": 700, "three hundred": 300,
    "eight thousand": 8000, "twelve hundred": 1200, "two hundred fifty": 250, "forty": 40, "twenty": 20,
}


def extract_with_rules(utterance: str) -> Extraction:
    t0 = time.perf_counter()
    text = fold(utterance)
    req: dict[str, Any] | None = None
    if ASK_VILLAGE.search(text):
        req = {"urgency": "unspecified", "red_flags": ["asks_village_to_pay"], "method": "bank_details"}
    elif MONEY.search(text) and ASK.search(text) and not NOT_ASK.search(text):
        req = {"urgency": "unspecified", "red_flags": []}
    if req is None:
        return Extraction("not_a_money_request", None, "rules", (time.perf_counter() - t0) * 1000)

    claimed = None
    if not NON_FAMILY_SPEAKER.search(text):
        for name, key in FAMILY.items():
            if re.search(rf"\b{name}\b", text):
                claimed = key
                break
    if claimed:
        req["claimed_member"] = claimed
        req["red_flags"].append("claimed_family_member")
    req["claimed_identity"] = claimed.capitalize() if claimed else "unknown caller"
    req.setdefault("method", _method(text))
    if any(w in text for w in ("right now", "ahora", "today", "hoy", "in an hour", "en una hora", "antes de")):
        req["urgency"] = "now"
    amount = _amount(text)
    if amount is not None:
        req["amount"] = amount
    req["currency"] = "USD"
    flag_words = {
        "secrecy": ("no le diga", "secret", "secreto"), "jail_bail": ("carcel", "arrest", "bail", "fianza", "preso"),
        "hospital": ("hospital",), "accident": ("accident", "choco", "atropello"), "new_number": ("new number", "different number"),
        "threat_arrest": ("police will", "policia"), "safe_account": ("safe account", "otra cuenta", "protected"),
        "prize": ("loteria", "lottery", "premio"), "voice_changed": ("se oia raro", "sounded"),
        "emotional_pressure": ("llorando", "crying"), "urgency": ("right now", "ahora", "today", "hoy", "in an hour"),
    }
    for flag, words in flag_words.items():
        if any(w in text for w in words):
            req["red_flags"].append(flag)
    hard = {"gift_card", "crypto", "wire_to_stranger", "cash_courier", "bank_details", "payment_app_to_stranger"}
    if req["method"] in hard:
        req["red_flags"].append(req["method"])
    req["red_flags"] = sorted(set(req["red_flags"]))
    return Extraction("report_money_request", req, "rules", (time.perf_counter() - t0) * 1000)


def _method(text: str) -> str:
    if re.search(r"tarjetas? de regalo|gift ?cards?|prepaid card", text):
        return "gift_card"
    if re.search(r"bitcoin|crypto", text):
        return "crypto"
    if "western union" in text or "wire" in text:
        return "wire_to_stranger"
    if re.search(r"zelle|cash app|venmo", text):
        return "payment_app_to_stranger" if re.search(r"companero|amiga|amigo|landlord|friend", text) else "payment_app"
    if "courier" in text:
        return "cash_courier"
    if re.search(r"numero|number|mi tarjeta|my card|by card|otra cuenta|safe account|confirme", text):
        return "bank_details"
    if re.search(r"efectivo|\bcash\b", text):
        return "cash"
    return "unknown"


def _amount(text: str) -> float | None:
    m = re.search(r"\$?\b(\d[\d,]*)\b", text)
    if m:
        return float(m.group(1).replace(",", ""))
    best = None
    for words, value in sorted(NUM_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{words}\b", text):
            best = value
            break
    return float(best) if best is not None else None


# ---------------------------------------------------------------- entry

def extract(utterance: str, mode: str = "auto", client: Any = None, model: str | None = None) -> Extraction:
    """mode: auto (model if on, else rules) | model | rules."""
    if mode == "rules":
        return extract_with_rules(utterance)
    if client is None:
        client, model = model_client()
    if client is None:
        if mode == "model":
            raise RuntimeError(f"model requested but unavailable ({model})")
        return extract_with_rules(utterance)
    try:
        return extract_with_model(utterance, client, model or "")
    except Exception as exc:
        if mode == "model":
            ex = extract_with_rules(utterance)
            ex.error = f"model_error:{type(exc).__name__}: {str(exc)[:160]}"
            ex.extractor = "rules(model_error)"
            return ex
        raise


def to_tool_request(ex: Extraction, utterance: str, case_id: str, village_id: str = "v_reyes") -> dict[str, Any] | None:
    """The full `req_report_money_request` body the voice agent would POST."""
    if ex.request is None:
        return None
    body = {
        "conversation_id": f"conv_eval_{case_id}",
        "caller_id": "m_carmen",
        "call_secs": 9,
        "utterance": utterance,
        "tool_call_id": f"toolu_eval_{case_id}",
        "village_id": village_id,
    }
    body.update(ex.request)
    return body


os.environ.setdefault("VILLAGE_EVALS", "1")
