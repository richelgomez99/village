"""Never-raise Arize wrappers for in-process evals (Arize down must not break a call)."""

from __future__ import annotations

import os
from typing import Any


def update_evaluations(rows: list[dict[str, Any]], project: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    """rows: [{span_id, name, label, score, explanation}] -> Arize span evaluations.

    Returns {"ok": bool, "error"?: str}. Requires the `arize` SDK (v8) at runtime; tests mock it.
    """
    space, key = os.environ.get("ARIZE_SPACE_ID"), os.environ.get("ARIZE_API_KEY")
    if not space or not key:
        return {"ok": False, "error": "no_arize_keys"}
    rows = [r for r in rows if r.get("span_id")]
    if not rows:
        return {"ok": False, "error": "no_span_id"}
    try:
        import pandas as pd
        from arize.client import ArizeClient

        data: dict[str, list[Any]] = {"context.span_id": [r["span_id"] for r in rows]}
        for r in rows:
            n = r["name"]
            data.setdefault(f"eval.{n}.label", []).append(r["label"])
            data.setdefault(f"eval.{n}.score", []).append(float(r.get("score") or 0.0))
            data.setdefault(f"eval.{n}.explanation", []).append(r.get("explanation") or "")
        client = ArizeClient(api_key=key)
        client.spans.update_evaluations(space_id=space, project_name=project or os.environ.get("ARIZE_PROJECT_NAME", "village"),
                                        dataframe=pd.DataFrame(data), timeout=timeout)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
