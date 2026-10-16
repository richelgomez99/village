"""Local blue/green publisher: candidates under var/releases/<v>/r<rev>/dist, the published
rev in var/releases/<v>/published.json. routes.py serves both. Core may replace this with
services.publish_rev / set_published_rev (see LANE-REPORT hooks)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LocalPublisher:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT / "var" / "releases"

    def dist_dir(self, village_id: str, rev: int) -> Path:
        return self.root / village_id / f"r{rev}" / "dist"

    async def stage(self, village_id: str, rev: int, dist_dir: Path) -> str:
        target = self.dist_dir(village_id, rev)
        if dist_dir.resolve() != target.resolve():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(dist_dir, target)
        if not (target / "index.html").exists():
            raise FileNotFoundError(f"no index.html in {target}")
        return f"/v/{village_id}/r/{rev}/"

    def published_rev(self, village_id: str) -> int | None:
        p = self.root / village_id / "published.json"
        return json.loads(p.read_text()).get("rev") if p.exists() else None

    async def publish(self, village_id: str, rev: int) -> int | None:
        if not (self.dist_dir(village_id, rev) / "index.html").exists():
            raise FileNotFoundError(f"rev {rev} not staged")
        prev = self.published_rev(village_id)
        p = self.root / village_id / "published.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"rev": rev, "previous": prev}))
        tmp.replace(p)  # atomic switch
        return prev
