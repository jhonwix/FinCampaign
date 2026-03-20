import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    existing_products: str = Field(default="")    # productos que el cliente ya tiene activos
    customer_id: Optional[int] = Field(default=None)  # DB id — None for anonymous profiles
    # Campaign product constraints — injected by run_campaign, None for ad-hoc analysis
    rate_min: Optional[float] = Field(default=None)
    rate_max: Optional[float] = Field(default=None)
    max_amount: Optional[float] = Field(default=None)
    term_months: Optional[int] = Field(default=None)
    message_tone: Optional[str] = Field(default=None)
    cta_text: Optional[str] = Field(default=None)


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
    confidence: float = 1.0  # agent's self-reported confidence (0.0–1.0)


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
    confidence: float = 1.0  # agent's self-reported confidence (0.0–1.0)


# ── Final Response Models ──────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    request_id: str
    customer_name: str
    customer_id: Optional[int] = None  # DB id of the customer; set during batch/db runs
    risk_assessment: RiskAssessment
    campaign: Campaign
    compliance: ComplianceResult
    stored_at: str
    processing_time_ms: Optional[int] = None
    correction_attempts: int = 0       # how many times campaign was regenerated after compliance rejection
    pipeline_route: str = "STANDARD"   # STANDARD | PREMIUM_FAST | CONDITIONAL | EDUCATIONAL
    pipeline_confidence: float = 1.0   # aggregated confidence [0.0–1.0]; <0.65 triggers human review


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
    type: str = Field(...)
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
    campaign_intent: str = Field(default="NEW", description="NEW=adquisicion, RENEWAL=renovacion, CROSS=cross-sell")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        from db.lookups import get_valid_values
        valid = get_valid_values("campaign_type")
        if valid and v not in valid:
            raise ValueError(f"'{v}' no es un tipo valido. Permitidos: {valid}")
        return v

    @field_validator("campaign_intent")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        from db.lookups import get_valid_values
        valid = get_valid_values("campaign_intent")
        if valid and v not in valid:
            raise ValueError(f"'{v}' no es una intencion valida. Permitidas: {valid}")
        return v


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


# ── Async Run Models ───────────────────────────────────────────────────────────

class CampaignRunStarted(BaseModel):
    """Immediate response from POST /campaigns/:id/run — job accepted."""
    batch_id: str
    status: str          # always "RUNNING" at creation time
    campaign_id: int
    total_targeted: int


class CampaignRunStatus(BaseModel):
    """Response from GET /campaigns/:id/run-status."""
    batch_id: str
    campaign_id: int
    status: str          # RUNNING | COMPLETED | FAILED
    total_targeted: int
    total_processed: int
    total_approved: int
    total_review: int
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


# ── Review Workflow Models ──────────────────────────────────────────────────────

class ReviewAction(BaseModel):
    """Request body for PATCH /campaigns/:id/results/:result_id/review."""
    action: str    # "APPROVE" or "REJECT"
    note: str = ""

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("APPROVE", "REJECT"):
            raise ValueError("action must be 'APPROVE' or 'REJECT'")
        return v


class ReviewResponse(BaseModel):
    """Response from PATCH review endpoint."""
    result_id: int
    review_status: str
    review_note: str
    reviewed_at: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def generate_request_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REQ-{today}-{suffix}"
