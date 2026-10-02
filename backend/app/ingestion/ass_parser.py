from pathlib import Path

import pysubs2


def parse_ass(
    path: Path,
    stream_id: str,
    part_id: str,
) -> list[dict[str, str | int]]:
    subs = pysubs2.load(str(path))

    results = []

    for line in subs:
        raw_text = line.text.strip()
        text = line.plaintext.strip()

        if not text:
            continue

        results.append(
            {
                "stream_id": stream_id,
                "part_id": part_id,
                "timestamp_ms": line.start,
                "raw_text": raw_text,
                "text": text,
            }
        )

    return results
