export interface Customer {
  id: number
  id_number: string
  name: string
  age: number
  monthly_income: number
  monthly_debt: number
  credit_score: number
  late_payments: number
  credit_utilization: number
  products_of_interest: string
  existing_products: string
  created_at: string
}

export interface RiskAssessment {
  segment: 'SUPER-PRIME' | 'PRIME' | 'NEAR-PRIME' | 'SUBPRIME' | 'DEEP-SUBPRIME'
  risk_level: 'VERY LOW' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  dti: number
  eligible_for_credit: boolean
  recommended_products: string[]
  rationale: string
  confidence?: number
}

export interface Campaign {
  product_name: string
  campaign_message: string
  key_benefits: string[]
  cta: string
  channel: string
  rates: string
}

export interface Compliance {
  fair_lending: 'PASS' | 'REVIEW' | 'FAIL'
  apr_disclosure: 'PASS' | 'REVIEW' | 'FAIL'
  messaging: 'PASS' | 'REVIEW' | 'FAIL'
  channel: 'PASS' | 'REVIEW' | 'FAIL'
  overall_verdict: 'APPROVED' | 'APPROVED_WITH_WARNINGS' | 'REVIEW' | 'REJECTED'
  warnings: string[]
  human_review_required: boolean
  confidence?: number
}

export type PipelineRoute = 'STANDARD' | 'PREMIUM_FAST' | 'CONDITIONAL' | 'EDUCATIONAL'

export interface AnalysisResult {
  request_id: string
  customer_name: string
  risk_assessment: RiskAssessment
  campaign: Campaign
  compliance: Compliance
  stored_at: string
  processing_time_ms: number
  correction_attempts: number
  pipeline_route: PipelineRoute
  pipeline_confidence: number
}

export interface CustomerResult {
  id: number
  request_id: string
  segment: string
  risk_level: string
  dti: number
  eligible_for_credit: boolean
  product_name: string
  compliance_verdict: string
  human_review_required: boolean
  gcs_path: string
  processing_ms: number
  processed_at: string
}

export type CampaignType = 'HIPOTECARIO' | 'VEHICULOS' | 'CDT' | 'PERSONAL' | 'TARJETA'
export type CampaignStatus = 'DRAFT' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type SegmentName = 'SUPER-PRIME' | 'PRIME' | 'NEAR-PRIME' | 'SUBPRIME' | 'DEEP-SUBPRIME'
export type CampaignIntent = 'NEW' | 'RENEWAL' | 'CROSS'

export interface CampaignCreate {
  name: string
  type: CampaignType
  description: string
  target_segments: SegmentName[]
  min_credit_score: number
  max_credit_score: number
  min_monthly_income: number
  max_dti: number
  max_late_payments: number
  max_credit_utilization: number
  product_name: string
  rate_min: number
  rate_max: number
  max_amount: number
  term_months: number
  channel: string
  message_tone: string
  cta_text: string
  campaign_intent: CampaignIntent
}

export interface CampaignRecord extends CampaignCreate {
  id: number
  status: CampaignStatus
  total_targeted: number
  total_processed: number
  total_approved: number
  total_review: number
  created_at: string
  last_run_at: string | null
}

export interface CampaignResultRow {
  id: number
  request_id: string
  customer_id: number
  customer_name: string
  segment: string
  risk_level: string
  dti: number
  eligible_for_credit: boolean
  product_name: string
  compliance_verdict: 'APPROVED' | 'APPROVED_WITH_WARNINGS' | 'REVIEW' | 'REJECTED'
  human_review_required: boolean
  pipeline_route: string
  pipeline_confidence: number | null
  correction_attempts: number | null
  processing_ms: number
  processed_at: string
  // Review workflow (Gap 2)
  review_status: 'APPROVED' | 'REJECTED' | null
  review_note: string | null
  reviewed_at: string | null
}

export interface LookupMap {
  campaign_type: string[]
  campaign_intent: string[]
  credit_segment: string[]
  campaign_status: string[]
  campaign_channel: string[]
  message_tone: string[]
  compliance_overall_verdict: string[]
  compliance_check_result: string[]
}

export interface ImportResult {
  total_rows: number
  imported: number
  duplicates: number
  validation_errors: Array<{ row: number; name: string; errors: string[] }>
  db_errors: Array<{ name: string; error: string }>
}

export interface CampaignRunResult {
  campaign_id: number
  batch_id: string
  total_targeted: number
  total_processed: number
  total_approved: number
  total_review: number
  results: AnalysisResult[]
  errors: Record<string, unknown>[]
}

// ── Async run types (Gap 1) ───────────────────────────────────────────────────

export interface CampaignRunStarted {
  batch_id: string
  status: 'RUNNING'
  campaign_id: number
  total_targeted: number
}

export interface CampaignRunStatus {
  batch_id: string
  campaign_id: number
  status: 'RUNNING' | 'COMPLETED' | 'FAILED'
  total_targeted: number
  total_processed: number
  total_approved: number
  total_review: number
  error_message: string | null
  started_at: string
  completed_at: string | null
}

// ── Review workflow types (Gap 2) ─────────────────────────────────────────────

export interface ReviewRequest {
  action: 'APPROVE' | 'REJECT'
  note?: string
}

export interface ReviewResponse {
  result_id: number
  review_status: 'APPROVED' | 'REJECTED'
  review_note: string
  reviewed_at: string
}
