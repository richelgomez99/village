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
    assert c.get("/villages/v_reyes/releases").json()["published_rev"] == 4
