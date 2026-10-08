from copy import deepcopy
from datetime import datetime
import sqlite3

import pytest

from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.source.stream import Stream
from app.domain.source.stream_part import StreamPart
from app.domain.source.vtuber import Vtuber
from app.investigation.evidence_aggregation import aggregate_evidence_windows
from app.investigation.evidence_bundle import build_investigation_evidence
from app.investigation.evidence_context import expand_evidence_window
from app.investigation.evidence_selector import select_window_evidence
from app.repository.danmaku_repo import insert_danmaku_batch, search_danmaku_for_vtuber
from app.repository.database import init_db
from app.repository.stream_part_repo import insert_stream_part
from app.repository.stream_repo import insert_stream
from app.repository.transcript_segment_repo import (
    insert_transcript_segment,
    search_transcripts_for_vtuber,
)
from app.repository.vtuber_repo import insert_vtuber


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    for vtuber_id in ("v1", "v2"):
        insert_vtuber(connection, Vtuber(id=vtuber_id, display_name=vtuber_id))
    for index, vtuber_id in enumerate(("v1", "v1", "v2"), start=1):
        stream_id = f"s{index}"
        insert_stream(connection, Stream(
            id=stream_id, vtuber_id=vtuber_id, title=f"直播 {index}",
            live_time=datetime(2026, 10, index),
        ))
        for part_id, offset in (("p0", 0), ("p1", 100_000)):
            insert_stream_part(connection, StreamPart(
                stream_id=stream_id, part_id=part_id, start_offset_ms=offset,
            ))
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def add_danmaku(db, timestamp_ms, text, *, stream_id="s1", part_id="p0"):
    part_db_id = db.execute(
        "SELECT id FROM stream_parts WHERE stream_id = ? AND part_id = ?",
        (stream_id, part_id),
    ).fetchone()[0]
    insert_danmaku_batch(db, part_db_id, [{
        "timestamp_ms": timestamp_ms, "text": text, "raw_text": f"{{ASS}}{text}",
    }])
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def add_transcript(db, start, end, text, *, stream_id="s1", part_id="p0", id=None):
    values = {"id": id} if id is not None else {}
    transcript = TranscriptSegment(
        **values, stream_id=stream_id, part_id=part_id, start_ms=start, end_ms=end,
        raw_text=f" 原始{text} ", text=text, source="test_subtitle",
    )
    insert_transcript_segment(db, transcript)
    return transcript


def windows(db, *, query="车祸", radius_ms=10_000):
    return aggregate_evidence_windows(
        search_transcripts_for_vtuber(db, vtuber_id="v1", query=query),
        search_danmaku_for_vtuber(db, vtuber_id="v1", query=query),
        radius_ms=radius_ms,
    )


def test_danmaku_only_preserves_audience_boundary_and_real_ids(db):
    seed = add_danmaku(db, 12_000, "车祸")
    nearby = add_danmaku(db, 13_000, "好")
    add_danmaku(db, 50_000, "远处")
    bundle = build_investigation_evidence(db, "v1", "车祸")
    assert (bundle.transcript_hit_count, bundle.danmaku_hit_count) == (0, 1)
    assert bundle.evidence_boundary == "speech_and_audience_reaction_separate"
    context = bundle.windows[0]
    assert context.speech_evidence == []
    assert [item.id for item in context.audience_reaction_evidence] == [seed, nearby]
    assert context.seed_evidence_ids == [f"danmaku:{seed}"]
    first = context.audience_reaction_evidence[0]
    assert first.is_seed and first.source is None
    assert first.raw_text == "{ASS}车祸"
    assert first.text == "车祸"
    assert first.timestamp_ms == first.stream_timestamp_ms == 12_000


def test_speech_only_has_no_invented_audience_reactions(db):
    seed = add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    add_transcript(db, 12_000, 13_000, "后续发言", id="context")
    bundle = build_investigation_evidence(db, "v1", "车祸")
    context = bundle.windows[0]
    assert context.audience_reaction_evidence == []
    assert context.seed_evidence_ids == [f"transcript:{seed.id}"]
    assert [item.id for item in context.speech_evidence] == ["seed", "context"]
    assert context.speech_evidence[0].source == "test_subtitle"
    assert context.speech_evidence[0].raw_text == seed.raw_text


def test_overlapping_windows_merge_and_keep_all_mixed_seeds(db):
    first = add_transcript(db, 10_000, 12_000, "车祸前", id="first")
    second = add_transcript(db, 20_000, 21_000, "车祸后", id="second")
    d1 = add_danmaku(db, 11_000, "车祸")
    d2 = add_danmaku(db, 25_000, "又车祸了")
    aggregated = windows(db)
    assert len(aggregated) == 1
    bundle = build_investigation_evidence(db, "v1", "车祸")
    assert len(bundle.windows) == 1
    selected = bundle.windows[0]
    assert selected.local_start_ms == 0
    assert selected.local_end_ms == 35_001
    assert set(selected.seed_evidence_ids) == {
        f"transcript:{first.id}", f"transcript:{second.id}", f"danmaku:{d1}", f"danmaku:{d2}",
    }
    assert all(item.is_seed for item in [*selected.speech_evidence, *selected.audience_reaction_evidence])


def test_stream_part_and_vtuber_isolation_through_entire_chain(db):
    for stream_id, part_id in (("s1", "p0"), ("s1", "p1"), ("s2", "p0"), ("s3", "p0")):
        add_transcript(db, 10_000, 12_000, "车祸", stream_id=stream_id, part_id=part_id)
        add_danmaku(db, 11_000, "附近观众", stream_id=stream_id, part_id=part_id)
    bundle = build_investigation_evidence(db, "v1", "车祸")
    assert [(w.stream_id, w.part_id) for w in bundle.windows] == [
        ("s2", "p0"), ("s1", "p0"), ("s1", "p1"),
    ]
    assert bundle.transcript_hit_count == 3
    for window in bundle.windows:
        assert len(window.speech_evidence) == len(window.audience_reaction_evidence) == 1
        assert all((item.stream_id, item.part_id) == (window.stream_id, window.part_id)
                   for item in [*window.speech_evidence, *window.audience_reaction_evidence])


def test_context_uses_half_open_danmaku_and_overlapping_transcripts(db):
    add_danmaku(db, 100, "车祸")
    at_start = add_danmaku(db, 90, "左边界")
    at_end = add_danmaku(db, 111, "右边界")
    add_transcript(db, 80, 90, "结束于左边界", id="exclude-left")
    add_transcript(db, 111, 120, "始于右边界", id="exclude-right")
    add_transcript(db, 80, 95, "跨左边界", id="cross-left")
    add_transcript(db, 105, 120, "跨右边界", id="cross-right")
    context = expand_evidence_window(db, windows(db, radius_ms=10)[0], vtuber_id="v1")
    assert (context.local_start_ms, context.local_end_ms) == (90, 111)
    assert [item.id for item in context.speech_evidence] == ["cross-left", "cross-right"]
    assert at_start in [item.id for item in context.audience_reaction_evidence]
    assert at_end not in [item.id for item in context.audience_reaction_evidence]


def test_original_times_and_global_offsets_are_both_preserved(db):
    transcript = add_transcript(db, 3_000, 6_500, "正文", part_id="p1")
    add_danmaku(db, 5_000, "车祸", part_id="p1")
    context = build_investigation_evidence(db, "v1", "车祸").windows[0]
    assert (context.local_start_ms, context.local_end_ms) == (0, 15_001)
    assert (context.stream_start_ms, context.stream_end_ms) == (100_000, 115_001)
    assert context.start_offset_ms == 100_000
    speech = context.speech_evidence[0]
    assert (speech.start_ms, speech.end_ms) == (transcript.start_ms, transcript.end_ms)
    assert (speech.stream_start_ms, speech.stream_end_ms) == (103_000, 106_500)
    audience = context.audience_reaction_evidence[0]
    assert audience.timestamp_ms == 5_000
    assert audience.stream_timestamp_ms == 105_000


def test_late_seed_survives_dense_context_and_selection_caps(db):
    for i in range(150):
        add_danmaku(db, i * 10, "重复观众消息")
    seed = add_danmaku(db, 2_000, "车祸")
    for i in range(8):
        add_transcript(db, i * 100, i * 100 + 50, "附近发言", id=f"t{i}")
    speech_seed = add_transcript(db, 2_000, 2_050, "车祸", id="late-seed")
    context = build_investigation_evidence(
        db, "v1", "车祸", max_transcripts=2, max_danmaku=4,
    ).windows[0]
    assert len(context.audience_reaction_evidence) == 4
    assert context.audience_reaction_available == 151
    assert seed in [item.id for item in context.audience_reaction_evidence]
    assert len(context.speech_evidence) == 2
    assert context.speech_available == 9
    assert speech_seed.id in [item.id for item in context.speech_evidence]


def test_repetition_and_punctuation_are_downranked_but_short_text_is_kept(db):
    seed = add_danmaku(db, 10_000, "车祸")
    for i in range(5):
        add_danmaku(db, 10_001 + i, "刷屏")
    short = add_danmaku(db, 10_010, "好")
    useful = add_danmaku(db, 10_011, "怎么了")
    punctuation = add_danmaku(db, 10_000, "？？？")
    context = expand_evidence_window(db, windows(db)[0], vtuber_id="v1")
    selected = select_window_evidence(context, max_danmaku=4)
    ids = [item.id for item in selected.audience_reaction_evidence]
    assert seed in ids and short in ids and useful in ids
    assert punctuation not in ids
    assert sum(item.text == "刷屏" for item in selected.audience_reaction_evidence) == 1
    complete = select_window_evidence(context, max_danmaku=100)
    assert punctuation in [item.id for item in complete.audience_reaction_evidence]


def test_low_information_seed_is_never_downranked_out(db):
    seed = add_danmaku(db, 10_000, "？")
    add_danmaku(db, 10_001, "有内容的观众反应")
    result = build_investigation_evidence(db, "v1", "？", max_danmaku=1)
    assert [item.id for item in result.windows[0].audience_reaction_evidence] == [seed]


def test_selector_deduplicates_ids_sorts_and_does_not_mutate_context(db):
    add_transcript(db, 10_000, 10_100, "车祸", id="z")
    add_transcript(db, 10_000, 10_100, "车祸", id="a")
    add_danmaku(db, 10_000, "车祸")
    context = expand_evidence_window(db, windows(db)[0], vtuber_id="v1")
    context.speech_evidence.extend(context.speech_evidence[:1])
    context.audience_reaction_evidence.extend(context.audience_reaction_evidence[:1])
    before = context.model_dump()
    result = select_window_evidence(context)
    assert [item.id for item in result.speech_evidence] == ["a", "z"]
    assert len(result.audience_reaction_evidence) == 1
    assert context.model_dump() == before


@pytest.mark.parametrize("kind", ["speech", "audience"])
def test_seed_overflow_is_explicit_not_silent_loss_or_cap_overrun(db, kind):
    for i in range(2):
        if kind == "speech":
            add_transcript(db, 10_000 + i, 11_000 + i, "车祸")
        else:
            add_danmaku(db, 10_000 + i, "车祸")
    with pytest.raises(ValueError, match="seed evidence exceeds"):
        build_investigation_evidence(db, "v1", "车祸", max_transcripts=1, max_danmaku=1)


@pytest.mark.parametrize("query", ["", " \t ", "找不到", "%", "' OR 1=1 --"])
def test_empty_or_no_literal_hits_returns_empty_bundle(db, query):
    add_danmaku(db, 10_000, "车祸")
    bundle = build_investigation_evidence(db, "v1", query)
    assert bundle.windows == []
    assert bundle.transcript_hit_count == bundle.danmaku_hit_count == 0


def test_max_windows_and_retrieval_limits_bound_results(db):
    for i in range(25):
        add_danmaku(db, i * 30_000, "车祸")
    limited = build_investigation_evidence(db, "v1", "车祸", max_windows=2)
    assert len(limited.windows) == 2
    assert limited.danmaku_hit_count == 20
    all_retrieved = build_investigation_evidence(db, "v1", "车祸", max_windows=50)
    assert len(all_retrieved.windows) == 20


@pytest.mark.parametrize("parameters", [
    {"max_windows": 0}, {"max_windows": 51}, {"max_windows": 1.5},
    {"max_transcripts": 0}, {"max_danmaku": 101}, {"max_danmaku": True},
])
def test_invalid_budgets_fail_even_without_hits(db, parameters):
    with pytest.raises(ValueError):
        build_investigation_evidence(db, "v1", "", **parameters)


@pytest.mark.parametrize("vtuber_id", ["", "  ", "unknown"])
def test_invalid_vtuber_is_rejected(db, vtuber_id):
    with pytest.raises(ValueError):
        build_investigation_evidence(db, vtuber_id, "车祸")


def test_context_refuses_foreign_vtuber_and_missing_part(db):
    add_danmaku(db, 10_000, "车祸")
    window = windows(db)[0]
    with pytest.raises(ValueError, match="VTuber workspace"):
        expand_evidence_window(db, window, vtuber_id="v2")
    window["part_id"] = "missing"
    with pytest.raises(ValueError, match="VTuber workspace"):
        expand_evidence_window(db, window, vtuber_id="v1")


@pytest.mark.parametrize("stream_id,part_id", [("s2", "p0"), ("s1", "p1"), ("s3", "p0")])
def test_context_rejects_seed_id_from_another_stream_or_part(db, stream_id, part_id):
    add_danmaku(db, 10_000, "车祸")
    foreign = add_danmaku(db, 10_000, "外部", stream_id=stream_id, part_id=part_id)
    window = windows(db)[0]
    window["matches"][0]["evidence_id"] = f"danmaku:{foreign}"
    with pytest.raises(ValueError, match="seed evidence missing"):
        expand_evidence_window(db, window, vtuber_id="v1")


def test_context_rejects_foreign_transcript_seed(db):
    add_transcript(db, 10_000, 11_000, "车祸", id="own")
    foreign = add_transcript(db, 10_000, 11_000, "其他字幕", stream_id="s2", id="foreign")
    window = windows(db)[0]
    window["matches"][0]["evidence_id"] = f"transcript:{foreign.id}"
    with pytest.raises(ValueError, match="seed evidence missing"):
        expand_evidence_window(db, window, vtuber_id="v1")


@pytest.mark.parametrize("change", ["missing", "seed_time", "seed_kind", "offset", "bad_bounds"])
def test_context_rejects_stale_or_tampered_seed_and_window(db, change):
    seed = add_danmaku(db, 10_000, "车祸")
    window = deepcopy(windows(db)[0])
    if change == "missing":
        db.execute("DELETE FROM danmaku WHERE id = ?", (seed,))
    elif change == "seed_time":
        window["matches"][0]["local_start_ms"] += 1
    elif change == "seed_kind":
        window["matches"][0]["kind"] = "transcript"
    elif change == "offset":
        window["stream_start_ms"] += 1
    else:
        window["local_start_ms"] = -1
    with pytest.raises(ValueError):
        expand_evidence_window(db, window, vtuber_id="v1")


def test_bundle_is_deterministic_read_only_and_closes_own_transaction(db):
    add_transcript(db, 10_000, 11_000, "车祸")
    add_danmaku(db, 10_000, "车祸")
    db.commit()
    before = "\n".join(db.iterdump())
    changes = db.total_changes
    first = build_investigation_evidence(db, " v1 ", " 车祸 ")
    second = build_investigation_evidence(db, "v1", "车祸")
    assert first.model_dump_json() == second.model_dump_json()
    assert not db.in_transaction
    assert db.total_changes == changes
    assert "\n".join(db.iterdump()) == before


def test_bundle_preserves_callers_uncommitted_transaction_on_success_and_failure(db):
    add_danmaku(db, 10_000, "车祸")
    add_danmaku(db, 10_001, "车祸")
    assert db.in_transaction
    assert build_investigation_evidence(db, "v1", "车祸").danmaku_hit_count == 2
    with pytest.raises(ValueError, match="seed evidence exceeds"):
        build_investigation_evidence(db, "v1", "车祸", max_danmaku=1)
    assert db.in_transaction
    assert db.execute("SELECT COUNT(*) FROM danmaku").fetchone()[0] == 2
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM danmaku").fetchone()[0] == 0
