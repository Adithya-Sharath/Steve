"""`POST /whatsapp/webhook` (D48): Twilio's inbound WhatsApp messages. Off unless WHATSAPP_ENABLED=true and WORKER_HASH_SECRET is set.

The webhook is SIGNED: anything without a valid `X-Twilio-Signature` is refused (403) and does nothing. A valid message is acknowledged at once with an empty TwiML
response, and the work (download a voice note, decode, translate, reply) happens afterwards, so Twilio's 15-second webhook timeout can never cut a reply short.
Replies are text messages sent through the provider's API. We never message first.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from ..ratelimit import limit
from ..services.messaging import Incoming, get_provider
from ..services.whatsapp import handle_incoming
from ..settings import settings

router = APIRouter(tags=["whatsapp"])

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/whatsapp/webhook", include_in_schema=False,
             dependencies=[Depends(limit("whatsapp", per_minute=lambda: settings.rl_whatsapp_per_min))])
async def whatsapp_webhook(request: Request, background: BackgroundTasks) -> Response:
    if not settings.whatsapp_enabled:
        raise HTTPException(404, "WhatsApp is not enabled on this server.")
    if len(settings.worker_hash_secret) < 16:
        raise HTTPException(503, "WhatsApp is not configured (WORKER_HASH_SECRET is missing or too short).")
    form = await request.form()
    params: dict[str, list[str]] = defaultdict(list)
    for key, value in form.multi_items():
        params[key].append(str(value))
    provider = get_provider()
    url = settings.whatsapp_webhook_url or str(request.url)
    if not provider.validate(url, dict(params), request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Invalid signature.")
    sid_in_form = params.get("AccountSid", [""])[0]
    if settings.twilio_account_sid and sid_in_form and sid_in_form != settings.twilio_account_sid:
        raise HTTPException(403, "Invalid signature.")
    n_media = int((params.get("NumMedia") or ["0"])[0] or 0) if (params.get("NumMedia") or ["0"])[0].isdigit() else 0
    media = tuple((params.get(f"MediaUrl{i}", [""])[0], params.get(f"MediaContentType{i}", [""])[0]) for i in range(min(n_media, 10)) if params.get(f"MediaUrl{i}"))
    incoming = Incoming(sender=params.get("From", [""])[0], to=params.get("To", [""])[0], body=params.get("Body", [""])[0], sid=params.get("MessageSid", [""])[0], media=media)
    if not incoming.sender:
        raise HTTPException(422, "Missing sender.")
    if not incoming.sender.startswith("whatsapp:"):
        return Response(EMPTY_TWIML, media_type="text/xml")  # this endpoint is for WhatsApp only: an SMS or anything else is acknowledged and ignored
    background.add_task(handle_incoming, incoming, provider)
    return Response(EMPTY_TWIML, media_type="text/xml")
