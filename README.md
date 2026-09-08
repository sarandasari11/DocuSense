# DocuSense

DocuSense is a context-aware document intelligence platform for grounded chat, policy comparison, contradiction detection, and temporal document retrieval.

## Stack

- FastAPI backend
- Static HTML/CSS/JavaScript frontend
- SQLModel with SQLite for development and PostgreSQL for production
- Qdrant for vector search
- Hybrid dense and BM25 retrieval with optional cross-encoder reranking
- Alembic database migrations

## Run locally

Copy the environment template and install the backend dependencies:

```powershell
Copy-Item .env.example .env
python -m pip install -r backend/requirements.txt
```

For containerized Qdrant and PostgreSQL:

```powershell
docker compose up -d
```

Start the development server:

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000.

## Production

Set `APP_ENV=production`, use a PostgreSQL `DATABASE_URL`, set `QDRANT_USE_LOCAL_STORAGE=false`, and configure `QDRANT_URL` and `QDRANT_API_KEY` when required.

Run migrations before starting the application:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production refuses SQLite and local file-backed Qdrant configuration.

## Health checks

- `GET /health/live` checks process liveness.
- `GET /health/ready` checks database, Qdrant, and model configuration.
- Every request receives an `X-Request-ID` response header and structured JSON logs are emitted.

## Project layout

- `backend/app`: API, database, retrieval, ingestion, and RAG services
- `backend/migrations`: Alembic migration history
- `backend/sample_data`: demo policy documents
- `backend/tests`: pipeline tests
- `eval`: benchmark dataset and evaluation script
- `frontend`: browser application
