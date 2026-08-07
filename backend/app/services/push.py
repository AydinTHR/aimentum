"""Web push delivery. This is the product's priority zero.

Web push has no delivery receipts, so reliability is proven operationally
rather than by an acknowledgement: every send attempt is written to
push_log with its outcome, and dead subscriptions are pruned the moment a
push gateway reports them gone. Pruning sets the log's foreign key to null
rather than cascading, so the history outlives the subscription.

The transport sits behind a Protocol: tests never touch the network, and a
failing send is a recorded outcome rather than an exception that could take
a scheduled job down with it.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PushLog, PushSubscription

logger = logging.getLogger(__name__)

# Gateways use these to say the endpoint is permanently dead.
GONE_STATUSES = {404, 410}
STATUS_MAX_CHARS = 200


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    url: str = "/today"

    def to_payload(self) -> str:
        return json.dumps({"title": self.title, "body": self.body, "url": self.url})


@dataclass(frozen=True)
class SendOutcome:
    """What happened on one send: the logged status, and whether to prune."""

    status: str
    gone: bool = False


class PushTransport(Protocol):
    def send(self, subscription: PushSubscription, payload: str) -> SendOutcome: ...


class WebPushTransport:
    """pywebpush over VAPID. Never raises: every failure becomes an outcome."""

    def send(self, subscription: PushSubscription, payload: str) -> SendOutcome:
        from pywebpush import WebPushException, webpush

        if not settings.vapid_private_key:
            return SendOutcome(status="error: VAPID_PRIVATE_KEY is not set")
        try:
            response = webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status is None:
                return SendOutcome(status=f"error: {error}"[:STATUS_MAX_CHARS])
            return SendOutcome(status=str(status), gone=status in GONE_STATUSES)
        except Exception as error:
            # A DNS failure or a malformed key must not take the job down;
            # it is logged as an outcome and the next subscription is tried.
            return SendOutcome(status=f"{type(error).__name__}: {error}"[:STATUS_MAX_CHARS])
        return SendOutcome(status=str(response.status_code))


class FakePushTransport:
    """Records every send and replays queued outcomes. Default is 201."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.outcomes: dict[str, SendOutcome] = {}
        self.default = SendOutcome(status="201")

    def set_outcome(self, endpoint: str, outcome: SendOutcome) -> None:
        self.outcomes[endpoint] = outcome

    def send(self, subscription: PushSubscription, payload: str) -> SendOutcome:
        self.sent.append((subscription.endpoint, payload))
        return self.outcomes.get(subscription.endpoint, self.default)


def send_to_all(
    session: Session,
    transport: PushTransport,
    job: str,
    notification: Notification,
) -> list[SendOutcome]:
    """Send to every subscription, log each attempt, prune the dead ones."""
    payload = notification.to_payload()
    subscriptions = session.scalars(select(PushSubscription).order_by(PushSubscription.id)).all()

    outcomes: list[SendOutcome] = []
    for subscription in subscriptions:
        outcome = transport.send(subscription, payload)
        session.add(
            PushLog(
                job=job,
                subscription_id=subscription.id,
                endpoint=subscription.endpoint,
                status=outcome.status,
            )
        )
        session.flush()
        if outcome.gone:
            logger.info("pruning dead push subscription %s", subscription.id)
            session.delete(subscription)
            session.flush()
        outcomes.append(outcome)

    if not outcomes:
        logger.warning("job %s had no push subscriptions to send to", job)
    return outcomes


@lru_cache(maxsize=1)
def get_push_transport() -> PushTransport:
    return WebPushTransport()


PushDep = Annotated[PushTransport, Depends(get_push_transport)]
