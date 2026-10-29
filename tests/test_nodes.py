import pytest
from unittest.mock import MagicMock, patch
from src.schemas import (
    ActionItem, EmailDraft, SummaryOutput, ActionList, CriticOutput, ReviseOutput
)
from src.nodes import (
    extract_summary, extract_actions, critic, revise, human_review, finalize
)

def test_extract_summary_node():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SummaryOutput(summary="Test meeting summary.")
    mock_llm.with_structured_output.return_value = mock_structured

    state = {"transcript": "Alice and Bob discussed project X."}
    result = extract_summary(state, llm=mock_llm)

    assert result["summary"] == "Test meeting summary."
    assert "extract_summary" in result["trace"]

def test_extract_actions_node():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = ActionList(
        actions=[
            ActionItem(
                id="",
                task="Do task 1",
                owner="Alice",
                due_date="2026-03-01",
                source_quote="I will do task 1."
            )
        ]
    )
    mock_llm.with_structured_output.return_value = mock_structured

    state = {"transcript": "Alice: I will do task 1."}
    result = extract_actions(state, llm=mock_llm)

    assert len(result["actions"]) == 1
    assert result["actions"][0].id == "a1"
    assert result["actions"][0].owner == "Alice"
    assert "extract_actions" in result["trace"]

def test_critic_node():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = CriticOutput(issues=["Missing due date for action 2"])
    mock_llm.with_structured_output.return_value = mock_structured

    state = {
        "transcript": "Meeting transcript",
        "summary": "Summary",
        "actions": [ActionItem(id="a1", task="Task", owner="Alice", due_date="2026-03-01", source_quote="quote")]
    }
    result = critic(state, llm=mock_llm)

    assert result["issues"] == ["Missing due date for action 2"]
    assert "critic" in result["trace"]

def test_revise_node():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    revised_action = ActionItem(id="a1", task="Task revised", owner="Alice", due_date="2026-03-01", source_quote="quote")
    mock_structured.invoke.return_value = ReviseOutput(
        summary="Revised summary",
        actions=[revised_action]
    )
    mock_llm.with_structured_output.return_value = mock_structured

    state = {
        "transcript": "Transcript",
        "summary": "Summary",
        "actions": [ActionItem(id="a1", task="Task", owner=None, due_date=None, source_quote="quote")],
        "issues": ["Missing owner"],
        "loops": 0
    }
    result = revise(state, llm=mock_llm)

    assert result["summary"] == "Revised summary"
    assert result["loops"] == 1
    assert result["issues"] == []
    assert "revise" in result["trace"]

def test_human_review_node():
    with patch("src.nodes.interrupt") as mock_interrupt:
        mock_interrupt.return_value = [
            ActionItem(id="a1", task="Approved task", owner="Alice", due_date="2026-03-01", source_quote="quote")
        ]
        state = {
            "summary": "Summary",
            "actions": [ActionItem(id="a1", task="Task", owner="Alice", due_date="2026-03-01", source_quote="quote")],
            "issues": []
        }
        result = human_review(state)

        assert len(result["approved"]) == 1
        assert result["approved"][0].task == "Approved task"
        assert "human_review" in result["trace"]

def test_finalize_node():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = EmailDraft(
        recipient="Alice",
        subject="Your Action Items",
        body="Hello Alice, please complete your tasks.",
        task_ids=["a1"]
    )
    mock_llm.with_structured_output.return_value = mock_structured

    state = {
        "approved": [
            ActionItem(id="a1", task="Task 1", owner="Alice", due_date="2026-03-05", source_quote="quote1"),
            ActionItem(id="a2", task="Task 2", owner="Alice", due_date="2026-03-01", source_quote="quote2")
        ]
    }
    result = finalize(state, llm=mock_llm)

    assert len(result["drafts"]) == 1
    assert result["drafts"][0].recipient == "Alice"
    assert result["drafts"][0].task_ids == ["a1", "a2"]
    
    assert len(result["timeline"]) == 2
    assert result["timeline"][0]["id"] == "a2"
    assert result["timeline"][1]["id"] == "a1"
    assert "finalize" in result["trace"]
