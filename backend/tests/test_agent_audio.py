import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import audio as audio_service
from app.services.stt import FakeSpeechToText

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_wav(path: Path, seconds: float) -> bytes:
    """Generate a small silent wav (8 kHz mono keeps 91s under the size cap)."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono",
            "-t",
            str(seconds),
            "-ar",
            "8000",
            "-ac",
            "1",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path.read_bytes()


def post_audio(client: TestClient, data: bytes) -> object:
    return client.post(
        "/checkin/morning/audio",
        files={"file": ("clip.wav", data, "audio/wav")},
    )


class TestMorningAudio:
    @needs_ffmpeg
    def test_round_trip_returns_the_transcript(
        self, client: TestClient, fake_stt: FakeSpeechToText, tmp_path: Path
    ) -> None:
        data = make_wav(tmp_path / "clip.wav", seconds=2)
        response = post_audio(client, data)

        assert response.status_code == 200
        assert response.json() == {"transcript": "apply to five roles then gym"}
        assert len(fake_stt.received) == 1
        assert fake_stt.received[0].startswith(b"fLaC")

    def test_oversized_upload_is_rejected(
        self, client: TestClient, fake_stt: FakeSpeechToText
    ) -> None:
        data = b"0" * (audio_service.MAX_UPLOAD_BYTES + 2)
        response = post_audio(client, data)
        assert response.status_code == 413
        assert fake_stt.received == []

    @needs_ffmpeg
    def test_too_long_recording_is_rejected(
        self, client: TestClient, fake_stt: FakeSpeechToText, tmp_path: Path
    ) -> None:
        data = make_wav(tmp_path / "long.wav", seconds=91)
        assert len(data) <= audio_service.MAX_UPLOAD_BYTES
        response = post_audio(client, data)
        assert response.status_code == 422
        assert "90 second" in response.json()["detail"]

    @needs_ffmpeg
    def test_undecodable_upload_is_rejected(
        self, client: TestClient, fake_stt: FakeSpeechToText
    ) -> None:
        response = post_audio(client, b"definitely not audio" * 50)
        assert response.status_code == 422

    def test_missing_ffmpeg_is_a_clear_server_error(
        self,
        client: TestClient,
        fake_stt: FakeSpeechToText,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(audio_service.shutil, "which", lambda name: None)
        response = post_audio(client, b"anything")
        assert response.status_code == 500
        assert "ffmpeg" in response.json()["detail"]
