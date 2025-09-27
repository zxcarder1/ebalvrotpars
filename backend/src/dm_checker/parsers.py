"""File parsing helpers for accounts, tokens, and proxies."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

ACCOUNT_REGEX = re.compile(r"(?:https?://x\.com/|@)?(?P<screen_name>[A-Za-z0-9_]{1,15})$")
PROXY_REGEX = re.compile(
    r"^(?:(?P<scheme>https?|socks4|socks5)://)?(?:(?P<user>[^:@]+)(?::(?P<password>[^@]+))?@)?(?P<host>[\w\.-]+)(?::(?P<port>\d+))?$"
)


@dataclass
class TokenRecord:
    login: str
    auth_token: str
    ct0: str
    web_bearer: str


@dataclass
class ProxyRecord:
    raw: str
    scheme: str
    username: str | None
    password: str | None
    host: str | None
    port: int | None


def parse_accounts(path: Path) -> list[str]:
    """Parse account identifiers from text file."""

    accounts: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        match = ACCOUNT_REGEX.match(line)
        if not match:
            raise ValueError(f"Unrecognised account format: {line}")
        accounts.append(match.group("screen_name"))
    return accounts


def parse_token_csv(rows: Sequence[str]) -> Iterator[TokenRecord]:
    reader = csv.DictReader(rows)
    required = {"login", "auth_token", "ct0", "web_bearer"}
    if not required.issubset(reader.fieldnames or {}):
        raise ValueError("CSV token file missing required columns")
    for row in reader:
        yield TokenRecord(
            login=row["login"].strip(),
            auth_token=row["auth_token"].strip(),
            ct0=row["ct0"].strip(),
            web_bearer=row["web_bearer"].strip(),
        )


def parse_token_jsonl(lines: Iterable[str]) -> Iterator[TokenRecord]:
    for line in lines:
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        yield TokenRecord(
            login=record["login"],
            auth_token=record["auth_token"],
            ct0=record["ct0"],
            web_bearer=record["web_bearer"],
        )


def parse_tokens(path: Path) -> list[TokenRecord]:
    """Parse token file either CSV or JSONL."""

    text = path.read_text().splitlines()
    if not text:
        return []
    first = text[0].lstrip()
    if first.startswith("{"):
        return list(parse_token_jsonl(text))
    return list(parse_token_csv(text))


def parse_proxies(path: Path) -> list[ProxyRecord]:
    """Parse proxy definitions from file."""

    proxies: list[ProxyRecord] = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = PROXY_REGEX.match(raw)
        if not match:
            raise ValueError(f"Invalid proxy entry: {raw}")
        scheme = match.group("scheme") or "http"
        username = match.group("user")
        password = match.group("password")
        host = match.group("host")
        port = int(match.group("port")) if match.group("port") else None
        proxies.append(
            ProxyRecord(
                raw=raw,
                scheme=scheme,
                username=username,
                password=password,
                host=host,
                port=port,
            )
        )
    return proxies
