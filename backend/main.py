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
)
from models.schemas import (
    AnalysisResponse,
    BatchRequest,
    BatchResponse,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
