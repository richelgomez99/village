"""Fallback FastAPI router core can include: `app.include_router(core.release.routes.router)`.

GET /v/{village}/r/{rev}/{path}   candidate build (blue/green: any staged rev)
GET /v/{village}/                 published rev (var/releases/<v>/published.json)
GET /releases/{rel}/qa/{file}     QA evidence (screenshots, report.json)
GET /villages/{village}/releases  receipts (local store)"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from core.release.receipts import ReceiptStore
from core.release.serve import LocalPublisher

router = APIRouter(tags=["release"])
VID = re.compile(r"^v_[a-z0-9_]{2,40}$")
REL = re.compile(r"^rel_([a-z0-9_]+)_r([0-9]+)$")


def _safe(base: Path, rel: str) -> Path:
    p = (base / (rel or "index.html")).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise HTTPException(404)
    if p.is_dir():
        p = p / "index.html"
    if not p.exists():
        # SPA fallback for client routes; real assets 404
        if "." in Path(rel).name:
            raise HTTPException(404)
        p = base / "index.html"
    if not p.exists():
        raise HTTPException(404)
    return p


def _dist(village: str, rev: int) -> Path:
    if not VID.match(village):
        raise HTTPException(404)
    return LocalPublisher().dist_dir(village, rev)


@router.get("/v/{village}/r/{rev}/{path:path}", include_in_schema=False)
async def candidate(village: str, rev: int, path: str = "") -> FileResponse:
    return FileResponse(_safe(_dist(village, rev), path), headers={"Cache-Control": "no-cache"})


@router.get("/v/{village}/", include_in_schema=False)
async def published(village: str) -> FileResponse:
    rev = LocalPublisher().published_rev(village) if VID.match(village) else None
    if rev is None:
        raise HTTPException(404, "no published rev")
    return FileResponse(_safe(_dist(village, rev), ""), headers={"Cache-Control": "no-cache"})


@router.get("/v/{village}/assets/{path:path}", include_in_schema=False)
async def published_assets(village: str, path: str) -> FileResponse:
    rev = LocalPublisher().published_rev(village) if VID.match(village) else None
    if rev is None:
        raise HTTPException(404)
    return FileResponse(_safe(_dist(village, rev) / "assets", path))


@router.get("/releases/{rel}/qa/{file}", include_in_schema=False)
async def qa_file(rel: str, file: str) -> FileResponse:
    m = REL.match(rel)
    if not m or "/" in file or file.startswith("."):
        raise HTTPException(404)
    base = LocalPublisher().root / f"v_{m.group(1)}" / f"r{m.group(2)}" / "qa"
    p = base / file
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@router.get("/villages/{village}/releases")
async def list_releases(village: str) -> JSONResponse:
    if not VID.match(village):
        raise HTTPException(404)
    return JSONResponse({"village": village, "published_rev": LocalPublisher().published_rev(village),
                         "releases": ReceiptStore().all(village)})
