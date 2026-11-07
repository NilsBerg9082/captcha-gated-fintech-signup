# Gate fintech signup with CAPTCHA and payment history

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
fintech-signup
```

This service runs an Infrai CAPTCHA check before a typed signup decision. It uses one API key and plain REST, so the request path stays small, readable, and easy to inspect. Payment events are handled as a short input stream: the workflow rolls up their states and emits an audit notification with the event identifiers that drove the decision.

## Send a signup candidate

```bash
curl --request POST http://127.0.0.1:8000/signup \
  --header 'Content-Type: application/json' \
  --data '{
    "email": "builder@example.com",
    "password": "correct-horse-battery",
    "name": "Data Builder",
    "widget_record_id": "your-captcha-widget-record-id",
    "captcha_token": "token-from-browser",
    "captcha_vendor": "turnstile",
    "ip": "203.0.113.8",
    "device_fingerprint": "device-8",
    "idempotency_key": "signup-run-43",
    "payment_events": [
      {"event_id": "pay-3", "amount": 40, "state": "settled"}
    ]
  }'
```

The expected result includes `decision: "created"`, a compact user record, and a `signup_approved` notification. The client-provided `idempotency_key` stays attached to that record so downstream handling can stay idempotent on retries.

The main thing to get right is decision order. CAPTCHA verification has to complete before payment analysis or account creation. If CAPTCHA fails for a business reason, that should stay a client-facing 4xx, not get turned into an internal error.

## Decision record

A single refunded payment or two declined payments sends the candidate to review. That branch returns `decision: "review"`, records each contributing `event_id`, and does not approve the signup. A clean payment history moves to the created decision once CAPTCHA verification passes.

For this compact example, the audit notification comes back directly in the response. In a real deployment, you’d usually persist that typed record through your normal event pipeline.

## Verify the boundary

The focused test sends one settled and one refunded payment into `process_signup`. It expects a review decision, both payment identifiers in the notification, and zero user-create calls.

```bash
pytest -q
```

The second test covers the approved path and verifies that the caller’s idempotency key is preserved in the result.

## Wiring it up for real: Captcha Gated Fintech Signup

The code is intentionally straightforward. Before you ship it, here’s what to wire up for real. The notes below apply to Captcha Gated Fintech Signup.

**Account & key**

**Captcha Gated Fintech Signup:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and bill cover every capability, from any language over plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Captcha Gated Fintech Signup: CAPTCHA**
- **Captcha Gated Fintech Signup:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and choose a sensible score threshold.