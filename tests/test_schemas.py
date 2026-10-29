import pytest
from pydantic import ValidationError
from src.schemas import ActionItem, EmailDraft, SummaryOutput, ActionList, CriticOutput, ReviseOutput
from src.state import MeetingState

def test_action_item_valid_due_date():
    item = ActionItem(
        id="a1",
        task="Finish report",
        owner="Alice",
        due_date="2026-12-31",
        source_quote="I will finish the report by Dec 31.",
        notes="Urgent"
    )
    assert item.due_date == "2026-12-31"

    item_none = ActionItem(
        id="a2",
        task="Review code",
        owner=None,
        due_date=None,
        source_quote="Let's review code."
    )
    assert item_none.due_date is None

def test_action_item_invalid_due_date():
    with pytest.raises(ValidationError) as excinfo:
        ActionItem(
            id="a3",
            task="Bad date test",
            owner="Bob",
            due_date="31-12-2026",
            source_quote="Bad date format."
        )
    assert "due_date must be in YYYY-MM-DD format" in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo2:
        ActionItem(
            id="a4",
            task="Invalid calendar date",
            owner="Bob",
            due_date="2026-02-30",
            source_quote="Invalid date."
        )
    assert "due_date must be in YYYY-MM-DD format" in str(excinfo2.value)

def test_email_draft_schema():
    draft = EmailDraft(
        recipient="Alice",
        subject="Action Items",
        body="Here are your tasks.",
        task_ids=["a1"]
    )
    assert draft.recipient == "Alice"
    assert draft.task_ids == ["a1"]

def test_state_keys():
    state: MeetingState = {
        "transcript": "Hello meeting",
        "summary": "Summary text",
        "actions": [],
        "issues": [],
        "loops": 0,
        "trace": [],
        "approved": [],
        "drafts": [],
        "timeline": []
    }
    assert state["transcript"] == "Hello meeting"
    assert state["loops"] == 0
    assert isinstance(state["trace"], list)
