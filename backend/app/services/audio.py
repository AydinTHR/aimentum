"""ffmpeg transcode for voice check-ins.

iOS Safari records audio as audio/mp4 (AAC), which Google STT does not
reliably accept, so every upload is transcoded to FLAC 16 kHz mono before
transcription (see ADR-0004). Files are used rather than pipes because the
mp4 container often puts its index at the end, which cannot be streamed.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_DURATION_SECONDS = 90


class AudioError(Exception):
    """Base error for the audio pipeline; message is safe to show the client."""


class FfmpegMissingError(AudioError):
    def __init__(self) -> None:
        super().__init__("ffmpeg is not installed on the server; the audio pipeline requires it")


class AudioTooLargeError(AudioError):
    def __init__(self) -> None:
        super().__init__(f"audio upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")


class AudioTooLongError(AudioError):
    def __init__(self) -> None:
        super().__init__(f"audio is longer than the {MAX_DURATION_SECONDS} second limit")


class AudioDecodeError(AudioError):
    def __init__(self) -> None:
        super().__init__("audio could not be decoded; upload a valid recording")


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise FfmpegMissingError()
    return path


def _probe_duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioDecodeError()
    try:
        return float(result.stdout.strip())
    except ValueError as error:
        raise AudioDecodeError() from error


def transcode_to_flac(data: bytes) -> bytes:
    """Transcode any uploaded container to FLAC 16 kHz mono."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise AudioTooLargeError()
    ffmpeg = _require_tool("ffmpeg")
    ffprobe = _require_tool("ffprobe")

    with tempfile.TemporaryDirectory(prefix="aimentum-audio-") as tmp:
        source = Path(tmp) / "input"
        target = Path(tmp) / "output.flac"
        source.write_bytes(data)

        if _probe_duration(ffprobe, source) > MAX_DURATION_SECONDS:
            raise AudioTooLongError()

        result = subprocess.run(
            [ffmpeg, "-y", "-i", str(source), "-ac", "1", "-ar", "16000", str(target)],
            capture_output=True,
        )
        if result.returncode != 0 or not target.exists():
            raise AudioDecodeError()
        return target.read_bytes()
