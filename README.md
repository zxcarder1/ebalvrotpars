# DM Checker Platform

This repository contains an asynchronous Python backend and a desktop UI scaffold for running large-scale checks of X (Twitter) accounts to determine whether direct messages are open.

## Repository structure

- `backend/` – Python 3.11+ backend service built on FastAPI, SQLModel, and httpx. It implements persistent queues, token/proxy pools with adaptive rate limiting, and ALEMBIC migrations.
- `frontend/` – Placeholder for the future desktop UI implementation (see `frontend/README.md`).

## Backend quick start

```bash
cd backend
pip install -e .
python -m dm_checker.cli init-db
python -m dm_checker.cli ingest-tokens path/to/tokens.txt
python -m dm_checker.cli ingest-proxies path/to/proxies.txt
python -m dm_checker.cli ingest-accounts path/to/accounts.txt
python -m dm_checker.cli serve
```

This will spin up the asynchronous worker pool and HTTP API (`create_app`) that the desktop UI can communicate with.

## Desktop UI

The desktop UI is envisaged as a Tauri + React application that connects to the backend HTTP API. See `frontend/README.md` for the interaction design and roadmap.
