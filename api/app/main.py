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
    install_log_filters,
    unhandled_exception_handler,
)
from .settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Steve API",
    version="0.1.0",
    description="Teach-back for mixed-language messages. Deterministic engine; LLM and STT are optional helpers.",
    lifespan=lifespan,
    dependencies=[Depends(default_ip_limit)],
)

# Starlette puts the LAST added middleware outermost. Security headers wrap everything (even CORS preflights), CORS wraps
# the body limit so a 413 or 429 is still readable by the browser, and the body limit sits next to the routes.
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.add_exception_handler(Exception, unhandled_exception_handler)
install_log_filters()

app.include_router(misc.router)
app.include_router(messages.router)
app.include_router(reader.router)
app.include_router(decode.router)
