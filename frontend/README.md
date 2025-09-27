# Desktop UI roadmap

The desktop application will be delivered as a Tauri + React bundle with the following high-level views:

1. **Data sources** – upload widgets for `accounts.txt`, `tokens.txt`, and `proxies.txt`, including preview of the first lines and column mapper for mismatched formats.
2. **Run control** – start/pause/stop buttons, configuration sliders for global/token/proxy concurrency, timeout and retry values, and the daily target calculator.
3. **Progress monitor** – live metrics (checked/pending/skipped/errors, RPS, token/proxy usage), progress bars, and structured logs with filtering and export.
4. **Results** – export manager supporting CSV/JSON filters, and real-time open-DM list persisted under `exports/open_dm_accounts.txt` by the backend.

The UI will communicate with the FastAPI backend via REST endpoints (`/load`, `/progress`, `/control`) and WebSocket streams for log updates. The UX is optimised for a "load files → press Start" workflow while retaining advanced tuning controls.
