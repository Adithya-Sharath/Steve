from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .ratelimit import default_ip_limit
from .routes import messages, misc, reader
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

app.include_router(misc.router)
app.include_router(messages.router)
app.include_router(reader.router)
