"""Ledger events -> Agent Memory facts with provenance (via the outbox).

`facts_from_event(event)` is pure: it returns fact drafts {entity, key, value,
observed_at, source, event_id, village, agent, text}. The subscriber enqueues them;
the outbox sends them later. Also the ledger mirror for degraded Fact views.
Kinds covered: dose, dose_repeat*, med_change (supersession: prior + new value on the
same key, in order), money_request, verification_*, incident, consent, shift,
call_*, release/spec_patch_applied. Operational kinds (qa, reminder, escalation, ack,
help_request) produce nothing (data-model.md §1).
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from core import village as village_reg
from core.memory import conventions as cv
from core.memory.outbox import Outbox
from core.settings import ROOT

AGENT = "memory"
SKIP = {"qa", "reminder", "escalation", "ack", "help_request", "pattern", "spec_patch_proposed",
        "village_activated", "invite_redeemed"}


def _vid(event: dict[str, Any]) -> str:
    return event.get("village") or event.get("village_id") or village_reg.default_village_id()


def _subject(event: dict[str, Any], p: dict[str, Any]) -> str:
    """Payload subject, else the village's care recipient (from its spec)."""
    return p.get("subject") or village_reg.care_recipient_id(_vid(event)) or "village"


def _draft(event: dict[str, Any], entity: str, key: str, value: Any, text: str, *,
           observed_at: Any = None, source: dict[str, Any] | None = None, role: str | None = None) -> dict[str, Any]:
    d = {
        "village": _vid(event),
        "entity": entity, "key": cv.norm_key(key), "value": str(value)[:400], "text": text[:300],
        "observed_at": cv.iso(observed_at or event.get("at")), "recorded_at": cv.iso(event.get("at")),
        "source": source or event.get("source") or {"kind": "system", "ref": "ledger"},
        "event_id": event.get("id"), "agent": AGENT, "rule_id": None,
    }
    if role:
        d["extra_labels"] = {"role": role}
    return d


def _prior_valid_from(payload: dict[str, Any], prescriptions: Iterable[dict[str, Any]] | None) -> str | None:
    frm = payload.get("from") or {}
    if frm.get("valid_from"):
        return frm["valid_from"]
    for rx in prescriptions or []:
        if rx.get("med_id") == frm.get("med_id") and rx.get("valid_from"):
            return rx["valid_from"]
    return None


def facts_from_event(event: dict[str, Any], prescriptions: Iterable[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    kind = event.get("kind", "")
    p = event.get("payload") or {}
    if kind in SKIP:
        return []
    if kind == "med_change":
        subj, med = _subject(event, p), p.get("med", "med")
        key = f"{med}_dose"
        eff = p.get("effective") or event.get("at")
        who = p.get("prescriber") or "the doctor"
        out = []
        frm = (p.get("from") or {}).get("dose")
        if frm:
            prior_at = _prior_valid_from(p, prescriptions) or (cv.to_dt(eff) - timedelta(days=30)).isoformat()
            rx = next((r for r in prescriptions or [] if r.get("med_id") == (p.get("from") or {}).get("med_id")), None)
            src = (rx or {}).get("source") or {"kind": "system", "ref": "seed"}
            out.append(_draft(event, subj, key, frm, f"{med.capitalize()} was {frm}.", observed_at=prior_at,
                              source=src, role="prior"))
        to = (p.get("to") or {}).get("dose", "")
        day = cv.to_dt(eff).strftime("%b %-d") if cv.to_dt(eff) else str(eff)
        out.append(_draft(event, subj, key, to, f"{med.capitalize()} is {to} since {day} ({who}).", observed_at=eff))
        return out
    if kind == "dose":
        t = p.get("taken_at") or event.get("at")
        hhmm = cv.to_dt(t).strftime("%-I:%M %p") if cv.to_dt(t) else t
        return [_draft(event, _subject(event, p), "last_dose_taken", cv.iso(t),
                       f"{p.get('slot', '').capitalize()} pills logged at {hhmm} via {p.get('via', '?')}.", observed_at=t)]
    if kind in ("dose_repeat_scan", "dose_repeat"):
        return [_draft(event, _subject(event, p), "last_repeat_dose_attempt",
                       f"{p.get('slot', '?')} {cv.iso(event.get('at'))}", "Tried to log the same pills twice; blocked.")]
    if kind == "money_request":
        amt = p.get("amount")
        txt = f"Money request: ${amt:,} {p.get('method', '')} claimed by {p.get('claimed_identity', '?')}." if isinstance(amt, (int, float)) \
            else f"Money request claimed by {p.get('claimed_identity', '?')}."
        return [_draft(event, _subject(event, p), "last_money_request",
                       f"{event.get('id')}: {amt} {p.get('currency', '')} {p.get('method', '')} claimed {p.get('claimed_identity', '?')}", txt)]
    if kind.startswith("verification_"):
        vid = p.get("verification_id", "ver_unknown")
        state = p.get("state") or kind.removeprefix("verification_")
        return [_draft(event, cv.norm_key(vid), "verification_outcome", state,
                       f"Check with {p.get('claimed_member_id', '?')}: {state.replace('_', ' ')}.")]
    if kind == "incident":
        title = (p.get("title") or {}).get("en", p.get("type", "incident"))
        return [_draft(event, "village", "last_incident", f"{p.get('type')} {p.get('incident_id')} {p.get('status')}",
                       f"Incident: {title} ({p.get('status')}).")]
    if kind == "consent":
        mid = p.get("member_id", "m_unknown")
        return [_draft(event, mid, f"consent_{scope}", "true" if bool(val) else "false",
                       f"{cv.member_names().get(mid, mid).split()[0]} {'agreed to' if val else 'declined'} {scope.replace('_', ' ')}.")
                for scope, val in sorted((p.get("scopes") or {}).items())]
    if kind == "shift":
        date = p.get("date", "")
        nm = cv.member_names().get(p.get("on_duty", ""), p.get("on_duty", "?")).split()[0]
        return [_draft(event, "village", f"on_duty_{date.replace('-', '_')}", p.get("on_duty", ""),
                       f"{nm} is on for {date} ({p.get('change', 'assigned')}).", observed_at=event.get("at"))]
    if kind.startswith("call_"):
        return [_draft(event, "village", f"last_{kind}", f"{p.get('conversation_id')} {p.get('reason', '')}".strip(),
                       f"Call {kind.removeprefix('call_')}: {p.get('reason', '')}.")]
    if kind in ("release", "spec_patch_applied"):
        rev = p.get("live_rev") or p.get("rev")
        return [_draft(event, "village", "published_rev", rev, f"Live app is rev {rev}.")]
    return []


def draft_item_id(d: dict[str, Any]) -> str:
    return f"{d.get('event_id') or 'noevent'}:{d['entity']}:{d['key']}:{d['value']}"[:300]


class LedgerSubscriber:
    """Turns ledger rows into outbox items. Never awaits the network."""

    def __init__(self, outbox: Outbox, *, prescriptions: Any = None,
                 voice_dir: Path | str | None = None) -> None:
        self.outbox = outbox
        self._prescriptions = prescriptions  # callable(village) -> list, or None (core.db)
        self.voice_dir = Path(voice_dir or os.getenv("VOICE_MEMORY_OUTBOX", str(ROOT / "core" / "voice" / "memory_outbox")))
        self._task: asyncio.Task | None = None
        self._consumed_path = outbox.path.parent / "voice_consumed.json"

    def _rx(self, village: str) -> list[dict[str, Any]]:
        if callable(self._prescriptions):
            return self._prescriptions(village) or []
        try:
            from core.db import db
            return db.prescriptions.get(village, [])
        except Exception:  # noqa: BLE001
            return []

    def on_event(self, event: dict[str, Any]) -> int:
        """Enqueue facts for one ledger row. Returns how many were new."""
        n = 0
        for d in facts_from_event(event, self._rx(_vid(event))):
            args = {k: d[k] for k in ("entity", "key", "value", "source", "village", "agent", "observed_at", "event_id", "rule_id")}
            if d.get("extra_labels"):
                args["extra_labels"] = d["extra_labels"]
            n += self.outbox.enqueue(draft_item_id(d), "fact", args)
        return n

    # ---------------------------------------------------------- voice post-call outbox
    def _consumed(self) -> set[str]:
        try:
            return set(json.loads(self._consumed_path.read_text()))
        except (OSError, ValueError):
            return set()

    def consume_voice_outbox(self) -> int:
        """Read core/voice post-call files ({conversation_id}.json) -> transcript + last_call fact."""
        if not self.voice_dir.is_dir():
            return 0
        done = self._consumed()
        n = 0
        for f in sorted(self.voice_dir.glob("*.json")):
            if f.name in done:
                continue
            try:
                payload = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            n += self.on_post_call(payload)
            done.add(f.name)
        self._consumed_path.parent.mkdir(parents=True, exist_ok=True)
        self._consumed_path.write_text(json.dumps(sorted(done)))
        return n

    def on_post_call(self, payload: dict[str, Any]) -> int:
        data = payload.get("data", payload)
        conv = payload.get("conversation_id") or data.get("conversation_id") or "unknown_conversation"
        village = payload.get("village_id") or (payload.get("dynamic_variables") or {}).get("village_id") or village_reg.default_village_id()
        member = payload.get("member_id") or (payload.get("dynamic_variables") or {}).get("member_id") or village_reg.care_recipient_id(village) or "village"
        transcript = data.get("transcript") or payload.get("transcript") or []
        lines = []
        if isinstance(transcript, list):
            for t in transcript:
                if isinstance(t, dict) and t.get("message"):
                    lines.append(f"{t.get('role', 'user')}: {t['message']}")
        elif isinstance(transcript, str):
            lines.append(transcript)
        secs = (data.get("metadata") or {}).get("call_duration_secs") or 0
        at = payload.get("at") or (data.get("metadata") or {}).get("start_time_unix_secs")
        src = {"kind": "call", "ref": conv, "secs": secs}
        n = 0
        if lines:
            n += self.outbox.enqueue(f"transcript:{conv}", "transcript", {
                "conversation_id": conv, "text": "\n".join(lines), "village": village, "entity": member,
                "source": src, "agent": "voice:post_call", "observed_at": at if isinstance(at, str) else None})
        summary = ((data.get("analysis") or {}).get("transcript_summary") or payload.get("summary") or f"call {conv}")[:400]
        n += self.outbox.enqueue(f"{conv}:last_call", "fact", {
            "entity": member if cv.is_member(member) else "village", "key": "last_call", "value": summary,
            "source": src, "village": village, "agent": "voice:post_call",
            "observed_at": at if isinstance(at, str) else None, "event_id": None, "rule_id": None})
        return n

    # ---------------------------------------------------------- live wiring
    async def _run(self, queue: asyncio.Queue) -> None:
        while True:
            table, row = await queue.get()
            if table == "event":
                try:
                    self.on_event(row)
                except Exception:  # noqa: BLE001 - never break the ledger fan-out
                    pass

    def start(self, db: Any) -> asyncio.Task:
        """Subscribe to core.db publish fan-out (db.subscribe() -> Queue[(table, row)])."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(db.subscribe()), name="memory-ledger-subscriber")
        return self._task

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
