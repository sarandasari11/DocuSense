# DocuSense

DocuSense is a document intelligence platform for grounded question answering, policy comparison, contradiction detection, and temporal document retrieval. It combines structured document ingestion with hybrid search so every answer can be traced back to the source document, page, and section.

## Highlights

- Grounded chat with page-level citations
- PDF, DOCX, and TXT document ingestion
- Section-aware chunking and metadata extraction
- Dense vector search with Qdrant
- Sparse BM25 keyword search
- Hybrid retrieval with Reciprocal Rank Fusion
- Optional cross-encoder reranking
- Temporal filtering for versioned documents and policies
- Side-by-side document comparison
- Numerical contradiction detection
- Google OAuth 2.0 sign-in
- PostgreSQL for production and SQLite for local development
- Static frontend served directly by FastAPI
- Health and readiness endpoints for deployment monitoring

## Architecture

```text
Browser
  |
  v
FastAPI application
  |-- Static HTML/CSS/JavaScript frontend
  |-- Document ingestion and parsing
  |-- Hybrid retrieval and RAG chat
  |-- Google OAuth and signed sessions
  |
  |-- PostgreSQL: documents, pages, chunks, conversations, citations
  |-- Qdrant Cloud: dense document vectors
  |-- Gemini/OpenAI: grounded answer generation
```

### Technology stack

| Area | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Frontend | Static HTML, CSS, and JavaScript |
| Relational database | SQLModel, SQLite, PostgreSQL |
| Migrations | Alembic |
| Vector database | Qdrant / Qdrant Cloud |
| Retrieval | Dense vectors, BM25, hybrid RRF |
| Embeddings | Deterministic development vectors or SentenceTransformers |
| Reranking | Optional SentenceTransformers CrossEncoder |
| LLM | Gemini, OpenAI, or offline grounded fallback |
| Authentication | Authlib, Google OAuth 2.0, signed HTTP-only sessions |

## How it works

### 1. Ingestion

An uploaded document is stored, parsed into pages, split into section-aware chunks, and recorded in PostgreSQL or SQLite. Supported formats are PDF, DOCX, and TXT.

### 2. Indexing

Each chunk receives document metadata such as version, effective date, page number, and section heading. Dense vectors are stored in Qdrant, while BM25 keyword retrieval is maintained by the application for exact terms, policy IDs, and names.

### 3. Retrieval

Queries can use dense, sparse, or hybrid retrieval. Hybrid results are combined with Reciprocal Rank Fusion and can optionally be reranked with a cross-encoder. Temporal expressions such as `in 2024` are extracted and applied as document filters.

### 4. Grounded generation

The RAG engine sends retrieved source passages to the configured LLM with instructions to answer only from the supplied evidence. Responses include citations containing the document, page, section, and excerpt. If no LLM key is configured, DocuSense returns a deterministic evidence-based fallback.

### 5. Comparison

Two indexed documents can be compared section by section. The comparison workflow also checks for conflicting numerical policy values and returns contradiction details.

## Requirements

- Python 3.11 or later
- Git
- Docker Desktop, optional for local PostgreSQL and Qdrant
- A Qdrant Cloud cluster for production
- A Gemini API key, or an OpenAI-compatible provider key, for generated answers

## Quick start

### 1. Clone the repository

```powershell
git clone <your-repository-url>
Set-Location DIS
```

### 2. Create a virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### 3. Create local environment settings

```powershell
Copy-Item .env.example .env
```

For a simple local run, use these values in `.env`:

```env
APP_ENV=development
DATABASE_URL=sqlite:///./backend/docusense.db
STORAGE_DIR=./backend/storage/documents
QDRANT_USE_LOCAL_STORAGE=true
QDRANT_PATH=./backend/storage/qdrant
MODEL_RUNTIME_MODE=deterministic
DEFAULT_LLM_PROVIDER=mock
AUTH_COOKIE_SECURE=false
```

The deterministic model mode avoids downloading model weights during local development. Set `DEFAULT_LLM_PROVIDER=gemini` and provide `GEMINI_API_KEY` when you want generated LLM answers.

### 4. Start the application

From the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Open the application at [http://127.0.0.1:8000](http://127.0.0.1:8000).

The API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Local Docker services

Docker Compose starts PostgreSQL and Qdrant with persistent named volumes:

```powershell
docker compose up -d
```

To use these services instead of SQLite and local file storage, configure `.env`:

```env
DATABASE_URL=postgresql://docusense:docusense_secret@localhost:5432/docusense_db
QDRANT_USE_LOCAL_STORAGE=false
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

Stop the services with:

```powershell
docker compose down
```

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `APP_ENV` | Yes | `development`, `test`, or `production` |
| `DATABASE_URL` | Yes in production | PostgreSQL in production; SQLite is supported locally |
| `SESSION_SECRET` | Yes in production | Signs the authentication session cookie |
| `STORAGE_DIR` | No | Local document storage directory |
| `QDRANT_USE_LOCAL_STORAGE` | Yes in production | Must be `false` in production |
| `QDRANT_URL` | Yes in production | Qdrant Cloud or hosted Qdrant endpoint |
| `QDRANT_API_KEY` | Yes for secured Qdrant | Qdrant Cloud API key |
| `QDRANT_COLLECTION` | No | Defaults to `docusense_chunks` |
| `MODEL_RUNTIME_MODE` | No | `deterministic` or `pretrained` |
| `MODEL_PRELOAD` | No | Starts model warmup during application startup |
| `DEFAULT_LLM_PROVIDER` | Yes | `gemini`, `openai`, or `mock` |
| `LLM_MODEL_NAME` | No | gemini-2.5-flash |
| `GEMINI_API_KEY` | Required for Gemini | Google Gemini API key |
| `OPENAI_API_KEY` | Required for OpenAI | OpenAI API key |
| `GOOGLE_CLIENT_ID` | Optional | Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth web client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | Optional | OAuth callback URL |
| `AUTH_COOKIE_SECURE` | Yes in production | Must be `true` over HTTPS |
| `CORS_ORIGINS` | No | Comma-separated allowed browser origins |

Never commit `.env` or place API keys in frontend JavaScript. Configure production secrets in Render's environment settings.

## Google OAuth

Google sign-in is optional. Create a Google OAuth 2.0 client of type **Web application**.

For local development, register:

```text
http://localhost:8000/auth/google/callback
```

For Render, register the exact deployed callback URL:

```text
https://YOUR-SERVICE.onrender.com/auth/google/callback
```

Configure the matching values in the environment:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=https://YOUR-SERVICE.onrender.com/auth/google/callback
AUTH_COOKIE_SECURE=true
```

The redirect URI must match Google Cloud exactly, including protocol, hostname, path, and trailing slash behavior.

## API endpoints

All application API routes use the `/api/v1` prefix unless noted otherwise.

### Health

```text
GET  /health/live       Process liveness
GET  /health/ready      Database, Qdrant, and model readiness
GET  /health            Readiness alias
```

### Documents

```text
GET    /api/v1/documents
POST   /api/v1/documents/upload
POST   /api/v1/documents/load-demo
GET    /api/v1/documents/{document_id}
GET    /api/v1/documents/{document_id}/content
DELETE /api/v1/documents/{document_id}
DELETE /api/v1/documents
```

### Search and chat

```text
POST /api/v1/search
POST /api/v1/chat
```

Search supports `dense`, `sparse`, and `hybrid` modes. Chat responses include grounded citations and retrieval metadata.

### Comparison and analytics

```text
POST /api/v1/compare
POST /api/v1/compare/contradictions
GET  /api/v1/analytics
```

### Authentication

```text
GET  /auth/google
GET  /auth/google/callback
GET  /auth/me
POST /auth/logout
```

## Deploy to Render

The repository includes a Render Blueprint in [render.yaml](render.yaml) and deployment scripts in [render-build.sh](render-build.sh) and [render-start.sh](render-start.sh).

### Blueprint deployment

1. Push the repository to GitHub or GitLab.
2. In Render, select **New + > Blueprint**.
3. Select the repository and apply `render.yaml`.
4. Confirm that Render provisions the web service and PostgreSQL database.
5. Add the following production variables in the Render dashboard:

```text
QDRANT_URL=https://YOUR-CLUSTER.cloud.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
GEMINI_API_KEY=your-gemini-api-key
CORS_ORIGINS=https://YOUR-SERVICE.onrender.com
```

6. For Google login, also add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and the production `GOOGLE_OAUTH_REDIRECT_URI`.
7. Deploy and inspect the service logs.

The startup script runs `alembic upgrade head` before starting Uvicorn. The Render health check uses `/health/live`.

### Production notes

- Keep `MODEL_RUNTIME_MODE=deterministic` on small Render instances.
- Use `MODEL_RUNTIME_MODE=pretrained` only when the service has enough memory for SentenceTransformers and the cross-encoder.
- Render's local filesystem is ephemeral. Uploaded documents should be moved to object storage for durable production storage.
- PostgreSQL and Qdrant data are separate from uploaded source files; back up or persist all three according to your retention needs.
- A new or deleted Qdrant cluster starts without document vectors. Re-upload documents or run **Load Demo Documents** after connecting a new cluster.

For the complete deployment walkthrough, see [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md).

## Verification

Check the deployed service:

```powershell
Invoke-RestMethod https://YOUR-SERVICE.onrender.com/health/live
Invoke-RestMethod https://YOUR-SERVICE.onrender.com/health/ready
```

`/health/live` should return HTTP 200 when the process is running. `/health/ready` should return HTTP 200 only when PostgreSQL, Qdrant, and the configured model services are ready.

Run the pipeline test locally:

```powershell
python -m pytest backend/tests -q
```

Run the benchmark evaluation:

```powershell
python eval/evaluate_benchmark.py
```

## Project structure

```text
DIS/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   ├── database/         # SQLModel and Qdrant integration
│   │   ├── models/           # Database and API models
│   │   ├── services/         # Parsing, ingestion, retrieval, RAG, comparison
│   │   ├── config.py         # Environment configuration and validation
│   │   └── main.py           # FastAPI application entrypoint
│   ├── migrations/           # Alembic migrations
│   ├── sample_data/          # Demo HR policy documents
│   ├── tests/                # Pipeline tests
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Static browser application
├── eval/                     # Evaluation script and benchmark dataset
├── docker-compose.yml        # Local PostgreSQL and Qdrant services
├── Dockerfile                # Container deployment image
├── render.yaml               # Render Blueprint
├── render-build.sh           # Render dependency installation
├── render-start.sh            # Render migrations and server startup
├── RENDER_DEPLOYMENT.md      # Detailed Render instructions
└── README.md
```

## Security checklist

- Keep `.env` out of version control.
- Rotate credentials if they are pasted into logs, screenshots, issues, or chat.
- Use a unique production `SESSION_SECRET`.
- Use HTTPS and `AUTH_COOKIE_SECURE=true` in production.
- Restrict `CORS_ORIGINS` to trusted origins.
- Give Qdrant API keys only the permissions required by the deployment.
- Do not expose Gemini, OAuth client secrets, database URLs, or Qdrant keys in frontend code.

## 📄 License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute this project, subject to the terms and conditions of the MIT License.

See the [LICENSE](LICENSE) file for the full license text.
