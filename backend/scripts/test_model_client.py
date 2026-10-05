from app.config.settings import settings
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)


def main() -> None:
    model = OpenAICompatibleChatClient(
        base_url=settings.event_scout_api_base_url,
        api_key=settings.event_scout_api_key,
        model=settings.event_scout_model,
        timeout_seconds=20,
        extra_body={
            "temperature": 0.6,
            "thinking": {
                "type": "disabled",
            },
        },
    )

    print("base_url:", settings.event_scout_api_base_url)
    print("model:", settings.event_scout_model)

    result = model.complete(
        messages=[
            {
                "role": "user",
                "content": "只回答 OK",
            }
        ]
    )

    print(result)


if __name__ == "__main__":
    main()
