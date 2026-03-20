import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Users } from 'lucide-react'
import { api } from '../api/client'
import type { CampaignCreate, CampaignType, CampaignIntent, SegmentName, Customer } from '../api/types'
import { useLookups } from '../api/useLookups'

// ── Segment score ranges ─────────────────────────────────────────────────────
const SEGMENT_RANGES: Record<SegmentName, [number, number]> = {
  'SUPER-PRIME':  [740, 850],
  'PRIME':        [670, 739],
  'NEAR-PRIME':   [620, 669],
  'SUBPRIME':     [580, 619],
  'DEEP-SUBPRIME':[300, 579],
}

const ALL_SEGMENTS: SegmentName[] = [
  'SUPER-PRIME', 'PRIME', 'NEAR-PRIME', 'SUBPRIME', 'DEEP-SUBPRIME',
]

// ── Type presets ─────────────────────────────────────────────────────────────
type Preset = {
  product_name: string
  min_credit_score: number
  max_credit_score: number
  min_monthly_income: number
  max_dti: number
  max_late_payments: number
  max_credit_utilization: number
  term_months: number
  max_amount: number
}

const PRESETS: Record<CampaignType, Preset> = {
  HIPOTECARIO: { product_name: 'Crédito Hipotecario', min_credit_score: 680, max_credit_score: 850, min_monthly_income: 3000, max_dti: 40, max_late_payments: 1, max_credit_utilization: 50, term_months: 360, max_amount: 500000 },
  VEHICULOS:   { product_name: 'Crédito Vehículo',    min_credit_score: 640, max_credit_score: 850, min_monthly_income: 2000, max_dti: 45, max_late_payments: 2, max_credit_utilization: 60, term_months: 72,  max_amount: 80000  },
  CDT:         { product_name: 'CDT',                  min_credit_score: 300, max_credit_score: 850, min_monthly_income: 500,  max_dti: 100, max_late_payments: 6, max_credit_utilization: 100, term_months: 12, max_amount: 50000  },
  PERSONAL:    { product_name: 'Crédito Personal',     min_credit_score: 600, max_credit_score: 850, min_monthly_income: 1500, max_dti: 50, max_late_payments: 3, max_credit_utilization: 70, term_months: 60,  max_amount: 30000  },
  TARJETA:     { product_name: 'Tarjeta de Crédito',   min_credit_score: 620, max_credit_score: 850, min_monthly_income: 1200, max_dti: 45, max_late_payments: 2, max_credit_utilization: 60, term_months: 0,   max_amount: 10000  },
}

// UI metadata for intent cards — label/description/color stay here, values come from /api/lookups
const INTENT_META: Record<string, { label: string; description: string; color: string }> = {
  NEW:     { label: 'Adquisición', description: 'Clientes que NO tienen el producto. El agente excluirá quienes ya lo posean.', color: 'indigo' },
  RENEWAL: { label: 'Renovación',  description: 'Clientes que YA tienen el producto. El agente generará mensajes de fidelización.', color: 'emerald' },
  CROSS:   { label: 'Cross-sell',  description: 'Todos los clientes calificados, sin importar si ya tienen el producto.', color: 'amber' },
}

const BLANK: CampaignCreate = {
  name: '',
  type: 'PERSONAL',
  description: '',
  target_segments: [],
  min_credit_score: 300,
  max_credit_score: 850,
  min_monthly_income: 0,
  max_dti: 100,
  max_late_payments: 10,
  max_credit_utilization: 100,
  product_name: '',
  rate_min: 0,
  rate_max: 100,
  max_amount: 0,
  term_months: 0,
  channel: 'Email',
  message_tone: 'Amigable',
  cta_text: '',
  campaign_intent: 'NEW',
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function customerSegment(score: number): SegmentName {
  for (const [seg, [lo, hi]] of Object.entries(SEGMENT_RANGES) as [SegmentName, [number, number]][]) {
    if (score >= lo && score <= hi) return seg
  }
  return 'DEEP-SUBPRIME'
}

function qualifies(c: Customer, form: CampaignCreate): boolean {
  const dti = c.monthly_income > 0 ? (c.monthly_debt / c.monthly_income) * 100 : 0
  if (c.credit_score < form.min_credit_score) return false
  if (c.credit_score > form.max_credit_score) return false
  if (c.monthly_income < form.min_monthly_income) return false
  if (dti > form.max_dti) return false
  if (c.late_payments > form.max_late_payments) return false
  if (c.credit_utilization > form.max_credit_utilization) return false
  if (form.target_segments.length > 0) {
    if (!form.target_segments.includes(customerSegment(c.credit_score))) return false
  }
  return true
}

// ── Form field components ────────────────────────────────────────────────────
function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-600 mb-1">{children}</label>
}

function Input({ className = '', onFocus, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 ${className}`}
      onFocus={(e) => {
        if (e.target.type === 'number') e.target.select()
        onFocus?.(e)
      }}
      {...props}
    />
  )
}

function Select({ className = '', ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white ${className}`}
      {...props}
    />
  )
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2 mb-4">
      {children}
    </h2>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export function CreateCampaign() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const lookups = useLookups()
  const [form, setForm] = useState<CampaignCreate>({ ...BLANK, ...PRESETS['PERSONAL'] })
  const [error, setError] = useState('')

  const { data: customersData } = useQuery({
    queryKey: ['customers'],
    queryFn: api.getCustomers,
  })

  const qualifying = useMemo(() => {
    if (!customersData?.customers) return { count: 0, total: 0 }
    const total = customersData.customers.length
    const count = customersData.customers.filter((c) => qualifies(c, form)).length
    return { count, total }
  }, [customersData, form])

  const mutation = useMutation({
    mutationFn: api.createCampaign,
    onSuccess: (campaign) => {
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      navigate(`/campaigns/${campaign.id}`)
    },
    onError: (e: Error) => setError(e.message),
  })

  function set<K extends keyof CampaignCreate>(key: K, value: CampaignCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function handleTypeChange(type: CampaignType) {
    setForm((f) => {
      const prevPresetName = PRESETS[f.type as CampaignType]?.product_name ?? ''
      const userCustomized = f.product_name !== prevPresetName
      return {
        ...f,
        type,
        ...PRESETS[type],
        // Keep user's custom product_name if they deviated from the previous preset
        product_name: userCustomized ? f.product_name : PRESETS[type].product_name,
      }
    })
  }

  function toggleSegment(seg: SegmentName) {
    setForm((f) => {
      const segs = f.target_segments.includes(seg)
        ? f.target_segments.filter((s) => s !== seg)
        : [...f.target_segments, seg]
      return { ...f, target_segments: segs }
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) { setError('El nombre es requerido'); return }
    setError('')
    mutation.mutate(form)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {/* Back */}
      <button
        onClick={() => navigate('/campaigns')}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ChevronLeft className="w-4 h-4" />
        Campañas
      </button>

      <h1 className="text-xl font-bold text-slate-900">Nueva Campaña</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* Section 1: Identity */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <SectionHeader>1 — Identidad</SectionHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label>Nombre *</Label>
              <Input
                required
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="Ej: Campaña Hipotecaria Q2"
              />
            </div>

            <div>
              <Label>Tipo de campaña</Label>
              <Select
                value={form.type}
                onChange={(e) => handleTypeChange(e.target.value as CampaignType)}
              >
                {(lookups.campaign_type.length ? lookups.campaign_type : ['HIPOTECARIO', 'VEHICULOS', 'CDT', 'PERSONAL', 'TARJETA']).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </div>

            <div>
              <Label>Canal</Label>
              <Select value={form.channel} onChange={(e) => set('channel', e.target.value)}>
                {(lookups.campaign_channel.length ? lookups.campaign_channel : ['Email', 'SMS', 'Push', 'WhatsApp']).map((ch) => (
                  <option key={ch}>{ch}</option>
                ))}
              </Select>
            </div>

            <div>
              <Label>Tono del mensaje</Label>
              <Select value={form.message_tone} onChange={(e) => set('message_tone', e.target.value)}>
                {(lookups.message_tone.length ? lookups.message_tone : ['Amigable', 'Profesional', 'Urgente', 'Premium', 'Empatico']).map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            </div>

            <div>
              <Label>Texto del CTA</Label>
              <Input
                value={form.cta_text}
                onChange={(e) => set('cta_text', e.target.value)}
                placeholder="Ej: Solicita ahora"
              />
            </div>

            <div className="col-span-2">
              <Label>Descripción</Label>
              <textarea
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
                rows={2}
                className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                placeholder="Descripción opcional..."
              />
            </div>
          </div>
        </div>

        {/* Section 2: Intent */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <SectionHeader>2 — Intención de campaña</SectionHeader>
          <div className="grid grid-cols-3 gap-3">
            {(lookups.campaign_intent.length ? lookups.campaign_intent : ['NEW', 'RENEWAL', 'CROSS']).map((intentValue) => {
              const meta = INTENT_META[intentValue] ?? { label: intentValue, description: '', color: 'indigo' }
              const selected = form.campaign_intent === intentValue
              const colorMap: Record<string, string> = {
                indigo:  selected ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400'  : 'border-slate-200 hover:border-indigo-300',
                emerald: selected ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-400' : 'border-slate-200 hover:border-emerald-300',
                amber:   selected ? 'border-amber-500 bg-amber-50 ring-1 ring-amber-400'    : 'border-slate-200 hover:border-amber-300',
              }
              const dotMap: Record<string, string> = {
                indigo: 'bg-indigo-500', emerald: 'bg-emerald-500', amber: 'bg-amber-500',
              }
              return (
                <button
                  key={intentValue}
                  type="button"
                  onClick={() => set('campaign_intent', intentValue as CampaignIntent)}
                  className={`text-left p-4 rounded-xl border-2 transition-all cursor-pointer ${colorMap[meta.color]}`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotMap[meta.color]}`} />
                    <span className="text-sm font-semibold text-slate-800">{meta.label}</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-snug">{meta.description}</p>
                </button>
              )
            })}
          </div>
        </div>

        {/* Section 3: Audience */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <SectionHeader>3 — Audiencia</SectionHeader>

          {/* Live preview */}
          <div className="mb-5 flex items-center gap-2 bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-2.5 text-sm">
            <Users className="w-4 h-4 text-indigo-500 shrink-0" />
            <span className="text-indigo-700 font-medium">
              {qualifying.count} de {qualifying.total} clientes califican
            </span>
            <span className="text-indigo-400 text-xs">(filtro en tiempo real)</span>
          </div>

          {/* Segments */}
          <div className="mb-4">
            <Label>Segmentos objetivo (vacío = todos)</Label>
            <div className="flex flex-wrap gap-2 mt-1">
              {ALL_SEGMENTS.map((seg) => (
                <button
                  key={seg}
                  type="button"
                  onClick={() => toggleSegment(seg)}
                  className={`px-3 py-1 text-xs rounded-full border font-medium transition-colors ${
                    form.target_segments.includes(seg)
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-slate-600 border-slate-300 hover:border-indigo-400'
                  }`}
                >
                  {seg}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Score mínimo</Label>
              <Input
                type="number" min={300} max={850}
                value={form.min_credit_score}
                onChange={(e) => set('min_credit_score', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Score máximo</Label>
              <Input
                type="number" min={300} max={850}
                value={form.max_credit_score}
                onChange={(e) => set('max_credit_score', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Ingreso mensual mínimo ($)</Label>
              <Input
                type="number" min={0}
                value={form.min_monthly_income}
                onChange={(e) => set('min_monthly_income', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>DTI máximo (%)</Label>
              <Input
                type="number" min={0} max={100}
                value={form.max_dti}
                onChange={(e) => set('max_dti', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Pagos tardíos máximos</Label>
              <Input
                type="number" min={0}
                value={form.max_late_payments}
                onChange={(e) => set('max_late_payments', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Utilización máxima (%)</Label>
              <Input
                type="number" min={0} max={100}
                value={form.max_credit_utilization}
                onChange={(e) => set('max_credit_utilization', Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        {/* Section 4: Product */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <SectionHeader>4 — Producto</SectionHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label>Nombre del producto</Label>
              <Input
                value={form.product_name}
                onChange={(e) => set('product_name', e.target.value)}
                placeholder="Ej: Crédito Hipotecario"
              />
            </div>
            <div>
              <Label>Tasa mínima (%)</Label>
              <Input
                type="number" min={0} step={0.01}
                value={form.rate_min}
                onChange={(e) => set('rate_min', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Tasa máxima (%)</Label>
              <Input
                type="number" min={0} step={0.01}
                value={form.rate_max}
                onChange={(e) => set('rate_max', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Monto máximo ($)</Label>
              <Input
                type="number" min={0}
                value={form.max_amount}
                onChange={(e) => set('max_amount', Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Plazo (meses)</Label>
              <Input
                type="number" min={0}
                value={form.term_months}
                onChange={(e) => set('term_months', Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/campaigns')}
            className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="px-5 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? 'Guardando...' : 'Crear Campaña'}
          </button>
        </div>
      </form>
    </div>
  )
}
