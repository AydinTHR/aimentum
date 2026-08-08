import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PushLog, PushSubscription
from app.services.push import FakePushTransport, SendOutcome

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


def subscribe(client: TestClient, endpoint: str = ENDPOINT, auth: str = "auth-1") -> dict:
    response = client.post(
        "/push/subscribe",
        json={
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key", "auth": auth},
            "user_agent": "iPhone Safari",
        },
    )
    assert response.status_code == 201
    return dict(response.json())


class TestSubscriptions:
    def test_subscribe_stores_the_subscription(
        self, client: TestClient, db_session: Session
    ) -> None:
        payload = subscribe(client)
        assert payload["endpoint"] == ENDPOINT

        stored = db_session.scalars(select(PushSubscription)).one()
        assert stored.p256dh == "p256dh-key"
        assert stored.user_agent == "iPhone Safari"

    def test_resubscribing_updates_keys_in_place(
        self, client: TestClient, db_session: Session
    ) -> None:
        first = subscribe(client, auth="auth-1")
        second = subscribe(client, auth="auth-2")

        assert first["id"] == second["id"]
        stored = db_session.scalars(select(PushSubscription)).one()
        assert stored.auth == "auth-2"

    def test_unsubscribe_removes_it(self, client: TestClient, db_session: Session) -> None:
        subscribe(client)
        response = client.request("DELETE", "/push/subscribe", json={"endpoint": ENDPOINT})
        assert response.status_code == 204
        assert db_session.query(PushSubscription).count() == 0

    def test_unsubscribing_an_unknown_endpoint_is_404(self, client: TestClient) -> None:
        response = client.request(
            "DELETE", "/push/subscribe", json={"endpoint": "https://example.com/gone"}
        )
        assert response.status_code == 404

    def test_subscribe_requires_the_bearer_token(self, client: TestClient) -> None:
        response = client.post(
            "/push/subscribe",
            json={"endpoint": ENDPOINT, "keys": {"p256dh": "x", "auth": "y"}},
            headers={"Authorization": "Bearer wrong"},
        )
        assert response.status_code == 401


class TestSendAndLogging:
    def test_test_push_sends_and_logs_every_attempt(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client, endpoint=ENDPOINT)
        subscribe(client, endpoint=ENDPOINT + "-2")

        payload = client.post("/push/test").json()
        assert payload == {"sent": 2, "statuses": ["201", "201"], "pruned": 0}

        assert len(fake_push.sent) == 2
        body = json.loads(fake_push.sent[0][1])
        assert body["title"] == "Aimentum is connected"
        assert body["url"] == "/today"

        logs = db_session.scalars(select(PushLog).order_by(PushLog.id)).all()
        assert [log.job for log in logs] == ["test", "test"]
        assert [log.status for log in logs] == ["201", "201"]
        assert logs[0].endpoint == ENDPOINT

    def test_failed_sends_are_logged_with_their_status(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        fake_push.set_outcome(ENDPOINT, SendOutcome(status="500"))

        payload = client.post("/push/test").json()
        assert payload["statuses"] == ["500"]

        log = db_session.scalars(select(PushLog)).one()
        assert log.status == "500"
        assert db_session.query(PushSubscription).count() == 1

    def test_network_errors_are_logged_rather_than_raised(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        fake_push.set_outcome(ENDPOINT, SendOutcome(status="ConnectionError: name resolution"))

        response = client.post("/push/test")
        assert response.status_code == 200
        assert db_session.scalars(select(PushLog)).one().status.startswith("ConnectionError")

    def test_gone_subscriptions_are_pruned_but_the_log_survives(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        """Pruning must not take the audit trail with it.

        Web push has no delivery receipts, so push_log is the only evidence
        a send happened. The row outlives the subscription with a null id.
        """
        subscribe(client, endpoint=ENDPOINT)
        subscribe(client, endpoint=ENDPOINT + "-live")
        fake_push.set_outcome(ENDPOINT, SendOutcome(status="410", gone=True))

        payload = client.post("/push/test").json()
        assert payload["pruned"] == 1

        remaining = db_session.scalars(select(PushSubscription)).all()
        assert [sub.endpoint for sub in remaining] == [ENDPOINT + "-live"]

        logs = db_session.scalars(select(PushLog).order_by(PushLog.id)).all()
        assert len(logs) == 2
        pruned_log = next(log for log in logs if log.status == "410")
        assert pruned_log.subscription_id is None
        assert pruned_log.endpoint == ENDPOINT

    def test_404_also_prunes(
        self, client: TestClient, db_session: Session, fake_push: FakePushTransport
    ) -> None:
        subscribe(client)
        fake_push.set_outcome(ENDPOINT, SendOutcome(status="404", gone=True))
        client.post("/push/test")
        assert db_session.query(PushSubscription).count() == 0
        assert db_session.query(PushLog).count() == 1

    def test_test_push_with_no_subscriptions_is_harmless(self, client: TestClient) -> None:
        payload = client.post("/push/test").json()
        assert payload == {"sent": 0, "statuses": [], "pruned": 0}


class TestVapidKey:
    def test_public_key_is_served(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", "BTestApplicationServerKey")
        response = client.get("/push/public-key")
        assert response.status_code == 200
        assert response.json() == {"public_key": "BTestApplicationServerKey"}
