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


# ── Campaign Models ────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    type: str = Field(..., pattern="^(HIPOTECARIO|VEHICULOS|CDT|PERSONAL|TARJETA)$")
    description: str = ""
    target_segments: list[str] = []
    min_credit_score: int = Field(300, ge=300, le=850)
    max_credit_score: int = Field(850, ge=300, le=850)
    min_monthly_income: float = Field(0, ge=0)
    max_dti: float = Field(100, ge=0, le=100)
    max_late_payments: int = Field(10, ge=0)
    max_credit_utilization: float = Field(100, ge=0, le=100)
    product_name: str = ""
    rate_min: float = Field(0, ge=0)
    rate_max: float = Field(100, ge=0)
    max_amount: float = Field(0, ge=0)
    term_months: int = Field(0, ge=0)
    channel: str = "Email"
    message_tone: str = "Amigable"
    cta_text: str = ""


class CampaignResponse(CampaignCreate):
    id: int
    status: str
    total_targeted: int
    total_processed: int
    total_approved: int
    total_review: int
    created_at: str
    last_run_at: Optional[str] = None


class CampaignRunResponse(BaseModel):
    campaign_id: int
    batch_id: str
    total_targeted: int
    total_processed: int
    total_approved: int
    total_review: int
    results: list[AnalysisResponse]
    errors: list[dict] = []


# ── Helpers ────────────────────────────────────────────────────────────────────

def generate_request_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REQ-{today}-{suffix}"
