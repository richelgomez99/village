from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordID:
    table: str
    key: str

    def __str__(self) -> str:
        return f"{self.table}:{self.key}"


PREFIX_TABLE = {
    "v": "village",
    "m": "member",
    "b": "member",
    "ev": "event",
    "ver": "verification",
    "dc": "decision",
    "msg": "message",
    "st": "slot_token",
    "rel": "release",
    "prop": "proposal",
}


def to_rid(contract_id: str) -> RecordID:
    prefix = contract_id.split("_", 1)[0]
    table = PREFIX_TABLE.get(prefix)
    if table is None:
        raise ValueError(f"unknown contract id prefix: {contract_id}")
    key = contract_id[2:] if prefix == "v" else contract_id
    return RecordID(table, key)


def to_cid(record_id: RecordID | str) -> str:
    if isinstance(record_id, str):
        table, key = record_id.split(":", 1)
    else:
        table, key = record_id.table, record_id.key
    if table == "village":
        return f"v_{key}"
    return key
