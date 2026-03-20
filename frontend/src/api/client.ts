import type {
  AnalysisResult,
  Campaign,
  CampaignCreate,
  CampaignRecord,
  CampaignResultRow,
  CampaignRunResult,
  CampaignRunStarted,
  CampaignRunStatus,
  Customer,
  CustomerResult,
  ImportResult,
  LookupMap,
  ReviewRequest,
  ReviewResponse,
} from './types'

// Re-export so pages can import from one place
export type {
  Campaign, CampaignCreate, CampaignRecord, CampaignResultRow, CampaignRunResult,
  CampaignRunStarted, CampaignRunStatus, ImportResult, LookupMap, ReviewRequest, ReviewResponse,
}

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  getCustomers: (): Promise<{ customers: Customer[]; total: number }> =>
    request('/customers'),

  analyzeCustomer: (customerId: number): Promise<AnalysisResult> =>
    request(`/analyze/db/${customerId}`, { method: 'POST' }),

  getCustomerResults: (
    customerId: number
  ): Promise<{ customer_id: number; results: CustomerResult[]; total: number }> =>
    request(`/customers/${customerId}/results`),

  health: (): Promise<{ status: string; version: string; timestamp: string }> =>
    request('/health'),

  // Campaign endpoints
  listCampaigns: (): Promise<CampaignRecord[]> =>
    request('/campaigns'),

  createCampaign: (body: CampaignCreate): Promise<CampaignRecord> =>
    request('/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  getCampaign: (id: number): Promise<CampaignRecord> =>
    request(`/campaigns/${id}`),

  runCampaign: (id: number): Promise<CampaignRunStarted> =>
    request(`/campaigns/${id}/run`, { method: 'POST' }),

  getRunStatus: (id: number, batchId: string): Promise<CampaignRunStatus> =>
    request(`/campaigns/${id}/run-status?batch_id=${encodeURIComponent(batchId)}`),

  getCampaignResults: (
    id: number
  ): Promise<{ campaign_id: number; results: CampaignResultRow[]; total: number }> =>
    request(`/campaigns/${id}/results`),

  reviewResult: (
    campaignId: number,
    resultId: number,
    body: ReviewRequest,
  ): Promise<ReviewResponse> =>
    request(`/campaigns/${campaignId}/results/${resultId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  importCustomers: (file: File): Promise<ImportResult> => {
    const form = new FormData()
    form.append('file', file)
    return request('/customers/import', { method: 'POST', body: form })
  },

  getLookups: (): Promise<LookupMap> =>
    request('/lookups'),
}
