# Complete Deployment Guide: DocuSense on Render + Qdrant Cloud + Google OAuth

This guide provides a comprehensive, step-by-step walkthrough to deploy **DocuSense** from scratch with:
- **Render** (FastAPI backend + integrated static frontend + PostgreSQL)
- **Qdrant Cloud** (Hosted vector database for fast semantic document retrieval)
- **Google Cloud Console** (OAuth 2.0 authentication)
- **Google Gemini API** (Document Q&A synthesis)

---

## 🏗️ Deployment Architecture

```
                          Render Web Service (FastAPI)
                     ┌───────────────────────────────────┐
                     │ • Serves Web UI (/, /app.js, etc) │
                     │ • Runs RAG Pipeline & Alembic     │
                     │ • Pre-warms Model Warmup          │
                     └───────┬───────────┬───────────────┘
                             │           │
       Internal Network      │           │ HTTPS
      (Oregon US-West)       ▼           ▼
   ┌───────────────────────────┐       ┌─────────────────────────────┐
   │ Render Managed PostgreSQL │       │    Qdrant Cloud Cluster     │
   │ (docusense-postgres)      │       │ (Vector DB - Free Tier 1GB) │
   └───────────────────────────┘       └─────────────────────────────┘
                                                 ▲
                                                 │
                               ┌─────────────────┴─────────────┐
                               │ External Cloud APIs:          │
                               │ • Google Gemini (AI Studio)   │
                               │ • Google Cloud OAuth 2.0      │
                               └───────────────────────────────┘
```

---

## 📋 Pre-Deployment Setup (Step-by-Step)

Complete these 3 external setup steps before launching on Render.

---

### Step 1: Set Up Qdrant Cloud (Vector Database)

DocuSense uses Qdrant Cloud to persist document vector embeddings permanently across Render deploys.

1. Go to [cloud.qdrant.io](https://cloud.qdrant.io) and sign up / log in.
2. In the dashboard, click **Create Cluster**.
3. Choose the **Free Tier** (1GB cluster, 0.5 vCPU, 1GB RAM — free forever).
4. Select a region close to your Render deployment (e.g. `US East / us-east-1` or `GCP us-east4`).
5. Give your cluster a name (e.g., `docusense-vectors`) and click **Create**.
6. Once the cluster status shows **Healthy / Running**:
   - Copy the **Cluster URL** (e.g., `https://xxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.us-east4-0.gcp.cloud.qdrant.io:6333`).
7. In the left sidebar, click **Data access control** (or **API Keys**):
   - Click **Create API Key**.
   - Copy your **API Key** immediately (you will not see it again).
8. **Save these two values**:
   - `QDRANT_URL` = `https://<your-cluster-endpoint>:6333`
   - `QDRANT_API_KEY` = `<your-qdrant-api-key>`

> [!NOTE]
> You **do NOT need to manually create any collections or tables in Qdrant**. DocuSense automatically detects, creates, and indexes the collection `docusense_chunks` (dim=384, cosine distance) upon startup.

---

### Step 2: Get a Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Click **Create API Key** (choose your Google Cloud project or create a default one).
3. Copy the generated key (`AQ...` or `AIzaSy...`).
4. **Save this value**:
   - `GEMINI_API_KEY` = `<your-gemini-key>`

---

### Step 3: Configure Google Cloud Console for OAuth 2.0

If you want users to sign in with Google:

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `DocuSense-App`) or select your existing project.

#### A. Configure the OAuth Consent Screen
1. In the navigation menu, go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** and click **Create**.
3. Fill in:
   - **App name**: `DocuSense`
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
4. Click **Save and Continue** through **Scopes** (standard openid, email, profile are sufficient).
5. **IMPORTANT (Test Users)**:
   - While your app is in "Testing" mode, **only registered test users can sign in**.
   - Under **Test users**, click **Add Users** and add your Google email address!
6. Click **Save and Continue** to finish.

#### B. Create OAuth 2.0 Client Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** > **OAuth client ID**.
3. Set **Application type**: `Web application`.
4. Set **Name**: `DocuSense Web Client`.
5. Under **Authorized JavaScript origins**, add:
   ```
   http://localhost:8000
   ```
   *(You will add your Render URL here after step 4, e.g. `https://docusense-backend.onrender.com`)*
6. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8000/auth/google/callback
   ```
   *(You will add your Render URL here after step 4, e.g. `https://docusense-backend.onrender.com/auth/google/callback`)*
7. Click **Create**.
8. Copy the **Client ID** and **Client Secret**:
   - `GOOGLE_CLIENT_ID` = `xxxxxxxxxxxx-xxxxxxxxxxxxxxxx.apps.googleusercontent.com`
   - `GOOGLE_CLIENT_SECRET` = `GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx`

---

## 🚀 Deploying to Render

You can deploy using either **Option 1 (Blueprint - Recommended)** or **Option 2 (Manual Dashboard Setup)**.

---

### Option 1: 1-Click Blueprint Deployment (Recommended)

DocuSense includes [`render.yaml`](./render.yaml), which automatically deploys both PostgreSQL and the Web Service in the same Oregon region with zero manual database wiring.

#### Steps:
1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "chore: ready for clean Render deployment"
   git push origin main
   ```
2. Log in to [Render Dashboard](https://dashboard.render.com/).
3. In the top right, click **New +** > **Blueprint**.
4. Connect your GitHub repository (`DocuSense`).
5. Render will inspect `render.yaml` and display two resources:
   - `docusense-postgres` (Managed PostgreSQL Database)
   - `docusense-backend` (Python Web Service)
6. Render will prompt you for the required environment variables:
   - **`QDRANT_URL`**: Paste your Qdrant cluster endpoint (e.g. `https://xxxx.cloud.qdrant.io:6333`).
   - **`QDRANT_API_KEY`**: Paste your Qdrant API key.
   - **`GEMINI_API_KEY`**: Paste your Google Gemini API key.
   - **`GOOGLE_CLIENT_ID`**: *(Optional)* Your Google OAuth Client ID.
   - **`GOOGLE_CLIENT_SECRET`**: *(Optional)* Your Google OAuth Client Secret.
7. Click **Apply**.
8. Render will now:
   - Create the PostgreSQL database.
   - Run `render-build.sh` (installs CPU PyTorch and Python requirements).
   - Run `render-start.sh` (runs Alembic migrations `alembic upgrade head` and launches FastAPI).
9. Note down your service's Render URL (e.g., `https://docusense-backend-xxxx.onrender.com`).

---

### Option 2: Manual Web Service Setup (Step-by-Step)

If you prefer to configure everything manually in the Render dashboard:

#### Step 1: Create PostgreSQL Database on Render
1. In Render, click **New +** > **PostgreSQL**.
2. Settings:
   - **Name**: `docusense-postgres`
   - **Database**: `docusense_db`
   - **User**: `docusense`
   - **Region**: `Oregon (US West)` (keep backend and DB in the same region)
   - **Plan**: `Free`
3. Click **Create Database**.
4. Wait 1 minute for it to become available, then copy the **Internal Database URL** (e.g. `postgres://docusense:xxxx@docusense-postgres/docusense_db`).

#### Step 2: Create Web Service on Render
1. In Render, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Settings:
   - **Name**: `docusense-backend`
   - **Region**: `Oregon (US West)` (must match database region)
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: `bash ./render-build.sh`
   - **Start Command**: `bash ./render-start.sh`
   - **Instance Type**: `Free`
4. Expand **Advanced Settings**:
   - Set **Health Check Path**: `/health/live`
   - Set **Auto-Deploy**: `Yes`
5. In the **Environment Variables** section, add the following table:

| Key | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | Enables production mode |
| `PYTHON_VERSION` | `3.11.9` | Matches Python version |
| `DATABASE_URL` | *(Paste Internal DB URL from Step 1)* | Automatically converted to `postgresql+psycopg://` |
| `SESSION_SECRET` | *(Random 32+ character string)* | e.g. `openssl rand -hex 32` |
| `MODEL_RUNTIME_MODE` | `deterministic` | Best for Free Tier (512MB RAM). |
| `MODEL_PRELOAD` | `true` | Warms up models on start |
| `MODEL_LOAD_TIMEOUT_SECONDS` | `120` | Timeout window |
| `QDRANT_USE_LOCAL_STORAGE` | `false` | Required for cloud Qdrant |
| `QDRANT_URL` | `https://xxxx.cloud.qdrant.io:6333` | From Qdrant Cloud |
| `QDRANT_API_KEY` | `<your-qdrant-api-key>` | From Qdrant Cloud |
| `DEFAULT_LLM_PROVIDER` | `gemini` | Primary LLM engine |
| `LLM_MODEL_NAME` | `gemini-1.5-flash` | Fast and accurate |
| `GEMINI_API_KEY` | `<your-gemini-api-key>` | From Google AI Studio |
| `AUTH_COOKIE_SECURE` | `true` | Enforces HTTPS session cookies |
| `GOOGLE_CLIENT_ID` | `<your-google-client-id>` | *(Optional, for OAuth)* |
| `GOOGLE_CLIENT_SECRET` | `<your-google-client-secret>` | *(Optional, for OAuth)* |

6. Click **Create Web Service**.

---

## 🔗 Step 4: Link Render URL into Google Cloud OAuth

Once your Render Web Service is deployed, you will see its assigned domain, such as:
`https://docusense-backend-xxxx.onrender.com`

To enable Google Sign-In with this live domain:
1. Open [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Click to edit your **OAuth 2.0 Web Client**.
3. Under **Authorized JavaScript origins**, click **+ Add URI** and add:
   ```
   https://<your-service-name>.onrender.com
   ```
4. Under **Authorized redirect URIs**, click **+ Add URI** and add:
   ```
   https://<your-service-name>.onrender.com/auth/google/callback
   ```
5. Click **Save**.
6. *(Note: Our backend automatically detects `RENDER_EXTERNAL_URL` and uses this callback URL without needing you to manually re-deploy!)*

---

## ✅ Step 5: Verification & Testing

Once the Render build and deploy finish with "Live":

1. **Liveness Check**:
   Open in browser or terminal:
   ```bash
   curl https://<your-service>.onrender.com/health/live
   ```
   Expected response:
   ```json
   {"status":"ok","app":"DocuSense","version":"1.0.0","environment":"production"}
   ```

2. **Readiness Check** (verifies PostgreSQL, Qdrant, and Models):
   ```bash
   curl https://<your-service>.onrender.com/health/ready
   ```
   Expected response:
   ```json
   {
     "status": "ready",
     "checks": {
       "database": {"status": "ok", "backend": "postgresql"},
       "vector_store": {"status": "ok", "collection": "docusense_chunks"},
       "models": {"status": "ok", "mode": "deterministic", ...}
     }
   }
   ```

3. **Access the Web Interface**:
   Visit `https://<your-service>.onrender.com/` in any browser:
   - Click **Sign in with Google** to test OAuth.
   - Upload sample documents (`.pdf`, `.docx`, `.txt`).
   - Run queries in **Chat** or **Search** to test hybrid retrieval and Gemini answer synthesis!

---

## 💡 Troubleshooting Common Issues

| Issue | Cause | Fix |
|---|---|---|
| **Build timed out or Out-of-Memory** | Default PyTorch pulls 1GB+ CUDA wheels from PyPI | `render-build.sh` is now updated to install CPU-only PyTorch (`--index-url https://download.pytorch.org/whl/cpu`), reducing download size to ~180MB. |
| **`403: access_denied` on Google Sign-In** | Google OAuth Consent Screen is in "Testing" mode and user is not listed | In Google Cloud Console > OAuth consent screen > **Test users**, add your Google email address. |
| **`MismatchingStateError` on Google Sign-In** | Expired session, multiple tabs, or stale cookie | Return to `https://<your-service>.onrender.com` and initiate sign-in cleanly. Also ensure `render-start.sh` uses `--proxy-headers --forwarded-allow-ips='*'`. |
| **`Qdrant connection error`** | QDRANT_URL missing scheme or bad API key | Enter the full URL starting with `https://` (e.g. `https://xxxx.cloud.qdrant.io:6333`) and ensure the API key is active. |
| **`Model not found` in Gemini** | Invalid model identifier | Ensure `LLM_MODEL_NAME=gemini-1.5-flash` (or `gemini-2.0-flash`). |
