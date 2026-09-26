from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .ratelimit import default_ip_limit
from .routes import decode, messages, misc, reader
from .security import (
    BodyLimitMiddleware,
    SecurityHeadersMiddleware,
    cors_options,
    install_log_filters,
    unhandled_exception_handler,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Steve API",
    version="2.0.0",
    description="Decode: plain English, where / when / what / how much, from accented or mixed speech and messages (text in, text out). Check mode: teach-back for mixed-language messages. Deterministic engine; LLM, speech-to-text and translation are optional helpers. Decode contract: docs/API.md.",
    lifespan=lifespan,
    dependencies=[Depends(default_ip_limit)],
)

# Starlette puts the LAST added middleware outermost. Security headers wrap everything (even CORS preflights), CORS wraps
# the body limit so a 413 or 429 is still readable by the browser, and the body limit sits next to the routes.
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(CORSMiddleware, **cors_options())
app.add_middleware(SecurityHeadersMiddleware)

app.add_exception_handler(Exception, unhandled_exception_handler)
install_log_filters()

app.include_router(misc.router)
app.include_router(messages.router)
app.include_router(reader.router)
app.include_router(decode.router)
