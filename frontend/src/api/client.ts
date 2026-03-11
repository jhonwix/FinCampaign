import type { AnalysisResult, Customer, CustomerResult } from './types'

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
}
