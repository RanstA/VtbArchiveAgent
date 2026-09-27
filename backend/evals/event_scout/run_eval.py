import json
from pathlib import Path

from app.config.settings import settings
from app.investigation.event_scout import EventScout
from app.investigation.model_client import OpenAICompatibleChatClient

from evals.event_scout.eval_tools import EvalEventScoutTools


def load_cases() -> list[dict]:
    """
    读取固定 Event Scout Eval Cases。
    """
    cases_path = Path(__file__).with_name("cases.json")

    with cases_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def main() -> None:
    cases = load_cases()
    if not cases:
        raise RuntimeError("No Event Scout eval cases found")

    case = cases[0]

    base_url = (settings.event_scout_api_base_url or "").strip()
    model_name = (settings.event_scout_model or "").strip()
    api_key = (settings.event_scout_api_key or "").strip()

    if not base_url or not model_name:
        raise RuntimeError("Event Scout model is not configured")

    model = OpenAICompatibleChatClient(
        base_url=base_url,
        model=model_name,
        api_key=api_key or None,
        timeout_seconds=(settings.event_scout_timeout_seconds),
    )

    vtuber_id = "aza"

    tools = EvalEventScoutTools(
        case=case,
        vtuber_id=vtuber_id,
    )
    
    scout = EventScout(
        model=model,
        tools=tools,
    )
    
    print(
        f"\n===== CASE: {case['id']} ====="
    )
    print(
        f"Query: {case['query']}"
    )

    result = scout.run(
        query=case["query"],
        vtuber_id=vtuber_id,
    )
    
    print("\n===== RESULT =====")
    print(
        result.model_dump_json(
            by_alias=True,
            indent=2,
        )
    )

    print("\n===== TOOL CALLS =====")
    for name, arguments in tools.calls:
        print(
            f"{name}: {arguments}"
        )


if __name__ == "__main__":
    main()
