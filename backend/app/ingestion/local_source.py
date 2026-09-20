import os
import re
import unicodedata
from pathlib import Path

from app.domain.vtuber import (
    Vtuber,
    VtuberSource,
)
from app.domain.danmaku import (
    Danmaku,
)
from app.domain.stream import (
    Stream,
)
from app.domain.stream_part import (
    StreamPart,
)
from app.ingestion.ass_parser import (
    parse_ass,
)
from app.ingestion.source import (
    ArchiveBundle,
)

MEDIA_SUFFIXES = {
    ".mp4",
    ".mkv",
    ".flv",
    ".ass",
    ".xml",
}

WINDOWS_FORBIDDEN = re.compile(
    r'[<>:"/\\|?*]'
)


def normalize_match_key(
    value: str,
) -> str:
    """
    仅用于本地文件 / 目录匹配。
    不修改 Domain 中保存的原始标题。
    """
    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = WINDOWS_FORBIDDEN.sub(
        "",
        value,
    )

    return value.strip()


def expected_month_directory(
    stream: Stream,
) -> str:
    """
    根据直播时间得到旧归档结构中的月份目录
    """
    return (
        f"{stream.live_time.year}年"
        f"{stream.live_time.month}月录播"
    )

def build_directory_index(
    archive_root: Path,
) -> dict[str, list[Path]]:
    """
    为旧式嵌套 archive 建立目录名称索引。
    """
    index: dict[
        str,
        list[Path],
    ] = {}

    for root, dirs, _ in os.walk(
        archive_root
    ):
        root_path = Path(root)

        for directory_name in dirs:
            directory_path = (
                root_path
                / directory_name
            )

            index.setdefault(
                directory_name,
                [],
            ).append(
                directory_path
            )

    return index


def resolve_nested_stream_directory(
    stream: Stream,
    archive_root: Path,
) -> Path | None:
    directory_index = (
        build_directory_index(
            archive_root
        )
    )

    expected_month = (
        expected_month_directory(
            stream
        )
    )

    exact_candidates = (
        directory_index.get(
            stream.title,
            [],
        )
    )

    if len(
        exact_candidates
    ) == 1:
        return exact_candidates[0]

    if len(
        exact_candidates
    ) > 1:
        month_candidates = [
            path
            for path
            in exact_candidates
            if (
                path.parent.name
                == expected_month
            )
        ]

        if len(
            month_candidates
        ) == 1:
            return month_candidates[0]

        if len(
            month_candidates
        ) > 1:
            raise RuntimeError(
                "正确月份内仍存在多个"
                "同名录播目录: "
                + " | ".join(
                    str(path)
                    for path
                    in month_candidates
                )
            )

        raise RuntimeError(
            "找到多个同名录播目录，"
            "但没有唯一正确月份目录: "
            + " | ".join(
                str(path)
                for path
                in exact_candidates
            )
        )

    normalized_title = (
        normalize_match_key(
            stream.title
        )
    )

    normalized_candidates: list[
        Path
    ] = []

    for (
        directory_name,
        paths,
    ) in directory_index.items():
        if (
            normalize_match_key(
                directory_name
            )
            != normalized_title
        ):
            continue

        for path in paths:
            if (
                path.parent.name
                == expected_month
            ):
                normalized_candidates.append(
                    path
                )

    if len(
        normalized_candidates
    ) == 1:
        return (
            normalized_candidates[0]
        )

    if len(
        normalized_candidates
    ) > 1:
        raise RuntimeError(
            "文件名归一化后仍匹配到"
            "多个录播目录: "
            + " | ".join(
                str(path)
                for path
                in normalized_candidates
            )
        )

    return None


def _group_media_files(
    paths: list[Path],
) -> list[dict[str, Path]]:
    groups: dict[
        str,
        dict[str, Path],
    ] = {}

    for path in paths:
        suffix = (
            path.suffix.lower()
        )

        if suffix not in MEDIA_SUFFIXES:
            continue

        stem = path.stem

        groups.setdefault(
            stem,
            {},
        )

        groups[stem][suffix] = (
            path
        )

    return [
        groups[stem]
        for stem in sorted(
            groups,
            key=lambda item: (
                normalize_match_key(
                    item
                )
            ),
        )
    ]

def _scan_nested_parts(
    directory: Path,
) -> list[
    dict[str, Path]
]:
    paths = [
        path for path in directory.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in MEDIA_SUFFIXES
        )
    ]

    return _group_media_files(paths)

def _flat_file_matches_stream(
    path: Path,
    stream: Stream,
) -> bool:
    title_key = normalize_match_key(
        stream.title
    )
    stem_key = normalize_match_key(
        path.stem
    )
    return (
        stem_key == title_key
        or stem_key.startswith(
            title_key + "_"
        )
    )

def _scan_flat_parts(
    archive_root: Path,
    stream: Stream,
) -> list[
    dict[str, Path]
]:
    paths = [
        path for path in archive_root.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in MEDIA_SUFFIXES
            and _flat_file_matches_stream(
                path,
                stream,
            )
        )
    ]

    return _group_media_files(paths)

def _build_stream_parts(
    stream: Stream,
    file_groups: list[
        dict[str, Path]
    ],
) -> list[StreamPart]:
    parts: list[
        StreamPart
    ] = []

    for index, files in enumerate(
        file_groups
    ):
        part_id = f"p{index}"

        video_path = (
            files.get(".mp4")
            or files.get(".mkv")
            or files.get(".flv")
        )

        danmaku_path = (
            files.get(".ass")
        )

        xml_path = (
            files.get(".xml")
        )

        parts.append(
            StreamPart(
                stream_id=stream.id,
                part_id=part_id,
                video_path=(
                    str(video_path)
                    if video_path
                    else None
                ),
                danmaku_path=(
                    str(danmaku_path)
                    if danmaku_path
                    else None
                ),
                xml_path=(
                    str(xml_path)
                    if xml_path
                    else None
                ),
            )
        )

    return parts


class LocalSource:
    """
    本地 Archive Source。

    支持两种 layout：

    nested:
        月份目录 / Stream 目录 / 文件

    flat:
        所有 ass/xml 等文件直接位于 archive_root

    auto:
        优先寻找 nested；
        找不到后尝试 flat。
    """

    def __init__(
        self,
        stream: Stream,
        archive_root: Path,
        *,
        vtuber: Vtuber,
        layout: str = "auto",
    ) -> None:
        if layout not in {
            "auto",
            "nested",
            "flat",
        }:
            raise ValueError(
                "layout must be one of: "
                "auto, nested, flat"
            )
        
        if (
            stream.vtuber_id
            != vtuber.id
        ):
            raise ValueError(
                "stream.creator_id "
                "must match creator.id"
            )

        self.stream = stream
        self.vtuber = vtuber
        self.archive_root = Path(
            archive_root
        )
        self.layout = layout

    def _resolve_file_groups(
        self,
    ) -> tuple[
        str,
        Path | None,
        list[dict[str, Path]],
    ]:
        if not self.archive_root.exists():
            raise FileNotFoundError(
                "Archive root does not exist: "
                f"{self.archive_root}"
            )

        if (
            not self.archive_root.is_dir()
        ):
            raise NotADirectoryError(
                "Archive root is not a directory: "
                f"{self.archive_root}"
            )

        if self.layout in {
            "auto",
            "nested",
        }:
            nested_directory = (
                resolve_nested_stream_directory(
                    stream=self.stream,
                    archive_root=(
                        self.archive_root
                    ),
                )
            )

            if (
                nested_directory
                is not None
            ):
                groups = (
                    _scan_nested_parts(
                        nested_directory
                    )
                )

                return (
                    "nested",
                    nested_directory,
                    groups,
                )

            if (
                self.layout
                == "nested"
            ):
                return (
                    "metadata_only",
                    None,
                    [],
                )

        if self.layout in {
            "auto",
            "flat",
        }:
            groups = (
                _scan_flat_parts(
                    archive_root=(
                        self.archive_root
                    ),
                    stream=self.stream,
                )
            )

            if groups:
                return (
                    "flat",
                    self.archive_root,
                    groups,
                )

        return (
            "metadata_only",
            None,
            [],
        )

    def load(
        self,
    ) -> ArchiveBundle:
        (
            resolved_layout,
            matched_path,
            file_groups,
        ) = (
            self._resolve_file_groups()
        )

        parts = (
            _build_stream_parts(
                stream=self.stream,
                file_groups=file_groups,
            )
        )

        danmaku: list[
            Danmaku
        ] = []

        for part in parts:
            if (
                part.danmaku_path
                is None
            ):
                continue

            danmaku.extend(
                parse_ass(
                    path=Path(
                        part.danmaku_path
                    ),
                    stream_id=(
                        self.stream.id
                    ),
                    part_id=(
                        part.part_id
                    ),
                )
            )

        return ArchiveBundle(
            source="local",
            vtuber=self.vtuber,
            vtuber_sources=[
                vtuber_source
            ],
            stream=self.stream,
            parts=parts,
            danmaku=danmaku,
            source_metadata={
                "layout": (
                    resolved_layout
                ),
                "archive_root": str(
                    self.archive_root
                ),
                "matched_path": (
                    str(matched_path)
                    if matched_path
                    is not None
                    else None
                ),
                "part_count": len(
                    parts
                ),
                "danmaku_count": len(
                    danmaku
                ),
            },
        )