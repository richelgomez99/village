from core import village
from core.memory.founding import enqueue_founding, founding_drafts


class _OB:
    def __init__(self):
        self.items = {}

    def enqueue(self, item_id, kind, args):
        if item_id in self.items:
            return False
        self.items[item_id] = args
        return True


def test_each_village_seeds_founding_facts_with_provenance():
    for vid in village.village_ids():
        ds = founding_drafts(vid)
        assert ds, vid
        for d in ds:
            assert d["village"] == vid and d["entity"] and d["key"] and d["text"]
            assert d["source"]["kind"] and d["source"]["ref"]


def test_reseed_is_idempotent():
    ob = _OB()
    first = enqueue_founding(ob)
    assert first > 0 and enqueue_founding(ob) == 0 and len(ob.items) == first
