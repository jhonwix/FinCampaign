"""
FinCampaign Coordinator — Dynamic Pipeline Orchestrator

Routes each customer through one of four specialized pipelines based on
their risk segment and eligibility, rather than forcing every customer
through the same sequence.

  EDUCATIONAL   — DEEP-SUBPRIME: financial rehabilitation plan, no credit offer
  PREMIUM_FAST  — SUPER-PRIME:   fast path, compliance checked once (no retry loop)
  CONDITIONAL   — SUBPRIME ineligible: conditional improvement offer
  STANDARD      — All other eligible customers: full pipeline with correction loop

Compliance is NEVER skipped — only the self-correction loop is shortened for
routes where retries add latency without material benefit (PREMIUM_FAST,
EDUCATIONAL).

Results are always persisted to GCS.
"""

import asyncio
import json
import time
from datetime import datetime

from google.cloud import storage as gcs_storage
from google.oauth2 import service_account

from agents.campaign_generator import campaign_generator_agent
from agents.compliance_checker import compliance_checker_agent
from agents.conditional_offer_agent import conditional_offer_agent
from agents.financial_education_agent import financial_education_agent
from agents.risk_analyst import risk_analyst_agent
from config import settings
from tools.customer_history import get_customer_history_context, summarize_history_for_log
from tools.customer_memory import get_customer_memory_card, refresh_customer_memory
from db.queries import save_customer_interaction
from models.schemas import (
    AnalysisResponse,
    Campaign,
    ComplianceResult,
    RiskAssessment,
    generate_request_id,
)

_MAX_CORRECTIONS = 2          # max campaign regeneration attempts (STANDARD route only)
_CONFIDENCE_THRESHOLD = 0.65  # below this → automatic human review escalation


def _compute_pipeline_confidence(
    risk_data: dict,
    compliance_data: dict,
    route: str,
) -> float:
    """
    Aggregate agent confidence scores and apply deterministic overrides.

    Base: minimum of risk_confidence and compliance_confidence (most conservative).
    Overrides: verdict-based caps and signal-based floor reductions.

    Args:
        risk_data:       Risk Analyst output (includes 'confidence' field).
        compliance_data: Compliance Checker output (includes 'confidence' field).
        route:           Active pipeline route.

    Returns:
        Float in [0.0, 1.0] representing overall pipeline confidence.
    """
    # EDUCATIONAL: the decision is clear (DEEP-SUBPRIME). Confidence reflects
    # the segmentation quality, not an approval decision.
    if route == "EDUCATIONAL":
        return round(float(risk_data.get("confidence", 0.90)), 2)

    # Base confidence: minimum of the two agent scores
    risk_conf = max(0.0, min(1.0, float(risk_data.get("confidence", 1.0))))
    comp_conf = max(0.0, min(1.0, float(compliance_data.get("confidence", 1.0))))
    conf = min(risk_conf, comp_conf)

    # ── Verdict-based caps ─────────────────────────────────────────────────────
    verdict = compliance_data.get("overall_verdict", "APPROVED")
    if verdict == "REJECTED":
        conf = min(conf, 0.40)
    elif verdict == "REVIEW":
        conf = min(conf, 0.65)
    elif verdict == "APPROVED_WITH_WARNINGS":
        conf = min(conf, 0.82)

    # ── Signal-based overrides ─────────────────────────────────────────────────
    # DTI near the 48% ineligibility boundary → ambiguous eligibility call
    dti = float(risk_data.get("dti", 0))
    if 43.0 <= dti <= 53.0:
        conf = min(conf, 0.72)

    # Many compliance warnings → verdict less certain
    n_warnings = len(compliance_data.get("warnings", []))
    if n_warnings >= 3:
        conf = min(conf, 0.65)
    elif n_warnings == 2:
        conf = min(conf, 0.75)

    return round(max(0.0, min(1.0, conf)), 2)


def _determine_route(risk_data: dict) -> str:
    """
    Select the pipeline route based on risk assessment output.

    Decision tree:
      DEEP-SUBPRIME              → EDUCATIONAL   (always ineligible; no credit offer)
      SUPER-PRIME                → PREMIUM_FAST  (streamlined; no retry loop needed)
      SUBPRIME + not eligible    → CONDITIONAL   (close to qualifying; improvement path)
      everything else            → STANDARD      (full pipeline with compliance loop)
    """
    segment = risk_data.get("segment", "NEAR-PRIME")
    eligible = risk_data.get("eligible_for_credit", False)

    if segment == "DEEP-SUBPRIME":
        return "EDUCATIONAL"
    if segment == "SUPER-PRIME":
        return "PREMIUM_FAST"
    if segment == "SUBPRIME" and not eligible:
        return "CONDITIONAL"
    return "STANDARD"


class FinCampaignOrchestrator:
    """
    Central coordinator for the multi-agent credit campaign pipeline.

    Determines the appropriate route per customer and dispatches to the
    correct agent sequence. All routes persist results to GCS.
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
        Run the appropriate pipeline for a single customer.

        Args:
            customer_profile: Dict matching CustomerProfile schema.

        Returns:
            AnalysisResponse with all agent outputs, route label, and GCS URI.
        """
        start_time = time.time()
        request_id = generate_request_id()

        # ── Step 1: Risk Analysis (always runs) ─────────────────────────────────
        risk_data = await risk_analyst_agent.analyze(customer_profile)
        risk_assessment = RiskAssessment(**risk_data)

        # ── Step 2: Route determination ─────────────────────────────────────────
        route = _determine_route(risk_data)

        # ── Step 2b: Customer memory card (Phase 3) ──────────────────────────────
        # Prefer the structured memory card over raw history.
        # Falls back to raw history if no memory card exists yet (first run).
        customer_id = customer_profile.get("customer_id")
        customer_history = await get_customer_memory_card(customer_id)
        if not customer_history:
            customer_history = await get_customer_history_context(customer_id)

        print(
            f"[Orchestrator] {customer_profile.get('name')} → route={route} "
            f"segment={risk_assessment.segment} eligible={risk_assessment.eligible_for_credit} "
            f"memory={summarize_history_for_log(customer_history)}"
        )

        # ── Step 3: Agent dispatch by route ─────────────────────────────────────
        correction_attempts = 0
        campaign_data: dict
        compliance_data: dict

        if route == "EDUCATIONAL":
            # DEEP-SUBPRIME: generate a financial rehabilitation plan.
            # Compliance runs once (to audit the educational message), no retry loop.
            campaign_data = await financial_education_agent.educate(
                customer_profile, risk_data
            )
            compliance_data = await compliance_checker_agent.check(
                customer_profile, risk_data, campaign_data
            )
            # Educational content rarely fails compliance, but if it does → escalate
            verdict = compliance_data.get("overall_verdict", "")
            has_fail = any(
                compliance_data.get(k) == "FAIL"
                for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
            )
            if verdict == "REJECTED" or has_fail:
                compliance_data["human_review_required"] = True
                compliance_data.setdefault("warnings", []).append(
                    "Ruta EDUCATIONAL: contenido educativo requiere revisión manual."
                )

        elif route == "PREMIUM_FAST":
            # SUPER-PRIME: standard campaign generation, compliance checked once.
            # Self-correction loop is skipped — SUPER-PRIME profiles are clean by nature.
            # If compliance unexpectedly fails, escalate directly to human review
            # rather than wasting retries on an already-strong profile.
            campaign_data = await campaign_generator_agent.generate(
                customer_profile, risk_data, customer_history=customer_history
            )
            compliance_data = await compliance_checker_agent.check(
                customer_profile, risk_data, campaign_data
            )
            verdict = compliance_data.get("overall_verdict", "")
            has_fail = any(
                compliance_data.get(k) == "FAIL"
                for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
            )
            if verdict == "REJECTED" or has_fail:
                compliance_data["human_review_required"] = True
                compliance_data.setdefault("warnings", []).append(
                    "Ruta PREMIUM_FAST: falla de compliance inesperada — requiere revisión manual."
                )

        elif route == "CONDITIONAL":
            # SUBPRIME ineligible: generate a conditional improvement path.
            # One correction pass is allowed (conditional messages can have
            # messaging compliance issues that are fixable).
            campaign_data = await conditional_offer_agent.generate_conditional(
                customer_profile, risk_data
            )
            compliance_data = await compliance_checker_agent.check(
                customer_profile, risk_data, campaign_data
            )
            verdict = compliance_data.get("overall_verdict", "")
            has_fail = any(
                compliance_data.get(k) == "FAIL"
                for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
            )
            if verdict == "REJECTED" or has_fail:
                correction_attempts += 1
                print(
                    f"[Orchestrator] CONDITIONAL compliance failed for "
                    f"{customer_profile.get('name')} — running one correction pass"
                )
                # Use campaign_generator.regenerate since the fix logic is generic
                campaign_data = await campaign_generator_agent.regenerate(
                    customer_profile, risk_data, campaign_data, compliance_data,
                    customer_history=customer_history,
                )
                compliance_data = await compliance_checker_agent.check(
                    customer_profile, risk_data, campaign_data
                )
                # After one pass: escalate if still failing
                verdict = compliance_data.get("overall_verdict", "")
                has_fail = any(
                    compliance_data.get(k) == "FAIL"
                    for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
                )
                if verdict == "REJECTED" or has_fail:
                    compliance_data["human_review_required"] = True
                    compliance_data.setdefault("warnings", []).append(
                        "Ruta CONDITIONAL: corrección fallida — requiere revisión manual."
                    )

        else:
            # STANDARD route: full Campaign Generation → Compliance → self-correction loop.
            # This is the core production path for PRIME, NEAR-PRIME, and eligible SUBPRIME.
            campaign_data = await campaign_generator_agent.generate(
                customer_profile, risk_data, customer_history=customer_history
            )
            compliance_data = await compliance_checker_agent.check(
                customer_profile, risk_data, campaign_data
            )

            for _ in range(_MAX_CORRECTIONS):
                verdict = compliance_data.get("overall_verdict", "")
                has_fail = any(
                    compliance_data.get(k) == "FAIL"
                    for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
                )
                if verdict != "REJECTED" and not has_fail:
                    break  # compliance passed well enough — exit loop

                correction_attempts += 1
                print(
                    f"[Orchestrator] Compliance {verdict} for {customer_profile.get('name')} "
                    f"— correction attempt {correction_attempts}/{_MAX_CORRECTIONS}"
                )
                campaign_data = await campaign_generator_agent.regenerate(
                    customer_profile, risk_data, campaign_data, compliance_data,
                    customer_history=customer_history,
                )
                compliance_data = await compliance_checker_agent.check(
                    customer_profile, risk_data, campaign_data
                )

            # Escalate if still failing after max retries
            if correction_attempts == _MAX_CORRECTIONS:
                verdict = compliance_data.get("overall_verdict", "")
                has_fail = any(
                    compliance_data.get(k) == "FAIL"
                    for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
                )
                if verdict == "REJECTED" or has_fail:
                    compliance_data["human_review_required"] = True
                    compliance_data.setdefault("warnings", []).append(
                        f"Auto-corrección fallida tras {correction_attempts} intentos. "
                        "Requiere revisión manual obligatoria."
                    )

        # ── Step 4: Confidence aggregation + automatic escalation ───────────────
        pipeline_confidence = _compute_pipeline_confidence(risk_data, compliance_data, route)

        # Auto-escalate when confidence is below threshold (except EDUCATIONAL,
        # which is already routed to human review by nature)
        if pipeline_confidence < _CONFIDENCE_THRESHOLD and route != "EDUCATIONAL":
            compliance_data["human_review_required"] = True
            compliance_data.setdefault("warnings", []).append(
                f"Confianza del pipeline: {pipeline_confidence:.0%} — "
                f"por debajo del umbral de {_CONFIDENCE_THRESHOLD:.0%}. "
                "Revisión manual recomendada."
            )
            print(
                f"[Orchestrator] LOW CONFIDENCE {pipeline_confidence:.2f} for "
                f"{customer_profile.get('name')} — auto-escalating to human review"
            )

        # ── Step 5: Build response models ───────────────────────────────────────
        campaign = Campaign(**campaign_data)
        compliance = ComplianceResult(**compliance_data)

        # ── Step 6: Persist to GCS ───────────────────────────────────────────────
        processing_ms = int((time.time() - start_time) * 1000)
        stored_at = await self._store_result(
            request_id=request_id,
            customer_profile=customer_profile,
            risk_assessment=risk_data,
            campaign=campaign_data,
            compliance=compliance_data,
            processing_ms=processing_ms,
            correction_attempts=correction_attempts,
            pipeline_route=route,
            pipeline_confidence=pipeline_confidence,
        )

        # ── Step 7b: Write interaction + refresh memory card ────────────────────
        if customer_id:
            try:
                await save_customer_interaction(
                    customer_id=customer_id,
                    request_id=request_id,
                    segment=risk_data.get("segment"),
                    eligible=risk_data.get("eligible_for_credit", False),
                    dti=float(risk_data.get("dti", 0)),
                    product_offered=campaign_data.get("product_name"),
                    verdict=compliance_data.get("overall_verdict"),
                    channel=campaign_data.get("channel"),
                    pipeline_route=route,
                    confidence=pipeline_confidence,
                    campaign_id=customer_profile.get("campaign_id"),
                )
                await refresh_customer_memory(customer_id, customer_profile.get("name", ""))
            except Exception as exc:
                print(f"[Memory] Failed to update memory for customer {customer_id}: {exc}")

        return AnalysisResponse(
            request_id=request_id,
            customer_name=customer_profile.get("name", "Unknown"),
            customer_id=customer_id,
            risk_assessment=risk_assessment,
            campaign=campaign,
            compliance=compliance,
            stored_at=stored_at,
            processing_time_ms=processing_ms,
            correction_attempts=correction_attempts,
            pipeline_route=route,
            pipeline_confidence=pipeline_confidence,
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
        correction_attempts: int = 0,
        pipeline_route: str = "STANDARD",
        pipeline_confidence: float = 1.0,
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

        payload = {
            "request_id": request_id,
            "timestamp": now.isoformat() + "Z",
            "pipeline_route": pipeline_route,
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
            "correction_attempts": correction_attempts,
            "pipeline_confidence": pipeline_confidence,
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
        # Route distribution summary
        route_counts: dict[str, int] = {}
        for r in results:
            route_counts[r.pipeline_route] = route_counts.get(r.pipeline_route, 0) + 1

        summary = {
            "batch_id": batch_id,
            "timestamp": now.isoformat() + "Z",
            "processed": len(results),
            "error_count": len(errors),
            "route_distribution": route_counts,
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
