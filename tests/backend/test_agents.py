from src.backend.agents import all_scripted_actions, dispute_agent_actions


def test_all_scripted_actions_nonempty_and_labeled():
    actions = all_scripted_actions()
    assert len(actions) >= 6
    assert all(a.label in ("in_policy", "violation") for a in actions)


def test_dispute_agent_has_at_least_one_violation():
    actions = dispute_agent_actions()
    assert any(a.label == "violation" for a in actions)


def test_each_action_has_agent_id_matching_its_generator():
    actions = dispute_agent_actions()
    assert all(a.action.agent_id == "dispute_agent" for a in actions)
