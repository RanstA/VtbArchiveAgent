
from collections import defaultdict


def aggregate_evidence_windows(
    transcript_hits: list[dict],
    danmaku_hits: list[dict],
    *,
    radius_ms: int = 10_000,
    max_windows: int = 8,
) -> list[dict]:
    """Group matched evidence into StreamPart-local investigation windows."""
    if radius_ms < 0 or not 1 <= max_windows <= 50:
        raise ValueError("invalid window parameters")

    groups = defaultdict(list)

    for kind, hits in (
        ("transcript", transcript_hits),
        ("danmaku", danmaku_hits),
    ):
        for hit in hits:
            local_start = (
                hit["start_ms"]
                if kind == "transcript"
                else hit["timestamp_ms"]
            )
            local_end = (
                hit["end_ms"]
                if kind == "transcript"
                else local_start + 1
            )

            offset = hit["stream_start_ms"] - local_start

            groups[(hit["stream_id"], hit["part_id"])].append({
                "kind": kind,
                "evidence_id": hit["evidence_id"],
                "text": hit["text"],
                "local_start_ms": local_start,
                "local_end_ms": local_end,
                "start_offset_ms": offset,
                "window_start_ms": max(0, local_start - radius_ms),
                "window_end_ms": local_end + radius_ms,
                "stream_title": hit["stream_title"],
                "live_time": hit["live_time"],
            })

    windows = []

    for (stream_id, part_id), seeds in groups.items():
        seeds.sort(key=lambda x: x["window_start_ms"])
        current = None

        for seed in seeds:
            if current is not None and (
                seed["window_start_ms"] <= current["local_end_ms"]
            ):
                if seed["start_offset_ms"] != current["start_offset_ms"]:
                    raise ValueError("inconsistent StreamPart offset")

                current["local_end_ms"] = max(
                    current["local_end_ms"], seed["window_end_ms"]
                )
                current["matches"].append(seed)
                continue

            current = {
                "stream_id": stream_id,
                "part_id": part_id,
                "start_offset_ms": seed["start_offset_ms"],
                "local_start_ms": seed["window_start_ms"],
                "local_end_ms": seed["window_end_ms"],
                "stream_title": seed["stream_title"],
                "live_time": seed["live_time"],
                "matches": [seed],
            }
            windows.append(current)

    for window in windows:
        offset = window.pop("start_offset_ms")
        window["stream_start_ms"] = offset + window["local_start_ms"]
        window["stream_end_ms"] = offset + window["local_end_ms"]
        window["matches"].sort(
            key=lambda x: (x["local_start_ms"], x["kind"], x["evidence_id"])
        )

    windows.sort(key=lambda x: x["stream_start_ms"])
    windows.sort(key=lambda x: x["live_time"], reverse=True)

    return windows[:max_windows]
