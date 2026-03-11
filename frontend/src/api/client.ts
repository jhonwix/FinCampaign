import type {
  AnalysisResult,
  Campaign,
  CampaignCreate,
  CampaignRecord,
  CampaignResultRow,
  CampaignRunResult,
  Customer,
  CustomerResult,
} from './types'

// Re-export so pages can import from one place
export type { Campaign, CampaignCreate, CampaignRecord, CampaignResultRow, CampaignRunResult }

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

  runCampaign: (id: number): Promise<CampaignRunResult> =>
    request(`/campaigns/${id}/run`, { method: 'POST' }),

  getCampaignResults: (
    id: number
  ): Promise<{ campaign_id: number; results: CampaignResultRow[]; total: number }> =>
    request(`/campaigns/${id}/results`),
}
