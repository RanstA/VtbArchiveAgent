from pathlib import Path

from app.domain.stream_part import StreamPart


def scan_stream_directory(
    directory: Path,
    stream_id: str,
) -> list[StreamPart]:

    groups: dict[str, dict[str, Path]] = {}

    for path in directory.iterdir():
        if path.suffix.lower() not in {".mp4", ".ass", ".xml"}:
            continue

        stem = path.stem

        groups.setdefault(stem, {})
        groups[stem][path.suffix.lower()] = path

    parts = []

    for stem, files in groups.items():
        part_id = stem.rsplit("_", 1)[-1]

        parts.append(
            StreamPart(
                stream_id=stream_id,
                part_id=part_id,
                video_path=str(files[".mp4"]) if ".mp4" in files else None,
                danmaku_path=str(files[".ass"]) if ".ass" in files else None,
                xml_path=str(files[".xml"]) if ".xml" in files else None,
            )
        )

    return parts