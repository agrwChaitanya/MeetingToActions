import pytest
from unittest.mock import MagicMock, patch
from langgraph.types import Command
from src.schemas import (
    ActionItem, EmailDraft, SummaryOutput, ActionList, CriticOutput, ReviseOutput
)
from src.graph import graph
from src.config import MAX_CRITIC_LOOPS

def get_mock_llm(actions=None, issues=None):
    if actions is None:
        actions = [
            ActionItem(id="a1", task="Task 1", owner="Alice", due_date="2026-03-05", source_quote="q1"),
            ActionItem(id="a2", task="Task 2", owner="Bob", due_date="2026-03-01", source_quote="q2")
        ]
    if issues is None:
        issues = []

    mock_llm = MagicMock()
    
    def mock_with_structured_output(schema):
        m = MagicMock()
        if schema == SummaryOutput:
            m.invoke.return_value = SummaryOutput(summary="Meeting summary")
        elif schema == ActionList:
            m.invoke.return_value = ActionList(actions=actions)
        elif schema == CriticOutput:
            m.invoke.return_value = CriticOutput(issues=issues)
        elif schema == EmailDraft:
            def side_effect_email(prompt):
                return EmailDraft(recipient="Alice", subject="Tasks", body="Body", task_ids=["a1"])
            m.invoke.side_effect = side_effect_email
        elif schema == ReviseOutput:
            m.invoke.return_value = ReviseOutput(summary="Revised summary", actions=actions)
        return m

    mock_llm.with_structured_output.side_effect = mock_with_structured_output
    return mock_llm

def test_graph_execution_success():
    mock_llm = get_mock_llm()

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
        config = {"configurable": {"thread_id": "success-thread"}}
        graph.invoke(initial_state, config)
        
        actions = [
            ActionItem(id="a1", task="Task 1", owner="Alice", due_date="2026-03-05", source_quote="q1"),
            ActionItem(id="a2", task="Task 2", owner="Bob", due_date="2026-03-01", source_quote="q2")
        ]
        result = graph.invoke(Command(resume=actions), config)

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
    mock_llm = get_mock_llm(issues=["Issue 1"])

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
        config = {"configurable": {"thread_id": "loop-thread"}}
        graph.invoke(initial_state, config)
        
        result = graph.invoke(Command(resume=[]), config)

        assert result["loops"] == 2
        assert "revise" in result["trace"]
        assert result["trace"].count("revise") == 2
        assert "human_review" in result["trace"]
        assert "finalize" in result["trace"]

def test_graph_interrupt_and_resume():
    mock_llm = get_mock_llm()

    config = {"configurable": {"thread_id": "m4-test-thread"}}
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
        # First invocation should pause at human_review
        graph.invoke(initial_state, config)
        
        # Verify graph state is interrupted at human_review
        state_snapshot = graph.get_state(config)
        assert "human_review" in state_snapshot.next

        # Resume with edited actions
        edited_actions = [ActionItem(id="a1", task="Edited Task by Human", owner="Alice", due_date="2026-03-01", source_quote="q")]
        final_result = graph.invoke(Command(resume=edited_actions), config)

        assert len(final_result["approved"]) == 1
        assert final_result["approved"][0].task == "Edited Task by Human"
        assert "finalize" in final_result["trace"]
