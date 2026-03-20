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
from db.lookups import load_lookup_cache, get_all_lookups
from db.queries import (
    get_customer_by_id,
    list_customers,
    count_customers,
    save_campaign_result,
    get_results_by_customer,
    create_campaign,
    get_campaign_by_id,
    list_campaigns,
    update_campaign_status,
    update_campaign_stats,
    get_campaign_results,
    delete_campaign_results,
    bulk_insert_customers,
)
from models.schemas import (
    AnalysisResponse,
    BatchRequest,
    BatchResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignRunResponse,
    CampaignRunStarted,
    CampaignRunStatus,
    CustomerProfile,
    DocumentListResponse,
    HealthResponse,
    ReviewAction,
    ReviewResponse,
)
from db.queries import update_result_review
from rag.indexer import index_local_documents
from rag.retriever import clear_rag_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[FinCampaign] Starting — project: {settings.google_cloud_project}")
    print(f"[FinCampaign] Datastore: {settings.vertex_ai_datastore_id}")
    # Initialize PostgreSQL pool
    try:
        await get_pool()
        print(f"[FinCampaign] PostgreSQL connected — db: {settings.postgres_db}")
        await load_lookup_cache()
        print("[FinCampaign] Lookup cache loaded.")
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

@app.get("/api/lookups")
async def get_lookups_endpoint():
    """Return all active lookup values grouped by category (served from in-memory cache)."""
    return get_all_lookups()


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
        customers, total = await asyncio.gather(
            list_customers(limit=limit, offset=offset),
            count_customers(),
        )
        for c in customers:
            if c.get("created_at"):
                c["created_at"] = c["created_at"].isoformat()
        return {"customers": customers, "total": total}
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
        "existing_products": customer.get("existing_products") or "",
        "customer_id": customer_id,  # enables history tool call in orchestrator
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
            pipeline_route=result.pipeline_route,
            pipeline_confidence=result.pipeline_confidence,
            correction_attempts=result.correction_attempts,
        )
    except Exception as exc:
        # Don't fail the response if DB save fails — result is already in GCS
        print(f"[DB] Failed to save result for customer {customer_id}: {exc}")

    return result


@app.post("/api/customers/import")
async def import_customers_csv(file: UploadFile = File(...)):
    """
    Bulk-import customers from a UTF-8 CSV file.

    Required columns: name, age, monthly_income, monthly_debt,
                      credit_score, late_payments, credit_utilization,
                      products_of_interest

    Returns a summary: total_rows, imported, duplicates,
                       validation_errors, db_errors.
    """
    import csv as _csv
    import io as _io

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = _csv.DictReader(_io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    required = {
        "id_number", "name", "age", "monthly_income", "monthly_debt",
        "credit_score", "late_payments", "credit_utilization",
        "products_of_interest",
    }
    missing = required - fieldnames
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {sorted(missing)}",
        )

    valid: list[dict] = []
    validation_errors: list[dict] = []

    for line_no, row in enumerate(reader, start=2):
        errs: list[str] = []
        try:
            id_number = str(row.get("id_number") or "").strip()
            name = (row.get("name") or "").strip()
            age = int(row.get("age", 0))
            monthly_income = float(row.get("monthly_income", 0))
            monthly_debt = float(row.get("monthly_debt", 0))
            credit_score = int(row.get("credit_score", 0))
            late_payments = int(row.get("late_payments", 0))
            credit_utilization = float(row.get("credit_utilization", 0))
            products_of_interest = (row.get("products_of_interest") or "").strip()

            if not id_number:             errs.append("id_number: requerido")
            elif len(id_number) < 4:      errs.append("id_number: mínimo 4 caracteres")
            elif len(id_number) > 20:     errs.append("id_number: máximo 20 caracteres")
            if len(name) < 2:             errs.append("name: mínimo 2 caracteres")
            if not (18 <= age <= 100):    errs.append("age: debe estar entre 18 y 100")
            if monthly_income <= 0:       errs.append("monthly_income: debe ser > 0")
            if monthly_debt < 0:          errs.append("monthly_debt: no puede ser negativo")
            if not (300 <= credit_score <= 850): errs.append("credit_score: rango válido 300-850")
            if late_payments < 0:         errs.append("late_payments: no puede ser negativo")
            if not (0 <= credit_utilization <= 100): errs.append("credit_utilization: rango 0-100")
            if len(products_of_interest) < 3: errs.append("products_of_interest: muy corto")

            if errs:
                validation_errors.append({"row": line_no, "name": name, "errors": errs})
                continue

            valid.append({
                "id_number": id_number,
                "name": name, "age": age,
                "monthly_income": monthly_income, "monthly_debt": monthly_debt,
                "credit_score": credit_score, "late_payments": late_payments,
                "credit_utilization": credit_utilization,
                "products_of_interest": products_of_interest,
                "existing_products": (row.get("existing_products") or "").strip(),
            })
        except (ValueError, TypeError) as exc:
            validation_errors.append({"row": line_no, "name": row.get("name", "?"), "errors": [str(exc)]})

    total_rows = len(valid) + len(validation_errors)

    if not valid:
        return {
            "total_rows": total_rows,
            "imported": 0, "duplicates": 0,
            "validation_errors": validation_errors, "db_errors": [],
        }

    try:
        result = await bulk_insert_customers(valid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB import failed: {exc}") from exc

    return {
        "total_rows": total_rows,
        "imported": result["inserted"],
        "duplicates": result["duplicates"],
        "validation_errors": validation_errors,
        "db_errors": result["errors"],
    }


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

# Campaign type → keyword to match in existing_products
_PRODUCT_KEYWORDS: dict[str, str] = {
    "VEHICULOS":   "vehiculo",
    "HIPOTECARIO": "hipotecario",
    "PERSONAL":    "personal",
    "CDT":         "cdt",
    "TARJETA":     "tarjeta",
}


# ── Async job store ────────────────────────────────────────────────────────────
# Maps batch_id → job metadata. Single-process POC; not persisted across restarts.
_run_jobs: dict[str, dict] = {}


def _filter_qualifying(campaign: dict, all_customers: list[dict]) -> list[dict]:
    """Return customers that pass all campaign filter criteria."""
    import json as _json

    segments = campaign["target_segments"]
    if isinstance(segments, str):
        segments = _json.loads(segments)

    min_score = int(campaign["min_credit_score"])
    max_score = int(campaign["max_credit_score"])
    min_income = float(campaign["min_monthly_income"])
    max_dti = float(campaign["max_dti"])
    max_late = int(campaign["max_late_payments"])
    max_util = float(campaign["max_credit_utilization"])

    qualifying = []
    for c in all_customers:
        score = int(c["credit_score"])
        income = float(c["monthly_income"])
        debt = float(c["monthly_debt"])
        dti = (debt / income * 100) if income > 0 else 0
        late = int(c["late_payments"])
        util = float(c["credit_utilization"])

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

        # Intent filter based on existing_products
        intent = (campaign.get("campaign_intent") or "NEW").upper()
        keyword = _PRODUCT_KEYWORDS.get(campaign["type"], "").lower()
        if keyword:
            existing = (c.get("existing_products") or "").lower()
            if intent == "NEW" and keyword in existing:
                continue
            elif intent == "RENEWAL" and keyword not in existing:
                continue

        qualifying.append(c)

    return qualifying


def _build_profiles(campaign: dict, qualifying: list[dict]) -> list[dict]:
    """Build CustomerProfile dicts from qualifying customers + campaign constraints."""
    product_override = campaign["product_name"]
    intent = (campaign.get("campaign_intent") or "NEW").upper()
    camp_rate_min = float(campaign.get("rate_min") or 0)
    camp_rate_max = float(campaign.get("rate_max") or 0)
    camp_max_amount = float(campaign.get("max_amount") or 0)
    camp_term_months = int(campaign.get("term_months") or 0)
    camp_message_tone = campaign.get("message_tone") or ""
    camp_cta_text = campaign.get("cta_text") or ""

    profiles = []
    for c in qualifying:
        p = {
            "name": c["name"],
            "age": c["age"],
            "monthly_income": float(c["monthly_income"]),
            "monthly_debt": float(c["monthly_debt"]),
            "credit_score": c["credit_score"],
            "late_payments": c["late_payments"],
            "credit_utilization": float(c["credit_utilization"]),
            "products_of_interest": product_override or c["products_of_interest"],
            "existing_products": c.get("existing_products") or "",
            "campaign_intent": intent,
            "customer_id": c["id"],
            "campaign_id": campaign.get("id"),
            "rate_min": camp_rate_min if camp_rate_min > 0 else None,
            "rate_max": camp_rate_max if camp_rate_max > 0 else None,
            "max_amount": camp_max_amount if camp_max_amount > 0 else None,
            "term_months": camp_term_months if camp_term_months > 0 else None,
            "message_tone": camp_message_tone or None,
            "cta_text": camp_cta_text or None,
        }
        profiles.append(p)
    return profiles


async def _execute_campaign_run(
    campaign_id: int,
    campaign: dict,
    batch_id: str,
) -> None:
    """
    Background coroutine: run the full batch pipeline and write results to DB.
    Updates _run_jobs[batch_id] throughout execution.
    Launched via asyncio.create_task() — never awaited directly by the HTTP handler.
    """
    job = _run_jobs[batch_id]
    try:
        # Clear previous results so each run produces a single clean report
        deleted = await delete_campaign_results(campaign_id)
        if deleted:
            print(f"[Campaign] Cleared {deleted} previous results for campaign {campaign_id}")

        clear_rag_cache()  # A1: reset per-batch RAG cache before processing begins

        all_customers = await list_customers(limit=10000)
        qualifying = _filter_qualifying(campaign, all_customers)
        profiles = _build_profiles(campaign, qualifying)
        targeted = len(qualifying)

        # Process customers with progressive updates — use asyncio.as_completed so
        # _run_jobs is updated after every individual customer, not only at the end.
        # Semaphore(10): doubled from 5 — safe with persistent httpx + RAG clients (A4)
        semaphore = asyncio.Semaphore(10)

        async def _process_one(profile: dict):
            async with semaphore:
                try:
                    return await orchestrator.analyze_customer(profile), None
                except Exception as exc:
                    return None, {"customer": profile.get("name"), "error": str(exc)}

        tasks = [asyncio.create_task(_process_one(p)) for p in profiles]

        approved = 0
        review = 0
        processed = 0
        errors: list = []

        for coro in asyncio.as_completed(tasks):
            res, err = await coro
            if err:
                errors.append(err)
            else:
                customer_id = res.customer_id
                if customer_id is None:
                    print(f"[Campaign] Warning: no customer_id on result {res.request_id}, skipping save")
                else:
                    verdict = res.compliance.overall_verdict
                    human_review = res.compliance.human_review_required
                    if human_review:
                        review += 1
                    elif verdict in ("APPROVED", "APPROVED_WITH_WARNINGS"):
                        approved += 1
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
                            pipeline_route=res.pipeline_route,
                            pipeline_confidence=res.pipeline_confidence,
                            correction_attempts=res.correction_attempts,
                        )
                    except Exception as exc:
                        print(f"[Campaign] Failed to save result for customer {customer_id}: {exc}")

            processed += 1
            # Update progress visible to the polling endpoint after every customer
            job.update({
                "total_processed": processed,
                "total_approved": approved,
                "total_review": review,
            })

        await update_campaign_stats(campaign_id, targeted, processed, approved, review)
        await update_campaign_status(campaign_id, "COMPLETED")

        job.update({
            "status": "COMPLETED",
            "total_processed": processed,
            "total_approved": approved,
            "total_review": review,
            "completed_at": datetime.utcnow().isoformat() + "Z",
        })
        print(f"[Campaign] batch {batch_id} COMPLETED — {processed}/{targeted} processed")

    except Exception as exc:
        try:
            await update_campaign_status(campaign_id, "FAILED")
        except Exception:
            pass
        job.update({
            "status": "FAILED",
            "error_message": str(exc),
            "completed_at": datetime.utcnow().isoformat() + "Z",
        })
        print(f"[Campaign] batch {batch_id} FAILED: {exc}")


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


@app.post("/api/campaigns/{campaign_id}/run", response_model=CampaignRunStarted)
async def run_campaign(campaign_id: int):
    """
    Start the batch pipeline asynchronously.

    Returns immediately with { batch_id, status: "RUNNING", campaign_id, total_targeted }.
    Poll GET /api/campaigns/{campaign_id}/run-status?batch_id=... for completion.
    """
    campaign = await get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    if campaign["status"] == "RUNNING":
        raise HTTPException(
            status_code=409,
            detail="Campaign is already running. Poll /run-status for progress.",
        )

    # Compute qualifying count now so the caller knows total_targeted immediately
    all_customers = await list_customers(limit=10000)
    qualifying = _filter_qualifying(campaign, all_customers)

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    batch_id = f"CAMP-{campaign_id}-{ts}"

    # Register the job BEFORE launching the task (avoids a race with the status poll)
    _run_jobs[batch_id] = {
        "batch_id": batch_id,
        "campaign_id": campaign_id,
        "status": "RUNNING",
        "total_targeted": len(qualifying),
        "total_processed": 0,
        "total_approved": 0,
        "total_review": 0,
        "error_message": None,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "completed_at": None,
    }

    await update_campaign_status(campaign_id, "RUNNING")

    # Fire and forget — does NOT block the HTTP response
    asyncio.create_task(_execute_campaign_run(campaign_id, campaign, batch_id))

    return CampaignRunStarted(
        batch_id=batch_id,
        status="RUNNING",
        campaign_id=campaign_id,
        total_targeted=len(qualifying),
    )


@app.get("/api/campaigns/{campaign_id}/run-status", response_model=CampaignRunStatus)
async def get_run_status(campaign_id: int, batch_id: str):
    """
    Poll for batch job progress.
    Returns current status from the in-memory job store.
    Once status = COMPLETED, invalidate campaign and results queries.
    """
    job = _run_jobs.get(batch_id)
    if job is None:
        # Fallback: job not found (server restarted mid-run) — read best-effort from DB
        campaign = await get_campaign_by_id(campaign_id)
        db_status = campaign["status"] if campaign else "FAILED"
        return CampaignRunStatus(
            batch_id=batch_id,
            campaign_id=campaign_id,
            status=db_status,
            total_targeted=int(campaign.get("total_targeted") or 0) if campaign else 0,
            total_processed=int(campaign.get("total_processed") or 0) if campaign else 0,
            total_approved=int(campaign.get("total_approved") or 0) if campaign else 0,
            total_review=int(campaign.get("total_review") or 0) if campaign else 0,
            error_message="Job state lost (server restart). Check campaign status.",
            started_at=campaign.get("last_run_at") or datetime.utcnow().isoformat() + "Z" if campaign else "",
            completed_at=None,
        )
    return CampaignRunStatus(**job)


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
            if r.get("reviewed_at"):
                r["reviewed_at"] = r["reviewed_at"].isoformat()
        return {"campaign_id": campaign_id, "results": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


@app.patch(
    "/api/campaigns/{campaign_id}/results/{result_id}/review",
    response_model=ReviewResponse,
)
async def review_campaign_result(
    campaign_id: int,
    result_id: int,
    body: ReviewAction,
):
    """
    Approve or reject a campaign result that has human_review_required=True.

    action: "APPROVE" or "REJECT"
    note:   optional analyst note (stored in review_note)

    Idempotent: re-reviewing the same result overwrites the previous decision.
    """
    campaign = await get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    review_status = "APPROVED" if body.action == "APPROVE" else "REJECTED"

    updated = await update_result_review(
        result_id=result_id,
        review_status=review_status,
        review_note=body.note,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Result {result_id} not found in campaign {campaign_id}",
        )

    return ReviewResponse(
        result_id=updated["id"],
        review_status=updated["review_status"],
        review_note=updated["review_note"] or "",
        reviewed_at=updated["reviewed_at"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
