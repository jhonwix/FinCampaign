# FinCampaign RAG Agent

Multi-agent credit campaign system powered by Vertex AI Search (RAG) + Gemini 2.5 Flash Lite + FastAPI + React.

The system receives a customer credit profile, runs it through 3 specialized AI agents coordinated by an orchestrator, retrieves relevant credit policies via RAG, and generates a personalized campaign with full compliance validation.

---

## Architecture

```
React Frontend (Vite + Tailwind)
        │
        │ /api/*  (Vite proxy)
        ▼
FastAPI Backend (Python 3.11)
        │
        ├── Orchestrator
        │       ├── [1] Risk Analyst Agent
        │       │       RAG: reglamento_scoring.txt
        │       │       Output: segment, DTI, risk_level, eligible_products
        │       │
        │       ├── [2] Campaign Generator Agent   (skipped if ineligible)
        │       │       RAG: catalogo_productos.txt
        │       │       Output: product, message, CTA, rates, channel
        │       │
        │       └── [3] Compliance Checker Agent   (never skipped)
        │               RAG: politicas_credito.txt
        │               Output: fair_lending, APR, verdict, human_review
        │
        ├── PostgreSQL  →  customers + campaign_results tables
        └── Google Cloud Storage  →  results/{YYYY}/{MM}/{DD}/{request_id}.json
```

**RAG:** Vertex AI Search (Discovery Engine) — `locations/global`
**LLM:** Gemini 2.5 Flash Lite via Vertex AI REST API with API key
**Credentials:** Service account JSON for Discovery Engine + GCS

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Gemini 2.5 Flash Lite (Vertex AI) |
| RAG | Vertex AI Search (Discovery Engine) |
| Backend | FastAPI + asyncpg + Python 3.11 |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Database | PostgreSQL (asyncpg connection pool) |
| Storage | Google Cloud Storage |
| Auth | Service Account JSON |

---

## Project Structure

```
FinCampaign/
├── .env.example
├── backend/
│   ├── main.py               FastAPI app + all endpoints
│   ├── config.py             Pydantic Settings (reads .env)
│   ├── gemini_client.py      Direct HTTP client for Vertex AI REST API
│   ├── requirements.txt
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── risk_analyst.py
│   │   ├── campaign_generator.py
│   │   └── compliance_checker.py
│   ├── rag/
│   │   ├── retriever.py      Vertex AI Search queries
│   │   ├── indexer.py        GCS upload + ImportDocuments
│   │   └── datastore.py      Datastore creation
│   ├── db/
│   │   ├── connection.py     asyncpg pool
│   │   └── queries.py        CRUD functions
│   └── models/
│       └── schemas.py        Pydantic models
├── frontend/
│   ├── package.json
│   ├── vite.config.ts        Proxy /api -> localhost:8081
│   └── src/
│       ├── App.tsx
│       ├── api/
│       │   ├── client.ts
│       │   └── types.ts
│       ├── components/
│       │   ├── Badge.tsx
│       │   ├── AnalysisCard.tsx
│       │   └── Layout.tsx
│       └── pages/
│           ├── Dashboard.tsx
│           └── CustomerDetail.tsx
├── rag_documents/
│   ├── politicas_credito.txt
│   ├── reglamento_scoring.txt
│   └── catalogo_productos.txt
├── scripts/
│   ├── create_datastore.py
│   ├── upload_documents.py
│   ├── setup_db.py           Creates tables + seeds 10 test customers
│   └── test_pipeline.py
└── deploy/
    ├── Dockerfile
    └── cloudbuild.yaml
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (local or remote)
- Google Cloud project with APIs enabled:
  - `discoveryengine.googleapis.com`
  - `storage.googleapis.com`
  - `aiplatform.googleapis.com`

### 1. Clone and configure

```bash
git clone https://github.com/jhonwix/FinCampaign.git
cd FinCampaign
cp .env.example .env
# Fill in .env with your values (see below)
```

### 2. Create a service account

```bash
gcloud iam service-accounts create fincampaign-backend \
  --display-name="FinCampaign Backend"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/discoveryengine.editor"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud iam service-accounts keys create backend/service-account.json \
  --iam-account=fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Create GCS bucket

```bash
gcloud storage buckets create gs://YOUR_PROJECT_ID-fincampaign-results \
  --location=us-central1
```

### 4. Backend setup

```bash
python -m venv venv
venv/Scripts/activate      # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r backend/requirements.txt
```

### 5. Database setup

```bash
python scripts/setup_db.py
# Creates customers + campaign_results tables
# Seeds 10 test customers (SUPER-PRIME to DEEP-SUBPRIME)
```

### 6. RAG setup

```bash
# Create Vertex AI Search datastore (one-time)
ACCESS_TOKEN=$(gcloud auth print-access-token --project=YOUR_PROJECT_ID)
curl -X POST \
  "https://discoveryengine.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/global/collections/default_collection/dataStores?dataStoreId=fincampaign-rag-datastore" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Goog-User-Project: YOUR_PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d '{"displayName":"FinCampaign RAG Datastore","industryVertical":"GENERIC","contentConfig":"CONTENT_REQUIRED"}'

# Upload and index the 3 policy documents
python scripts/upload_documents.py
# Wait 10-15 minutes for Vertex AI Search to finish indexing
```

### 7. Start backend

```bash
cd backend
uvicorn main:app --reload --port 8081
# API: http://localhost:8081
# Docs: http://localhost:8081/docs
```

### 8. Start frontend

```bash
cd frontend
npm install
npm run dev
# UI: http://localhost:3000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/customers` | List all customers from PostgreSQL |
| `POST` | `/api/analyze` | Run pipeline for a raw customer profile |
| `POST` | `/api/analyze/db/{id}` | Run pipeline for a customer from the DB |
| `GET` | `/api/customers/{id}/results` | Get analysis history for a customer |
| `POST` | `/api/batch` | Batch process up to 100 customers |
| `GET` | `/api/results/{request_id}` | Retrieve a stored result from GCS |
| `GET` | `/api/documents` | List indexed RAG documents |
| `POST` | `/api/documents/upload` | Upload a new TXT/PDF to the datastore |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
GOOGLE_API_KEY=          # From console.cloud.google.com/vertex-ai/studio/settings/api-keys
GOOGLE_CLOUD_PROJECT=    # Your GCP project ID
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

VERTEX_AI_DATASTORE_ID=fincampaign-rag-datastore
GCS_BUCKET_NAME=YOUR_PROJECT_ID-fincampaign-results

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

## Credit Segments

| Segment | Score Range | Risk | Behavior |
|---|---|---|---|
| SUPER-PRIME | 740+ | LOW | Full campaign |
| PRIME | 670–739 | LOW | Full campaign |
| NEAR-PRIME | 620–669 | MEDIUM | Full campaign |
| SUBPRIME | 580–619 | HIGH | Full campaign + warnings |
| DEEP-SUBPRIME | <580 | CRITICAL | Compliance short-circuits to REVIEW, `human_review_required: true` |

---

## RAG Documents

| File | Content | Used by |
|---|---|---|
| `politicas_credito.txt` | Loan eligibility, rate bands, compliance rules | Risk Analyst + Compliance |
| `reglamento_scoring.txt` | Segment thresholds, DTI calculation, scoring rules | Risk Analyst |
| `catalogo_productos.txt` | Product catalog, messaging tone by segment | Campaign Generator |

---

> **Disclaimer:** This system is for demonstration purposes. Final credit decisions require human review by a licensed underwriting team. All customer data must comply with applicable data protection regulations.
