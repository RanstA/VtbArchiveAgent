from app.agent.prompts.loader import load_prompt

def test_event_scout_prompt_exists():

    prompt = load_prompt("event_scout")

    assert len(prompt) > 100

    assert (
        "Evidence"
        in prompt
    )