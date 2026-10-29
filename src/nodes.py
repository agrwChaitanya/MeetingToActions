import os
import logging
from typing import Dict, Any, List
from langgraph.types import interrupt
from src.schemas import (
    ActionItem, EmailDraft, SummaryOutput, ActionList, CriticOutput, ReviseOutput
)
from src.config import MAX_CRITIC_LOOPS
from src.llm import get_llm

logger = logging.getLogger(__name__)

def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def extract_summary(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running extract_summary node")
    if llm is None:
        llm = get_llm()
    prompt_template = load_prompt("summarize.txt")
    prompt = prompt_template.format(transcript=state.get("transcript", ""))
    
    structured_llm = llm.with_structured_output(SummaryOutput)
    result = structured_llm.invoke(prompt)
    
    return {
        "summary": result.summary,
        "trace": ["extract_summary"]
    }

def extract_actions(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running extract_actions node")
    if llm is None:
        llm = get_llm()
    prompt_template = load_prompt("extract_actions.txt")
    prompt = prompt_template.format(transcript=state.get("transcript", ""))
    
    structured_llm = llm.with_structured_output(ActionList)
    result = structured_llm.invoke(prompt)
    
    actions = []
    for idx, item in enumerate(result.actions, start=1):
        item_dict = item.model_dump()
        if not item_dict.get("id"):
            item_dict["id"] = f"a{idx}"
        actions.append(ActionItem(**item_dict))
        
    return {
        "actions": actions,
        "trace": ["extract_actions"]
    }

def critic(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running critic node")
    if llm is None:
        llm = get_llm()
    prompt_template = load_prompt("critic.txt")
    prompt = prompt_template.format(
        transcript=state.get("transcript", ""),
        summary=state.get("summary", ""),
        actions=str([a.model_dump() for a in state.get("actions", [])])
    )
    
    structured_llm = llm.with_structured_output(CriticOutput)
    result = structured_llm.invoke(prompt)
    
    return {
        "issues": result.issues,
        "trace": ["critic"]
    }

def revise(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running revise node")
    if llm is None:
        llm = get_llm()
    prompt_template = load_prompt("revise.txt")
    prompt = prompt_template.format(
        transcript=state.get("transcript", ""),
        summary=state.get("summary", ""),
        actions=str([a.model_dump() for a in state.get("actions", [])]),
        issues=str(state.get("issues", []))
    )
    
    structured_llm = llm.with_structured_output(ReviseOutput)
    result = structured_llm.invoke(prompt)
    
    loops = state.get("loops", 0) + 1
    return {
        "summary": result.summary,
        "actions": result.actions,
        "issues": [],
        "loops": loops,
        "trace": ["revise"]
    }

def human_review(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Running human_review node")
    resume_value = interrupt({
        "summary": state.get("summary", ""),
        "actions": [a.model_dump() for a in state.get("actions", [])],
        "issues": state.get("issues", [])
    })
    
    approved_actions = []
    if resume_value is not None:
        if isinstance(resume_value, list):
            for item in resume_value:
                if isinstance(item, dict):
                    approved_actions.append(ActionItem(**item))
                elif isinstance(item, ActionItem):
                    approved_actions.append(item)
        else:
            approved_actions = state.get("actions", [])
    else:
        approved_actions = state.get("actions", [])
        
    return {
        "approved": approved_actions,
        "trace": ["human_review"]
    }

def finalize(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running finalize node")
    if llm is None:
        llm = get_llm()
        
    approved = state.get("approved", []) or state.get("actions", [])
    
    owner_map: Dict[str, List[ActionItem]] = {}
    for item in approved:
        owner = item.owner or "Unassigned"
        if owner not in owner_map:
            owner_map[owner] = []
        owner_map[owner].append(item)
        
    prompt_template = load_prompt("email_drafter.txt")
    drafts = []
    for owner, items in owner_map.items():
        items_str = str([item.model_dump() for item in items])
        prompt = prompt_template.format(recipient=owner, approved_actions=items_str)
        structured_llm = llm.with_structured_output(EmailDraft)
        try:
            draft = structured_llm.invoke(prompt)
            draft.task_ids = [item.id for item in items]
            draft.recipient = owner
            drafts.append(draft)
        except Exception as e:
            logger.error(f"Error generating email draft for {owner}: {e}")
            drafts.append(EmailDraft(
                recipient=owner,
                subject=f"Action Items from Meeting",
                body=f"Hello {owner},\n\nPlease review your tasks:\n" + "\n".join([f"- {i.task}" for i in items]),
                task_ids=[item.id for item in items]
            ))
            
    all_items_with_dates = [item for item in approved if item.due_date]
    all_items_without_dates = [item for item in approved if not item.due_date]
    
    sorted_dated = sorted(all_items_with_dates, key=lambda x: x.due_date)
    sorted_items = sorted_dated + all_items_without_dates
    
    timeline = [
        {
            "id": item.id,
            "due_date": item.due_date,
            "task": item.task,
            "owner": item.owner
        }
        for item in sorted_items
    ]
    
    return {
        "drafts": drafts,
        "timeline": timeline,
        "trace": ["finalize"]
    }

def route_after_critic(state: Dict[str, Any]) -> str:
    issues = state.get("issues", [])
    loops = state.get("loops", 0)
    if issues and loops < MAX_CRITIC_LOOPS:
        return "revise"
    return "human_review"
