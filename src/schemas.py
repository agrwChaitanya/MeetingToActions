from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class ActionItem(BaseModel):
    id: str = ""
    task: str = ""
    owner: Optional[str] = None
    due_date: Optional[str] = None
    source_quote: str = ""
    notes: str = ""

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"due_date must be in YYYY-MM-DD format, got: '{v}'")
        return v

class EmailDraft(BaseModel):
    recipient: str
    subject: str
    body: str
    task_ids: List[str]

class SummaryOutput(BaseModel):
    summary: str = ""

class ActionList(BaseModel):
    actions: List[ActionItem] = Field(default_factory=list)

class CriticOutput(BaseModel):
    issues: List[str] = Field(default_factory=list)

class ReviseOutput(BaseModel):
    summary: str = ""
    actions: List[ActionItem] = Field(default_factory=list)
