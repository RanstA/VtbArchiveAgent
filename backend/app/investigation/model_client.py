from dataclasses import (
    dataclass,
)
from typing import Any

import httpx


class ModelClientError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True
)
class OpenAICompatibleChatClient:
    base_url: str
    model: str

    api_key: (
        str
        | None
    ) = None

    timeout_seconds: float = 60.0

    def complete(
        self,
        *,
        messages: list[
            dict[str, Any]
        ],
        tools: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        endpoint = (
            self.base_url
            .rstrip("/")
            + "/chat/completions"
        )

        headers = {
            "Content-Type": (
                "application/json"
            ),
        }

        if (
            self.api_key
            and self.api_key.strip()
        ):
            headers[
                "Authorization"
            ] = (
                "Bearer "
                + self.api_key.strip()
            )

        payload = {
            "model": (
                self.model
            ),
            "messages": (
                messages
            ),
            "tools": (
                tools
            ),
            "tool_choice": (
                "auto"
            ),
            "temperature": 1,
        }

        try:
            response = httpx.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=(
                    self.timeout_seconds
                ),
            )

            response.raise_for_status()

        except httpx.HTTPError as exc:
            raise ModelClientError(
                "Event Scout model request failed: "
                f"{exc}\n"
                f"response={response.text if 'response' in locals() else ''}"
            ) from exc

        try:
            body = (
                response.json()
            )

            choices = body[
                "choices"
            ]

            message = (
                choices[0][
                    "message"
                ]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as exc:
            raise ModelClientError(
                "Invalid OpenAI-compatible "
                "model response"
            ) from exc

        if not isinstance(
            message,
            dict,
        ):
            raise ModelClientError(
                "Model message must be an object"
            )

        return message