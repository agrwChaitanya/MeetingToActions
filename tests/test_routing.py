import pytest
from src.nodes import route_after_critic

def test_route_after_critic_revise():
    state_revise = {"issues": ["Missing owner"], "loops": 0}
    assert route_after_critic(state_revise) == "revise"

    state_revise_1 = {"issues": ["Missing date"], "loops": 1}
    assert route_after_critic(state_revise_1) == "revise"

def test_route_after_critic_review():
    state_no_issues = {"issues": [], "loops": 0}
    assert route_after_critic(state_no_issues) == "human_review"

    state_max_loops = {"issues": ["Missing owner"], "loops": 2}
    assert route_after_critic(state_max_loops) == "human_review"

    state_max_loops_3 = {"issues": ["Missing owner"], "loops": 3}
    assert route_after_critic(state_max_loops_3) == "human_review"
