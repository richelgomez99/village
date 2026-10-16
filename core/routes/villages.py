"""Village list for the Control Room switcher (core-glue T4) and the printable fridge card (T7).

GET /villages                     control token -> [{id, name, status, kind, people_count, rev}]
GET /villages/{id}/print/fridge   control or that village's coordinator token -> HTML (design/FridgeCard)
Everything comes from the registry / live specs / builder runs (D30): no village literals."""
from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse

from core import village as villages
from core.auth import resolve_token
from core.clock import clock
from core.db import db

router = APIRouter(tags=["villages"])


def _token(authorization: str | None, t: str | None) -> str | None:
    return resolve_token(authorization) or resolve_token(t)


def _builder_runs() -> dict[str, Any]:
    try:
        from core.builder.founding import RUNS

        return RUNS
    except Exception:
        return {}


def village_row(village_id: str) -> dict[str, Any]:
    spec = villages.spec(village_id)
    v = spec.get("village", {})
    run = _builder_runs().get(village_id)
    status = v.get("status")
    if not status:
        status = "active" if village_id in villages.village_ids() else ("founding" if run is not None else "draft")
    if run is not None and not spec:
        status = "founding"
    return {
        "id": village_id,
        "name": v.get("name") or village_id,
        "status": status,
        "kind": v.get("kind") or spec.get("blueprint", {}).get("kind") or "care",
        "people_count": len(spec.get("blueprint", {}).get("people", [])),
        "rev": int(spec.get("rev", 0) or 0),
    }


@router.get("/villages")
async def list_villages(authorization: str | None = Header(default=None), t: str | None = None) -> list[dict[str, Any]]:
    if _token(authorization, t) != "control":
        raise HTTPException(status_code=401, detail="control token required")
    ids: list[str] = list(villages.village_ids())
    for vid in list(db.specs) + list(_builder_runs()):
        if vid and vid not in ids:
            ids.append(vid)
    return [village_row(vid) for vid in ids]


def _family_word(village_id: str) -> str | None:
    """Only from the builder's run (spoken during founding); never read from the spec (masked there)."""
    run = _builder_runs().get(village_id)
    return getattr(run, "family_word", None) if run is not None else None


def _pretty(phone: str) -> str:
    digits = phone[2:] if phone.startswith("+1") and len(phone) == 12 else None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if digits else phone


def fridge_html(village_id: str) -> str:
    spec = villages.spec(village_id)
    name = villages.village_name(village_id)
    number = villages.village_number(village_id)
    recipient = villages.care_recipient_id(village_id)
    word = _family_word(village_id)
    contacts = []
    for p in villages.people(village_id):
        if p.get("id") == recipient:
            continue
        phone = villages.member_phone(village_id, p.get("id"))
        if phone:
            contacts.append(f'<li><b>{escape(str(p.get("name", "")).split()[0])}</b> <span>{escape(_pretty(phone))}</span></li>')
    word_html = escape(word) if word else "__________"
    number_html = escape(_pretty(number)) if number else "(número pendiente · number pending)"
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Fridge card · {escape(name)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>:root{{--paper:#FFFFFF;--ink:#1A1511;--ink2:#4A4037;--line:#9A8C7C;--tomato:#A8331A;--sage:#2F6B57;--display:'Fraunces',Georgia,serif;--body:'Atkinson Hyperlegible','Noto Sans',system-ui,sans-serif}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body)}}.card{{max-width:640px;margin:24px auto;border:2px solid var(--ink);padding:24px}}
h1{{font-family:var(--display);margin:0 0 12px}}.money{{border-left:6px solid var(--tomato);padding-left:12px}}.sos{{color:var(--tomato);font-weight:700}}
.line{{font-size:32px;font-weight:700;color:var(--sage)}}ul{{list-style:none;padding:0}}li{{padding:4px 0;border-bottom:1px solid var(--line)}}small{{color:var(--ink2)}}</style></head>
<body><article class="card" data-village="{escape(village_id)}">
<h1>{escape(name)}</h1>
<section class="money"><p><b>Si alguien pide dinero:</b> <i>If anyone asks for money:</i></p>
<ol><li>Cuelgue. <i>Hang up.</i></li><li>Llame a Village. <i>Call Village. It checks with the real person.</i></li><li>No mande nada hoy. <i>Send nothing today.</i></li></ol></section>
<p class="sos" data-emergency="911">Emergencia: 911 primero. <i>Emergency: 911 first. Village is not for emergencies.</i></p>
<section><div>Village</div><div class="line" data-village-number="{escape(number or '')}">{number_html}</div>
<small>Contesta en español, día y noche. · Answers in Spanish, day and night.</small></section>
<section><div>Nuestra palabra familiar · family word</div><div class="word">{word_html}</div>
<small>Pregúntela a quien diga ser de la familia. · Ask anyone who says they're family.</small></section>
<ul class="contacts">{''.join(contacts)}</ul>
<small>Impreso por Village · {clock.now():%d %b %Y} · rev {int(spec.get('rev', 0) or 0)} · Village only ever calls from the number above.</small>
</article></body></html>"""


@router.get("/villages/{village_id}/print/fridge", response_class=HTMLResponse)
async def print_fridge(village_id: str, authorization: str | None = Header(default=None), t: str | None = None) -> HTMLResponse:
    who = _token(authorization, t)
    allowed = who == "control" or (who is not None and who == villages.coordinator_id(village_id))
    if not allowed:
        raise HTTPException(status_code=401, detail="control or coordinator token required")
    if not villages.spec(village_id):
        raise HTTPException(status_code=404, detail="unknown village")
    return HTMLResponse(fridge_html(village_id), headers={"Cache-Control": "no-store"})
