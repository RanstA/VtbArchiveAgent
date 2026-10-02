from datetime import datetime
from pathlib import Path

from app.domain.event import (
    Event,
    make_event_id,
)
from app.domain.source.stream import (
    Stream,
    make_stream_id,
)
from app.domain.source.vtuber import (
    Vtuber,
)
from app.event_pipeline.events import (
    EventCandidate,
)
from app.event_pipeline.semanticizer import (
    EventSemanticizerInput,
)
from app.event_pipeline.stream_semanticizer import (
    semanticize_stream,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.event_repo import (
    list_events_by_stream,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)


class FakeSemanticizer:
    def __init__(self):
        self.inputs = []

    def semanticize(
        self,
        semanticizer_input: EventSemanticizerInput,
    ) -> Event:
        self.inputs.append(semanticizer_input)

        candidate = semanticizer_input.candidate

        offset = semanticizer_input.part_start_offset_ms

        start_ms = offset + candidate.start_ms

        end_ms = offset + candidate.end_ms

        anchor_ms = offset + candidate.peak_ms

        return Event(
            id=make_event_id(
                stream_id=(candidate.stream_id),
                start_ms=start_ms,
                end_ms=end_ms,
            ),
            stream_id=(candidate.stream_id),
            source_part_ids=[
                candidate.part_id,
            ],
            start_ms=start_ms,
            end_ms=end_ms,
            anchor_ms=anchor_ms,
            source_highlight_ids=(candidate.source_highlight_ids),
            title="测试事件",
            summary="测试事件摘要",
            keywords=[
                "测试",
            ],
            entities=[],
            semantic_text=("测试事件\n" "测试事件摘要\n" "测试"),
            salience_score=(semanticizer_input.salience_score),
            segmenter_version=(semanticizer_input.segmenter_version),
            semanticizer_version=("fake-v1"),
        )


def test_semanticize_stream_persists_event(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "semanticizer.db"

    connection = connect_db(db_path)

    try:
        init_db(connection)

        vtuber = Vtuber(
            id="aza",
            display_name="阿萨Aza",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        live_time = datetime(
            2026,
            9,
            29,
            20,
            0,
        )

        stream_id = make_stream_id(
            vtuber_id="aza",
            live_time=live_time,
        )

        insert_stream(
            connection=connection,
            stream=Stream(
                id=stream_id,
                vtuber_id="aza",
                live_time=live_time,
                title="测试直播",
            ),
        )

        semanticizer_input = EventSemanticizerInput(
            candidate=EventCandidate(
                stream_id=stream_id,
                part_id="p1",
                start_ms=10_000,
                end_ms=40_000,
                peak_ms=20_000,
                source_highlight_ids=[
                    "highlight-1",
                ],
            ),
            stream_title=("测试直播"),
            danmaku_texts=[
                "测试弹幕",
            ],
            part_start_offset_ms=(100_000),
            salience_score=0.97,
        )

        monkeypatch.setattr(
            (
                "app.event_pipeline."
                "stream_semanticizer."
                "build_semanticizer_inputs_for_stream"
            ),
            lambda **_: [semanticizer_input],
        )

        fake = FakeSemanticizer()

        events = semanticize_stream(
            connection=connection,
            stream_id=stream_id,
            semanticizer=fake,
            limit=1,
        )

        assert events is not None
        assert len(events) == 1

        assert len(fake.inputs) == 1

        assert fake.inputs[0].stream_title == "测试直播"

        event = events[0]

        # p1 offset = 100 秒
        assert event.start_ms == 110_000
        assert event.end_ms == 140_000
        assert event.anchor_ms == 120_000

        persisted = list_events_by_stream(
            connection=connection,
            stream_id=stream_id,
        )

        assert persisted == [event]

    finally:
        connection.close()
