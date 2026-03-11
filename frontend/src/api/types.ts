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
