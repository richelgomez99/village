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


def test_model_record_answer_never_overwrites_known_fields() -> None:
    import asyncio

    from core.builder.conversation import record_answer
    from core.builder.llm_port import FakeLLM

    st = IntakeState(opener="x")
    st.fields["availability"]["helper_days"] = {"days": ["Tue", "Thu"]}
    q = Question("availability", "speaker_days", "And you?", 2)
    fake = FakeLLM(responses=[{"fields": {"availability": {"helper_days": {"days": ["Mon"]}, "speaker_days": "Monday and Wednesday"}, "money": {"family_word": "secret"}}}])
    found = asyncio.run(record_answer("Monday, Wednesday, Sunday, after four.", q, st, fake))
    assert "helper_days" not in found.get("availability", {})
    assert found["availability"]["speaker_days"]["days"] == ["Mon", "Wed", "Sun"]
    assert "money" not in found


def test_partially_filled_topic_still_gets_its_lead_question() -> None:
    rows = load_intake()
    st = IntakeState(opener=rows[0]["text"])
    merge(st, extract(rows[0]["text"], None, st))
    st.fields["routine"]["how_taken"] = "weekly organizer"
    for t in ("members", "availability", "meds"):
        for f in st.topics[[x["id"] for x in st.topics].index(t)]["required"]:
            st.fields[t][f] = "x"
    q = next_question(st)
    assert q.topic == "routine"
