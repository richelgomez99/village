from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("VILLAGE_LLM", "off")
os.environ.setdefault("BUILDER_PROMPT_SOURCE", "local")  # tests never call Prompt Hub unless they mock it
