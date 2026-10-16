import pytest

from core.release import run_release
from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals, FakeLLMClient, Recorder
from core.release.receipts import STAGES, validate_control, validate_receipt


async def _run(spec, rev, publisher, store, **kw):
    rec = Recorder()
    history = []
    args = dict(broadcast=rec, llm=None, daytona=FakeDaytona(), anchor=FakeAnchor(), evals=FakeEvals(),
                publisher=publisher, store=store, public_base="https://example.ts.net", history=history)
    args.update(kw)
    r = await run_release("v_reyes", spec, rev, **args)
    return r, history, rec


def _check_frames(rec):
    assert rec.receipts(), "no release frames"
    for _, kind, payload in rec.frames:
        frame = {"type": "control", "kind": kind, "payload": payload, "at": "2026-10-16T12:00:00-04:00"}
        assert validate_control(frame) == [], (kind, validate_control(frame))


async def test_released_all_six_stages(spec, publisher, store):
    r, history, rec = await _run(spec, 4, publisher, store)
    assert validate_receipt(r) == []
    assert [s["name"] for s in r["stages"]] == list(STAGES)
    assert all(s["status"] == "passed" for s in r["stages"])
    assert r["result"] == "released" and r["live_rev"] == 4 and r["previous_live_rev"] is None
    assert r["candidate_path"] == "/v/v_reyes/r/4/"
    assert publisher.published_rev("v_reyes") == 4
    qa = r["stages"][3]
    assert qa["details"]["live_view_url"].startswith("https://")
    assert any(e["kind"] == "screenshot" for e in qa["evidence_urls"])
    _check_frames(rec)
    assert store.all("v_reyes")[-1]["id"] == "rel_reyes_r4"


async def test_break_contrast_builder_fixes_its_own_build(spec, publisher, store):
    # rev 2 already live
    (publisher.dist_dir("v_reyes", 2)).mkdir(parents=True)
    (publisher.dist_dir("v_reyes", 2) / "index.html").write_text("r2")
    await publisher.publish("v_reyes", 2)
    r, history, rec = await _run(spec, 3, publisher, store, inject="contrast")
    assert [h["id"] for h in history] == ["rel_reyes_r3", "rel_reyes_r4"]
    r3, r4 = history
    assert validate_receipt(r3) == [] and validate_receipt(r4) == []
    assert r3["result"] == "blocked" and r3["live_rev"] == 2
    assert r3["stages"][2]["status"] == "failed"
    assert r3["stages"][2]["details"]["summary"] == "contrast 4.1:1 on elder Text (needs 7:1)"
    assert [s["status"] for s in r3["stages"][3:]] == ["skipped"] * 3
    assert r4["result"] == "released" and r4["live_rev"] == 4 and r4["attempt"] == 2
    assert r4["trigger"] == "repair" and r4["repair_of"] == "rel_reyes_r3"
    assert r4["previous_live_rev"] == 2
    assert "floor ink" in r4["stages"][0]["details"]["summary"]
    assert r is r4
    assert publisher.published_rev("v_reyes") == 4
    _check_frames(rec)


async def test_repair_with_llm_patch(spec, publisher, store):
    client = FakeLLMClient('{"patch":[{"path":"tones.info.fg","value":"#1F1A15"}],"why":"info text to floor ink for 7:1"}')
    r, history, _ = await _run(spec, 3, publisher, store, inject="contrast", llm=lambda role: client)
    assert len(history) == 2 and r["result"] == "released"
    assert "contrast 4.1:1" in client.prompts[0]
    assert history[1]["stages"][0]["details"]["summary"] == "info text to floor ink for 7:1"


async def test_repairs_exhausted_keeps_last_good(spec, publisher, store):
    (publisher.dist_dir("v_reyes", 2)).mkdir(parents=True)
    (publisher.dist_dir("v_reyes", 2) / "index.html").write_text("r2")
    await publisher.publish("v_reyes", 2)
    r, history, _ = await _run(spec, 3, publisher, store, daytona=FakeDaytona(always_fail=True))
    assert len(history) == 3 and [h["attempt"] for h in history] == [1, 2, 3]
    assert all(h["result"] == "blocked" and h["live_rev"] == 2 for h in history)
    assert all(validate_receipt(h) == [] for h in history)
    assert publisher.published_rev("v_reyes") == 2


async def test_build_failure_blocks(spec, publisher, store):
    r, history, _ = await _run(spec, 4, publisher, store, daytona=FakeDaytona(build_fail=True))
    assert r["result"] == "blocked" and r["stages"][1]["status"] == "failed"
    assert validate_receipt(r) == [] and len(history) == 1


async def test_anchor_failure_blocks(spec, publisher, store):
    r, _, _ = await _run(spec, 4, publisher, store, anchor=FakeAnchor(ok=False))
    assert r["result"] == "blocked" and r["stages"][3]["status"] == "failed"
    assert r["stages"][4]["status"] == "skipped" and r["live_rev"] is None
    assert validate_receipt(r) == []


async def test_anchor_degraded_still_passes(spec, publisher, store):
    r, _, _ = await _run(spec, 4, publisher, store, anchor=FakeAnchor(degraded=True))
    assert r["result"] == "released"
    assert r["stages"][3]["details"]["summary"].startswith("degraded")
    assert validate_receipt(r) == []


async def test_eval_failure_blocks(spec, publisher, store):
    r, _, _ = await _run(spec, 4, publisher, store, evals=FakeEvals(ok=False))
    assert r["result"] == "blocked" and r["stages"][4]["status"] == "failed"
    assert validate_receipt(r) == []


async def test_publish_false_stops_before_live(spec, publisher, store):
    r, _, _ = await _run(spec, 4, publisher, store, publish=False)
    assert r["result"] == "in_progress" and r["stages"][5]["status"] == "pending"
    assert publisher.published_rev("v_reyes") is None
    assert validate_receipt(r) == []


async def test_invalid_spec_blocks(spec, publisher, store):
    del spec["views"]
    r, _, _ = await _run(spec, 4, publisher, store)
    assert r["result"] == "blocked" and r["stages"][0]["status"] == "failed"
    assert validate_receipt(r) == []


async def test_real_evals_model_off(spec, publisher, store, tmp_path):
    from core.release.evals import ReleaseEvals

    r, _, _ = await _run(spec, 4, publisher, store, evals=ReleaseEvals(llm=None, mirror_dir=tmp_path / "evals"))
    ev = r["stages"][4]
    assert ev["status"] == "passed"
    assert ev["details"]["eval_scores"]["needs_coverage"] == 1.0
    assert (tmp_path / "evals" / "rel_reyes_r4.json").exists()
