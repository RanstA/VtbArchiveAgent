from app.domain.highlight import Highlight, make_highlight_id
from app.event_pipeline.events import merge_highlights


def make_highlight(
    *,
    start_ms: int,
    end_ms: int,
    peak_ms: int,
    score: float = 0.9,
    stream_id: str = "stream-1",
    part_id: str = "part-1",
) -> Highlight:
    return Highlight(
        id=make_highlight_id(
            stream_id=stream_id,
            part_id=part_id,
            start_ms=start_ms,
            end_ms=end_ms,
        ),
        stream_id=stream_id,
        part_id=part_id,
        start_ms=start_ms,
        end_ms=end_ms,
        peak_ms=peak_ms,
        score=score,
        density_score=0.9,
        repetition_score=0.8,
        reaction_score=0.7,
        danmaku_count=100,
        unique_text_count=50,
        repetition_ratio=0.3,
        reaction_ratio=0.4,
        laugh_count=20,
        question_count=10,
        exclamation_count=5,
        detector_version="v0.1",
    )


def test_overlapping_highlights_are_merged():
    highlights = [
        make_highlight(
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
        ),
        make_highlight(
            start_ms=20_000,
            end_ms=50_000,
            peak_ms=35_000,
        ),
    ]

    result = merge_highlights(highlights)

    assert len(result) == 1
    assert result[0].start_ms == 0
    assert result[0].end_ms == 50_000
    assert len(result[0].source_highlight_ids) == 2


def test_nearby_highlights_are_merged():
    highlights = [
        make_highlight(
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
        ),
        make_highlight(
            start_ms=40_000,
            end_ms=70_000,
            peak_ms=55_000,
        ),
    ]

    result = merge_highlights(highlights)

    assert len(result) == 1


def test_distant_highlights_are_not_merged():
    highlights = [
        make_highlight(
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
        ),
        make_highlight(
            start_ms=50_000,
            end_ms=80_000,
            peak_ms=65_000,
        ),
    ]

    result = merge_highlights(highlights)

    assert len(result) == 2


def test_highlights_from_different_parts_are_not_merged():
    highlights = [
        make_highlight(
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
            part_id="part-1",
        ),
        make_highlight(
            start_ms=20_000,
            end_ms=50_000,
            peak_ms=35_000,
            part_id="part-2",
        ),
    ]

    result = merge_highlights(highlights)

    assert len(result) == 2


def test_event_duration_limit_prevents_chain_merge():
    highlights = [
        make_highlight(
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
        ),
        make_highlight(
            start_ms=40_000,
            end_ms=70_000,
            peak_ms=55_000,
        ),
        make_highlight(
            start_ms=80_000,
            end_ms=110_000,
            peak_ms=95_000,
        ),
        make_highlight(
            start_ms=120_000,
            end_ms=150_000,
            peak_ms=135_000,
        ),
    ]

    result = merge_highlights(
        highlights,
        max_event_duration_ms=120_000,
    )

    assert len(result) == 2
    assert result[0].start_ms == 0
    assert result[0].end_ms == 110_000
    assert result[1].start_ms == 120_000
    assert result[1].end_ms == 150_000