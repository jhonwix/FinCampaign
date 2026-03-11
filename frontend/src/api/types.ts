export interface Customer {
  id: number
  name: string
  age: number
  monthly_income: number
  monthly_debt: number
  credit_score: number
  late_payments: number
  credit_utilization: number
  products_of_interest: string
  created_at: string
}

export interface RiskAssessment {
  segment: 'SUPER-PRIME' | 'PRIME' | 'NEAR-PRIME' | 'SUBPRIME' | 'DEEP-SUBPRIME'
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  dti: number
  eligible_for_credit: boolean
  recommended_products: string[]
  rationale: string
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
  fair_lending: string
  apr_disclosure: string
  messaging: string
  channel: string
  overall_verdict: 'PASS' | 'REVIEW' | 'FAIL'
  warnings: string[]
  human_review_required: boolean
}

export interface AnalysisResult {
  request_id: string
  customer_name: string
  risk_assessment: RiskAssessment
  campaign: Campaign
  compliance: Compliance
  stored_at: string
  processing_time_ms: number
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
export type CampaignStatus = 'DRAFT' | 'RUNNING' | 'COMPLETED'
export type SegmentName = 'SUPER-PRIME' | 'PRIME' | 'NEAR-PRIME' | 'SUBPRIME' | 'DEEP-SUBPRIME'

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
  compliance_verdict: string
  human_review_required: boolean
  processing_ms: number
  processed_at: string
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
