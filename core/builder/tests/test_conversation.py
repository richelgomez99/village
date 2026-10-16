from __future__ import annotations

from core.builder.conversation import ConversationState, Done, Question, facts, intake_needs, load_transcript, mark_asked, next_turn, person_assignments


def _play(mode: str) -> tuple[ConversationState, list[Question], Done]:
    opener, answers = load_transcript()
    st = ConversationState(opener=opener, mode=mode)
    qs = []
    while True:
        t = next_turn(st)
        if isinstance(t, Done):
            return st, qs, t
        qs.append(t)
        mark_asked(st, t)
        st.add(t.slot, t.text, answers.get(t.slot, ""))


def test_full_replay_asks_in_gap_order_and_skips_known() -> None:
    st, qs, done = _play("full")
    assert [q.slot for q in qs] == ["center", "people", "contact", "health", "coordination", "household", "rules", "consent"]
    assert "money" not in [q.slot for q in qs]  # the opener already said it
    assert done.reason == "complete"
    assert 8 <= len(qs) + 1 <= 12  # questions + closing summary
    assert qs[0].reflection.startswith("I heard the pills, a money call in Marco's name and a missed visit")
    assert qs[0].text == "What's your mom's name, and which language is easiest for her?"
    assert qs[1].reflection == "Carmen, 78, in Queens, Spanish first."
    assert "Besides you and Marco" in qs[1].text
    assert qs[4].reflection.startswith("Carmen takes 4 medications; I'm checking them on DailyMed")
    f = facts(st)
    assert f["meds"] == ["apixaban", "atorvastatin", "lisinopril", "metformin"] and f["quiet_hours"] == "21:30-07:00"


def test_fast_mode_stops_after_two_questions() -> None:
    st, qs, done = _play("fast")
    assert [q.slot for q in qs] == ["center", "people"] and done.gaps


def test_complete_opener_needs_few_questions() -> None:
    opener = ("My mom Carmen, 78, Spanish, flip phone, won't use an app. My brother Marco and my sister Lucía help; Marco does Tuesdays and Thursdays, "
              "I do Mondays. She takes Eliquis and metformin. Someone pretending to be Marco asked her for money. The bodega delivers groceries, the super has keys. "
              "No calls after 9:30. Marco said it's fine to call him.")
    st = ConversationState(opener=opener)
    q = next_turn(st)
    assert isinstance(q, Done) or q.slot in ("center", "worry")
    n = 0
    while isinstance(q, Question):
        mark_asked(st, q)
        st.add(q.slot, q.text, "Carmen" if q.slot == "center" else "The scams.")
        n += 1
        q = next_turn(st)
    assert n <= 2


def test_intake_needs_spans_and_assignments() -> None:
    st, _, _ = _play("full")
    text = st.text
    needs = intake_needs(text, "m_carmen")
    ids = {n["id"] for n in needs}
    assert {"n_groceries", "n_insurance", "n_home_safety", "n_keys", "n_appointments"} <= ids
    for n in needs:
        s = n["source_span"]
        assert text[s["start"] : s["end"]] in n["text"]
    a = person_assignments(text, {"Marco": "m_marco", "Lucía": "m_lucia", "Carmen": "m_carmen"})
    assert a["m_marco"]["days"] == ["Tue", "Thu", "Fri", "Sat"] and a["m_marco"]["refill"]
    assert set(a["m_lucia"]["areas"]) >= {"money", "daily_living"}
