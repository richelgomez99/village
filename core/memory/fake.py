"""FakeAgentMemory: an httpx MockTransport that behaves like the Agent Memory REST
surface we use (shapes recorded from the live probe on 2026-10-16). Tests only."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote

import httpx


def _slug(name: str) -> str:
    return re.sub(r"\s+", "_", name.strip().lower())


class FakeAgentMemory:
    def __init__(self) -> None:
        self.scopes: set[str] = set()
        self.attrs: list[dict[str, Any]] = []   # every attribute version
        self.unknowns: list[dict[str, Any]] = []
        self.requests: list[tuple[str, str, Any]] = []
        self.down = False
        self.status_override: int | None = None
        self._n = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _id(self) -> str:
        self._n += 1
        return f"am{self._n:06d}"

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down", request=request)
        body = json.loads(request.content or b"{}") if request.content else None
        path = unquote(request.url.path.split("/api/v1/", 1)[1].split("/", 1)[1])
        self.requests.append((request.method, "/" + path, body))
        if self.status_override:
            return httpx.Response(self.status_override, json={"error": "forced"})
        if request.method == "POST" and path == "scopes":
            if body["path"] in self.scopes:
                return httpx.Response(409, json={"error": "exists"})
            self.scopes.add(body["path"])
            return httpx.Response(201, json={"path": body["path"] + "/"})
        if request.method == "POST" and path == "facts":
            return self._facts(body)
        if request.method == "GET" and path.startswith("entities/"):
            parts = path.split("/")
            etype, name = parts[1], parts[2]
            ent = f"entity:{etype}/{_slug(name)}"
            rows = [a for a in self.attrs if a["entity"] == ent]
            if len(parts) >= 5 and parts[3] == "history":
                rows = sorted([a for a in rows if a["key"] == parts[4]], key=lambda a: a["createdAt"])
                return httpx.Response(200 if rows else 404, json={"history": rows})
            if not rows:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json={"entity": {"name": name}, "attributes": [a for a in rows if a["validUntil"] is None]})
        if request.method == "GET" and path == "uncertainty":
            return httpx.Response(200, json={"unknowns": [u for u in self.unknowns if not u["resolved"]], "page": {"hasMore": False}})
        if request.method == "POST" and path.startswith("uncertainty/") and path.endswith("/resolve"):
            uid = path.split("/")[1]
            for u in self.unknowns:
                if u["id"] == uid:
                    u["resolved"] = True
                    return httpx.Response(200, json={"id": uid, "resolved": True, "acceptedValue": body["acceptedValue"]})
            return httpx.Response(404, json={"error": "nf"})
        if request.method == "POST" and path == "query":
            q = body["query"].lower()
            hits = [{"id": "attribute:" + a["id"], "text": a["summary"], "source": "attribute", "score": 0.5}
                    for a in self.attrs if a["key"].split("_")[0] in q
                    and (not body.get("asOf") or a["createdAt"] <= body["asOf"].replace("Z", "+00:00"))
                    and (a["validUntil"] is None or not body.get("asOf") or a["validUntil"] > body["asOf"].replace("Z", "+00:00"))]
            return httpx.Response(200, json={"tier": "direct", "hits": hits, "queryMs": 3, "trace": {"traceId": "trfake"}})
        if request.method == "POST" and path == "scopes/forget":
            self.attrs = [a for a in self.attrs if not a["scope"][0][0].startswith(body["path"])]
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": "unknown route " + path})

    def _facts(self, body: dict[str, Any]) -> httpx.Response:
        if body.get("infer") != "triples":
            return httpx.Response(200, json={"turnId": self._id(), "extraction": {"attributes": []}, "mode": body.get("infer")})
        if not all(s in self.scopes for s in body["scopes"][0]):
            return httpx.Response(422, json={"error": "unknown scope"})
        attrs, corrections = [], []
        at = body["observed_at"].replace("Z", "+00:00")
        for t in body["triples"]:
            ent = f"entity:{t['entity']['type']}/{_slug(t['entity']['name'])}"
            new = {"id": self._id(), "entity": ent, "key": t["key"], "value": t["value"],
                   "summary": f"{t['entity']['name']}'s {t['key'].replace('_', ' ')} is {t['value']}",
                   "scope": [[s + "/" for s in body["scopes"][0]]], "labels": body.get("labels", []),
                   "validFrom": None, "validUntil": None, "supersedes": None, "supersededBy": None,
                   "source": {"kind": "upsert", "trust": 0.95}, "createdAt": at}
            for old in self.attrs:
                if old["entity"] == ent and old["key"] == t["key"] and old["validUntil"] is None:
                    if old["value"] == t["value"]:
                        new = None
                        break
                    old["validUntil"], old["supersededBy"], new["supersedes"] = at, new["id"], old["id"]
                    corrections.append({"entityId": ent, "key": t["key"], "oldValue": old["value"], "newValue": t["value"]})
            if new:
                self.attrs.append(new)
                attrs.append({"id": new["id"], "key": new["key"], "value": new["value"]})
        return httpx.Response(200, json={"extraction": {"attributes": attrs, "corrections": corrections, "uncertainties": []},
                                         "mode": "triples", "turnId": self._id()})

    def add_uncertainty(self, entity_ref: str, key: str, prior: str, new: str, scope: str) -> str:
        uid = self._id()
        self.unknowns.append({"id": uid, "about": f"entity.{key} (turn vs document)",
                              "reason": f'cross-provenance contradiction: prior upsert fact = "{prior}"; new document fact = "{new}"',
                              "entity": entity_ref, "key": key, "resolved": False, "resolvable": True,
                              "scope": [[scope + "/"]], "labels": [], "createdAt": "2026-10-16T15:06:34.671429395+00:00"})
        return uid
