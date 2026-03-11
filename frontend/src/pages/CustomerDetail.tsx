import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Zap, Loader2, ClipboardList, RefreshCw } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { AnalysisCard } from '../components/AnalysisCard'
import { Badge, ScoreBadge } from '../components/Badge'
import type { AnalysisResult } from '../api/types'

export function CustomerDetail() {
  const { id } = useParams<{ id: string }>()
  const customerId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [analyzing, setAnalyzing] = useState(false)
  const [latestResult, setLatestResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: customersData } = useQuery({
    queryKey: ['customers'],
    queryFn: api.getCustomers,
  })
  const customer = customersData?.customers.find((c) => c.id === customerId)

  const { data: resultsData, isLoading: resultsLoading } = useQuery({
    queryKey: ['customer-results', customerId],
    queryFn: () => api.getCustomerResults(customerId),
  })

  async function handleAnalyze() {
    setAnalyzing(true)
    setError(null)
    setLatestResult(null)
    try {
      const result = await api.analyzeCustomer(customerId)
      setLatestResult(result)
      queryClient.invalidateQueries({ queryKey: ['customer-results', customerId] })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div>
      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-5 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to portfolio
      </button>

      {/* Customer header */}
      {customer && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-900">{customer.name}</h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Age {customer.age} · Interested in: {customer.products_of_interest}
              </p>
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-wait transition-colors"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Run Analysis
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-slate-100">
            <div>
              <p className="text-xs text-slate-500">Credit Score</p>
              <div className="mt-1"><ScoreBadge score={customer.credit_score} /></div>
            </div>
            <div>
              <p className="text-xs text-slate-500">Monthly Income</p>
              <p className="text-sm font-semibold text-slate-800">${customer.monthly_income.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Monthly Debt</p>
              <p className="text-sm font-semibold text-slate-800">${customer.monthly_debt.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">DTI (raw)</p>
              <p className="text-sm font-semibold text-slate-800">
                {((customer.monthly_debt / customer.monthly_income) * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Late Payments</p>
              <p className={`text-sm font-semibold ${customer.late_payments > 0 ? 'text-orange-600' : 'text-emerald-600'}`}>
                {customer.late_payments}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Credit Utilization</p>
              <p className={`text-sm font-semibold ${customer.credit_utilization >= 60 ? 'text-red-600' : customer.credit_utilization >= 30 ? 'text-yellow-600' : 'text-emerald-600'}`}>
                {customer.credit_utilization}%
              </p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Latest result from this session */}
      {analyzing && (
        <div className="bg-white rounded-xl border border-indigo-200 p-8 mb-5 flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-sm text-slate-600">Running 3-agent pipeline…</p>
          <p className="text-xs text-slate-400">Risk Analyst → Campaign Generator → Compliance Checker</p>
        </div>
      )}

      {latestResult && !analyzing && (
        <div className="bg-white rounded-xl border border-indigo-200 p-5 mb-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
            <h2 className="text-sm font-semibold text-slate-700">Latest Result</h2>
          </div>
          <AnalysisCard result={latestResult} />
        </div>
      )}

      {/* Historical results */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-700">
              Analysis History ({resultsData?.total ?? 0})
            </h2>
          </div>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['customer-results', customerId] })}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {resultsLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
          </div>
        ) : resultsData?.results.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">
            No analyses yet. Click "Run Analysis" to start.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs">
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Request ID</th>
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Segment</th>
                  <th className="text-right px-3 py-2 font-semibold text-slate-600">DTI</th>
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Product</th>
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Compliance</th>
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Review</th>
                  <th className="text-right px-3 py-2 font-semibold text-slate-600">ms</th>
                  <th className="text-left px-3 py-2 font-semibold text-slate-600">Processed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {resultsData?.results.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-500">{r.request_id}</td>
                    <td className="px-3 py-2.5"><Badge value={r.segment} /></td>
                    <td className="px-3 py-2.5 text-right text-slate-700">{r.dti?.toFixed(1)}%</td>
                    <td className="px-3 py-2.5 text-slate-700 text-xs">{r.product_name}</td>
                    <td className="px-3 py-2.5"><Badge value={r.compliance_verdict} /></td>
                    <td className="px-3 py-2.5">
                      {r.human_review_required ? (
                        <span className="text-xs text-red-600 font-medium">Required</span>
                      ) : (
                        <span className="text-xs text-emerald-600">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-500 text-xs">{r.processing_ms?.toLocaleString()}</td>
                    <td className="px-3 py-2.5 text-xs text-slate-400">
                      {new Date(r.processed_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
