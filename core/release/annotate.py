"""Human-in-the-loop on Arize: the member's approval of a proposal becomes a `human_approval`
annotation (label "approved", score 1, updated_by = member id) on the release's AGENT span,
written with the Arize v8 SDK `client.spans.update_annotations(space_id, project_name, dataframe)`.

The span also always carries `human.approval = approved_by:<member>` (visible even when the
`arize` SDK or keys are missing). Never raises; annotation runs in the background because the
span must be exported and indexed first."""
from __future__ import annotations

import asyncio
import os
from typing import Any

LAST: dict[str, Any] = {}


def _write(span_id: str, member: str, label: str, score: float, note: str) -> dict[str, Any]:
    space, key = os.environ.get("ARIZE_SPACE_ID"), os.environ.get("ARIZE_API_KEY")
    if not space or not key:
        return {"ok": False, "error": "no_arize_keys"}
    try:
        import pandas as pd
        from arize.client import ArizeClient
    except Exception as exc:  # the `arize` SDK is optional (uv run --with arize)
        return {"ok": False, "error": f"arize_sdk_missing: {type(exc).__name__}"}
    try:
        df = pd.DataFrame({
            "context.span_id": [span_id],
            "annotation.human_approval.label": [label],
            "annotation.human_approval.score": [float(score)],
            "annotation.human_approval.updated_by": [member],
            "annotation.notes": [note],
        })
        ArizeClient(api_key=key).spans.update_annotations(
            space_id=space, project_name=os.environ.get("ARIZE_PROJECT_NAME", "village"), dataframe=df)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def _flush() -> None:
    try:
        from opentelemetry import trace

        trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]
    except Exception:
        pass


async def write_human_approval(span_id: str | None, member: str, *, release_id: str, label: str = "approved",
                               score: float = 1.0, delays: tuple[float, ...] = (5.0, 25.0, 60.0)) -> dict[str, Any]:
    """Retry while Arize indexes the span. Result kept in LAST[release_id]."""
    if not span_id:
        LAST[release_id] = {"ok": False, "error": "no_span"}
        return LAST[release_id]
    res: dict[str, Any] = {"ok": False, "error": "not_tried"}
    note = f"{member} approved {release_id} in Village"
    for d in delays:
        await asyncio.to_thread(_flush)
        await asyncio.sleep(d)
        res = await asyncio.to_thread(_write, span_id, member, label, score, note)
        if res["ok"] or "missing" in res.get("error", "") or res.get("error") == "no_arize_keys":
            break
    LAST[release_id] = {**res, "span_id": span_id, "member": member}
    return LAST[release_id]
