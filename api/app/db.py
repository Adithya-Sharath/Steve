from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import settings


def _now() -> datetime:
    return datetime.now(UTC)


class Message(SQLModel, table=True):
    id: str = Field(primary_key=True)
    text: str
    sender_name: str = ""
    context: str = "other"
    confirmed: bool = False
    demo: bool = False
    created_at: datetime = Field(default_factory=_now)


class Fact(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(foreign_key="message.id", index=True)
    fact_id: str
    type: str
    value: Any = Field(default=None, sa_column=Column(JSON))
    unit: str | None = None
    critical: bool = True
    label: str = ""
    position: int = 0


class ReaderLink(SQLModel, table=True):
    token: str = Field(primary_key=True)
    message_id: str = Field(foreign_key="message.id", index=True)
    created_at: datetime = Field(default_factory=_now)


class Reply(SQLModel, table=True):
    id: str = Field(primary_key=True)
    message_id: str = Field(foreign_key="message.id", index=True)
    text: str
    source: str = "text"  # text | voice  (audio itself is NEVER stored)
    created_at: datetime = Field(default_factory=_now)


class FactResultRow(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    reply_id: str = Field(foreign_key="reply.id", index=True)
    message_id: str = Field(index=True)
    fact_id: str
    status: str
    heard_value: Any = Field(default=None, sa_column=Column(JSON))
    expected_value: Any = Field(default=None, sa_column=Column(JSON))
    evidence: Any = Field(default=None, sa_column=Column(JSON))
    confidence: float = 0.0
    reason: str = ""
    matched_terms: Any = Field(default=None, sa_column=Column(JSON))
    flags: Any = Field(default=None, sa_column=Column(JSON))


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        _engine = create_engine(url, **kwargs)
    return _engine


# columns added after the first release: `create_all` never alters existing tables, so add them in place
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "factresultrow": {"flags": "JSON"},
}


def _ensure_columns() -> None:
    insp = inspect(get_engine())
    with get_engine().begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
    _ensure_columns()


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
