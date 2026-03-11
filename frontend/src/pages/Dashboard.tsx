import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Zap, ChevronRight, Loader2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Badge, ScoreBadge } from '../components/Badge'

export function Dashboard() {
  const navigate = useNavigate()
  const [analyzing, setAnalyzing] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: api.getCustomers,
  })

  async function handleAnalyze(customerId: number) {
    setAnalyzing(customerId)
    setError(null)
    try {
      await api.analyzeCustomer(customerId)
      navigate(`/customers/${customerId}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setAnalyzing(null)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="bg-indigo-600 p-2 rounded-lg">
          <Users className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-slate-900">Customer Portfolio</h1>
          <p className="text-sm text-slate-500">
            {data?.total ?? 0} customers · Click Analyze to run the AI pipeline
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 font-semibold text-slate-600">ID</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Name</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Age</th>
                <th className="text-right px-4 py-3 font-semibold text-slate-600">Income</th>
                <th className="text-right px-4 py-3 font-semibold text-slate-600">Debt</th>
                <th className="text-right px-4 py-3 font-semibold text-slate-600">Score</th>
                <th className="text-right px-4 py-3 font-semibold text-slate-600">Late Pmts</th>
                <th className="text-right px-4 py-3 font-semibold text-slate-600">Util%</th>
                <th className="text-left px-4 py-3 font-semibold text-slate-600">Products</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.customers.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-400 font-mono text-xs">{c.id}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">
                    <button
                      className="hover:text-indigo-600 transition-colors text-left"
                      onClick={() => navigate(`/customers/${c.id}`)}
                    >
                      {c.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{c.age}</td>
                  <td className="px-4 py-3 text-right text-slate-700">
                    ${c.monthly_income.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    ${c.monthly_debt.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ScoreBadge score={c.credit_score} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.late_payments > 0 ? (
                      <span className="text-orange-600 font-medium">{c.late_payments}</span>
                    ) : (
                      <span className="text-emerald-600">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={c.credit_utilization >= 60 ? 'text-red-600 font-medium' : c.credit_utilization >= 30 ? 'text-yellow-600' : 'text-slate-600'}>
                      {c.credit_utilization}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-32 truncate">
                    {c.products_of_interest}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => navigate(`/customers/${c.id}`)}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                        title="View results"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleAnalyze(c.id)}
                        disabled={analyzing === c.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-wait transition-colors"
                      >
                        {analyzing === c.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Zap className="w-3.5 h-3.5" />
                        )}
                        Analyze
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
