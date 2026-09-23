from collections import (
    Counter,
)
from pathlib import Path
from typing import Any

from app.repository.database import (
    connect_db,
)
from app.repository.danmaku_repo import (
    list_danmaku_window,
)
from app.repository.highlight_repo import (
    get_highlight_by_id,
    search_highlights_for_vtuber,
)
from app.repository.stream_repo import (
    get_stream_by_id,
)


class EventScoutTools:
    """
    Event Scout 可访问的最小工具集合。

    Scout 不直接拿 SQLite connection，
    只能经过这个 Harness boundary。
    """

    def __init__(
        self,
        *,
        database_path: Path,
        vtuber_id: str,
    ) -> None:
        self.database_path = (
            database_path
        )

        self.vtuber_id = (
            vtuber_id
        )

    @staticmethod
    def tool_schemas() -> list[
        dict[str, Any]
    ]:
        return [
            {
                "type": "function",
                "function": {
                    "name": (
                        "search_highlights"
                    ),
                    "description": (
                        "Search high audience-reaction "
                        "Highlight candidates for the "
                        "current VTuber workspace. "
                        "Use this before inspecting "
                        "raw danmaku."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top_k": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 12,
                                "description": (
                                    "Number of Highlight "
                                    "candidates to retrieve."
                                ),
                            },
                            "min_score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": (
                                    "Minimum detector score."
                                ),
                            },
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": (
                        "get_danmaku_window"
                    ),
                    "description": (
                        "Read audience danmaku inside "
                        "one retrieved Highlight. "
                        "This is audience reaction "
                        "evidence only and does not "
                        "prove what the streamer said "
                        "or did."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "highlight_id": {
                                "type": "string",
                                "description": (
                                    "Stable Highlight ID "
                                    "returned by "
                                    "search_highlights."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                            },
                        },
                        "required": [
                            "highlight_id",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def execute(
        self,
        name: str,
        arguments: dict[
            str,
            Any,
        ],
    ) -> dict:
        if (
            name
            == "search_highlights"
        ):
            return (
                self.search_highlights(
                    top_k=arguments.get(
                        "top_k",
                        8,
                    ),
                    min_score=arguments.get(
                        "min_score",
                        0.85,
                    ),
                )
            )

        if (
            name
            == "get_danmaku_window"
        ):
            return (
                self.get_danmaku_window(
                    highlight_id=str(
                        arguments.get(
                            "highlight_id",
                            "",
                        )
                    ),
                    limit=arguments.get(
                        "limit",
                        80,
                    ),
                )
            )

        raise ValueError(
            f"unknown Event Scout tool: {name}"
        )

    def search_highlights(
        self,
        *,
        top_k: int = 8,
        min_score: float = 0.85,
    ) -> dict:
        top_k = min(
            max(
                int(
                    top_k
                ),
                1,
            ),
            12,
        )

        min_score = min(
            max(
                float(
                    min_score
                ),
                0.0,
            ),
            1.0,
        )

        connection = connect_db(
            self.database_path
        )

        try:
            rows = (
                search_highlights_for_vtuber(
                    connection,
                    vtuber_id=(
                        self.vtuber_id
                    ),
                    limit=top_k,
                    min_score=min_score,
                )
            )

        finally:
            connection.close()

        candidates = []

        for row in rows:
            highlight = row[
                "highlight"
            ]

            candidates.append(
                {
                    "highlight_id": (
                        highlight.id
                    ),
                    "stream_id": (
                        highlight.stream_id
                    ),
                    "stream_title": (
                        row[
                            "stream_title"
                        ]
                    ),
                    "live_time": (
                        row[
                            "live_time"
                        ]
                    ),
                    "part_id": (
                        highlight.part_id
                    ),
                    "start_ms": (
                        highlight.start_ms
                    ),
                    "end_ms": (
                        highlight.end_ms
                    ),
                    "peak_ms": (
                        highlight.peak_ms
                    ),
                    "score": (
                        highlight.score
                    ),
                    "density_score": (
                        highlight
                        .density_score
                    ),
                    "repetition_score": (
                        highlight
                        .repetition_score
                    ),
                    "reaction_score": (
                        highlight
                        .reaction_score
                    ),
                    "danmaku_count": (
                        highlight
                        .danmaku_count
                    ),
                    "laugh_count": (
                        highlight
                        .laugh_count
                    ),
                    "question_count": (
                        highlight
                        .question_count
                    ),
                    "exclamation_count": (
                        highlight
                        .exclamation_count
                    ),
                    "evidence_id": (
                        "highlight:"
                        f"{highlight.id}"
                    ),
                }
            )

        return {
            "vtuber_id": (
                self.vtuber_id
            ),
            "candidate_count": len(
                candidates
            ),
            "candidates": (
                candidates
            ),
        }

    def get_danmaku_window(
        self,
        *,
        highlight_id: str,
        limit: int = 80,
    ) -> dict:
        highlight_id = (
            highlight_id.strip()
        )

        if not highlight_id:
            raise ValueError(
                "highlight_id cannot be empty"
            )

        limit = min(
            max(
                int(
                    limit
                ),
                1,
            ),
            120,
        )

        connection = connect_db(
            self.database_path
        )

        try:
            highlight = (
                get_highlight_by_id(
                    connection,
                    highlight_id,
                )
            )

            if highlight is None:
                raise ValueError(
                    "Highlight not found"
                )

            stream = (
                get_stream_by_id(
                    connection,
                    highlight.stream_id,
                )
            )

            if stream is None:
                raise ValueError(
                    "Highlight stream not found"
                )

            if (
                stream[
                    "vtuber_id"
                ]
                != self.vtuber_id
            ):
                raise ValueError(
                    "Highlight does not belong "
                    "to current VTuber workspace"
                )

            danmaku = (
                list_danmaku_window(
                    connection,
                    stream_id=(
                        highlight.stream_id
                    ),
                    part_id=(
                        highlight.part_id
                    ),
                    start_ms=(
                        highlight.start_ms
                    ),
                    end_ms=(
                        highlight.end_ms
                    ),
                    limit=limit,
                )
            )

        finally:
            connection.close()

        text_counter = Counter(
            item["text"]
            for item in danmaku
            if item["text"].strip()
        )

        top_texts = [
            {
                "text": text,
                "count": count,
            }
            for text, count
            in text_counter.most_common(
                10
            )
        ]

        return {
            "highlight_id": (
                highlight.id
            ),
            "stream_id": (
                highlight.stream_id
            ),
            "stream_title": (
                stream["title"]
            ),
            "live_time": (
                stream["live_time"]
            ),
            "part_id": (
                highlight.part_id
            ),
            "start_ms": (
                highlight.start_ms
            ),
            "end_ms": (
                highlight.end_ms
            ),
            "peak_ms": (
                highlight.peak_ms
            ),
            "score": (
                highlight.score
            ),
            "returned_count": len(
                danmaku
            ),
            "top_texts": (
                top_texts
            ),
            "danmaku": [
                {
                    "id": item[
                        "id"
                    ],
                    "evidence_id": (
                        "danmaku:"
                        f"{item['id']}"
                    ),
                    "timestamp_ms": (
                        item[
                            "timestamp_ms"
                        ]
                    ),
                    "text": (
                        item[
                            "text"
                        ]
                    ),
                }
                for item
                in danmaku
            ],
            "evidence_boundary": (
                "These are audience reactions. "
                "They do not prove streamer "
                "speech or actions."
            ),
        }