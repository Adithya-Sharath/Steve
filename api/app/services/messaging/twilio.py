"""Twilio provider (D48), written against Twilio's current docs (read 2026-09-26):

* Webhook signature (docs.twilio.com "Validating requests"): `X-Twilio-Signature` = base64( HMAC-SHA1( auth token, URL + every POST parameter sorted by name, each
  appended as name then value with no delimiter ) ). The URL is the exact one configured in Twilio (query string included; for WhatsApp/SMS callbacks the port is kept).
  Checked in a test against the worked example in Twilio's documentation (`https://example.com/myapp.php?foo=1&bar=2`, token `12345`, `L/OH5YylLD5NRKLltdqwSvS0BnU=`).
* Send: `POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json`, HTTP basic auth (AccountSid, AuthToken), form fields `From`, `To`, `Body`
  (at most 1,600 characters); WhatsApp addresses look like `whatsapp:+<E.164>`. The sandbox sender is `whatsapp:+14155238886`.
* Incoming media: `MediaUrl0` / `MediaContentType0` with `NumMedia`; media URLs need HTTP basic auth (AccountSid, AuthToken) when the account enforces it, so we always send it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx

from .base import MediaTooLarge, MediaUnavailable

log = logging.getLogger("steve.whatsapp")  # never log numbers or message text

API = "https://api.twilio.com/2010-04-01"


def compute_signature(auth_token: str, url: str, params: dict[str, list[str]]) -> str:
    payload = url
    for key in sorted(params):
        for value in sorted(params[key]):
            payload += key + value
    return base64.b64encode(hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")


class TwilioProvider:
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, base_url: str = API, timeout: float = 20.0):
        self.account_sid, self.auth_token, self.base_url, self.timeout = account_sid, auth_token, base_url.rstrip("/"), timeout

    def validate(self, url: str, params: dict[str, list[str]], signature: str) -> bool:
        if not signature or not self.auth_token:
            return False
        return hmac.compare_digest(compute_signature(self.auth_token, url, params), signature.strip())

    def send(self, to: str, from_: str, body: str) -> None:
        try:
            r = httpx.post(f"{self.base_url}/Accounts/{self.account_sid}/Messages.json", auth=(self.account_sid, self.auth_token),
                           data={"From": from_, "To": to, "Body": body}, timeout=self.timeout)
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("could not send a reply: %s", type(e).__name__)  # no number, no text, no provider body
            raise

    def download(self, url: str, max_bytes: int) -> bytes:
        try:
            with httpx.stream("GET", url, auth=(self.account_sid, self.auth_token), follow_redirects=True, timeout=self.timeout) as r:
                r.raise_for_status()
                if int(r.headers.get("content-length") or 0) > max_bytes:
                    raise MediaTooLarge(url)
                out = bytearray()
                for chunk in r.iter_bytes():
                    out += chunk
                    if len(out) > max_bytes:
                        raise MediaTooLarge(url)
                return bytes(out)
        except httpx.HTTPError as e:
            raise MediaUnavailable(type(e).__name__) from e
