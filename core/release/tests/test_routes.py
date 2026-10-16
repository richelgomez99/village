from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.release import routes
from core.release.serve import LocalPublisher


def test_candidate_and_published_served(tmp_path, monkeypatch):
    pub = LocalPublisher(tmp_path)
    d = pub.dist_dir("v_reyes", 4)
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>r4</html>")
    (d / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path / "v_reyes").mkdir(exist_ok=True)
    monkeypatch.setattr(routes, "LocalPublisher", lambda: pub)
    app = FastAPI()
    app.include_router(routes.router)
    c = TestClient(app)
    assert c.get("/v/v_reyes/r/4/").text == "<html>r4</html>"
    assert c.get("/v/v_reyes/r/4/assets/a.js").status_code == 200
    assert c.get("/v/v_reyes/r/4/assets/missing.js").status_code == 404
    assert c.get("/v/v_reyes/r/4/../../../etc/passwd").status_code == 404
    assert c.get("/v/v_reyes/").status_code == 404
    import asyncio

    asyncio.run(pub.publish("v_reyes", 4))
    assert c.get("/v/v_reyes/").text == "<html>r4</html>"
    assert c.get("/villages/v_reyes/releases").json() == {"receipts": [], "live_rev": 4} or c.get("/villages/v_reyes/releases").json()["live_rev"] == 4


def test_post_release_runs_pipeline_with_fakes(tmp_path, monkeypatch):
    import time

    from core.release import service
    from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals, Recorder
    from core.release.receipts import ReceiptStore

    pub, store, rec = LocalPublisher(tmp_path / "rel"), ReceiptStore(tmp_path / "rc"), Recorder()
    monkeypatch.setattr(routes, "LocalPublisher", lambda: pub)
    monkeypatch.setattr(routes, "ReceiptStore", lambda: store)
    service.set_service(service.ReleaseService(daytona=FakeDaytona(), anchor=FakeAnchor(), evals=FakeEvals(), llm=None,
                                               broadcast=rec, publisher=pub, store=store))
    try:
        app = FastAPI()
        app.include_router(routes.router)
        with TestClient(app) as c:
            r = c.post("/villages/v_reyes/releases", json={"rev": 3, "inject_failure": "contrast"})
            assert r.status_code == 202 and r.json() == {"release_id": "rel_reyes_r3", "candidate_path": "/v/v_reyes/r/3/"}
            assert c.post("/villages/v_reyes/releases", json={"rev": 0}).status_code == 422
            assert c.post("/villages/v_nobody/releases", json={"rev": 1}).status_code == 404
            for _ in range(100):
                if not service.get_service().busy("v_reyes"):
                    break
                time.sleep(0.05)
            body = c.get("/villages/v_reyes/releases").json()
        assert body["live_rev"] == 4
        assert [x["id"] for x in body["receipts"]][:2] == ["rel_reyes_r4", "rel_reyes_r3"]
        assert {x["result"] for x in body["receipts"]} == {"released", "blocked"}
    finally:
        service.set_service(None)


def test_post_release_409_when_busy(monkeypatch):
    import asyncio

    from core.release import service
    from core.release.fakes import FakeDaytona

    svc = service.ReleaseService(daytona=FakeDaytona(), anchor=None, evals=None, llm=None, broadcast=lambda *a: None)

    class Pending:
        def done(self) -> bool:
            return False

    svc.tasks["v_reyes"] = Pending()  # type: ignore[assignment]
    service.set_service(svc)
    try:
        app = FastAPI()
        app.include_router(routes.router)
        assert TestClient(app).post("/villages/v_reyes/releases", json={"rev": 5}).status_code == 409
    finally:
        service.set_service(None)
