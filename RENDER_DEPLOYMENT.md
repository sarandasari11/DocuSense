# DocuSense Backend Deployment Guide for Render

This guide walks you through deploying the **DocuSense** backend and static frontend to [Render](https://render.com).

---

## 🏗️ Architecture on Render

```
   ┌─────────────────────────────────────────────────────────────┐
   │                       Render Cloud                          │
   │                                                             │
   │  ┌───────────────────────┐       ┌───────────────────────┐  │
   │  │   DocuSense Web       │◄─────►│   Render PostgreSQL   │  │
   │  │   Service (FastAPI)   │       │   (Managed Database)  │  │
   │  └───────────┬───────────┘       └───────────────────────┘  │
   └──────────────┼──────────────────────────────────────────────┘
                  │ HTTPS
                  ▼
   ┌─────────────────────────────┐
   │    Qdrant Cloud Cluster     │
   │    (Free 1GB Vector DB)     │
   │    https://cloud.qdrant.io  │
   └─────────────────────────────┘
```

---

## 📋 Prerequisites

1. A [Render Account](https://render.com).
2. A GitHub or GitLab repository containing your DocuSense code.
3. A free [Qdrant Cloud](https://cloud.qdrant.io) account for vector storage.
4. A [Google Gemini API Key](https://aistudio.google.com/app/apikey) (or OpenAI / Groq key).

---

## 🚀 Option 1: 1-Click Blueprint Deployment (Recommended)

The repository includes a ready-to-use [`render.yaml`](./render.yaml) Blueprint that automatically provisions:
- A managed **PostgreSQL Database** (`docusense-postgres`).
- A **Python Web Service** with automated migrations (`render-start.sh`) and health checks.

### Steps:

1. **Push your code** to GitHub or GitLab.
2. In the **[Render Dashboard](https://dashboard.render.com/)**, click **New +** > **Blueprint**.
3. Connect your repository.
4. Render will detect `render.yaml` and list the resources to create (`docusense-postgres` and `docusense-backend`).
5. Fill in the required environment variables when prompted:
   - `QDRANT_URL`: Your Qdrant Cloud cluster endpoint (e.g., `https://xxxx.cloud.qdrant.io:6333`).
   - `QDRANT_API_KEY`: Your Qdrant Cloud API key.
   - `GEMINI_API_KEY`: Your Google AI Studio API key.
   - `CORS_ORIGINS`: Your Render web service URL (e.g., `https://docusense-backend.onrender.com`).
6. Click **Apply**.
7. Render will build the environment, run database migrations (`alembic upgrade head`), and start the FastAPI service.

---

## 🛠️ Option 2: Manual Web Service Setup

If you prefer to configure the services manually in the Render dashboard:

### Step 1: Create a PostgreSQL Database on Render
1. Go to **New +** > **PostgreSQL**.
2. Set Name: `docusense-postgres`.
3. Set Database: `docusense_db`.
4. Set User: `docusense`.
5. Select the **Free** instance type (or Starter for permanent persistence).
6. Click **Create Database**.
7. Copy the **Internal Database URL** (e.g., `postgres://docusense:...@docusense-postgres:5432/docusense_db`).

### Step 2: Create the Web Service
1. Go to **New +** > **Web Service**.
2. Connect your Git repository.
3. Configure the service settings:
   - **Name**: `docusense-backend`
   - **Language**: `Python`
   - **Region**: Same region as your database (e.g., `Oregon (US West)`)
   - **Branch**: `main` (or your active branch)
   - **Build Command**: `./render-build.sh`
   - **Start Command**: `./render-start.sh`
   - **Instance Type**: `Free` (or `Starter` if using `MODEL_RUNTIME_MODE=pretrained`)

### Step 3: Add Environment Variables
Under the **Environment Variables** section, add:

| Key | Example Value | Description |
|---|---|---|
| `APP_ENV` | `production` | Enables production mode |
| `PYTHON_VERSION` | `3.11.9` | Ensures Python 3.11 runtime |
| `DATABASE_URL` | *(Paste Internal DB URL from Step 1)* | Render automatically connects to PostgreSQL |
| `SESSION_SECRET` | *(Generate a 32+ char random string)* | Used for cookie signing |
| `MODEL_RUNTIME_MODE` | `deterministic` | Use `deterministic` for Free tier (512MB RAM) or `pretrained` for Starter tier (1GB+ RAM) |
| `MODEL_PRELOAD` | `true` | Preloads models on startup |
| `QDRANT_USE_LOCAL_STORAGE` | `false` | Disables local disk SQLite Qdrant |
| `QDRANT_URL` | `https://xxxx.aws.cloud.qdrant.io:6333` | Your Qdrant Cloud cluster endpoint |
| `QDRANT_API_KEY` | `th1s-1s-y0ur-qdrant-k3y` | Qdrant Cloud API key |
| `DEFAULT_LLM_PROVIDER` | `gemini` | `gemini` \| `openai` \| `groq` |
| `LLM_MODEL_NAME` | `gemini-1.5-flash` | Model identifier |
| `GEMINI_API_KEY` | `AIzaSy...` | Your Google Gemini API Key |
| `AUTH_COOKIE_SECURE` | `true` | Enforces HTTPS cookie security |
| `CORS_ORIGINS` | `https://docusense-backend.onrender.com` | Allowed frontend origins |

### Step 4: Health Check Path
- In **Advanced Settings**, set **Health Check Path** to: `/health/live`.

---

## 🐳 Option 3: Deploy via Docker

You can also deploy DocuSense using the provided `Dockerfile`:
1. In Render, select **New +** > **Web Service**.
2. Connect your repository.
3. Select **Docker** as the Runtime.
4. Set the same Environment Variables listed above.
5. Render will automatically build the image and execute `render-start.sh`.

---

## 🌐 Vector Database Setup (Qdrant Cloud)

Because Render free web services have ephemeral storage, production uses hosted Qdrant:

1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Click **Create Cluster** (The **Free Tier** includes a 1GB cluster with 0.5 vCPU and 1GB RAM forever).
3. Once provisioned:
   - Copy the **Cluster URL** (e.g., `https://xxxxxx-xxxx.cloud.qdrant.io:6333`).
   - Click **API Keys** > **Create API Key**, and copy the key.
4. Set these as `QDRANT_URL` and `QDRANT_API_KEY` in Render.

---

## 🔑 Google OAuth Setup (Optional)

If you enable Google Sign-In on Render:
1. Open [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Edit your OAuth 2.0 Web Client.
3. Add your Render domain to **Authorized JavaScript origins**:
   ```
   https://docusense-backend.onrender.com
   ```
4. Add the callback to **Authorized redirect URIs**:
   ```
   https://docusense-backend.onrender.com/auth/google/callback
   ```
5. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in Render.

---

## 🔍 Verification & Health Checks

Once deployed, you can verify your service status:

- **Liveness Check**:
  ```bash
  curl https://<your-service>.onrender.com/health/live
  ```
  Expected output:
  ```json
  {"status":"ok","app":"DocuSense","version":"1.0.0","environment":"production"}
  ```

- **Readiness Check** (Checks PostgreSQL, Qdrant, and Model status):
  ```bash
  curl https://<your-service>.onrender.com/health/ready
  ```

- **API Documentation**:
  Visit `https://<your-service>.onrender.com/docs` for interactive Swagger documentation.

- **Web Application**:
  Visit `https://<your-service>.onrender.com/` to access the DocuSense UI.

---

## 💡 Important Tips for Render Free Tier

1. **Memory Limits (512MB RAM on Free Tier)**:
   - Running full neural embedding models (`SentenceTransformer` + `CrossEncoder`) simultaneously in memory requires ~800MB RAM.
   - For the **Render Free Tier**, keep `MODEL_RUNTIME_MODE=deterministic` to ensure snappy responses and avoid Out-Of-Memory (OOM) crashes.
   - For high-accuracy neural embeddings in production, upgrade the Web Service to Render's **Starter Plan (1GB RAM, $7/mo)** and set `MODEL_RUNTIME_MODE=pretrained`.

2. **Database Driver URL Compatibility**:
   - Render passes `DATABASE_URL` in `postgres://...` format. DocuSense's configuration automatically normalizes this to `postgresql+psycopg://` so it works seamlessly with SQLAlchemy and psycopg3.

3. **Automatic Migrations**:
   - Every deployment executes `render-start.sh`, ensuring Alembic schema migrations run before FastAPI accepts incoming traffic.
