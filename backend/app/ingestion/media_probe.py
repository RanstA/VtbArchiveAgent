import math
import subprocess
from pathlib import Path

DEFAULT_PROBE_TIMEOUT_SECONDS = 30


class MediaProbeError(RuntimeError):
    pass


def probe_duration_ms(
    video_path: str | Path,
    *,
    timeout_seconds: int = (DEFAULT_PROBE_TIMEOUT_SECONDS),
) -> int:
    """
    使用 ffprobe 获取媒体文件实际时长。

    返回：
        duration_ms，单位毫秒。

    注意：
        这里只负责探测单个 Part 的媒体时长，
        不负责计算 Stream-global offset。
    """

    path = Path(video_path)

    if not path.exists():
        raise FileNotFoundError(f"Media file does not exist: {path}")

    if not path.is_file():
        raise MediaProbeError(f"Media path is not a file: {path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        ("default=" "noprint_wrappers=1:" "nokey=1"),
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )

    except FileNotFoundError as exc:
        raise MediaProbeError(
            "ffprobe executable was not found. "
            "Please install FFmpeg and make sure "
            "ffprobe is available in PATH."
        ) from exc

    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError("ffprobe timed out while probing: " f"{path}") from exc

    if result.returncode != 0:
        error_message = result.stderr.strip() or "unknown ffprobe error"

        raise MediaProbeError("ffprobe failed for " f"{path}: {error_message}")

    raw_duration = result.stdout.strip()

    try:
        duration_seconds = float(raw_duration)

    except ValueError as exc:
        raise MediaProbeError(
            "ffprobe returned invalid duration " f"for {path}: {raw_duration!r}"
        ) from exc

    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise MediaProbeError(
            "ffprobe returned invalid duration " f"for {path}: {duration_seconds}"
        )

    duration_ms = round(duration_seconds * 1000)

    if duration_ms <= 0:
        raise MediaProbeError("Media duration must be positive: " f"{path}")

    return duration_ms
