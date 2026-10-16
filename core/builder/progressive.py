"""D33 cause → effect: after each answer, the components that answer decided are announced
(`control{blueprint, stage: will_build}`) and then added to that role's DRAFT view with
`patch{base_rev, rev, role, ops, highlight}` so phone mirrors grow card by card."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import frames
from .conversation import UNKNOWN, IntakeState, plan


class _Vars(dict):
    def __missing__(self, key: str) -> str:
        return "…"


class DraftBuilder:
    def __init__(self, template: dict[str, Any], kind: str, village_id: str, services: Any, trace_id: str) -> None:
        self.template, self.kind, self.vid, self.svc, self.trace_id = template, kind, village_id, services, trace_id
        self.draft = deepcopy(template)
        for role, view in self.draft["views"].items():
            s = deepcopy(view["elements"]["s"])
            s["children"] = []
            view["elements"] = {"s": s}
            view["needs_served"] = {}
        self.draft["village"]["status"] = "draft"
        self.rev = 1
        self.done: set[str] = set()
        self.built: set[tuple[str, str]] = set()
        self.store = True  # False once the final draft spec is stored (patches still broadcast)

    async def start(self) -> None:
        self.draft["rev"] = self.rev
        await self.svc.store_spec(self.vid, self.draft, status="draft")

    def _people(self, role: str, who: str | None, speaker_id: str | None, helper: str | None) -> list[dict[str, Any]]:
        people = [p for p in self.template["blueprint"]["people"] if p.get("view") == role]
        if who == "speaker":
            people = [p for p in people if p["id"] == speaker_id] or people[:1]
        elif who == "helper" and helper:
            people = [p for p in people if p["name"].split()[0] == helper] or people[:1]
        return people

    def triggered(self, intake: IntakeState) -> list[str]:
        cov = set(intake.covered())
        out = []
        for trig in plan(self.kind).get("builds", {}):
            if trig in self.done:
                continue
            topic, _, field = trig.partition(".")
            val = intake.fields.get(topic, {}).get(field) if field else None
            if (field and val not in (None, "", [], UNKNOWN)) or (not field and topic in cov):
                out.append(trig)
        return out

    async def on_answer(self, intake: IntakeState, variables: dict[str, Any], *, speaker_id: str | None, helper: str | None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        ops_by_role: dict[str, list[dict[str, Any]]] = {}
        for trig in self.triggered(intake):
            self.done.add(trig)
            for b in plan(self.kind)["builds"][trig]:
                role, eid = b["role"], b["element"]
                tview = self.template["views"].get(role)
                if not tview or eid not in tview["elements"] or (role, eid) in self.built:
                    continue
                self.built.add((role, eid))
                el = deepcopy(tview["elements"][eid])
                reason = b["reason"].format_map(_Vars(variables))
                for p in self._people(role, b.get("who"), speaker_id, helper)[:3]:
                    items.append({"person": p["id"], "display_name": p.get("short_name") or p["name"].split()[0], "role": role, "component": el["type"], "element": eid, "reason": reason[:160]})
                ops_by_role.setdefault(role, []).append({"op": "add", "path": f"/elements/{eid}", "value": el})
        if not items:
            return []
        await self.svc.broadcast_control(self.vid, frames.blueprint(self.vid, "will_build", items, self.trace_id))
        await self.push(ops_by_role)
        return items

    async def add_element(self, role: str, eid: str, el: dict[str, Any], reason: str, person: dict[str, Any], needs: list[str]) -> None:
        """Review edits (e.g. RefillCard for one person) take the same will_build → patch path."""
        await self.svc.broadcast_control(self.vid, frames.blueprint(self.vid, "will_build", [{"person": person["id"], "display_name": person["name"].split()[0], "role": role, "component": el["type"], "element": eid, "reason": reason[:160]}], self.trace_id))
        self.template["views"][role]["elements"][eid] = deepcopy(el)
        self.template["views"][role].setdefault("needs_served", {})[eid] = needs
        children = self.template["views"][role]["elements"]["s"]["children"]
        if eid not in children:
            children.insert(1, eid)
        self.built.add((role, eid))
        await self.push({role: [{"op": "add", "path": f"/elements/{eid}", "value": deepcopy(el)}]})

    async def push(self, ops_by_role: dict[str, list[dict[str, Any]]]) -> None:
        for role, adds in ops_by_role.items():
            view = self.draft["views"][role]
            order = self.template["views"][role]["elements"]["s"]["children"]
            ops: list[dict[str, Any]] = []
            new_ids = []
            for op in adds:
                eid = op["path"].split("/")[2]
                view["elements"][eid] = op["value"]
                served = self.template["views"][role].get("needs_served", {}).get(eid)
                if served:
                    view["needs_served"][eid] = served
                ops.append(op)
                new_ids.append(eid)
            present = [c for c in order if c in view["elements"]]
            for eid in new_ids:
                idx = present.index(eid) if eid in present else len(view["elements"]["s"]["children"])
                kids = view["elements"]["s"]["children"]
                pos = sum(1 for c in present[:idx] if c in kids)
                kids.insert(pos, eid)
                ops.append({"op": "add", "path": f"/elements/s/children/{pos}", "value": eid})
            base = self.rev
            self.rev += 1
            self.draft["rev"] = self.rev
            frame = {"type": "patch", "rev": self.rev, "base_rev": base, "role": role, "ops": ops[:24], "highlight": new_ids}
            if self.store:
                await self.svc.store_spec(self.vid, self.draft, status="draft")
            if hasattr(self.svc, "broadcast_patch"):
                await self.svc.broadcast_patch(self.vid, frame)
