import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Models ─────────────────────────────────────────────────────────────

class CustomerProfile(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=18, le=100)
    monthly_income: float = Field(..., gt=0)
    monthly_debt: float = Field(..., ge=0)
    credit_score: int = Field(..., ge=300, le=850)
    late_payments: int = Field(..., ge=0)
    credit_utilization: float = Field(..., ge=0, le=100)
    products_of_interest: str = Field(..., min_length=3)


class BatchRequest(BaseModel):
    batch_id: str = Field(
        default_factory=lambda: f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    customers: list[CustomerProfile] = Field(..., min_length=1, max_length=100)


# ── Sub-Response Models ────────────────────────────────────────────────────────

class RiskAssessment(BaseModel):
    segment: str       # SUPER-PRIME / PRIME / NEAR-PRIME / SUBPRIME / DEEP-SUBPRIME
    risk_level: str    # VERY LOW / LOW / MEDIUM / HIGH / CRITICAL
    dti: float
    eligible_for_credit: bool
    recommended_products: list[str]
    rationale: str


class Campaign(BaseModel):
    product_name: str
    campaign_message: str
    key_benefits: list[str]
    cta: str
    channel: str
    rates: str


class ComplianceResult(BaseModel):
    fair_lending: str      # PASS / FAIL
    apr_disclosure: str    # PASS / REVIEW / FAIL
    messaging: str         # PASS / REVIEW / FAIL
    channel: str           # PASS / REVIEW
    overall_verdict: str   # APPROVED / APPROVED_WITH_WARNINGS / REVIEW / REJECTED
    warnings: list[str]
    human_review_required: bool


# ── Final Response Models ──────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    request_id: str
    customer_name: str
    risk_assessment: RiskAssessment
    campaign: Campaign
    compliance: ComplianceResult
    stored_at: str
    processing_time_ms: Optional[int] = None


class BatchResponse(BaseModel):
    batch_id: str
    total_customers: int
    processed: int
    results: list[AnalysisResponse]
    errors: list[dict] = []
    stored_at: str


# ── Utility Models ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: dict[str, str]


class DocumentInfo(BaseModel):
    name: str
    size_bytes: Optional[int] = None
    content_type: str
    updated: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    datastore_id: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def generate_request_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REQ-{today}-{suffix}"
