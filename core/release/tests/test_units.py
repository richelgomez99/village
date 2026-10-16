import json

from core.release import bundle, floor_tests, repair
from core.release.contrast import ratio
from core.release.evals import elder_heuristic, needs_coverage, no_medical_advice
from core.release.fakes import FakeLLMClient
from core.release.daytona_svc import parse_vitest


def test_contrast_matches_wcag():
    assert round(ratio("#000000", "#FFFFFF"), 1) == 21.0
    assert ratio(bundle.BROKEN_INFO_FG, "#FFFFFF") < 4.2
    assert ratio(bundle.BROKEN_INFO_FG, "#FFFFFF") >= 4.1


def test_floor_test_render_covers_the_floor():
    src = floor_tests.render("v_reyes", 4)
    for needle in ("floor/contrast", "floor/sizes", "floor/safety_colors", "floor/catalog", "floor/elder_view",
                   "floor/no_network", '"elder_button_px": 88', '"elder_actionable_px": 28', '"elder_min_px": 22',
                   '"elder_contrast": 7.0', "911", '"#A8331A"', '"#2E6F42"', "v_reyes rev 4"):
        assert needle in src, needle


def test_bundle_strips_printables_and_injects(spec):
    files = bundle.build(spec, 3, inject="contrast")
    pub = json.loads(files["src/village/spec.json"])
    assert "printables" not in pub and pub["rev"] == 3 and set(pub["views"]) == {"elder", "coordinator", "helper"}
    theme = json.loads(files["src/village/theme.json"])
    assert theme["tones"]["info"]["fg"] == bundle.BROKEN_INFO_FG
    assert "tests/floor/floor.test.ts" in files and "package.json" in files and "src/render.ts" in files
    assert not any(k.startswith("node_modules") for k in files)
    clean = json.loads(bundle.build(spec, 4)["src/village/theme.json"])
    assert ratio(clean["tones"]["info"]["fg"], clean["tones"]["info"]["bg"]) >= 7


def test_template_theme_meets_floor():
    th = bundle.base_theme()
    assert th["safety"] == floor_tests.FLOOR["safety"]
    assert th["floor"]["paper"] == "#FBF6EE" and th["floor"]["ink"] == "#1F1A15"
    assert th["floor"]["tomato"] == "#A8331A" and th["floor"]["ok"] == "#2E6F42" and th["floor"]["sage"] == "#2F6B57"
    assert repair.failing_tones(th) == []


def test_deterministic_repair():
    th = bundle.inject_failure(bundle.base_theme(), "contrast")
    res = repair.repair(th, ["contrast 4.1:1"], llm=None)
    assert res.mode == "deterministic" and res.changed == ["tones.info.fg"]
    assert res.theme["tones"]["info"]["fg"] == "#1F1A15"
    assert res.summary == "elder info tone mapped to floor ink"


def test_llm_repair_rejects_bad_patch_then_falls_back():
    th = bundle.inject_failure(bundle.base_theme(), "contrast")
    bad = FakeLLMClient('{"patch":[{"path":"safety.stopped","value":"#000000"}]}')
    res = repair.repair(th, ["x"], llm=lambda r: bad)
    assert res.mode == "deterministic" and "not allowed" in (res.llm_error or "")
    weak = FakeLLMClient('{"patch":[{"path":"tones.info.fg","value":"#5A86B5"}]}')
    res = repair.repair(th, ["x"], llm=lambda r: weak)
    assert res.mode == "deterministic" and "still fails" in (res.llm_error or "")


def test_llm_off_client_falls_back():
    from core.llm import OffClient

    th = bundle.inject_failure(bundle.base_theme(), "contrast")
    res = repair.repair(th, ["x"], llm=lambda r: OffClient(role=r))
    assert res.mode == "deterministic" and "LLMOff" in (res.llm_error or "")


def test_evals_code_checks(spec):
    nc = needs_coverage(spec)
    assert nc["score"] == 1.0 and nc["label"] == "covered"  # rev 5 (1.2.0) serves n_refills via RefillCard
    for view in spec["views"].values():
        view["needs_served"] = {k: [n for n in v if n != "n_refills"] for k, v in (view.get("needs_served") or {}).items()}
    for c in spec.get("custom_components") or []:
        c["needs_served"] = [n for n in c.get("needs_served") or [] if n != "n_refills"]
    part = needs_coverage(spec)
    assert part["score"] < 1.0 and "n_refills" in part["explanation"]
    assert no_medical_advice(spec)["score"] == 1.0
    assert elder_heuristic(spec)["score"] == 1.0
    spec["views"]["elder"]["elements"]["b_village"]["props"]["label"] = "Tome dos pastillas, 20 mg"
    assert no_medical_advice(spec)["score"] == 0.0


def test_parse_vitest():
    report = {"numPassedTests": 45, "numFailedTests": 1, "testResults": [{"name": "/home/daytona/app/tests/floor/floor.test.ts",
              "assertionResults": [{"status": "failed", "ancestorTitles": ["floor/contrast"], "title": "elder BigButton tone=info #b_call contrast >= 7:1",
                                    "failureMessages": ["AssertionError: contrast 4.1:1 on elder Text (x) < 7:1: expected false to be true\n at ..."]}]}]}
    p, f, fails = parse_vitest(report)
    assert (p, f) == (45, 1)
    assert fails[0].startswith("floor.test.ts › floor/contrast › elder BigButton tone=info")
    assert "contrast 4.1:1 on elder Text" in fails[0]


def test_anchor_assertions_elder_and_other():
    from core.release.anchor_qa import assertions_from

    btn = {"id": "b", "text": "x", "h": 88, "fs": 28, "visible": True}
    elder = assertions_from({"theme": "elder", "buttons": [btn] * 3, "e911": [{"visible": True, "h": 90}], "title": "Hola"})
    assert all(a["ok"] for a in elder) and len(elder) == 5
    assert not all(a["ok"] for a in assertions_from({"theme": "elder", "buttons": [btn] * 2, "e911": [], "title": "x"}))
    other = assertions_from({"theme": "family", "buttons": [dict(btn, h=56)], "e911": [], "title": "Block"})
    assert all(a["ok"] for a in other)


def test_template_catalog_matches_contract():
    import json
    import re

    enum = json.loads((bundle.ROOT / "contracts/schemas/village_spec.schema.json").read_text())["$defs"]["catalog_type"]["enum"]
    ts = (bundle.TEMPLATE_DIR / "src/catalog.ts").read_text()
    listed = re.findall(r'"([A-Z][A-Za-z]+)"', ts.split("export const CATALOG = [")[1].split("] as const")[0])
    assert listed == enum
