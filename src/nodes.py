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
    
    try:
        structured_llm = llm.with_structured_output(SummaryOutput)
        result = structured_llm.invoke(prompt)
        summary = result.summary
    except Exception as e:
        logger.error(f"Error parsing SummaryOutput: {e}. Falling back to transcript excerpt.")
        summary = state.get("transcript", "")[:500]
    
    return {
        "summary": summary,
        "trace": ["extract_summary"]
    }

def extract_actions(state: Dict[str, Any], llm=None) -> Dict[str, Any]:
    logger.info("Running extract_actions node")
    if llm is None:
        llm = get_llm()
    prompt_template = load_prompt("extract_actions.txt")
    prompt = prompt_template.format(transcript=state.get("transcript", ""))
    
    try:
        structured_llm = llm.with_structured_output(ActionList)
        result = structured_llm.invoke(prompt)
        raw_actions = result.actions
    except Exception as e:
        logger.error(f"Error parsing ActionList: {e}. Falling back to empty actions list.")
        raw_actions = []
    
    actions = []
    for idx, item in enumerate(raw_actions, start=1):
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
    
    try:
        structured_llm = llm.with_structured_output(CriticOutput)
        result = structured_llm.invoke(prompt)
        issues = result.issues
    except Exception as e:
        logger.error(f"Error parsing CriticOutput: {e}. Falling back to zero issues.")
        issues = []
    
    return {
        "issues": issues,
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
    
    try:
        structured_llm = llm.with_structured_output(ReviseOutput)
        result = structured_llm.invoke(prompt)
        
        existing_actions = state.get("actions", [])
        existing_map = {a.id: a for a in existing_actions if a.id}
        
        actions = []
        for idx, item in enumerate(result.actions, start=1):
            item_dict = item.model_dump()
            action_id = item_dict.get("id")
            if not action_id:
                if idx <= len(existing_actions):
                    action_id = existing_actions[idx - 1].id
                else:
                    action_id = f"a{idx}"
            item_dict["id"] = action_id

            if not item_dict.get("source_quote"):
                if action_id in existing_map:
                    item_dict["source_quote"] = existing_map[action_id].source_quote
                else:
                    item_dict["source_quote"] = ""

            if not item_dict.get("task"):
                if action_id in existing_map:
                    item_dict["task"] = existing_map[action_id].task
                else:
                    item_dict["task"] = "Task"

            actions.append(ActionItem(**item_dict))
        
        summary = result.summary if result.summary else state.get("summary", "")
    except Exception as e:
        logger.error(f"Error parsing ReviseOutput: {e}. Falling back to existing actions and summary.")
        summary = state.get("summary", "")
        actions = state.get("actions", [])
    
    loops = state.get("loops", 0) + 1
    return {
        "summary": summary,
        "actions": actions,
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
            task_details = "\n".join([f"- {i.task} (Due: {i.due_date or 'TBD'})" for i in items])
            drafts.append(EmailDraft(
                recipient=owner,
                subject=f"Action Items & Follow-up for {owner} ({len(items)} task{'s' if len(items) > 1 else ''})",
                body=f"Hello {owner},\n\nHere are your assigned action items from our recent meeting:\n\n{task_details}\n\nPlease let us know if you have any questions.\n\nBest regards,\nMeeting Facilitator",
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
