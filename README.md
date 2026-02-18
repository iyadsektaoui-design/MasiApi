# MasiApi — Usage & OpenAPI Samples

This repository exposes a small FastAPI service that serves Moroccan market data from an SQLite database (`stocks_morocco.db`). Changes in this PR update the API to support the new DB schema (ISO dates) and add `DailyVariation` endpoints and OpenAPI samples.

## New features

- `/company/list` now returns, for each symbol, the latest row (latest `date`) with fields: `symbol`, `name`, `price`, `change`, `volume`, `date`.
- DailyVariation endpoints:
  - `GET /variation/symbol?symbol=XXX[&date_from=YYYY-MM-DD][&date_to=YYYY-MM-DD]`
  - `GET /variation/latest[?symbol=XXX]`
  - `GET /variation/recent?symbol=XXX[&limit=50]`
- `GET /openapi/samples` returns example curl requests and sample responses. These samples are included in the OpenAPI export.

## Quick start

1. Install requirements (recommended in a virtualenv):

```bash
pip install -r requirements.txt
# or at least: pip install fastapi uvicorn
```

2. Set the database path (optional):

```bash
export DB_PATH="/full/path/to/stocks_morocco.db"
# on Windows (PowerShell): $env:DB_PATH = 'C:\path\to\stocks_morocco.db'
```

3. Run the API with uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. Example curl requests:

```bash
# List latest per symbol
curl -s 'http://localhost:8000/company/list'

# Latest day rows
curl -s 'http://localhost:8000/company/latest'

# Latest DailyVariation for all symbols
curl -s 'http://localhost:8000/variation/latest'

# Latest 100 DailyVariation rows for a symbol
curl -s 'http://localhost:8000/variation/recent?symbol=ADH&limit=100'

# OpenAPI samples
curl -s 'http://localhost:8000/openapi/samples'
```

## Running tests

This repo includes a small pytest test file. Run:

```bash
pip install pytest requests
pytest -q
```

## Notes

- Ensure the `DB_PATH` environment variable points to the same database file we used during migration (e.g. `C:\Users\admin\Downloads\apiyahoo\data\masi\stocks_morocco.db`).
- If you run the update script externally, re-open DB Browser (or click Refresh) to see changes.
