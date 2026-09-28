from app.config.settings import settings
from app.event_pipeline.events import (
    merge_highlights,
)
from app.event_pipeline.semanticizer import (
    EventSemanticizer,
    EventSemanticizerInput,
)
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)
from app.repository.database import (
    connect_db,
)
from app.repository.danmaku_repo import (
    list_danmaku_window,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
)
from app.repository.stream_repo import (
    list_streams,
)


SAMPLE_COUNT = 3
DANMAKU_LIMIT = 120


def main() -> None:
    if not settings.event_scout_api_base_url:
        raise RuntimeError(
            "EVENT_SCOUT_API_BASE_URL is required"
        )

    if not settings.event_scout_model:
        raise RuntimeError(
            "EVENT_SCOUT_MODEL is required"
        )

    model = OpenAICompatibleChatClient(
        base_url=(
            settings.event_scout_api_base_url
        ),
        api_key=(
            settings.event_scout_api_key
        ),
        model=(
            settings.event_scout_model
        ),
        timeout_seconds=(
            settings.event_scout_timeout_seconds
        ),
    )

    semanticizer = EventSemanticizer(
        model=model
    )

    connection = connect_db(
        settings.database_path
    )

    generated = 0

    try:
        streams = list_streams(
            connection
        )

        # 从较早直播开始看，
        # 每场最多抽一个 candidate，
        # 尽量让 3 个样例来自不同直播。
        for stream in reversed(streams):
            if generated >= SAMPLE_COUNT:
                break

            stream_id = stream["id"]

            highlights = (
                list_highlights_by_stream(
                    connection,
                    stream_id,
                )
            )

            if not highlights:
                continue

            candidates = merge_highlights(
                highlights
            )

            # 优先测试真正由多个 Highlight
            # 合并出来的 EventCandidate。
            candidates = sorted(
                candidates,
                key=lambda candidate: (
                    -len(
                        candidate
                        .source_highlight_ids
                    ),
                    candidate.start_ms,
                ),
            )

            selected = None
            selected_danmaku = None

            for candidate in candidates:
                danmaku = list_danmaku_window(
                    connection,
                    stream_id=(
                        candidate.stream_id
                    ),
                    part_id=(
                        candidate.part_id
                    ),
                    start_ms=(
                        candidate.start_ms
                    ),
                    end_ms=(
                        candidate.end_ms
                    ),
                    limit=DANMAKU_LIMIT,
                )

                if not danmaku:
                    continue

                selected = candidate
                selected_danmaku = danmaku
                break

            if (
                selected is None
                or selected_danmaku is None
            ):
                continue

            texts = [
                (
                    item["text"]
                    or item["raw_text"]
                ).strip()
                for item in selected_danmaku
                if (
                    item["text"]
                    or item["raw_text"]
                ).strip()
            ]

            if not texts:
                continue

            print()
            print("=" * 80)
            print(
                f"Stream: {stream['title']}"
            )
            print(
                f"Part: {selected.part_id}"
            )
            print(
                f"Range: "
                f"{selected.start_ms} "
                f"→ {selected.end_ms}"
            )
            print(
                "Source Highlights: "
                f"{len(selected.source_highlight_ids)}"
            )
            print(
                f"Danmaku: {len(texts)}"
            )

            print()
            print("Sample Danmaku:")
            for text in texts[:10]:
                print(
                    f"  - {text}"
                )

            event = semanticizer.semanticize(
                EventSemanticizerInput(
                    candidate=selected,
                    stream_title=(
                        stream["title"]
                    ),
                    danmaku_texts=texts,
                )
            )

            print()
            print("Semanticized Event:")
            print(
                f"  ID: {event.id}"
            )
            print(
                f"  Title: {event.title}"
            )
            print(
                f"  Summary: {event.summary}"
            )
            print(
                f"  Keywords: {event.keywords}"
            )
            print(
                f"  Entities: {event.entities}"
            )

            print()
            print("Semantic Text:")
            print(
                event.semantic_text
            )

            generated += 1

    finally:
        connection.close()

    print()
    print("=" * 80)
    print(
        f"Generated Events: {generated}"
    )


if __name__ == "__main__":
    main()