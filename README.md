# DocuSense

DocuSense is a context-aware document intelligence platform for grounded chat, policy comparison, contradiction detection, and temporal document retrieval.

## Stack

- FastAPI backend
- Static HTML/CSS/JavaScript frontend
- SQLModel with SQLite for development and PostgreSQL for production
- Qdrant for vector search
- Hybrid dense and BM25 retrieval with optional cross-encoder reranking
- Alembic database migrations
- Deterministic development embeddings with startup model warmup controls

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

$processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn.*app.main|multiprocessing.spawn' }; $processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; python -m uvicorn app.main:app --app-dir D:\DIS\backend --host localhost --port 8000
```

Open http://127.0.0.1:8000.

## Google OAuth login

Create an OAuth 2.0 **Web application** client in Google Cloud Console. Add this authorized redirect URI for local development:

```text
http://localhost:8000/auth/google/callback
```

Set the resulting credentials in `.env`:

```env
SESSION_SECRET=use-a-long-random-secret
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback
AUTH_COOKIE_SECURE=false
```

The UI sign-in button starts the server-side OAuth flow. Google never exposes the client secret to the browser. After callback, DocuSense stores the verified user identity in a signed, HTTP-only session cookie. In production, use an HTTPS callback URL and set `AUTH_COOKIE_SECURE=true`.

Development uses `MODEL_RUNTIME_MODE=deterministic` by default, so the first query does not download model weights. Production switches to `pretrained`; embedding and reranker loading starts once during application startup and reports `loading` through `/health/ready` until complete.

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
