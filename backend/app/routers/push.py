from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.db import DbSession
from app.models import PushSubscription
from app.schemas import PushSubscriptionIn, PushSubscriptionOut, PushTestOut, PushUnsubscribeIn
from app.services.push import Notification, PushDep, send_to_all

router = APIRouter(tags=["push"])


@router.post("/push/subscribe", status_code=201)
def subscribe(payload: PushSubscriptionIn, session: DbSession) -> PushSubscriptionOut:
    """Register a browser push subscription.

    Re-subscribing with the same endpoint updates the keys in place rather
    than erroring: browsers rotate keys, and the endpoint is the identity.
    """
    subscription = session.scalars(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).first()
    if subscription is None:
        subscription = PushSubscription(
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
        )
        session.add(subscription)
    else:
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.user_agent = payload.user_agent
    session.commit()
    return PushSubscriptionOut.model_validate(subscription)


@router.delete("/push/subscribe", status_code=204)
def unsubscribe(payload: PushUnsubscribeIn, session: DbSession) -> Response:
    subscription = session.scalars(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).first()
    if subscription is None:
        raise HTTPException(404, "subscription not found")
    session.delete(subscription)
    session.commit()
    return Response(status_code=204)


@router.post("/push/test")
def send_test(session: DbSession, transport: PushDep) -> PushTestOut:
    """Send a test notification now and report what each endpoint said.

    This is the Settings screen's verification button. It runs inline rather
    than in the background so the owner sees the real outcome.
    """
    notification = Notification(
        title="Aimentum is connected", body="Push notifications are working on this device."
    )
    outcomes = send_to_all(session, transport, "test", notification)
    session.commit()
    return PushTestOut(
        sent=len(outcomes),
        statuses=[outcome.status for outcome in outcomes],
        pruned=sum(1 for outcome in outcomes if outcome.gone),
    )
