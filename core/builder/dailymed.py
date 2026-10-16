from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class ConsentCallPort(Protocol):
    async def request_availability_consent(self, *, village_id: str, member_id: str, phone: str | None) -> dict[str, Any]: ...


@dataclass
class DailyMedResult:
    name: str
    checked: bool
    url: str
    title: str | None = None
    setid: str | None = None
    error: str | None = None


async def lookup_medication(name: str, client: httpx.AsyncClient | None = None) -> DailyMedResult:
    url = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
    params = {"drug_name": name, "pagesize": 1}
    owned = client is None
    http = client or httpx.AsyncClient(timeout=10)
    try:
        response = await http.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        item = (data.get("data") or [{}])[0]
        setid = item.get("setid")
        return DailyMedResult(
            name=name,
            checked=True,
            url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}" if setid else "https://dailymed.nlm.nih.gov/dailymed/",
            title=item.get("title"),
            setid=setid,
        )
    except Exception as exc:
        return DailyMedResult(name=name, checked=False, url="https://dailymed.nlm.nih.gov/dailymed/", error=str(exc))
    finally:
        if owned:
            await http.aclose()
