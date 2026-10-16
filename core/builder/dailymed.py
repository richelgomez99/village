"""DailyMed REST lookup (D23 #4: the Founder does work). One search per medication; the result is a
fact with url provenance. Network failures degrade to 'will check after you invite'."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

SEARCH_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"


@dataclass
class DailyMedResult:
    name: str
    checked: bool
    url: str
    title: str | None = None
    setid: str | None = None
    published: str | None = None
    ms: int = 0
    error: str | None = None
    search_url: str = ""

    def fact(self, village_id: str, member_id: str | None) -> dict[str, Any]:
        return {
            "village": village_id,
            "entity": member_id or "village",
            "key": f"med_label:{self.name}",
            "value": self.title if self.checked else None,
            "status": "checked" if self.checked else "unchecked",
            "source": {"kind": "url", "ref": "dailymed", "url": self.url},
            "labels": {"src": "url:dailymed", "agent": "builder", "village": village_id},
        }


def _pick(name: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    lname = name.lower()
    single = [i for i in items if " and " not in i.get("title", "").lower()]
    starts = [i for i in single if i.get("title", "").lower().startswith(lname)]
    return (starts or single or items)[0]


async def lookup_medication(name: str, client: httpx.AsyncClient | None = None, timeout: float = 6.0) -> DailyMedResult:
    t0 = time.perf_counter()
    params = {"drug_name": name, "pagesize": 5}
    owned = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    search_url = f"{SEARCH_URL}?drug_name={name}&pagesize=5"
    try:
        response = await http.get(SEARCH_URL, params=params)
        response.raise_for_status()
        item = _pick(name, response.json().get("data") or [])
        if not item:
            return DailyMedResult(name, False, search_url, error="no label found", ms=int((time.perf_counter() - t0) * 1000), search_url=search_url)
        return DailyMedResult(
            name=name,
            checked=True,
            url=LABEL_URL.format(setid=item["setid"]),
            title=item.get("title"),
            setid=item.get("setid"),
            published=item.get("published_date"),
            ms=int((time.perf_counter() - t0) * 1000),
            search_url=search_url,
        )
    except Exception as exc:
        return DailyMedResult(name, False, search_url, error=f"{type(exc).__name__}", ms=int((time.perf_counter() - t0) * 1000), search_url=search_url)
    finally:
        if owned:
            await http.aclose()


def fixture_transport(directory: Any) -> httpx.MockTransport:
    """Replays recorded DailyMed responses (`<drug>.json`) — tests and `--llm off` demo runs."""
    from pathlib import Path

    root = Path(directory)

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.params.get("drug_name", "")
        path = root / f"{name.lower()}.json"
        if not path.exists():
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, content=path.read_bytes(), headers={"content-type": "application/json"})

    return httpx.MockTransport(handler)
