# Runestreet — OSRS Dump Detector

Monorepo with:
- `backend/`: FastAPI API + Postgres cache + scan compute
- `frontend/`: Vite + React UI

## MVP data strategy

We ingest 5-minute buckets in bulk using:
- `GET https://prices.runescape.wiki/api/v1/osrs/5m?timestamp=<unix_seconds>`

and cache them in Postgres, then run the dump scan on demand.

**Important:** The OSRS Wiki blocks default User-Agents (e.g. `python-requests`, `curl`). You must set `OSRS_USER_AGENT`.

## Local development

### Prereqs
- Python 3.11+
- Node 18+
- Postgres (or use Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# start a local postgres and set DATABASE_URL, or use docker-compose you create later
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/runestreet"
export OSRS_USER_AGENT="runestreet-dump-detector - contact: you@example.com"

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
export VITE_API_BASE_URL="http://localhost:8000"
npm run dev
```

## Railway deployment (2 services + Postgres)

Create a Railway project with:
- **Postgres** addon (Railway provides `DATABASE_URL`)
- **Backend service**: root directory `backend/`
- **Frontend service**: root directory `frontend/`

Set variables:
- Backend:
  - `DATABASE_URL` (from Railway Postgres)
  - `OSRS_USER_AGENT` (**required**; do not use defaults like `python-requests`/`curl`)
  - `OSRS_BASE_URL` (optional; default `https://prices.runescape.wiki/api/v1/osrs`)
  - `CORS_ALLOWED_ORIGINS` (optional; comma-separated list including your frontend URL)
- Frontend:
  - `VITE_API_BASE_URL` (backend public URL)

### Railway notes for monorepos

- **Root Directory**: each Railway service can be pointed at a subdirectory (isolated monorepo). Set this to `backend/` and `frontend/` respectively.
- **Port**: backend must listen on `$PORT` (Railway injects it). Frontend is built as static assets via Vite.


