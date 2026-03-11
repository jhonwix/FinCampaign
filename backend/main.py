"""
FinCampaign RAG Agent — FastAPI Backend
"""

import asyncio
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from agents.orchestrator import orchestrator
from config import settings
from db.connection import get_pool, close_pool
from db.queries import (
    get_customer_by_id,
    list_customers,
    save_campaign_result,
    get_results_by_customer,
    create_campaign,
    get_campaign_by_id,
    list_campaigns,
    update_campaign_status,
    update_campaign_stats,
    get_campaign_results,
)
from models.schemas import (
    AnalysisResponse,
    BatchRequest,
    BatchResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignRunResponse,
    CustomerProfile,
    DocumentListResponse,
    HealthResponse,
)
from rag.indexer import index_local_documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[FinCampaign] Starting — project: {settings.google_cloud_project}")
    print(f"[FinCampaign] Datastore: {settings.vertex_ai_datastore_id}")
    # Initialize PostgreSQL pool
    try:
        await get_pool()
        print(f"[FinCampaign] PostgreSQL connected — db: {settings.postgres_db}")
    except Exception as e:
        print(f"[FinCampaign] PostgreSQL unavailable: {e}")
    yield
    await close_pool()
    print("[FinCampaign] Shutting down")


app = FastAPI(
    title="FinCampaign RAG Agent API",
    description="Multi-agent credit campaign system powered by Vertex AI Search + Gemini",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
        services={
            "vertex_ai": "configured",
            "discovery_engine": "configured",
            "gcs": "configured",
        },
    )


# ── Single Analysis ────────────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_customer(customer: CustomerProfile):
    """Run the full 3-agent pipeline for a single customer."""
    try:
        return await orchestrator.analyze_customer(customer.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


# ── Batch Processing ───────────────────────────────────────────────────────────

@app.post("/api/batch", response_model=BatchResponse)
async def process_batch(batch: BatchRequest):
    """
    Process up to 100 customers concurrently (semaphore-controlled, max 5 parallel).
    """
    try:
        result = await orchestrator.analyze_batch(
            customers=[c.model_dump() for c in batch.customers],
            batch_id=batch.batch_id,
        )
        return BatchResponse(
            batch_id=result["batch_id"],
            total_customers=result["total_customers"],
            processed=result["processed"],
            results=result["results"],
            errors=result["errors"],
            stored_at=result["stored_at"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch failed: {exc}") from exc


# ── Result Retrieval ───────────────────────────────────────────────────────────

@app.get("/api/results/{request_id}")
async def get_result(request_id: str):
    """Retrieve a stored analysis result from GCS by request_id."""
    try:
        return await orchestrator.get_result(request_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Result {request_id} not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── PostgreSQL Integration ─────────────────────────────────────────────────────

@app.get("/api/customers")
async def list_customers_endpoint(limit: int = 100, offset: int = 0):
    """List all customers from PostgreSQL."""
    try:
        customers = await list_customers(limit=limit, offset=offset)
        # Convert datetime to string for JSON serialization
        for c in customers:
            if c.get("created_at"):
                c["created_at"] = c["created_at"].isoformat()
        return {"customers": customers, "total": len(customers)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


@app.post("/api/analyze/db/{customer_id}", response_model=AnalysisResponse)
async def analyze_customer_from_db(customer_id: int):
    """
    Fetch a customer from PostgreSQL, run the full 3-agent pipeline,
    and save the result to both GCS and the campaign_results table.
    """
    # Fetch customer from DB
    customer = await get_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    # Convert Decimal/datetime fields for the pipeline
    profile = {
        "name": customer["name"],
        "age": customer["age"],
        "monthly_income": float(customer["monthly_income"]),
        "monthly_debt": float(customer["monthly_debt"]),
        "credit_score": customer["credit_score"],
        "late_payments": customer["late_payments"],
        "credit_utilization": float(customer["credit_utilization"]),
        "products_of_interest": customer["products_of_interest"],
    }

    try:
        result = await orchestrator.analyze_customer(profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    # Save result to PostgreSQL
    try:
        await save_campaign_result(
            customer_id=customer_id,
            request_id=result.request_id,
            risk_assessment=result.risk_assessment.model_dump(),
            campaign=result.campaign.model_dump(),
            compliance=result.compliance.model_dump(),
            gcs_path=result.stored_at,
            processing_ms=result.processing_time_ms or 0,
        )
    except Exception as exc:
        # Don't fail the response if DB save fails — result is already in GCS
        print(f"[DB] Failed to save result for customer {customer_id}: {exc}")

    return result


@app.get("/api/customers/{customer_id}/results")
async def get_customer_results(customer_id: int):
    """List all campaign results for a customer from PostgreSQL."""
    try:
        results = await get_results_by_customer(customer_id)
        for r in results:
            if r.get("processed_at"):
                r["processed_at"] = r["processed_at"].isoformat()
        return {"customer_id": customer_id, "results": results, "total": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


# ── RAG Document Management ────────────────────────────────────────────────────

@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents():
    """List documents currently indexed in the Vertex AI Search datastore."""
    from google.cloud import discoveryengine_v1 as discoveryengine

    def _list():
        client = discoveryengine.DocumentServiceClient()
        parent = (
            f"projects/{settings.google_cloud_project}"
            f"/locations/global/collections/default_collection"
            f"/dataStores/{settings.vertex_ai_datastore_id}/branches/default_branch"
        )
        return list(client.list_documents(parent=parent, page_size=100))

    loop = asyncio.get_running_loop()
    try:
        documents = await loop.run_in_executor(None, _list)
        return DocumentListResponse(
            documents=[
                {
                    "name": doc.name.split("/")[-1],
                    "size_bytes": None,
                    "content_type": "text/plain",
                    "updated": None,
                }
                for doc in documents
            ],
            datastore_id=settings.vertex_ai_datastore_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {exc}"
        ) from exc


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a new .txt or .pdf document to the RAG datastore."""
    allowed = {"text/plain", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: {allowed}",
        )

    suffix = f"_{file.filename}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: index_local_documents(os.path.dirname(tmp_path)),
        )
        return {"message": "Document uploaded and indexed", "details": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
    finally:
        os.unlink(tmp_path)


# ── Campaign Endpoints ─────────────────────────────────────────────────────────

# Segment label → credit score range mapping
_SEGMENT_RANGES: dict[str, tuple[int, int]] = {
    "SUPER-PRIME":  (740, 850),
    "PRIME":        (670, 739),
    "NEAR-PRIME":   (620, 669),
    "SUBPRIME":     (580, 619),
    "DEEP-SUBPRIME":(300, 579),
}


def _campaign_row_to_response(row: dict) -> dict:
    """Serialize asyncpg row to CampaignResponse-compatible dict."""
    import json as _json
    r = dict(row)
    # JSONB comes back as a string from asyncpg in some versions
    if isinstance(r.get("target_segments"), str):
        r["target_segments"] = _json.loads(r["target_segments"])
    if r.get("created_at"):
        r["created_at"] = r["created_at"].isoformat()
    if r.get("last_run_at"):
        r["last_run_at"] = r["last_run_at"].isoformat()
    # Cast Decimal fields to float so Pydantic is happy
    for field in ("min_monthly_income", "max_dti", "max_credit_utilization",
                  "rate_min", "rate_max", "max_amount"):
        if r.get(field) is not None:
            r[field] = float(r[field])
    return r


@app.get("/api/campaigns", response_model=list[CampaignResponse])
async def list_campaigns_endpoint(limit: int = 100, offset: int = 0):
    """List all campaigns."""
    try:
        rows = await list_campaigns(limit=limit, offset=offset)
        return [_campaign_row_to_response(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


@app.post("/api/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign_endpoint(body: CampaignCreate):
    """Create a new campaign definition."""
    try:
        campaign_id = await create_campaign(body.model_dump())
        row = await get_campaign_by_id(campaign_id)
        return _campaign_row_to_response(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


@app.get("/api/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign_endpoint(campaign_id: int):
    """Get a campaign by id (includes qualifying_count in the response)."""
    row = await get_campaign_by_id(campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return _campaign_row_to_response(row)


@app.post("/api/campaigns/{campaign_id}/run", response_model=CampaignRunResponse)
async def run_campaign(campaign_id: int):
    """
    Execute the 3-agent pipeline against all qualifying customers.

    Filters applied locally:
      - credit_score BETWEEN min/max
      - monthly_income >= min
      - (monthly_debt/monthly_income*100) <= max_dti
      - late_payments <= max
      - credit_utilization <= max
      - if target_segments not empty → only matching segments
    """
    campaign = await get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    await update_campaign_status(campaign_id, "RUNNING")

    try:
        all_customers = await list_customers(limit=10000)

        # Deserialize target_segments
        import json as _json
        segments = campaign["target_segments"]
        if isinstance(segments, str):
            segments = _json.loads(segments)

        min_score    = int(campaign["min_credit_score"])
        max_score    = int(campaign["max_credit_score"])
        min_income   = float(campaign["min_monthly_income"])
        max_dti      = float(campaign["max_dti"])
        max_late     = int(campaign["max_late_payments"])
        max_util     = float(campaign["max_credit_utilization"])

        qualifying = []
        for c in all_customers:
            score  = int(c["credit_score"])
            income = float(c["monthly_income"])
            debt   = float(c["monthly_debt"])
            dti    = (debt / income * 100) if income > 0 else 0
            late   = int(c["late_payments"])
            util   = float(c["credit_utilization"])

            if not (min_score <= score <= max_score):
                continue
            if income < min_income:
                continue
            if dti > max_dti:
                continue
            if late > max_late:
                continue
            if util > max_util:
                continue

            # Segment filter
            if segments:
                seg = next(
                    (s for s, (lo, hi) in _SEGMENT_RANGES.items() if lo <= score <= hi),
                    None,
                )
                if seg not in segments:
                    continue

            qualifying.append(c)

        # Override products_of_interest with campaign product_name
        product_override = campaign["product_name"]
        profiles = []
        for c in qualifying:
            p = {
                "name":                c["name"],
                "age":                 c["age"],
                "monthly_income":      float(c["monthly_income"]),
                "monthly_debt":        float(c["monthly_debt"]),
                "credit_score":        c["credit_score"],
                "late_payments":       c["late_payments"],
                "credit_utilization":  float(c["credit_utilization"]),
                "products_of_interest": product_override or c["products_of_interest"],
            }
            profiles.append(p)

        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        batch_id = f"CAMP-{campaign_id}-{ts}"

        batch = await orchestrator.analyze_batch(profiles, batch_id=batch_id)

        results: list = batch.get("results", [])
        errors: list  = batch.get("errors", [])

        # Save each result to campaign_results
        approved = 0
        review   = 0
        for i, res in enumerate(results):
            customer_id = qualifying[i]["id"]
            verdict = res.compliance.overall_verdict if hasattr(res, "compliance") else ""
            if verdict in ("APPROVED", "APPROVED_WITH_WARNINGS"):
                approved += 1
            if getattr(getattr(res, "compliance", None), "human_review_required", False):
                review += 1
            try:
                await save_campaign_result(
                    customer_id=customer_id,
                    request_id=res.request_id,
                    risk_assessment=res.risk_assessment.model_dump(),
                    campaign=res.campaign.model_dump(),
                    compliance=res.compliance.model_dump(),
                    gcs_path=res.stored_at,
                    processing_ms=res.processing_time_ms or 0,
                    campaign_id=campaign_id,
                )
            except Exception as exc:
                print(f"[Campaign] Failed to save result for customer {customer_id}: {exc}")

        targeted   = len(qualifying)
        processed  = len(results)

        await update_campaign_stats(campaign_id, targeted, processed, approved, review)
        await update_campaign_status(campaign_id, "COMPLETED")

        return CampaignRunResponse(
            campaign_id=campaign_id,
            batch_id=batch_id,
            total_targeted=targeted,
            total_processed=processed,
            total_approved=approved,
            total_review=review,
            results=results,
            errors=errors,
        )

    except Exception as exc:
        # Reset status so the campaign can be re-run
        try:
            await update_campaign_status(campaign_id, "DRAFT")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Campaign run failed: {exc}") from exc


@app.get("/api/campaigns/{campaign_id}/results")
async def get_campaign_results_endpoint(campaign_id: int):
    """Return campaign result history."""
    campaign = await get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    try:
        rows = await get_campaign_results(campaign_id)
        for r in rows:
            if r.get("processed_at"):
                r["processed_at"] = r["processed_at"].isoformat()
        return {"campaign_id": campaign_id, "results": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
