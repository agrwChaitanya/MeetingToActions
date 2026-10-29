import pytest
from unittest.mock import MagicMock, patch
from src.schemas import (
    ActionItem, EmailDraft, SummaryOutput, ActionList, CriticOutput, ReviseOutput
)
from src.graph import graph
from src.config import MAX_CRITIC_LOOPS

def test_graph_execution_success():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    
    mock_structured.invoke.side_effect = [
        SummaryOutput(summary="Meeting summary"),
        ActionList(actions=[
            ActionItem(id="a1", task="Task 1", owner="Alice", due_date="2026-03-05", source_quote="q1"),
            ActionItem(id="a2", task="Task 2", owner="Bob", due_date="2026-03-01", source_quote="q2")
        ]),
        CriticOutput(issues=[]),
        EmailDraft(recipient="Alice", subject="Tasks", body="Body", task_ids=["a1"]),
        EmailDraft(recipient="Bob", subject="Tasks", body="Body", task_ids=["a2"])
    ]
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("src.nodes.get_llm", return_value=mock_llm):
        initial_state = {
            "transcript": "Alice and Bob meeting transcript",
            "summary": "",
            "actions": [],
            "issues": [],
            "loops": 0,
            "trace": [],
            "approved": [],
            "drafts": [],
            "timeline": []
        }
        result = graph.invoke(initial_state)

        assert result["summary"] == "Meeting summary"
        assert len(result["actions"]) == 2
        assert "extract_summary" in result["trace"]
        assert "extract_actions" in result["trace"]
        assert "critic" in result["trace"]
        assert "human_review" in result["trace"]
        assert "finalize" in result["trace"]

        # Check timeline sorted by due_date (a2 due 2026-03-01 comes before a1 due 2026-03-05)
        assert len(result["timeline"]) == 2
        assert result["timeline"][0]["id"] == "a2"
        assert result["timeline"][1]["id"] == "a1"

def test_graph_loop_cap():
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    
    mock_structured.invoke.side_effect = [
        SummaryOutput(summary="Summary"),
        ActionList(actions=[ActionItem(id="a1", task="Task", owner="Alice", due_date="2026-03-01", source_quote="q")]),
        CriticOutput(issues=["Issue 1"]),
        ReviseOutput(summary="Revised 1", actions=[ActionItem(id="a1", task="Task", owner="Alice", due_date="2026-03-01", source_quote="q")]),
        CriticOutput(issues=["Issue 2"]),
        ReviseOutput(summary="Revised 2", actions=[ActionItem(id="a1", task="Task", owner="Alice", due_date="2026-03-01", source_quote="q")]),
        CriticOutput(issues=["Issue 3"]), # loops reached MAX_CRITIC_LOOPS=2
        EmailDraft(recipient="Alice", subject="Tasks", body="Body", task_ids=["a1"])
    ]
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("src.nodes.get_llm", return_value=mock_llm):
        initial_state = {
            "transcript": "Transcript",
            "summary": "",
            "actions": [],
            "issues": [],
            "loops": 0,
            "trace": [],
            "approved": [],
            "drafts": [],
            "timeline": []
        }
        result = graph.invoke(initial_state)

        assert result["loops"] == 2
        assert "revise" in result["trace"]
        assert result["trace"].count("revise") == 2
        assert "human_review" in result["trace"]
        assert "finalize" in result["trace"]
