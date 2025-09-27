"""SQLModel ORM models for DM checker."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class AccountStatus(str, enum.Enum):
    pending = "pending"
    checking = "checking"
    checked = "checked"
    skipped = "skipped"
    error = "error"


class TokenState(str, enum.Enum):
    active = "active"
    throttled = "throttled"
    invalid = "invalid"
    cooling_down = "cooling_down"


class ProxyType(str, enum.Enum):
    http = "http"
    https = "https"
    socks4 = "socks4"
    socks5 = "socks5"
    unknown = "unknown"


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    screen_name: str = Field(index=True, unique=True)
    rest_id: Optional[str] = Field(default=None, index=True)
    status: AccountStatus = Field(default=AccountStatus.pending, index=True)
    last_checked_at: Optional[datetime] = Field(default=None, index=True)
    last_result: Optional[str] = Field(default=None)
    attempt_count: int = Field(default=0)
    error: Optional[str] = Field(default=None)

    checks: list["Check"] = Relationship(back_populates="account")


class Token(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    login: str = Field(index=True)
    auth_token: str
    ct0: str
    web_bearer: str
    state: TokenState = Field(default=TokenState.active, index=True)
    last_429_at: Optional[datetime] = Field(default=None)
    estimated_rps: float = Field(default=1 / 60)
    consecutive_429: int = Field(default=0)
    last_response: Optional[str] = Field(default=None)

    checks: list["Check"] = Relationship(back_populates="token")


class Proxy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    raw: str = Field(index=True, unique=True)
    type: ProxyType = Field(default=ProxyType.unknown, index=True)
    last_used_at: Optional[datetime] = Field(default=None)
    fails: int = Field(default=0)

    checks: list["Check"] = Relationship(back_populates="proxy")


class Check(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    token_id: Optional[int] = Field(default=None, foreign_key="token.id")
    proxy_id: Optional[int] = Field(default=None, foreign_key="proxy.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    response_code: Optional[int] = None
    response_body_snippet: Optional[str] = Field(default=None, max_length=2000)

    account: Optional[Account] = Relationship(back_populates="checks")
    token: Optional[Token] = Relationship(back_populates="checks")
    proxy: Optional[Proxy] = Relationship(back_populates="checks")
