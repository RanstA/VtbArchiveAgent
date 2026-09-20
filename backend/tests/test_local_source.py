from datetime import datetime
from pathlib import Path
import shutil

from app.domain.stream import (
    Stream,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.ingestion.local_source import (
    LocalSource,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
)


TEST_VTUBER = Vtuber(
    id="vtuber-test",
    display_name="测试主播",
)


def make_stream(
    *,
    title: str = "测试直播",
) -> Stream:
    return Stream(
        id="stream-test",
        vtuber_id=(
            TEST_VTUBER.id
        ),
        month="2025-09",
        live_time=datetime(
            2025,
            9,
            11,
            19,
            0,
        ),
        publish_times=[],
        bv_ids=[],
        title=title,
        video_url="",
        status="local",
    )


def test_local_source_loads_nested_layout(
    tmp_path: Path,
) -> None:
    stream = make_stream()

    stream_directory = (
        tmp_path
        / "2025年9月录播"
        / stream.title
    )

    stream_directory.mkdir(
        parents=True
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        stream_directory
        / "archive_123.ass",
    )

    (
        stream_directory
        / "archive_123.xml"
    ).touch()

    source = LocalSource(
        stream=stream,
        archive_root=tmp_path,
        vtuber=TEST_VTUBER,
    )

    bundle = source.load()

    assert (
        bundle.source
        == "local"
    )

    assert (
        bundle.vtuber
        == TEST_VTUBER
    )

    assert (
        bundle.stream.id
        == "stream-test"
    )

    assert (
        bundle.stream.vtuber_id
        == TEST_VTUBER.id
    )

    assert (
        len(
            bundle.vtuber_sources
        )
        == 1
    )

    vtuber_source = (
        bundle.vtuber_sources[0]
    )

    assert (
        vtuber_source.vtuber_id
        == TEST_VTUBER.id
    )

    assert (
        vtuber_source.source
        == "local"
    )

    assert (
        vtuber_source.display_name
        == TEST_VTUBER.display_name
    )

    assert (
        bundle.source_metadata[
            "layout"
        ]
        == "nested"
    )

    assert len(
        bundle.parts
    ) == 1

    assert (
        bundle.parts[0]
        .part_id
        == "p0"
    )

    assert (
        bundle.parts[0]
        .danmaku_path
        is not None
    )

    assert (
        bundle.parts[0]
        .xml_path
        is not None
    )

    assert len(
        bundle.danmaku
    ) == 2

    assert all(
        item.part_id
        == "p0"
        for item
        in bundle.danmaku
    )


def test_local_source_loads_flat_layout(
    tmp_path: Path,
) -> None:
    stream = make_stream(
        title=(
            "【直播回放】"
            "いろいろ聊 "
            "2025年09月11日19点场"
        )
    )

    stem = (
        stream.title
        + "_32316327100"
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        tmp_path
        / f"{stem}.ass",
    )

    (
        tmp_path
        / f"{stem}.xml"
    ).touch()

    source = LocalSource(
        stream=stream,
        archive_root=tmp_path,
        vtuber=TEST_VTUBER,
    )

    bundle = source.load()

    assert (
        bundle.source_metadata[
            "layout"
        ]
        == "flat"
    )

    assert len(
        bundle.parts
    ) == 1

    assert (
        bundle.parts[0]
        .part_id
        == "p0"
    )

    assert len(
        bundle.danmaku
    ) == 2

    assert all(
        item.stream_id
        == stream.id
        for item
        in bundle.danmaku
    )


def test_local_source_assigns_stable_part_ids(
    tmp_path: Path,
) -> None:
    stream = make_stream()

    stream_directory = (
        tmp_path
        / "2025年9月录播"
        / stream.title
    )

    stream_directory.mkdir(
        parents=True
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        stream_directory
        / "archive_200.ass",
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        stream_directory
        / "archive_100.ass",
    )

    source = LocalSource(
        stream=stream,
        archive_root=tmp_path,
        vtuber=TEST_VTUBER,
    )

    bundle = source.load()

    assert [
        part.part_id
        for part
        in bundle.parts
    ] == [
        "p0",
        "p1",
    ]

    assert {
        item.part_id
        for item
        in bundle.danmaku
    } == {
        "p0",
        "p1",
    }

    assert len(
        bundle.danmaku
    ) == 4


def test_local_source_returns_metadata_only_when_files_are_missing(
    tmp_path: Path,
) -> None:
    stream = make_stream()

    source = LocalSource(
        stream=stream,
        archive_root=tmp_path,
        vtuber=TEST_VTUBER,
    )

    bundle = source.load()

    assert (
        bundle.source_metadata[
            "layout"
        ]
        == "metadata_only"
    )

    assert (
        bundle.parts
        == []
    )

    assert (
        bundle.danmaku
        == []
    )

    assert (
        bundle.source_metadata[
            "matched_path"
        ]
        is None
    )


def test_local_source_can_force_flat_layout(
    tmp_path: Path,
) -> None:
    stream = make_stream()

    nested_directory = (
        tmp_path
        / "2025年9月录播"
        / stream.title
    )

    nested_directory.mkdir(
        parents=True
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        nested_directory
        / "nested.ass",
    )

    flat_stem = (
        stream.title
        + "_999"
    )

    shutil.copy(
        FIXTURES / "sample.ass",
        tmp_path
        / f"{flat_stem}.ass",
    )

    source = LocalSource(
        stream=stream,
        archive_root=tmp_path,
        vtuber=TEST_VTUBER,
        layout="flat",
    )

    bundle = source.load()

    assert (
        bundle.source_metadata[
            "layout"
        ]
        == "flat"
    )

    assert len(
        bundle.parts
    ) == 1

    assert len(
        bundle.danmaku
    ) == 2


def test_local_source_rejects_vtuber_mismatch(
    tmp_path: Path,
) -> None:
    stream = make_stream()

    other_vtuber = Vtuber(
        id="another-vtuber",
        display_name="另一个主播",
    )

    try:
        LocalSource(
            stream=stream,
            archive_root=tmp_path,
            vtuber=other_vtuber,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "vtuber mismatch "
            "should be rejected"
        )