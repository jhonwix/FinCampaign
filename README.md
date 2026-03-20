# FinCampaign — Multi-Agent Credit Campaign System

A production-grade multi-agent AI system for personalized credit campaign generation, built on **Google ADK 1.27.2**, **Vertex AI**, and **Gemini 2.5 Flash Lite**.

The system receives a customer credit profile, routes it through a hierarchy of 13 specialized AI agents, retrieves credit policies via RAG, and generates a compliance-validated personalized campaign — with automatic self-correction, confidence scoring, and full explainability.

---

## Agentic Architecture

```
                    FinCampaignPipeline (SequentialAgent)
                              │
                    ┌─────────┴──────────┐
              RiskAnalystAgent      FinCampaignOrchestrator
              (segment + DTI)        (dynamic routing)
                                          │
                    ┌─────────────────────┼──────────────────────┐
                    │                     │                       │
            EducationalAgent       PremiumPipeline         CorrectionLoop
            (DEEP-SUBPRIME)        (SUPER-PRIME)         (LoopAgent, ≤3x)
            rehabilitation         fast-track               │         │
            plan, no offer         no retry             CampaignVariants  ComplianceGate
                                   PremiumCampaign      (ParallelAgent)   (exit_loop)
                                   PremiumCompliance    3 tones A/B/C
                                                        CampaignEvaluator
                                                        (LLM-as-Judge)
                                                              │
                                                       ConditionalAgent
                                                       (SUBPRIME ineligible)
                                                       gap analysis
                                          │
                              ExplainabilityAgent
                              (customer-facing explanation)
```

**13 agents** — LlmAgent + SequentialAgent + LoopAgent + ParallelAgent

### Pipeline Routes

| Route | Segment | Behavior |
|-------|---------|----------|
| **EDUCATIONAL** | DEEP-SUBPRIME | Financial rehabilitation plan, no credit offer |
| **PREMIUM_FAST** | SUPER-PRIME | Single-pass generation + compliance, no retry |
| **CONDITIONAL** | SUBPRIME (ineligible) | Gap analysis — "reduce DTI by X to qualify" |
| **STANDARD** | PRIME / NEAR-PRIME / eligible SUBPRIME | Full loop with auto-correction |

---

## Key Agentic Features

| Feature | Implementation |
|---------|---------------|
| **Dynamic routing** | Orchestrator reads risk segment → transfers to correct pipeline |
| **Auto-correction loop** | ComplianceGate rejects → CampaignGenerator rewrites (≤3x) |
| **Parallel A/B/C variants** | ParallelAgent generates 3 tones simultaneously |
| **LLM-as-Judge** | CampaignEvaluator selects best variant before compliance |
| **Persistent memory** | Per-customer interaction log + aggregated memory card (PostgreSQL) |
| **RAG pre-injection** | KB context injected at instruction-build time — no tool call latency |
| **Confidence scoring** | Risk + compliance self-report confidence → auto-escalate at < 0.65 |
| **Human-in-the-loop** | `PATCH /campaigns/:id/results/:rid/review` + ReviewActions UI |
| **Explainability** | ExplainabilityAgent generates customer-facing justification in Spanish |
| **Eval suite** | `adk eval` — 7 cases across 2 evalsets, response_match_score ≥ 0.4 |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Agent Framework** | Google ADK | 1.27.2 |
| **LLM** | Gemini 2.5 Flash Lite (Vertex AI) | — |
| **RAG** | Vertex AI Search (Discovery Engine) | — |
| **Auth** | Self-signed JWT (google-auth) | 2.49.1 |
| **Backend** | FastAPI + asyncpg | 0.135.1 / 0.31.0 |
| **ASGI Server** | Uvicorn | 0.42.0 |
| **Frontend** | React + TypeScript + Vite | 19.2 / 5.9.3 / 7.3.1 |
| **Styling** | Tailwind CSS | 4.2.1 |
| **State Management** | TanStack Query | 5.90.21 |
| **Database** | PostgreSQL (asyncpg) | — |
| **Storage** | Google Cloud Storage | — |
| **Runtime** | Python 3.11 / Node.js 22 | — |
| **Eval metric** | ROUGE-L (rouge_score) | 0.1.2 |

---

## Project Structure

```
FinCampaign/
├── backend/
│   ├── main.py                    FastAPI app — all REST endpoints
│   ├── agents_adk/                Google ADK multi-agent system
│   │   ├── fincampaign_pipeline.py  Root SequentialAgent
│   │   ├── orchestrator.py          Dynamic routing orchestrator
│   │   ├── risk_analyst.py          Segment + DTI + eligibility
│   │   ├── premium_pipeline.py      SUPER-PRIME fast-track
│   │   ├── correction_loop.py       LoopAgent with auto-correction
│   │   ├── campaign_generator.py    Campaign generation
│   │   ├── campaign_variants.py     ParallelAgent — 3 tones
│   │   ├── campaign_evaluator.py    LLM-as-Judge
│   │   ├── compliance_gate.py       Compliance check + exit_loop
│   │   ├── conditional_agent.py     SUBPRIME gap analysis
│   │   ├── educational_agent.py     DEEP-SUBPRIME rehabilitation
│   │   ├── explainability_agent.py  Customer-facing explanation
│   │   ├── search_tool.py           RAG via Discovery Engine REST + JWT
│   │   ├── memory_service.py        Customer memory card builder
│   │   └── agent.py                 adk eval entry point
│   ├── eval_agent/                ADK eval wrapper
│   │   ├── __init__.py              importlib loader (adk eval compat)
│   │   ├── agent.py                 root_agent entry point
│   │   ├── segment_routing.evalset.json   5 routing cases
│   │   ├── compliance_gates.evalset.json  2 compliance cases
│   │   └── eval_config.json         response_match_score: 0.4
│   ├── agents/                    Legacy FastAPI agents (REST pipeline)
│   ├── db/
│   │   ├── connection.py            asyncpg pool
│   │   ├── queries.py               CRUD + memory + history functions
│   │   └── lookups.py               Lookup values (segments, channels)
│   ├── models/
│   │   └── schemas.py               Pydantic v2 schemas
│   └── tools/
│       ├── customer_history.py      Last 6 months interaction context
│       └── customer_memory.py       Memory card refresh
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx          Customer list + stats
│       │   ├── CustomerImport.tsx     CSV bulk import
│       │   ├── CreateCampaign.tsx     Campaign configuration
│       │   ├── CampaignDetail.tsx     Results + review workflow
│       │   └── ArchitecturePage.tsx   Animated BPM flow (14 steps)
│       └── api/
│           ├── client.ts
│           ├── types.ts
│           └── useLookups.ts
├── scripts/
│   ├── setup_db.py                  Create tables + seed 10 customers
│   ├── migrate_add_memory.py        customer_interactions + customer_memory
│   ├── migrate_add_pipeline_route.py campaign_results.pipeline_route
│   ├── migrate_add_confidence.py    campaign_results.pipeline_confidence
│   ├── migrate_add_review.py        review_status / review_note fields
│   ├── migrate_add_intent.py        campaign_intent field
│   └── migrate_lookup_values.py     Seed lookup tables
└── data/
    └── customers_test_100.csv       100 test customers (5 segments)
```

---

## Database Schema

```sql
customers            -- id, name, age, monthly_income, monthly_debt,
                     --   credit_score, late_payments, credit_utilization,
                     --   products_of_interest, existing_products, channel

campaigns            -- id, name, description, criteria, intent,
                     --   rate_min/max, max_amount, term_months,
                     --   message_tone, cta_text, created_at

campaign_results     -- id, campaign_id, customer_id, segment, pipeline_route,
                     --   pipeline_confidence, campaign (JSON), compliance (JSON),
                     --   explanation (JSON), correction_attempts,
                     --   review_status, review_note, reviewed_at

customer_interactions -- id, customer_id, campaign_id, segment, verdict,
                      --   dti, correction_attempts, pipeline_route, created_at

customer_memory      -- customer_id (unique), segment_trend, products_offered,
                     --   verdict_counts (JSON), dti_trend, last_updated
```

---

## Mass Campaign Workflow

```
1. Import customers  →  POST /api/customers/import  (CSV upload)
2. Create campaign   →  POST /api/campaigns          (criteria + constraints)
3. Run pipeline      →  POST /api/campaigns/:id/run  (async batch)
4. Poll status       →  GET  /api/campaigns/:id/run-status  (3s polling)
5. Review results    →  GET  /api/campaigns/:id/results
6. Human review      →  PATCH /api/campaigns/:id/results/:rid/review
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/customers` | List customers |
| `POST` | `/api/customers/import` | Bulk CSV import |
| `POST` | `/api/campaigns` | Create campaign |
| `GET` | `/api/campaigns` | List campaigns |
| `POST` | `/api/campaigns/:id/run` | Start batch pipeline (async) |
| `GET` | `/api/campaigns/:id/run-status` | Poll batch progress |
| `GET` | `/api/campaigns/:id/results` | Campaign results |
| `PATCH` | `/api/campaigns/:id/results/:rid/review` | Human review action |
| `POST` | `/api/analyze` | Single customer (ADK pipeline) |

---

## Quick Start

### Prerequisites

- Python 3.11+ / Node.js 22+
- PostgreSQL (local or remote)
- Google Cloud project with APIs enabled:
  - `discoveryengine.googleapis.com`
  - `aiplatform.googleapis.com`
  - `storage.googleapis.com`

### 1. Clone and configure

```bash
git clone https://github.com/jhonwix/FinCampaign.git
cd FinCampaign
cp .env.example .env
# Fill in .env values
```

### 2. Service account setup

```bash
gcloud iam service-accounts create fincampaign-backend \
  --display-name="FinCampaign Backend"

# Roles needed:
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/discoveryengine.editor"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud iam service-accounts keys create backend/service-account.json \
  --iam-account=fincampaign-backend@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Backend setup

```powershell
python -m venv venv
venv\Scripts\activate          # Windows PowerShell
pip install -r backend/requirements.txt
```

### 4. Database setup

```bash
python scripts/setup_db.py
python scripts/migrate_add_memory.py
python scripts/migrate_add_pipeline_route.py
python scripts/migrate_add_confidence.py
python scripts/migrate_add_review.py
python scripts/migrate_add_intent.py
python scripts/migrate_lookup_values.py
```

### 5. Start backend

```powershell
cd backend
uvicorn main:app --reload --port 8081
# API: http://localhost:8081/docs
```

### 6. Start ADK web (optional — local agent UI)

```powershell
cd backend
adk web agents_adk
# UI: http://localhost:8000
```

### 7. Start frontend

```bash
cd frontend
npm install
npm run dev
# UI: http://localhost:3000
```

---

## Running Evals

```bash
cd backend
# Route classification — 5 cases (EDUCATIONAL, PREMIUM, CONDITIONAL, STANDARD)
adk eval eval_agent eval_agent/segment_routing.evalset.json \
  --config_file_path eval_agent/eval_config.json \
  --print_detailed_results

# Compliance quality — 2 cases (approved clean, rejected deep-subprime)
adk eval eval_agent eval_agent/compliance_gates.evalset.json \
  --config_file_path eval_agent/eval_config.json \
  --print_detailed_results
```

**Current eval status: 7/7 PASSED** (response_match_score threshold: 0.4)

---

## Environment Variables

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
VERTEX_AI_LOCATION=us-central1

# Vertex AI Search
VERTEX_AI_DATASTORE_ID=fincampaign-rag-datastore

# GCS
GCS_BUCKET_NAME=your-project-id-fincampaign-results

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=fincampaign
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

## Credit Segments

| Segment | Score | DTI Max | Route |
|---------|-------|---------|-------|
| SUPER-PRIME | 750+ | 25% | PremiumPipeline |
| PRIME | 700–749 | 35% | CorrectionLoop |
| NEAR-PRIME | 650–699 | 45% | CorrectionLoop |
| SUBPRIME (eligible) | 600–649 | 48% | CorrectionLoop |
| SUBPRIME (ineligible) | 600–649 | >48% | ConditionalAgent |
| DEEP-SUBPRIME | <600 | any | EducationalAgent |

---

## RAG Knowledge Base

| Document | Content | Used by |
|----------|---------|---------|
| `politicas_credito.txt` | Rate bands, compliance rules, eligibility | Risk Analyst + Compliance |
| `reglamento_scoring.txt` | Segment thresholds, DTI rules, scoring | Risk Analyst |
| `catalogo_productos.txt` | Product catalog, tone guidelines | Campaign Generator |

RAG is implemented via **Vertex AI Search REST API** with **self-signed JWT** authentication (avoids oauth2.googleapis.com dependency). KB context is pre-injected into agent instructions at call time — no tool call round-trip.

---

> **Disclaimer:** This system is for demonstration purposes. Final credit decisions require human review by a licensed underwriting team. All customer data must comply with applicable data protection and financial regulations.
