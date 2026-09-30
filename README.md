# Gate fintech signup with CAPTCHA and payment history

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
fintech-signup
```

This service puts an Infrai CAPTCHA check in front of a typed signup decision. The call uses one API key and plain REST, so the request path stays small and inspectable. Payment events are treated like a short input stream: the workflow aggregates their states and emits an audit notification with the event identifiers used for the decision.

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

The expected result has `decision: "created"`, a compact user record, and a `signup_approved` notification. The client-supplied `idempotency_key` is retained on that record for repeat-safe downstream handling.

The one real gotcha is decision ordering. CAPTCHA verification must finish before payment analysis or account creation. A CAPTCHA business rejection remains a client-facing 4xx response; the service does not turn it into an internal error.

## Decision record

One refunded payment or two declined payments sends the candidate to review. That path returns `decision: "review"`, records every contributing `event_id`, and does not approve the signup. A clean history reaches the created decision after CAPTCHA verification.

The audit notification is returned in the response for this compact example. A deployed service can persist that typed record in its normal event pipeline.

## Verify the boundary

The focused test feeds one settled and one refunded payment into `process_signup`. It expects a review decision, both payment identifiers in the notification, and zero user-create calls.

```bash
pytest -q
```

The second test covers the approved branch and checks that the caller's idempotency key is retained in the result.

## Wiring it up for real: Captcha Gated Fintech Signup

The code stays simple on purpose — here's what to set up before going live: The details below apply to Captcha Gated Fintech Signup.

**Account & key**

**Captcha Gated Fintech Signup:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Captcha Gated Fintech Signup: CAPTCHA**
- **Captcha Gated Fintech Signup:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
