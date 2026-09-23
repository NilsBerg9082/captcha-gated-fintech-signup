import json
from typing import Any

import httpx

from fintech_signup.infrai_client import InfraiClient
from fintech_signup.signup_service import SignupRequest, process_signup


class RecordingGateway:
    def __init__(self) -> None:
        self.captcha_calls: list[dict[str, Any]] = []

    def captcha_verify(self, token: str, **kwargs: Any) -> dict[str, Any]:
        self.captcha_calls.append({"token": token, **kwargs})
        return {"verified": True}


def test_captcha_client_sends_required_widget_record_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "data": {"verified": True}})

    client = InfraiClient("test-key", transport=httpx.MockTransport(handler))

    client.captcha_verify(
        "browser-token",
        widget_record_id="widget-signup",
        vendor="turnstile",
        ip="203.0.113.7",
        action="fintech_signup",
        score_threshold=0.7,
    )

    assert captured["widget_record_id"] == "widget-signup"


def test_refunded_payment_routes_signup_to_review_without_creating_user() -> None:
    gateway = RecordingGateway()
    request = SignupRequest(
        email="analyst@example.com",
        password="correct-horse-battery",
        name="Pipeline Analyst",
        widget_record_id="widget-signup",
        captcha_token="browser-token",
        captcha_vendor="turnstile",
        ip="203.0.113.7",
        device_fingerprint="device-7",
        idempotency_key="signup-run-42",
        payment_events=[
            {"event_id": "pay-1", "amount": 80, "state": "settled"},
            {"event_id": "pay-2", "amount": 20, "state": "refunded"},
        ],
    )

    result = process_signup(request, gateway)

    assert result.decision == "review"
    assert result.notification.reason == "payment_history_requires_review"
    assert result.notification.payment_event_ids == ["pay-1", "pay-2"]
    assert gateway.captcha_calls[0]["action"] == "fintech_signup"
    assert gateway.captcha_calls[0]["widget_record_id"] == "widget-signup"


def test_clean_payment_history_returns_created_record_with_idempotency_key() -> None:
    gateway = RecordingGateway()
    request = SignupRequest(
        email="builder@example.com",
        password="correct-horse-battery",
        name="Data Builder",
        widget_record_id="widget-signup",
        captcha_token="browser-token",
        captcha_vendor="turnstile",
        ip="203.0.113.8",
        device_fingerprint="device-8",
        idempotency_key="signup-run-43",
        payment_events=[{"event_id": "pay-3", "amount": 40, "state": "settled"}],
    )

    result = process_signup(request, gateway)

    assert result.decision == "created"
    assert result.user == {
        "email": "builder@example.com",
        "name": "Data Builder",
        "idempotency_key": "signup-run-43",
    }
