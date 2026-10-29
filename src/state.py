import operator
from typing import Annotated, List, Dict, Any
from typing_extensions import TypedDict
from src.schemas import ActionItem, EmailDraft

class MeetingState(TypedDict):
    transcript: str
    summary: str
    actions: List[ActionItem]
    issues: List[str]
    loops: int
    trace: Annotated[List[str], operator.add]
    approved: List[ActionItem]
    drafts: List[EmailDraft]
    timeline: List[Dict[str, Any]]
