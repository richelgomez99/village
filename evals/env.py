"""Load .env for eval scripts without leaking empty values (an empty
AWS_BEARER_TOKEN_BEDROCK makes the Bedrock Mantle client send 'Bearer ')."""

from __future__ import annotations

import os

from evals.reyes import ROOT


def load_env() -> None:
    try:
        from dotenv import dotenv_values
    except Exception:  # pragma: no cover
        return
    for key, value in dotenv_values(ROOT / ".env").items():
        if value and not os.environ.get(key):
            os.environ[key] = value
    for key in [k for k, v in os.environ.items() if v == "" and (k.startswith("AWS_") or k.startswith("ARIZE_"))]:
        os.environ.pop(key, None)
