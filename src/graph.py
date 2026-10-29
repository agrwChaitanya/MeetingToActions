from langgraph.graph import StateGraph, START, END
from src.state import MeetingState
from src.nodes import (
    extract_summary,
    extract_actions,
    critic,
    revise,
    human_review,
    finalize,
    route_after_critic
)

def build_graph():
    workflow = StateGraph(MeetingState)

    # Add nodes
    workflow.add_node("extract_summary", extract_summary)
    workflow.add_node("extract_actions", extract_actions)
    workflow.add_node("critic", critic)
    workflow.add_node("revise", revise)
    workflow.add_node("human_review", human_review)
    workflow.add_node("finalize", finalize)

    # Add edges for parallel fan-out from START to extract_summary and extract_actions
    workflow.add_edge(START, "extract_summary")
    workflow.add_edge(START, "extract_actions")

    # Fan-in from extract_summary and extract_actions to critic
    workflow.add_edge("extract_summary", "critic")
    workflow.add_edge("extract_actions", "critic")

    # Conditional edge from critic using route_after_critic
    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "revise": "revise",
            "human_review": "human_review"
        }
    )

    # Revise loops back to critic
    workflow.add_edge("revise", "critic")

    # human_review leads to finalize
    workflow.add_edge("human_review", "finalize")

    # finalize leads to END
    workflow.add_edge("finalize", END)

    return workflow

graph = build_graph().compile()
