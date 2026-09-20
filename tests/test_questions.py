"""Both engines must receive the same questions, or the comparison means nothing."""

from __future__ import annotations

import json

import pytest

from agentbench.data import CASES
from agentbench.engines.questions import QUESTION_SETS
from agentbench.types import PRIORITY_LEVELS


@pytest.mark.parametrize("name", sorted(QUESTION_SETS))
def test_question_ids_are_unique_within_a_set(name):
    ids = [spec.id for spec in QUESTION_SETS[name].questions]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", sorted(QUESTION_SETS))
def test_every_question_carries_its_full_meaning(name):
    """Ids are for code only, so the instructions have to stand alone."""
    for spec in QUESTION_SETS[name].questions:
        assert spec.instructions
        assert len(spec.instructions) > 30


@pytest.mark.parametrize("name", sorted(QUESTION_SETS))
def test_choice_and_score_criteria_are_described(name):
    for spec in QUESTION_SETS[name].questions:
        if spec.kind == "choice":
            assert isinstance(spec.criteria, dict)
            assert all(spec.criteria.values()), f"{spec.id} has an undescribed option"
        elif spec.kind == "score":
            assert isinstance(spec.criteria, list)
            assert len(spec.criteria) >= 2
            # Levels must describe concrete situations, not bare adjectives.
            assert all(len(level) > 20 for level in spec.criteria)


def test_priority_rubric_matches_the_label_list():
    priority = QUESTION_SETS["triage"].by_id()["priority"]
    assert len(priority.criteria) == len(PRIORITY_LEVELS)


def test_openai_schema_is_strict_and_covers_every_question():
    from agentbench.engines import structured

    for name, question_set in QUESTION_SETS.items():
        schema = structured.openai_response_format(question_set)
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False
        assert set(schema["schema"]["required"]) == {
            spec.id for spec in question_set.questions
        }
        json.dumps(schema)  # must be serializable as-is


def test_prompt_engines_see_the_same_rubrics():
    """OpenAI and Gemini share this text, so it must carry every rubric."""
    from agentbench.engines import structured

    for question_set in QUESTION_SETS.values():
        rendered = structured.render_questions(question_set)
        for spec in question_set.questions:
            assert spec.id in rendered
            assert spec.instructions in rendered
            if spec.kind == "score":
                for level in spec.criteria:
                    assert level in rendered


def test_dataset_is_well_formed():
    ids = [ticket.id for ticket, _ in CASES]
    assert len(ids) == len(set(ids))

    for ticket, gold in CASES:
        assert 0 <= gold.priority < len(PRIORITY_LEVELS)
        assert gold.department in ("billing", "technical", "escalation")
        state = ticket.as_state()
        assert set(state) == {"ticket", "account"}
        assert state["ticket"]["message"]


def test_dataset_covers_every_label():
    departments = {gold.department for _, gold in CASES}
    priorities = {gold.priority for _, gold in CASES}
    assert departments == {"billing", "technical", "escalation"}
    assert priorities == set(range(len(PRIORITY_LEVELS)))
