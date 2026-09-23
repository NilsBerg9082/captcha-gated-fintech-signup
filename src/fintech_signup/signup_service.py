from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_client import InfraiClient, InfraiError, InfraiTransportError


class PaymentState(str, Enum):
    settled = "settled"
    declined = "declined"
    refunded = "refunded"


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1)
    amount: float = Field(ge=0)
    state: PaymentState


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=12)
    name: str
    widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    captcha_vendor: str
    ip: str
    device_fingerprint: str
    idempotency_key: str = Field(min_length=8)
    payment_events: list[PaymentEvent] = Field(default_factory=list)


class AuditNotification(BaseModel):
    kind: Literal["signup_approved", "signup_review"]
    email: str
    reason: str
    occurred_at: datetime
    payment_event_ids: list[str]


class SignupResult(BaseModel):
    decision: Literal["created", "review"]
    user: dict[str, Any] | None = None
    notification: AuditNotification


def process_signup(request: SignupRequest, client: Any) -> SignupResult:
    client.captcha_verify(
        request.captcha_token,
        widget_record_id=request.widget_record_id,
        vendor=request.captcha_vendor,
        ip=request.ip,
        action="fintech_signup",
        score_threshold=0.7,
    )

    declined = sum(event.state is PaymentState.declined for event in request.payment_events)
    refunded = sum(event.state is PaymentState.refunded for event in request.payment_events)
    needs_review = declined >= 2 or refunded >= 1
    event_ids = [event.event_id for event in request.payment_events]
    now = datetime.now(timezone.utc)

    if needs_review:
        return SignupResult(
            decision="review",
            notification=AuditNotification(
                kind="signup_review",
                email=request.email,
                reason="payment_history_requires_review",
                occurred_at=now,
                payment_event_ids=event_ids,
            ),
        )

    user = {
        "email": request.email,
        "name": request.name,
        "idempotency_key": request.idempotency_key,
    }
    return SignupResult(
        decision="created",
        user=user,
        notification=AuditNotification(
            kind="signup_approved",
            email=request.email,
            reason="captcha_and_payment_checks_passed",
            occurred_at=now,
            payment_event_ids=event_ids,
        ),
    )


def create_app(client: Any | None = None) -> FastAPI:
    app = FastAPI(title="Fintech signup gate")
    gateway = client or InfraiClient.from_environment()

    @app.post("/signup", response_model=SignupResult)
    def signup(request: SignupRequest) -> SignupResult:
        try:
            return process_signup(request, gateway)
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail={"code": exc.code}) from exc
        except InfraiTransportError as exc:
            raise HTTPException(status_code=502, detail="upstream request failed") from exc

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
