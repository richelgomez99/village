from __future__ import annotations

from core.builder.conversation import UNKNOWN, IntakeState, Question, Review, extract, load_intake, merge, next_question, plan


def test_plan_has_ten_topics_with_required_fields_and_questions() -> None:
    t = plan("care")["topics"]
    assert [x["n"] for x in t] == list(range(1, 11))
    assert all(x["required"] and x["questions"] for x in t)


def test_replay_meter_and_question_order() -> None:
    rows = load_intake()
    st = IntakeState(opener=rows[0]["text"])
    merge(st, extract(rows[0]["text"], None, st))
    assert st.meter() == "1 of 10 covered · 9 gaps"
    asked = []
    for r in rows[1:12]:
        q = next_question(st)
        assert isinstance(q, Question)
        assert q.text == r["asked"], (q.text, r["asked"])
        asked.append(q.topic)
        st.asked.append(f"{q.topic}.{q.field}")
        merge(st, extract(r["text"], q, st))
    assert st.meter() == "10 of 10 covered · 0 gaps"
    assert isinstance(next_question(st), Review)
    assert st.family_word == "Pavo" and st.fields["money"]["family_word"] == "set"


def test_dont_know_marks_unknown_gap_never_reasked() -> None:
    rows = load_intake()
    st = IntakeState(opener=rows[0]["text"])
    merge(st, extract(rows[0]["text"], None, st))
    q = next_question(st)
    st.asked.append(f"{q.topic}.{q.field}")
    merge(st, extract("I don't know.", q, st))
    assert st.fields["members"]["members"] == UNKNOWN
    assert "Who is in the village" in st.gaps()
    assert next_question(st).topic != "members"
