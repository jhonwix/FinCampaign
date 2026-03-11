import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft, Play, Users, CheckCircle, AlertTriangle,
  BarChart2, Clock, RefreshCw,
} from 'lucide-react'
import { api } from '../api/client'
import type { CampaignRecord, CampaignResultRow, CampaignRunResult } from '../api/types'

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined) {
  return n == null ? '—' : n.toLocaleString('es-CO')
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function passRate(approved: number, processed: number) {
  if (!processed) return '—'
  return `${Math.round((approved / processed) * 100)}%`
}

// ── Badge components ──────────────────────────────────────────────────────────
function VerdictBadge({ verdict }: { verdict: string }) {
  const map: Record<string, string> = {
    APPROVED: 'bg-emerald-100 text-emerald-700',
    APPROVED_WITH_WARNINGS: 'bg-blue-100 text-blue-700',
    REVIEW: 'bg-amber-100 text-amber-700',
    REJECTED: 'bg-red-100 text-red-700',
    PASS: 'bg-emerald-100 text-emerald-700',
    FAIL: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${map[verdict] ?? 'bg-slate-100 text-slate-600'}`}>
      {verdict}
    </span>
  )
}

function SegmentBadge({ segment }: { segment: string }) {
  const map: Record<string, string> = {
    'SUPER-PRIME':  'bg-emerald-100 text-emerald-700',
    'PRIME':        'bg-blue-100 text-blue-700',
    'NEAR-PRIME':   'bg-yellow-100 text-yellow-700',
    'SUBPRIME':     'bg-orange-100 text-orange-700',
    'DEEP-SUBPRIME':'bg-red-100 text-red-700',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${map[segment] ?? 'bg-slate-100 text-slate-600'}`}>
      {segment}
    </span>
  )
}

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({
  label, value, color = 'text-slate-900',
  icon,
}: {
  label: string
  value: string | number
  color?: string
  icon: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
      <div className="p-2 bg-slate-50 rounded-lg text-slate-500">{icon}</div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className={`text-xl font-bold mt-0.5 ${color}`}>{value}</p>
      </div>
    </div>
  )
}

// ── Info row ─────────────────────────────────────────────────────────────────
function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-xs font-medium text-slate-700">{value}</span>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [runResult, setRunResult] = useState<CampaignRunResult | null>(null)
  const [runError, setRunError] = useState('')

  const { data: campaign, isLoading } = useQuery<CampaignRecord>({
    queryKey: ['campaign', campaignId],
    queryFn: () => api.getCampaign(campaignId),
  })

  const { data: resultsData, refetch: refetchResults } = useQuery<{
    campaign_id: number
    results: CampaignResultRow[]
    total: number
  }>({
    queryKey: ['campaign-results', campaignId],
    queryFn: () => api.getCampaignResults(campaignId),
  })

  const runMutation = useMutation({
    mutationFn: () => api.runCampaign(campaignId),
    onSuccess: (data) => {
      setRunResult(data)
      setRunError('')
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
      qc.invalidateQueries({ queryKey: ['campaign-results', campaignId] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
    onError: (e: Error) => {
      setRunError(e.message)
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
    },
  })

  if (isLoading || !campaign) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    )
  }

  const totalApproved = runResult?.total_approved ?? campaign.total_approved
  const totalReview   = runResult?.total_review   ?? campaign.total_review
  const totalProc     = runResult?.total_processed ?? campaign.total_processed
  const totalTarget   = runResult?.total_targeted  ?? campaign.total_targeted

  return (
    <div className="space-y-5">
      {/* Back */}
      <button
        onClick={() => navigate('/campaigns')}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ChevronLeft className="w-4 h-4" />
        Campañas
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{campaign.name}</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {campaign.type} · Creada {fmtDate(campaign.created_at)}
          </p>
          {campaign.description && (
            <p className="text-sm text-slate-600 mt-1">{campaign.description}</p>
          )}
        </div>

        <button
          onClick={() => {
            setRunError('')
            runMutation.mutate()
          }}
          disabled={runMutation.isPending || campaign.status === 'RUNNING'}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {runMutation.isPending ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Ejecutando...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Ejecutar Campaña
            </>
          )}
        </button>
      </div>

      {runError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded-lg">
          {runError}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Objetivo"   value={fmt(totalTarget)}  icon={<Users className="w-4 h-4" />} />
        <StatCard label="Procesados" value={fmt(totalProc)}    icon={<BarChart2 className="w-4 h-4" />} />
        <StatCard label="Aprobados"  value={fmt(totalApproved)} color="text-emerald-600" icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="Revisión"   value={fmt(totalReview)}  color="text-amber-600"   icon={<AlertTriangle className="w-4 h-4" />} />
        <StatCard label="Pass Rate"  value={passRate(totalApproved, totalProc)} color="text-indigo-600" icon={<BarChart2 className="w-4 h-4" />} />
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Targeting */}
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Filtros de Audiencia</h3>
          <InfoRow label="Score mínimo" value={campaign.min_credit_score} />
          <InfoRow label="Score máximo" value={campaign.max_credit_score} />
          <InfoRow label="Ingreso mínimo" value={`$${fmt(campaign.min_monthly_income)}`} />
          <InfoRow label="DTI máximo" value={`${campaign.max_dti}%`} />
          <InfoRow label="Pagos tardíos máx." value={campaign.max_late_payments} />
          <InfoRow label="Utilización máx." value={`${campaign.max_credit_utilization}%`} />
          <InfoRow
            label="Segmentos objetivo"
            value={campaign.target_segments.length === 0 ? 'Todos' : campaign.target_segments.join(', ')}
          />
        </div>

        {/* Product */}
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Configuración de Producto</h3>
          <InfoRow label="Producto" value={campaign.product_name || '—'} />
          <InfoRow label="Tasa mínima" value={`${campaign.rate_min}%`} />
          <InfoRow label="Tasa máxima" value={`${campaign.rate_max}%`} />
          <InfoRow label="Monto máximo" value={`$${fmt(campaign.max_amount)}`} />
          <InfoRow label="Plazo" value={campaign.term_months ? `${campaign.term_months} meses` : '—'} />
          <InfoRow label="Canal" value={campaign.channel} />
          <InfoRow label="Tono" value={campaign.message_tone} />
          {campaign.cta_text && <InfoRow label="CTA" value={campaign.cta_text} />}
          <InfoRow label="Última ejecución" value={fmtDate(campaign.last_run_at)} />
        </div>
      </div>

      {/* Results table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-700">
            Resultados ({resultsData?.total ?? 0})
          </h3>
          <button
            onClick={() => refetchResults()}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Actualizar
          </button>
        </div>

        {!resultsData || resultsData.results.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-400">
            No hay resultados aún. Ejecuta la campaña para generar resultados.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Cliente</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Segmento</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Riesgo</th>
                  <th className="text-right px-4 py-2 font-medium text-slate-500">DTI</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Producto</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Cumplimiento</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-500">Revisión</th>
                  <th className="text-right px-4 py-2 font-medium text-slate-500">ms</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {resultsData.results.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-4 py-2 font-medium text-slate-800">{r.customer_name}</td>
                    <td className="px-4 py-2">
                      <SegmentBadge segment={r.segment} />
                    </td>
                    <td className="px-4 py-2 text-slate-600">{r.risk_level}</td>
                    <td className="px-4 py-2 text-right text-slate-600">{r.dti?.toFixed(1)}%</td>
                    <td className="px-4 py-2 text-slate-600 max-w-[120px] truncate">{r.product_name}</td>
                    <td className="px-4 py-2">
                      <VerdictBadge verdict={r.compliance_verdict} />
                    </td>
                    <td className="px-4 py-2 text-center">
                      {r.human_review_required ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mx-auto" />
                      ) : (
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mx-auto" />
                      )}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-500">{r.processing_ms}</td>
                    <td className="px-4 py-2 text-slate-500 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {fmtDate(r.processed_at)}
                      </span>
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
