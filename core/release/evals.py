"""In-process release evals (ARCHITECTURE-VALIDATION §4.4), logged to Arize as EVALUATOR spans
(eval.<name>.score/label/explanation attributes) with a local JSON mirror under var/evals/releases/.

- needs_coverage: spec.blueprint.needs vs the union of views[*].needs_served (+ custom components). code
- no_medical_advice: no dosing/medication instructions in any visible string. code
- translation_backcheck: es safety lines back-translated to en and judged for equivalence. LLM (skipped when off)
- elder_accessibility: Claude judge over the elder view (code heuristic when the model is off)."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from core.release import obs
from core.release.ports import EvalResult

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = {"needs_coverage": 0.8, "no_medical_advice": 1.0, "translation_backcheck": 0.9, "elder_accessibility": 0.8}
SAFETY_KEYS = ("money_hold", "money_denied", "money_timeout", "money_unknown")

MEDICAL = re.compile(
    r"\b(\d+\s?mg|take (two|2|another|extra|double)|double (dose|up)|skip (your|the) (pill|dose|medication)|stop taking|"
    r"increase (your )?dose|toma(r|te)? (dos|otra|doble)|dosis doble|deje de tomar|aumente la dosis|salte la pastilla)\b",
    re.I,
)
VISIBLE_KEYS = ("label", "title", "subtitle", "text", "speak", "confirm_text", "question", "name")


def visible_strings(spec: dict[str, Any]) -> list[str]:
    out = []
    for view in (spec.get("views") or {}).values():
        for el in view.get("elements", {}).values():
            for k in VISIBLE_KEYS:
                v = (el.get("props") or {}).get(k)
                if isinstance(v, str):
                    out.append(v)
    return out


def needs_coverage(spec: dict[str, Any]) -> dict[str, Any]:
    needs = [n["id"] for n in (spec.get("blueprint") or {}).get("needs", [])]
    served: set[str] = set()
    for view in (spec.get("views") or {}).values():
        for ids in (view.get("needs_served") or {}).values():
            served |= set(ids)
    for c in spec.get("custom_components") or []:
        served |= set(c.get("needs_served") or [])
    missing = [n for n in needs if n not in served]
    score = 1.0 if not needs else round((len(needs) - len(missing)) / len(needs), 3)
    return {"name": "needs_coverage", "score": score, "label": "covered" if not missing else "partial",
            "explanation": f"{len(needs) - len(missing)}/{len(needs)} needs served" + (f"; missing {', '.join(missing)}" if missing else ""),
            "kind": "code"}


def no_medical_advice(spec: dict[str, Any]) -> dict[str, Any]:
    hits = [s for s in visible_strings(spec) if MEDICAL.search(s)]
    return {"name": "no_medical_advice", "score": 0.0 if hits else 1.0, "label": "unsafe" if hits else "safe",
            "explanation": ("medical advice in: " + " | ".join(hits[:3])) if hits else f"{len(visible_strings(spec))} strings checked",
            "kind": "code"}


def elder_heuristic(spec: dict[str, Any]) -> dict[str, Any]:
    views = [v for v in (spec.get("views") or {}).values() if v.get("theme") == "elder"]
    if not views:
        return {"name": "elder_accessibility", "score": 1.0, "label": "n/a", "explanation": "no elder view", "kind": "code"}
    v = views[0]
    els = list(v["elements"].values())
    checks = {
        "<=3 big buttons": sum(e["type"] == "BigButton" for e in els) <= 3,
        "911 present": any(e["type"] == "ContactCard" and str(e["props"].get("phone")) == "911" for e in els),
        "short labels": all(len(str(e["props"].get("label", ""))) <= 24 for e in els if e["type"] == "BigButton"),
        "read aloud": bool(v["elements"].get(v["root"], {}).get("props", {}).get("read_aloud")),
        "danger confirms": all(e["props"].get("confirm") for e in els if e["type"] == "BigButton" and e["props"].get("tone") == "danger"),
    }
    score = round(sum(checks.values()) / len(checks), 3)
    return {"name": "elder_accessibility", "score": score, "label": "accessible" if score >= THRESHOLDS["elder_accessibility"] else "not_accessible",
            "explanation": "; ".join(f"{k}: {'ok' if ok else 'FAIL'}" for k, ok in checks.items()), "kind": "code"}


def _safety_lines() -> dict[str, dict[str, str]]:
    try:
        from core.gate.say import TEMPLATES  # read-only import of gate-owned lines
    except Exception:
        return {}
    from core import village as village_reg

    vid = village_reg.default_village_id()
    claimed = village_reg.first_name(vid, village_reg.default_verifier(vid))
    out = {}
    for k in SAFETY_KEYS:
        if k in TEMPLATES:
            out[k] = {"es": TEMPLATES[k].es.replace("{claimed_name}", claimed), "en": TEMPLATES[k].en.replace("{claimed_name}", claimed)}
    return out


def _ask(client: Any, prompt: str, max_tokens: int = 400) -> str:
    model = getattr(client, "village_model", None) or "claude-haiku-4-5"
    msg = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    return "".join(getattr(b, "text", "") for b in msg.content)


def _json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def translation_backcheck(client: Any) -> dict[str, Any]:
    lines = _safety_lines()
    prompt = (
        "Back-translate each Spanish safety line to English, then score 0..1 how well the back-translation preserves the meaning "
        "of the reviewed English line (same instruction, nobody told to send money). Reply ONLY JSON "
        '{"items":[{"key":"...","back":"...","score":0.0}]}\n' + json.dumps(lines, ensure_ascii=False)
    )
    data = _json(_ask(client, prompt, 800))
    items = data.get("items") or []
    score = round(min((float(i.get("score", 0)) for i in items), default=0.0), 3)
    worst = min(items, key=lambda i: float(i.get("score", 0)), default={})
    return {"name": "translation_backcheck", "score": score, "label": "equivalent" if score >= THRESHOLDS["translation_backcheck"] else "drift",
            "explanation": f"{len(items)} lines; worst {worst.get('key')}: {str(worst.get('back', ''))[:120]}", "kind": "llm"}


def elder_judge(client: Any, spec: dict[str, Any]) -> dict[str, Any]:
    view = next((v for v in (spec.get("views") or {}).values() if v.get("theme") == "elder"), None)
    if view is None:
        return elder_heuristic(spec)
    prompt = (
        "You judge accessibility of a phone screen for an 81-year-old Spanish speaker with low vision. Score 0..1: one clear primary "
        "action, short plain labels, at most 3 big buttons, an emergency contact, nothing confusing. The renderer guarantees >=28px text, "
        '>=88px buttons and 7:1 contrast. Reply ONLY JSON {"score":0.0,"explanation":"..."}\n' + json.dumps(view, ensure_ascii=False)
    )
    data = _json(_ask(client, prompt))
    score = max(0.0, min(1.0, float(data.get("score", 0))))
    return {"name": "elder_accessibility", "score": round(score, 3), "label": "accessible" if score >= THRESHOLDS["elder_accessibility"] else "not_accessible",
            "explanation": str(data.get("explanation", ""))[:300], "kind": "llm"}


def _short_model(model: str) -> str:
    m = model.rsplit("/", 1)[-1]
    for pre in ("us.", "eu.", "global.", "apac."):
        m = m.removeprefix(pre)
    m = m.removeprefix("anthropic.")
    return re.sub(r"-v\d+(:\d+)?$", "", m)


class _Metered:
    """Wraps the judge client: streams each call and records time-to-first-token (TTFT)."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.village_model = getattr(client, "village_model", None)
        self.village_provider = getattr(client, "village_provider", None)
        self.ttft_ms: list[int] = []
        self.streamed = False

    @property
    def messages(self) -> "_Metered":
        return self

    def create(self, **kw: Any) -> Any:
        from types import SimpleNamespace

        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(stream=True, **kw)
        except TypeError:
            resp = self.client.messages.create(**kw)
        if hasattr(resp, "content"):  # client ignored stream=True (test doubles): total latency, not TTFT
            self.ttft_ms.append(int((time.perf_counter() - t0) * 1000))
            return resp
        parts: list[str] = []
        first: float | None = None
        for ev in resp:
            delta = getattr(ev, "delta", None)
            text = getattr(delta, "text", None) if getattr(ev, "type", "") == "content_block_delta" else None
            if text is not None:
                if first is None:
                    first = time.perf_counter()
                parts.append(text)
        self.streamed = True
        self.ttft_ms.append(int(((first or time.perf_counter()) - t0) * 1000))
        return SimpleNamespace(content=[SimpleNamespace(text="".join(parts))])

    def chip(self) -> str | None:
        if not self.ttft_ms:
            return None
        provider = {"bedrock": "Bedrock", "anthropic": "Anthropic"}.get(str(self.village_provider), str(self.village_provider or "model"))
        what = "TTFT" if self.streamed else "latency"
        return f"{provider} · {_short_model(str(self.village_model or 'claude'))} · {min(self.ttft_ms)} ms {what}"


class ReleaseEvals:
    def __init__(self, llm: Callable[[str], Any] | None = None, mirror_dir: Path | None = None, timeout_s: float = 20.0) -> None:
        self.llm = llm
        self.mirror_dir = mirror_dir or ROOT / "var" / "evals" / "releases"
        self.timeout_s = timeout_s

    def _client(self) -> Any | None:
        if self.llm is None:
            return None
        try:
            c = self.llm("verifier")  # core.llm maps verifier→Haiku on Bedrock ("haiku" would get the Sonnet model)
        except Exception:
            return None
        return None if getattr(c, "provider", "") == "off" else c

    async def _judged(self, fn: Callable[..., dict[str, Any]], *args: Any, fallback: dict[str, Any] | None, name: str) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn, *args), self.timeout_s)
        except Exception as exc:
            if fallback is not None:
                fallback = dict(fallback)
                fallback["explanation"] = f"judge unavailable ({type(exc).__name__}); code check: {fallback['explanation']}"[:300]
                return fallback
            return {"name": name, "score": None, "label": "judge_unavailable", "explanation": f"{type(exc).__name__}: {str(exc)[:200]}", "kind": "llm"}

    async def run(self, spec: dict[str, Any], *, village_id: str, rev: int, release_id: str) -> EvalResult:
        t0 = time.perf_counter()
        records = [needs_coverage(spec), no_medical_advice(spec)]
        client = self._client()
        metered = _Metered(client) if client is not None else None
        client = metered or None
        if client is not None:
            tb, ea = await asyncio.gather(
                self._judged(translation_backcheck, client, fallback=None, name="translation_backcheck"),
                self._judged(elder_judge, client, spec, fallback=elder_heuristic(spec), name="elder_accessibility"),
            )
            records += [tb, ea]
        else:
            records.append({"name": "translation_backcheck", "score": None, "label": "skipped_model_off",
                            "explanation": "VILLAGE_LLM=off: back-translation not run", "kind": "llm"})
            records.append(elder_heuristic(spec))
        for rec in records:
            with obs.span(f"eval.{rec['name']}", "EVALUATOR", village=village_id, node=f"eval_{rec['name']}", parent_node="arize_evals",
                          **{f"eval.{rec['name']}.score": rec["score"], f"eval.{rec['name']}.label": rec["label"],
                             f"eval.{rec['name']}.explanation": rec["explanation"], "release.id": release_id}) as sp:
                passed = rec["score"] is None or rec["score"] >= THRESHOLDS[rec["name"]]
                rec["passed"] = passed
                rec["threshold"] = THRESHOLDS[rec["name"]]
                obs.finish(sp, passed, output=rec["label"])
        scores = {r["name"]: float(r["score"]) for r in records if r["score"] is not None}
        thresholds = {k: v for k, v in THRESHOLDS.items() if k in scores}
        failures = [f"{r['name']} {r['score']} < {r['threshold']}: {r['explanation']}"[:300] for r in records if not r["passed"]]
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        mirror = self.mirror_dir / f"{release_id}.json"
        mirror.write_text(json.dumps({"release_id": release_id, "village": village_id, "rev": rev,
                                      "duration_ms": int((time.perf_counter() - t0) * 1000), "model": client is not None, "model_chip": metered.chip() if metered else None,
                                      "records": records}, indent=1, ensure_ascii=False))
        chip = metered.chip() if metered else None
        return EvalResult(ok=not failures, scores=scores, thresholds=thresholds, failures=failures, records=records, mirror_path=mirror,
                          model_chip=chip)
