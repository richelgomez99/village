import httpx

from core.memory.client import MemoryClient

CALL = {"kind": "call", "ref": "conv_setup_0003", "secs": 88, "quote": "five to ten"}


async def test_remember_supersedes_and_labels(client, fake):
    r1 = await client.remember_fact("m_carmen", "lisinopril_dose", "5 mg", source={"kind": "system", "ref": "seed"},
                                    village="v_reyes", agent="memory", observed_at="2026-09-01")
    r2 = await client.remember_fact("m_carmen", "lisinopril_dose", "10 mg", source=CALL, village="v_reyes",
                                    agent="memory", observed_at="2026-10-03", event_id="ev_1003_1740_med_change")
    assert not r1["degraded"] and not r2["degraded"]
    assert r2["corrections"][0]["oldValue"] == "5 mg"
    assert r2["fact_id"] == "fact:lisinopril_dose:m_carmen:2026-10-03"
    body = [b for m, p, b in fake.requests if p == "/facts"][-1]
    assert body["infer"] == "triples" and body["scopes"] == [["village/v_reyes/m_carmen"]]
    assert "src=call:conv_setup_0003" in body["labels"] and "secs=88" in body["labels"]
    assert "village=v_reyes" in body["labels"] and "agent=memory" in body["labels"]
    assert body["triples"][0]["entity"] == {"type": "person", "name": "Carmen Reyes (m_carmen)"}
    h = await client.fact_history("m_carmen", "lisinopril_dose", village="v_reyes")
    assert [x["value"] for x in h["history"]] == ["5 mg", "10 mg"]
    assert h["history"][0]["supersededBy"] == h["history"][1]["id"]


async def test_scopes_registered_once(client, fake):
    for v in ("1", "2", "3"):
        await client.remember_fact("m_carmen", "k_x", v, source=CALL, village="v_reyes", observed_at="2026-10-01")
    scope_posts = [p for m, p, b in fake.requests if p == "/scopes"]
    assert len(scope_posts) == 3  # village, village/v_reyes, village/v_reyes/m_carmen


async def test_scope_409_is_ok(fake):
    fake.scopes.update({"village", "village/v_reyes"})
    c = MemoryClient("https://am.test", "ctx", "sp", transport=fake.transport())
    assert await c.ensure_scopes("village", "v_reyes")


async def test_down_is_degraded_never_raises(client, fake):
    fake.down = True
    r = await client.remember_fact("m_carmen", "lisinopril_dose", "10 mg", source=CALL, village="v_reyes")
    assert r["degraded"] and r["degraded_reason"] == "memory_unreachable"
    assert (await client.fact_history("m_carmen", "lisinopril_dose"))["degraded"]
    assert (await client.facts_for("v_reyes", ["m_carmen"]))["degraded"]
    assert (await client.uncertainties("v_reyes"))["degraded"]
    assert (await client.resolve_uncertainty("unc_x", "10 mg", "m_ana"))["degraded"]
    assert (await client.query("lisinopril"))["degraded"]


async def test_timeout_reason():
    def boom(req):
        raise httpx.ReadTimeout("slow", request=req)
    c = MemoryClient("https://am.test", "ctx", "sp", transport=httpx.MockTransport(boom))
    r = await c.fact_history("m_carmen", "lisinopril_dose")
    assert r["degraded"] and r["degraded_reason"] == "memory_timeout"


async def test_5xx_degraded(client, fake):
    fake.status_override = 503
    r = await client.remember_fact("m_carmen", "k_y", "1", source=CALL, village="v_reyes")
    assert r["degraded"] and r["status"] == 503


async def test_unconfigured_is_degraded():
    c = MemoryClient("", "", "")
    assert (await c.query("x"))["degraded"]


async def test_facts_for_filters_village(client):
    await client.remember_fact("m_carmen", "lisinopril_dose", "10 mg", source=CALL, village="v_reyes", observed_at="2026-10-03")
    r = await client.facts_for("v_reyes", ["m_carmen", "m_ana"])
    assert not r["degraded"] and [f["value"] for f in r["facts"]] == ["10 mg"]


async def test_query_as_of(client):
    await client.remember_fact("m_carmen", "lisinopril_dose", "5 mg", source=CALL, village="v_reyes", observed_at="2026-09-01")
    await client.remember_fact("m_carmen", "lisinopril_dose", "10 mg", source=CALL, village="v_reyes", observed_at="2026-10-03")
    r = await client.query("lisinopril dose", as_of="2026-09-15T00:00:00Z", village="v_reyes")
    assert [h["text"].split()[-2] for h in r["hits"]] == ["5"]


async def test_uncertainty_list_and_resolve(client, fake):
    uid = fake.add_uncertainty("entity:person/carmen_reyes_(m_carmen)", "lisinopril_dose", "10 mg", "20 mg", "village/v_reyes/m_carmen")
    u = await client.uncertainties("v_reyes")
    assert u["uncertainties"][0]["id"] == uid
    r = await client.resolve_uncertainty("unc_" + uid, "10 mg", "m_ana")
    assert not r["degraded"]
    assert (await client.uncertainties("v_reyes"))["uncertainties"] == []
