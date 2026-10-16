import asyncio
import json
import re

from evals import rounds_port
from evals.reyes import ROOT, seed_events


def test_rerun_scam_set_shape(monkeypatch, tmp_path):
    import evals.scam_experiment as se

    monkeypatch.setattr(se, "OUT", tmp_path)
    monkeypatch.setattr(se, "SETS", tmp_path)
    orig = se.run
    monkeypatch.setattr(se, "run", lambda mode, village, out_dir=None: orig(mode, village, out_dir=tmp_path))
    res = asyncio.run(rounds_port.rerun_scam_set("v_reyes"))
    for k in ("n_caught", "n_total", "n_false_alarms", "n_benign", "n_base", "n_village", "caught", "total"):
        assert k in res
    assert (res["n_total"], res["n_benign"], res["n_base"], res["n_village"]) == (30, 20, 50, 0)


def test_detect_patterns_port():
    ex = json.loads((ROOT / "contracts/schemas/event.schema.json").read_text())["examples"]
    today = next(e for e in ex if e["id"] == "ev_1016_1402_money")
    pats = asyncio.run(rounds_port.detect_patterns("v_reyes", seed_events("v_reyes") + [today]))
    assert pats and pats[0]["claimed_member_id"] == "m_marco" and pats[0]["evidence"]


def test_safety_path_imports_no_evals_memory_or_arize():
    """T007: the gate and the voice tool path stay deterministic."""
    files = list((ROOT / "core" / "gate").rglob("*.py")) + list((ROOT / "core" / "voice").glob("tools*.py"))
    pat = re.compile(r"^\s*(from|import)\s+(evals|arize|core\.memory|core\.obs)\b", re.M)
    offenders = [str(f) for f in files if pat.search(f.read_text())]
    assert offenders == []
