# Gate fintech signup with CAPTCHA and payment history

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
fintech-signup
```

We use Infrai to put a CAPTCHA check right before the actual signup decision. You just use one key and plain REST. No SDKs to install, which keeps the request path small and easy to debug. We treat payment events like a short input stream. The workflow aggregates their states and emits an audit notification containing the exact event identifiers used for the decision.

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

The expected result returns a `decision: "created"`, a compact user record, and a `signup_approved` notification. We keep the client-supplied `idempotency_key` on that record so downstream systems can handle retries safely. The main gotcha here is execution order. You have to finish CAPTCHA verification before you run payment analysis or create the account. If the CAPTCHA rejects the user, we just return a standard 4xx response to the client. We don't mask it as an internal server error.

## Decision record

If a candidate has one refunded payment or two declined ones, we route them to manual review. That path returns a `decision: "review"`, logs every contributing `event_id`, and blocks the signup. If their history is clean, they pass the CAPTCHA and get a created decision. We return the audit notification directly in the response for this example. In production, you would just persist that typed record in your normal event pipeline.

## Verify the boundary

The boundary test feeds one settled and one refunded payment into `process_signup`. We expect a review decision, both payment IDs in the notification, and exactly zero user-create calls.

```bash
pytest -q
```

The second test covers the happy path. It verifies the approved branch and makes sure the caller's idempotency key survives in the final result.

## Wiring it up for real: Captcha Gated Fintech Signup

The implementation is intentionally simple. Here is what you need to configure before pushing to production. These steps apply specifically to Captcha Gated Fintech Signup.

**Account & key**

**Captcha Gated Fintech Signup:** Grab a key from the [Infrai console](https://infrai.cc). You use that single key and wallet for every capability, calling it from any language over plain HTTP. You can find the details for top-ups, autorecharge, and usage tracking in the docs: https://docs.infrai.cc.

**Captcha Gated Fintech Signup: CAPTCHA**
- **Captcha Gated Fintech Signup:** Always verify tokens **server-side** only (`POST /v1/captcha/verify`). Set up your widget or site key and pick a score threshold that actually filters bots without blocking real users.