"""The agent has to fail out loud but politely.

Planning is the first thing the owner touches each day, so a missing key or
an Anthropic outage must reach the screen as readable copy, not as a 500
with a stack trace behind it.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.llm import AnthropicClient, LlmUnavailable, get_llm


@pytest.fixture(autouse=True)
def keyless_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force a real, keyless client into the app for this module.

    Overriding explicitly rather than relying on an unset environment: once a
    key lands in backend/.env these tests would otherwise start billing real
    Anthropic calls.
    """
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    app.dependency_overrides[get_llm] = AnthropicClient
    yield
    app.dependency_overrides.pop(get_llm, None)


class TestClientGuard:
    def test_a_missing_key_raises_a_typed_error(self) -> None:
        with pytest.raises(LlmUnavailable, match="ANTHROPIC_API_KEY"):
            AnthropicClient().complete_daily("anything")

    def test_building_the_client_needs_no_key(self) -> None:
        """Construction is lazy, so importing the app never needs credentials."""
        AnthropicClient()


class TestEndpointDegradation:
    def test_morning_checkin_answers_503_with_a_reason(self, client: TestClient) -> None:
        response = client.post("/checkin/morning", json={"raw_text": "plan my day"})

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "The agent could not be reached right now. Try again in a moment."
        )

    def test_evening_checkin_answers_503_with_a_reason(self, client: TestClient) -> None:
        response = client.post("/checkin/evening", json={"applications_sent": 3})

        assert response.status_code == 503
        assert "could not be reached" in response.json()["detail"]

    def test_the_reason_is_not_leaked_to_the_client(self, client: TestClient) -> None:
        """The log gets the detail; the response does not. The message could
        name an env var or quote an upstream error."""
        body = client.post("/checkin/morning", json={"raw_text": "plan my day"}).text
        assert "ANTHROPIC_API_KEY" not in body
