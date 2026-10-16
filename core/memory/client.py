"""Async Agent Memory client (SurrealDB Agent Memory REST, raw httpx).

Never raises into the caller: every method returns a dict with `degraded` (bool) and,
on failure, `degraded_reason` + `status`. Provenance rides in labels (src=, secs=, url=,
agent=, village=). Scopes are registered once per process per path (201/409 both OK).
Shapes pinned from smoke 06 + a live probe on 2026-10-16 (see LANE-REPORT.md).
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from urllib.parse import quote

import httpx

from core.memory import conventions as cv
from core.settings import ROOT

CONNECT_S = 2.0
READ_S = 8.0
QUERY_READ_S = 25.0  # hybrid recall measured 4-14 s live


def _env() -> dict[str, str]:
    vals: dict[str, str] = {}
    try:
        from dotenv import dotenv_values

        vals.update({k: v for k, v in dotenv_values(ROOT / ".env").items() if v})
    except Exception:  # noqa: BLE001
        pass
    for k in ("SURREAL_MEMORY_URL", "SURREAL_MEMORY_CONTEXT", "SURREAL_MEMORY_API_KEY"):
        if os.getenv(k):
            vals[k] = os.environ[k]
    return vals


class MemoryClient:
    def __init__(self, base_url: str | None = None, context: str | None = None, api_key: str | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None, connect_s: float = CONNECT_S,
                 read_s: float = READ_S, agent: str = "memory") -> None:
        env = _env() if base_url is None or context is None or api_key is None else {}
        self.base_url = (base_url or env.get("SURREAL_MEMORY_URL", "")).rstrip("/").removesuffix("/api/v1")
        self.context = context or env.get("SURREAL_MEMORY_CONTEXT", "")
        self._key = api_key or env.get("SURREAL_MEMORY_API_KEY", "")
        self.agent = agent
        self._transport = transport
        self._timeout = httpx.Timeout(read_s, connect=connect_s)
        self._http: httpx.AsyncClient | None = None
        self._scopes: set[str] = set()
        self._scope_lock = asyncio.Lock()
        self.timings: list[tuple[str, float, int]] = []

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.context and self._key)

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=f"{self.base_url}/api/v1/{quote(self.context, safe='')}",
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=self._timeout, transport=self._transport)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _req(self, method: str, path: str, label: str, *, timeout: float | None = None, **kw: Any) -> dict[str, Any]:
        """Returns {ok, status, data, ms} or {ok: False, degraded_reason}. Never raises."""
        if not self.configured:
            return {"ok": False, "status": 0, "data": None, "ms": 0.0, "degraded_reason": "memory_unreachable"}
        t0 = time.perf_counter()
        try:
            if timeout is not None:
                kw["timeout"] = httpx.Timeout(timeout, connect=CONNECT_S)
            r = await self._client().request(method, path, **kw)
        except httpx.TimeoutException:
            ms = (time.perf_counter() - t0) * 1000
            self.timings.append((label, ms, 0))
            return {"ok": False, "status": 0, "data": None, "ms": ms, "degraded_reason": "memory_timeout"}
        except Exception:  # noqa: BLE001 - network, DNS, TLS, anything
            ms = (time.perf_counter() - t0) * 1000
            self.timings.append((label, ms, 0))
            return {"ok": False, "status": 0, "data": None, "ms": ms, "degraded_reason": "memory_unreachable"}
        ms = (time.perf_counter() - t0) * 1000
        self.timings.append((label, ms, r.status_code))
        try:
            data = r.json()
        except ValueError:
            data = {"_text": r.text[:300]}
        ok = r.status_code < 300
        out = {"ok": ok, "status": r.status_code, "data": data, "ms": ms}
        if not ok:
            out["degraded_reason"] = "memory_unreachable"
        return out

    # ---------------------------------------------------------------- scopes
    async def ensure_scopes(self, entity: str, village: str) -> bool:
        ok = True
        for path in cv.scope_chain(entity, village):
            if path in self._scopes:
                continue
            async with self._scope_lock:
                if path in self._scopes:
                    continue
                r = await self._req("POST", "/scopes", "scopes register", json={"path": path, "description": "village"})
                if r["ok"] or r["status"] == 409:
                    self._scopes.add(path)
                else:
                    ok = False
        return ok

    # ---------------------------------------------------------------- writes
    async def remember_fact(self, entity: str, key: str, value: Any, *, source: dict[str, Any], village: str,
                            agent: str | None = None, observed_at: Any = None, event_id: str | None = None,
                            rule_id: str | None = None, extra_labels: dict[str, str] | None = None) -> dict[str, Any]:
        """Structured write (infer:triples). Same-kind writes on entity+key supersede."""
        key = cv.norm_key(key)
        await self.ensure_scopes(entity, village)
        body = {
            "infer": "triples",
            "scopes": [[cv.scope_for(entity, village)]],
            "observed_at": cv.utc_iso(observed_at),
            "labels": cv.make_labels(source=source, village=village, agent=agent or self.agent,
                                     event_id=event_id, rule_id=rule_id, extra=extra_labels),
            "triples": [{"entity": cv.am_entity(entity, village), "key": key, "value": str(value)}],
        }
        r = await self._req("POST", "/facts", "remember_fact", json=body)
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "status": r["status"], "ms": r["ms"]}
        ext = (r["data"] or {}).get("extraction", {}) or {}
        attrs = ext.get("attributes") or []
        return {"degraded": False, "status": r["status"], "ms": r["ms"],
                "am_id": attrs[0].get("id") if attrs else None,
                "fact_id": cv.fact_id(key, entity, observed_at),
                "corrections": ext.get("corrections") or [],
                "uncertainties": ext.get("uncertainties") or [],
                "turn_id": (r["data"] or {}).get("turnId")}

    async def remember_transcript(self, conversation_id: str, text: str, *, village: str, entity: str = "village",
                                  source: dict[str, Any] | None = None, agent: str = "voice:post_call",
                                  observed_at: Any = None) -> dict[str, Any]:
        """Full post-call transcript (infer:full) for spans; never on the safety path."""
        await self.ensure_scopes(entity, village)
        body = {"text": text[:20000], "infer": "full", "role": "user", "session_id": conversation_id,
                "scopes": [[cv.scope_for(entity, village)]], "observed_at": cv.utc_iso(observed_at),
                "labels": cv.make_labels(source=source or {"kind": "call", "ref": conversation_id, "secs": 0},
                                         village=village, agent=agent)}
        r = await self._req("POST", "/facts", "remember_transcript", json=body, timeout=QUERY_READ_S)
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "status": r["status"], "ms": r["ms"]}
        return {"degraded": False, "status": r["status"], "ms": r["ms"], "turn_id": (r["data"] or {}).get("turnId")}

    # ---------------------------------------------------------------- reads
    async def fact_history(self, entity: str, key: str, *, village: str = "v_reyes") -> dict[str, Any]:
        e = cv.am_entity(entity, village)
        path = f"/entities/{quote(e['type'])}/{quote(e['name'], safe='')}/history/{quote(cv.norm_key(key))}"
        r = await self._req("GET", path, "fact_history")
        if r["status"] == 404:
            return {"degraded": False, "history": [], "ms": r["ms"]}
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "history": [], "ms": r["ms"]}
        data = r["data"]
        rows = data.get("history", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        return {"degraded": False, "history": rows, "ms": r["ms"]}

    async def entity_facts(self, entity: str, *, village: str, as_of: Any = None) -> dict[str, Any]:
        e = cv.am_entity(entity, village)
        params = {"asOf": cv.utc_iso(as_of)} if as_of else None
        r = await self._req("GET", f"/entities/{quote(e['type'])}/{quote(e['name'], safe='')}", "entity_facts", params=params)
        if r["status"] == 404:
            return {"degraded": False, "attributes": [], "ms": r["ms"]}
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "attributes": [], "ms": r["ms"]}
        return {"degraded": False, "attributes": (r["data"] or {}).get("attributes", []) or [], "ms": r["ms"]}

    async def facts_for(self, village: str, entities: list[str] | None = None, *, as_of: Any = None) -> dict[str, Any]:
        """Current attributes for the village's entities, filtered on label village=<id>."""
        ents = list(dict.fromkeys(entities or ["village"]))
        results = await asyncio.gather(*(self.entity_facts(e, village=village, as_of=as_of) for e in ents))
        rows: list[dict[str, Any]] = []
        degraded, reason = False, None
        for ent, res in zip(ents, results):
            if res["degraded"]:
                degraded, reason = True, res.get("degraded_reason")
                continue
            for a in res["attributes"]:
                if cv.parse_labels(a.get("labels")).get("village", village) == village:
                    rows.append({**a, "_entity": ent})
        out = {"degraded": degraded, "facts": rows}
        if degraded:
            out["degraded_reason"] = reason
        return out

    async def uncertainties(self, village: str, *, resolved: bool = False) -> dict[str, Any]:
        r = await self._req("GET", "/uncertainty", "uncertainties",
                            params={"resolved": str(resolved).lower(), "limit": 50})
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "uncertainties": []}
        d = r["data"]
        items = (d.get("unknowns") or d.get("uncertainties") or d.get("items") or []) if isinstance(d, dict) else d or []
        scope = cv.village_scope(village)
        mine = [u for u in items if not u.get("scope") or any(scope in str(s) for s in u.get("scope"))]
        return {"degraded": False, "uncertainties": mine}

    async def resolve_uncertainty(self, uid: str, value: str, by: str, *, note: str | None = None) -> dict[str, Any]:
        am_id = uid.removeprefix("unc_")
        body = {"acceptedValue": value, "note": (note or f"resolved by {by}")[:300]}
        r = await self._req("POST", f"/uncertainty/{quote(am_id, safe='')}/resolve", "resolve_uncertainty", json=body)
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "status": r["status"]}
        return {"degraded": False, "status": r["status"], "data": r["data"]}

    async def query(self, text: str, as_of: Any = None, *, village: str | None = None, k: int = 5,
                    members: list[str] | None = None) -> dict[str, Any]:
        """Hybrid recall. Lens = village scope OR each member scope (lenses are not hierarchical;
        verified live: [[village/v_reyes]] alone misses facts in village/v_reyes/m_carmen)."""
        body: dict[str, Any] = {"query": text, "k": k, "source": "village"}
        if village:
            mids = members if members is not None else sorted(cv.member_names())
            body["lens"] = [[cv.village_scope(village)]] + [[cv.member_scope(village, m)] for m in mids]
        if as_of:
            body["asOf"] = cv.utc_iso(as_of)
        r = await self._req("POST", "/query", "query", json=body, timeout=QUERY_READ_S)
        if not r["ok"]:
            return {"degraded": True, "degraded_reason": r.get("degraded_reason"), "hits": [], "ms": r["ms"]}
        d = r["data"] or {}
        return {"degraded": False, "hits": d.get("hits", []), "tier": d.get("tier"),
                "trace_id": (d.get("trace") or {}).get("traceId"), "ms": r["ms"], "query_ms": d.get("queryMs")}

    async def forget_scope(self, path: str) -> dict[str, Any]:
        r = await self._req("POST", "/scopes/forget", "forget_scope", json={"path": path})
        self._scopes = {s for s in self._scopes if not s.startswith(path)}
        return {"degraded": not r["ok"], "status": r["status"]}


_default: MemoryClient | None = None


def get_client() -> MemoryClient:
    global _default
    if _default is None:
        _default = MemoryClient()
    return _default
