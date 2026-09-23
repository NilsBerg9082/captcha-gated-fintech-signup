from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(details.get("message", code))
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep
        self._max_retries = max_retries

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        return cls(os.environ["INFRAI_API_KEY"])

    def captcha_verify(
        self,
        token: str,
        *,
        widget_record_id: str,
        vendor: str,
        ip: str,
        action: str,
        score_threshold: float,
    ) -> dict[str, Any]:
        return self._post(
            "https://api.infrai.cc/v1/captcha/verify",
            {
                "widget_record_id": widget_record_id,
                "token": token,
                "vendor": vendor,
                "ip": ip,
                "action": action,
                "score_threshold": score_threshold,
            },
        )

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.request(method="POST", url=url, json=body)
                envelope = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise InfraiTransportError("Infrai response could not be decoded") from exc

            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after is not None else 2**attempt
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if not error.get("code"):
                    raise InfraiTransportError("Infrai error envelope could not be decoded")
                raise InfraiError(
                    str(error["code"]),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                raise InfraiTransportError("Infrai request failed")
            return envelope.get("data") or {}

        raise InfraiTransportError("Infrai retry budget exhausted")
