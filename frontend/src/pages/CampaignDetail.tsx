import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft, Play, Users, CheckCircle, AlertTriangle, XCircle,
  BarChart2, Clock, RefreshCw, RotateCcw, Zap, BookOpen, GitBranch,
} from 'lucide-react'
import { api } from '../api/client'
import type {
  CampaignRecord, CampaignResultRow, CampaignRunStatus, ReviewRequest,
} from '../api/types'

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

// ── Confidence badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-slate-300">—</span>
  const pct = Math.round(value * 100)
  const color =
    pct >= 80 ? 'bg-emerald-100 text-emerald-700'
    : pct >= 65 ? 'bg-amber-100 text-amber-700'
    : 'bg-red-100 text-red-700'
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold ${color}`}>
      {pct}%
    </span>
  )
}

// ── Route badge ───────────────────────────────────────────────────────────────
const ROUTE_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  STANDARD:     { label: 'Standard',    color: 'bg-slate-100 text-slate-600',    icon: <GitBranch className="w-2.5 h-2.5" /> },
  PREMIUM_FAST: { label: 'Premium',     color: 'bg-emerald-100 text-emerald-700', icon: <Zap className="w-2.5 h-2.5" /> },
  CONDITIONAL:  { label: 'Condicional', color: 'bg-amber-100 text-amber-700',    icon: <GitBranch className="w-2.5 h-2.5" /> },
  EDUCATIONAL:  { label: 'Educativo',   color: 'bg-blue-100 text-blue-700',      icon: <BookOpen className="w-2.5 h-2.5" /> },
}

function RouteBadge({ route }: { route: string }) {
  const meta = ROUTE_META[route] ?? ROUTE_META.STANDARD
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium ${meta.color}`}>
      {meta.icon}
      {meta.label}
    </span>
  )
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

// ── Review badge ──────────────────────────────────────────────────────────────
function ReviewBadge({ status }: { status: 'APPROVED' | 'REJECTED' | null }) {
  if (!status) return null
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
      status === 'APPROVED' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
    }`}>
      {status === 'APPROVED' ? 'Aprobado' : 'Rechazado'}
    </span>
  )
}

// ── Review actions (per-row) ──────────────────────────────────────────────────
function ReviewActions({
  row,
  campaignId,
  onDone,
}: {
  row: CampaignResultRow
  campaignId: number
  onDone: () => void
}) {
  const [showNote, setShowNote] = useState(false)
  const [note, setNote] = useState('')
  const [pendingAction, setPendingAction] = useState<'APPROVE' | 'REJECT' | null>(null)

  const mutation = useMutation({
    mutationFn: (action: 'APPROVE' | 'REJECT') =>
      api.reviewResult(campaignId, row.id, { action, note } as ReviewRequest),
    onSuccess: () => {
      setShowNote(false)
      setNote('')
      setPendingAction(null)
      onDone()
    },
  })

  // Already reviewed
  if (row.review_status) {
    return (
      <div className="flex flex-col items-center gap-0.5">
        <ReviewBadge status={row.review_status} />
        {row.review_note && (
          <span
            className="text-[9px] text-slate-400 max-w-[90px] truncate"
            title={row.review_note}
          >
            {row.review_note}
          </span>
        )}
      </div>
    )
  }

  // Doesn't need review
  if (!row.human_review_required) {
    return <span className="text-slate-300 text-xs">—</span>
  }

  // Needs review — show action buttons
  return (
    <div className="flex flex-col gap-1 items-center">
      {!showNote ? (
        <div className="flex gap-1">
          <button
            onClick={() => { setPendingAction('APPROVE'); setShowNote(true) }}
            disabled={mutation.isPending}
            className="px-2 py-0.5 text-[10px] font-medium bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
          >
            Aprobar
          </button>
          <button
            onClick={() => { setPendingAction('REJECT'); setShowNote(true) }}
            disabled={mutation.isPending}
            className="px-2 py-0.5 text-[10px] font-medium bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            Rechazar
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1 w-28">
          <input
            type="text"
            placeholder="Nota (opcional)"
            value={note}
            onChange={e => setNote(e.target.value)}
            className="text-[10px] border border-slate-200 rounded px-1.5 py-0.5 w-full"
          />
          <div className="flex gap-1">
            <button
              onClick={() => mutation.mutate(pendingAction!)}
              disabled={mutation.isPending}
              className={`flex-1 px-1.5 py-0.5 text-[10px] font-medium text-white rounded disabled:opacity-50 ${
                pendingAction === 'APPROVE' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-red-600 hover:bg-red-700'
              }`}
            >
              {mutation.isPending ? '...' : 'Confirmar'}
            </button>
            <button
              onClick={() => { setShowNote(false); setNote(''); setPendingAction(null) }}
              className="px-1.5 py-0.5 text-[10px] bg-slate-100 text-slate-600 rounded hover:bg-slate-200"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
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
  icon?: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-500">{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <span className={`text-xs font-medium ${color}`}>{value}</span>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between py-1 border-b border-slate-50 last:border-0">
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
  const [runStatus, setRunStatus] = useState<CampaignRunStatus | null>(null)
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)
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
      setRunError('')
      setActiveBatchId(data.batch_id)
      setRunStatus({
        batch_id: data.batch_id,
        campaign_id: data.campaign_id,
        status: 'RUNNING',
        total_targeted: data.total_targeted,
        total_processed: 0,
        total_approved: 0,
        total_review: 0,
        error_message: null,
        started_at: new Date().toISOString(),
        completed_at: null,
      })
      setIsPolling(true)
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
    onError: (e: Error) => {
      setRunError(e.message)
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
    },
  })

  // ── Polling effect ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isPolling || !activeBatchId) return

    let tid: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const s = await api.getRunStatus(campaignId, activeBatchId!)
        setRunStatus(s)

        if (s.status === 'RUNNING') {
          tid = setTimeout(poll, 3000)
        } else {
          setIsPolling(false)
          setActiveBatchId(null)
          qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
          qc.invalidateQueries({ queryKey: ['campaign-results', campaignId] })
          qc.invalidateQueries({ queryKey: ['campaigns'] })
          if (s.status === 'FAILED') {
            setRunError(s.error_message ?? 'Campaign run failed')
          }
        }
      } catch {
        setIsPolling(false)
        setRunError('Polling failed — refresh the page to check status')
      }
    }

    poll()
    return () => clearTimeout(tid)
  }, [isPolling, activeBatchId, campaignId, qc])

  if (isLoading || !campaign) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    )
  }

  // Totals that don't change after the run
  const totalProc   = runStatus?.total_processed ?? campaign.total_processed
  const totalTarget = runStatus?.total_targeted  ?? campaign.total_targeted

  // When results are loaded compute live stats; otherwise fall back to DB campaign stats.
  // This ensures approve/reject actions instantly update the numbers without a page reload.
  const _rows = resultsData?.results ?? []
  const hasResults = _rows.length > 0

  const totalApproved = hasResults
    ? _rows.filter(r =>
        (!r.human_review_required && ['APPROVED', 'APPROVED_WITH_WARNINGS'].includes(r.compliance_verdict))
        || r.review_status === 'APPROVED'
      ).length
    : (runStatus?.total_approved ?? campaign.total_approved)

  const totalHumanReview = hasResults
    ? _rows.filter(r => r.human_review_required).length
    : (runStatus?.total_review ?? campaign.total_review)

  const humanRejected  = _rows.filter(r => r.review_status === 'REJECTED').length
  const pendingReview  = _rows.filter(r => r.human_review_required && !r.review_status).length
  const totalCorrected = _rows.filter(r => (r as any).correction_attempts > 0).length

  const avgConfidence = (() => {
    if (!hasResults) return null
    const vals = _rows
      .map(r => r.pipeline_confidence)
      .filter((v): v is number => v != null && !isNaN(v))
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
  })()

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

        <div className="flex flex-col items-end gap-2">
          <button
            onClick={() => {
              setRunError('')
              runMutation.mutate()
            }}
            disabled={runMutation.isPending || isPolling || campaign.status === 'RUNNING'}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {runMutation.isPending ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Iniciando...
              </>
            ) : isPolling ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Procesando...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Ejecutar Campaña
              </>
            )}
          </button>

          {/* Progress strip */}
          {isPolling && runStatus && (() => {
            const pct = runStatus.total_targeted > 0
              ? Math.round((runStatus.total_processed / runStatus.total_targeted) * 100)
              : 0
            return (
              <div className="w-64 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-indigo-700">Procesando campaña...</span>
                  <span className="font-mono text-[10px] text-indigo-600 font-semibold">
                    {runStatus.total_processed}/{runStatus.total_targeted}
                  </span>
                </div>
                <div className="w-full bg-indigo-100 rounded-full h-2">
                  <div
                    className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(4, pct)}%` }}
                  />
                </div>
                <p className="text-[10px] text-indigo-400 mt-1 text-right">{pct}%</p>
              </div>
            )
          })()}
        </div>
      </div>

      {runError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded-lg">
          {runError}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
        <StatCard label="Objetivo"    value={fmt(totalTarget)}   icon={<Users className="w-4 h-4" />} />
        <StatCard label="Procesados"  value={fmt(totalProc)}     icon={<BarChart2 className="w-4 h-4" />} />
        <StatCard label="Aprobados"    value={fmt(totalApproved)}    color="text-emerald-600" icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="Rev. Humana"  value={fmt(totalHumanReview)} color="text-amber-600"   icon={<AlertTriangle className="w-4 h-4" />} />
        <StatCard label="Pass Rate"    value={passRate(totalApproved, totalProc)} color="text-indigo-600" icon={<BarChart2 className="w-4 h-4" />} />
        {humanRejected > 0 && (
          <StatCard label="Rechazados" value={humanRejected} color="text-red-600" icon={<XCircle className="w-4 h-4" />} />
        )}
        {pendingReview > 0 && (
          <StatCard label="Sin revisar" value={pendingReview} color="text-orange-600" icon={<Clock className="w-4 h-4" />} />
        )}
        {totalCorrected > 0 && (
          <StatCard label="Auto-corregidos" value={totalCorrected} color="text-violet-600" icon={<RotateCcw className="w-4 h-4" />} />
        )}
        {avgConfidence != null && (
          <StatCard
            label="Confianza Prom."
            value={`${Math.round(avgConfidence * 100)}%`}
            color={avgConfidence >= 0.80 ? 'text-emerald-600' : avgConfidence >= 0.65 ? 'text-amber-600' : 'text-red-600'}
            icon={<BarChart2 className="w-4 h-4" />}
          />
        )}
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
            {isPolling
              ? 'Procesando... los resultados aparecerán aquí al finalizar.'
              : 'No hay resultados aún. Ejecuta la campaña para generar resultados.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Cliente</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Ruta</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Segmento</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Riesgo</th>
                  <th className="text-right px-4 py-2 font-medium text-slate-500">DTI</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Producto</th>
                  <th className="text-left px-4 py-2 font-medium text-slate-500">Cumplimiento</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-500">Rev. Humana</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-500">Acción</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-500">Correc.</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-500">Confianza</th>
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
                      <RouteBadge route={r.pipeline_route ?? 'STANDARD'} />
                    </td>
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
                    <td className="px-4 py-2 text-center">
                      <ReviewActions
                        row={r}
                        campaignId={campaignId}
                        onDone={() => refetchResults()}
                      />
                    </td>
                    <td className="px-4 py-2 text-center">
                      {(r as any).correction_attempts > 0 ? (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-violet-600 bg-violet-50 px-1.5 py-0.5 rounded">
                          <RotateCcw className="w-2.5 h-2.5" />
                          {(r as any).correction_attempts}x
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <ConfidenceBadge value={r.pipeline_confidence} />
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
