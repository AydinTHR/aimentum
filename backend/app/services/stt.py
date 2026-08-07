"""Speech to text behind a Protocol so the provider is swappable in one class.

The real implementation uses Google Cloud Speech-to-Text v2 short-form
recognition. Language codes come from env so other languages can sit
alongside English later. The browser Web Speech API is deliberately not
used: it is unreliable in installed iOS PWAs, which is where this app lives
(see ADR-0004).
"""

import os
import tempfile
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends

from app.core.config import settings


class SpeechToText(Protocol):
    def transcribe(self, flac_audio: bytes) -> str: ...


class GoogleSpeechToText:
    """Google Cloud Speech-to-Text v2, short-form recognition.

    The client is created lazily so importing this module never requires
    credentials. GOOGLE_APPLICATION_CREDENTIALS_JSON (the full service
    account JSON in one env var, the Render-friendly shape) is written to a
    temp file on first use and handed to the SDK via the standard
    GOOGLE_APPLICATION_CREDENTIALS variable.
    """

    def __init__(self) -> None:
        self._client: object | None = None

    @staticmethod
    def _ensure_credentials_file() -> None:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return
        raw_json = settings.google_application_credentials_json
        if not raw_json:
            return
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="gcp-credentials-", delete=False
        ) as handle:
            handle.write(raw_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = handle.name

    def transcribe(self, flac_audio: bytes) -> str:
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech

        self._ensure_credentials_file()
        if self._client is None:
            self._client = SpeechClient()
        client: SpeechClient = self._client  # type: ignore[assignment]

        language_codes = [code.strip() for code in settings.stt_language_codes.split(",")]
        request = cloud_speech.RecognizeRequest(
            recognizer=f"projects/{settings.google_cloud_project}/locations/global/recognizers/_",
            config=cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=language_codes,
                model="short",
            ),
            content=flac_audio,
        )
        response = client.recognize(request=request)
        parts = [
            result.alternatives[0].transcript for result in response.results if result.alternatives
        ]
        return " ".join(part.strip() for part in parts).strip()


class FakeSpeechToText:
    """Deterministic transcriber for tests: returns a canned transcript."""

    def __init__(self, transcript: str = "apply to five roles then gym") -> None:
        self.transcript = transcript
        self.received: list[bytes] = []

    def transcribe(self, flac_audio: bytes) -> str:
        self.received.append(flac_audio)
        return self.transcript


@lru_cache(maxsize=1)
def get_stt() -> SpeechToText:
    return GoogleSpeechToText()


SttDep = Annotated[SpeechToText, Depends(get_stt)]
