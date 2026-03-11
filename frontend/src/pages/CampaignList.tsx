import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Play, CheckCircle, Clock, FileText } from 'lucide-react'
import { api } from '../api/client'
import type { CampaignRecord, CampaignStatus, CampaignType } from '../api/types'

const TYPE_COLORS: Record<CampaignType, string> = {
  HIPOTECARIO: 'bg-blue-100 text-blue-700',
  VEHICULOS:   'bg-purple-100 text-purple-700',
  CDT:         'bg-emerald-100 text-emerald-700',
  PERSONAL:    'bg-amber-100 text-amber-700',
  TARJETA:     'bg-rose-100 text-rose-700',
}

const STATUS_ICON: Record<CampaignStatus, React.ReactNode> = {
  DRAFT:     <FileText className="w-3.5 h-3.5" />,
  RUNNING:   <Play className="w-3.5 h-3.5" />,
  COMPLETED: <CheckCircle className="w-3.5 h-3.5" />,
}

const STATUS_COLORS: Record<CampaignStatus, string> = {
  DRAFT:     'bg-slate-100 text-slate-600',
  RUNNING:   'bg-yellow-100 text-yellow-700',
  COMPLETED: 'bg-emerald-100 text-emerald-700',
}

function TypeBadge({ type }: { type: CampaignType }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[type]}`}>
      {type}
    </span>
  )
}

function StatusBadge({ status }: { status: CampaignStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status]}`}>
      {STATUS_ICON[status]}
      {status}
    </span>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function CampaignList() {
  const navigate = useNavigate()

  const { data: campaigns, isLoading, error } = useQuery<CampaignRecord[]>({
    queryKey: ['campaigns'],
    queryFn: api.listCampaigns,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
        Error cargando campañas: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Campañas</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {campaigns?.length ?? 0} campaña{campaigns?.length !== 1 ? 's' : ''} registrada{campaigns?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => navigate('/campaigns/new')}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nueva Campaña
        </button>
      </div>

      {/* Table */}
      {!campaigns || campaigns.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <FileText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No hay campañas todavía.</p>
          <button
            onClick={() => navigate('/campaigns/new')}
            className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Crear primera campaña
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 font-medium text-slate-600 w-10">#</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Nombre</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Tipo</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Última Ejecución</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Objetivo</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Aprobados</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Revisión</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/campaigns/${c.id}`)}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-slate-400">{c.id}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{c.name}</td>
                  <td className="px-4 py-3">
                    <TypeBadge type={c.type as CampaignType} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status as CampaignStatus} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {formatDate(c.last_run_at)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-700">{c.total_targeted}</td>
                  <td className="px-4 py-3 text-right text-emerald-600 font-medium">{c.total_approved}</td>
                  <td className="px-4 py-3 text-right text-amber-600 font-medium">{c.total_review}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
