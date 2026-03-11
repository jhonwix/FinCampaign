"""
FinCampaign Coordinator — Deterministic Pipeline Orchestrator

Enforces: Risk Analysis → Campaign Generation → Compliance Check
Compliance is NEVER skipped. Results are always persisted to GCS.
"""

import asyncio
import json
import time
from datetime import datetime

from google.cloud import storage as gcs_storage
from google.oauth2 import service_account

from agents.campaign_generator import campaign_generator_agent
from agents.compliance_checker import compliance_checker_agent
from agents.risk_analyst import risk_analyst_agent
from config import settings
from models.schemas import (
    AnalysisResponse,
    Campaign,
    ComplianceResult,
    RiskAssessment,
    generate_request_id,
)

_INELIGIBLE_CAMPAIGN = {
    "product_name": "N/A",
    "campaign_message": (
        "Actualmente no calificas para los productos disponibles. "
        "Te recomendamos trabajar en tu historial crediticio y "
        "contactarnos nuevamente en 6 meses para una nueva evaluación."
    ),
    "key_benefits": ["Asesoría gratuita de crédito disponible"],
    "cta": "Habla con un asesor financiero",
    "channel": "Teléfono",
    "rates": "N/A",
}


class FinCampaignOrchestrator:
    """
    Central coordinator for the multi-agent credit campaign pipeline.

    Enforces the strict sequence:
      1. Risk Analysis      (always runs)
      2. Campaign Generation (skipped for ineligible customers)
      3. Compliance Check   (always runs, never skippable)
      4. GCS Storage        (always runs)
    """

    def __init__(self) -> None:
        self._gcs_client: gcs_storage.Client | None = None

    @property
    def gcs_client(self) -> gcs_storage.Client:
        if self._gcs_client is None:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.service_account_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                self._gcs_client = gcs_storage.Client(
                    project=settings.google_cloud_project,
                    credentials=credentials,
                )
            except Exception:
                self._gcs_client = gcs_storage.Client(project=settings.google_cloud_project)
        return self._gcs_client

    async def analyze_customer(self, customer_profile: dict) -> AnalysisResponse:
        """
        Run the full pipeline for a single customer.

        Args:
            customer_profile: Dict matching CustomerProfile schema.

        Returns:
            AnalysisResponse with all three agent outputs and GCS storage URI.
        """
        start_time = time.time()
        request_id = generate_request_id()

        # Step 1: Risk Analysis
        risk_data = await risk_analyst_agent.analyze(customer_profile)
        risk_assessment = RiskAssessment(**risk_data)

        # Step 2: Campaign Generation (skipped if ineligible)
        if not risk_assessment.eligible_for_credit:
            campaign_data = _INELIGIBLE_CAMPAIGN
        else:
            campaign_data = await campaign_generator_agent.generate(
                customer_profile, risk_data
            )
        campaign = Campaign(**campaign_data)

        # Step 3: Compliance Check — mandatory, no exceptions
        compliance_data = await compliance_checker_agent.check(
            customer_profile, risk_data, campaign_data
        )
        compliance = ComplianceResult(**compliance_data)

        # Step 4: Persist to GCS
        processing_ms = int((time.time() - start_time) * 1000)
        stored_at = await self._store_result(
            request_id=request_id,
            customer_profile=customer_profile,
            risk_assessment=risk_data,
            campaign=campaign_data,
            compliance=compliance_data,
            processing_ms=processing_ms,
        )

        return AnalysisResponse(
            request_id=request_id,
            customer_name=customer_profile.get("name", "Unknown"),
            risk_assessment=risk_assessment,
            campaign=campaign,
            compliance=compliance,
            stored_at=stored_at,
            processing_time_ms=processing_ms,
        )

    async def analyze_batch(
        self, customers: list[dict], batch_id: str
    ) -> dict:
        """
        Process multiple customers with controlled concurrency.
        Semaphore prevents Gemini API quota exhaustion.

        Args:
            customers: List of customer profile dicts.
            batch_id: Identifier for this batch run.

        Returns:
            Summary dict with results, errors, and GCS URI.
        """
        semaphore = asyncio.Semaphore(5)
        results: list[AnalysisResponse] = []
        errors: list[dict] = []

        async def _bounded_analyze(customer: dict):
            async with semaphore:
                try:
                    return await self.analyze_customer(customer), None
                except Exception as exc:
                    return None, {
                        "customer": customer.get("name"),
                        "error": str(exc),
                    }

        raw = await asyncio.gather(
            *[_bounded_analyze(c) for c in customers],
            return_exceptions=False,
        )

        for result, error in raw:
            if error:
                errors.append(error)
            else:
                results.append(result)

        stored_at = await self._store_batch_summary(batch_id, results, errors)

        return {
            "batch_id": batch_id,
            "total_customers": len(customers),
            "processed": len(results),
            "results": results,
            "errors": errors,
            "stored_at": stored_at,
        }

    async def get_result(self, request_id: str) -> dict:
        """Retrieve a stored analysis result from GCS by request_id."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._find_and_read(request_id)
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _store_result(
        self,
        request_id: str,
        customer_profile: dict,
        risk_assessment: dict,
        campaign: dict,
        compliance: dict,
        processing_ms: int,
    ) -> str:
        """
        Persist analysis result to GCS.
        Path: results/{YYYY}/{MM}/{DD}/{request_id}.json
        """
        now = datetime.utcnow()
        blob_name = (
            f"results/{now.year}/{now.month:02d}/{now.day:02d}"
            f"/{request_id}.json"
        )

        # Store profile with reduced PII (scores and ratios only)
        payload = {
            "request_id": request_id,
            "timestamp": now.isoformat() + "Z",
            "customer_name": customer_profile.get("name"),
            "customer_profile": {
                "credit_score": customer_profile.get("credit_score"),
                "monthly_income": customer_profile.get("monthly_income"),
                "monthly_debt": customer_profile.get("monthly_debt"),
                "late_payments": customer_profile.get("late_payments"),
            },
            "risk_assessment": risk_assessment,
            "campaign": campaign,
            "compliance": compliance,
            "processing_ms": processing_ms,
        }

        content = json.dumps(payload, ensure_ascii=False, indent=2)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._write_gcs(blob_name, content)
        )

    async def _store_batch_summary(
        self,
        batch_id: str,
        results: list[AnalysisResponse],
        errors: list[dict],
    ) -> str:
        now = datetime.utcnow()
        blob_name = (
            f"batches/{now.year}/{now.month:02d}/{now.day:02d}"
            f"/{batch_id}.json"
        )
        summary = {
            "batch_id": batch_id,
            "timestamp": now.isoformat() + "Z",
            "processed": len(results),
            "error_count": len(errors),
            "result_ids": [r.request_id for r in results],
        }
        content = json.dumps(summary, indent=2)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._write_gcs(blob_name, content)
        )

    def _write_gcs(self, blob_name: str, content: str) -> str:
        """Synchronous GCS write — run via run_in_executor."""
        bucket = self.gcs_client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="application/json")
        return f"gs://{settings.gcs_bucket_name}/{blob_name}"

    def _find_and_read(self, request_id: str) -> dict:
        """Search GCS results/ prefix for a file containing request_id."""
        bucket = self.gcs_client.bucket(settings.gcs_bucket_name)
        for blob in bucket.list_blobs(prefix="results/"):
            if request_id in blob.name:
                return json.loads(blob.download_as_text())
        raise FileNotFoundError(f"Result not found: {request_id}")


orchestrator = FinCampaignOrchestrator()
