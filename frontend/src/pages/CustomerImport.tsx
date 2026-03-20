/**
 * CustomerImport — Primera pantalla del flujo de campañas masivas.
 *
 * Flujo: IDLE → PARSED (validación client-side) → IMPORTING → DONE
 *
 * El usuario:
 *   1. Descarga la plantilla CSV (opcional)
 *   2. Arrastra o selecciona su archivo
 *   3. Ve la distribución por segmento ANTES de importar
 *   4. Confirma → los clientes se cargan en PostgreSQL
 *   5. Redirige a crear campaña
 */

import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload, FileText, CheckCircle2, XCircle, AlertCircle,
  Download, ArrowRight, RotateCcw, Users, ChevronDown, ChevronUp,
} from 'lucide-react'
import { api } from '../api/client'
import type { ImportResult } from '../api/types'

/* ─── CSV template ────────────────────────────────────────────────────────── */
const TEMPLATE_HEADERS =
  'id_number,name,age,monthly_income,monthly_debt,credit_score,late_payments,credit_utilization,products_of_interest,existing_products'
const TEMPLATE_EXAMPLE = [
  '1000000001,Carlos García López,35,4500.00,810.00,725,0,22.5,credito hipotecario,',
  '1000000002,María Rodríguez Pérez,28,3200.00,640.00,685,1,38.0,tarjeta de credito,vehiculo credito personal',
  '1000000003,Juan Torres Gómez,42,2500.00,875.00,640,2,55.0,credito personal,hipotecario',
  '1000000004,Ana Martínez Silva,31,5200.00,520.00,760,0,15.0,credito vehiculo,vehiculo',
].join('\n')

function downloadTemplate() {
  const content = `${TEMPLATE_HEADERS}\n${TEMPLATE_EXAMPLE}\n`
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'plantilla_clientes.csv'; a.click()
  URL.revokeObjectURL(url)
}

/* ─── Types ───────────────────────────────────────────────────────────────── */
interface ParsedRow {
  id_number: string; name: string; age: number; monthly_income: number; monthly_debt: number
  credit_score: number; late_payments: number; credit_utilization: number
  products_of_interest: string; existing_products: string
}
interface RowError { row: number; name: string; errors: string[] }
interface ParseResult {
  valid: ParsedRow[]; errors: RowError[]; total: number
  segmentDist: Record<string, number>
}

/* ─── Helpers ─────────────────────────────────────────────────────────────── */
const REQUIRED = [
  'id_number','name','age','monthly_income','monthly_debt',
  'credit_score','late_payments','credit_utilization','products_of_interest',
]

function getSegment(score: number): string {
  if (score >= 750) return 'SUPER-PRIME'
  if (score >= 675) return 'PRIME'
  if (score >= 625) return 'NEAR-PRIME'
  if (score >= 580) return 'SUBPRIME'
  return 'DEEP-SUBPRIME'
}

const SEG_META: Record<string, { color: string; bg: string; bar: string }> = {
  'SUPER-PRIME':  { color: '#6366f1', bg: '#eef2ff', bar: '#6366f1' },
  'PRIME':        { color: '#0891b2', bg: '#ecfeff', bar: '#0891b2' },
  'NEAR-PRIME':   { color: '#059669', bg: '#ecfdf5', bar: '#059669' },
  'SUBPRIME':     { color: '#d97706', bg: '#fffbeb', bar: '#d97706' },
  'DEEP-SUBPRIME':{ color: '#dc2626', bg: '#fef2f2', bar: '#dc2626' },
}

function parseCSVText(text: string): ParseResult {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().split('\n')
  if (lines.length < 2) return { valid: [], errors: [], total: 0, segmentDist: {} }

  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, '').toLowerCase())
  const missing = REQUIRED.filter(r => !headers.includes(r))
  if (missing.length > 0) {
    return {
      valid: [], total: 0, segmentDist: {},
      errors: [{ row: 1, name: '—', errors: [`Columnas faltantes: ${missing.join(', ')}`] }],
    }
  }

  const valid: ParsedRow[] = []
  const errors: RowError[] = []
  const segDist: Record<string, number> = {}

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue
    const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
    const row: Record<string, string> = {}
    headers.forEach((h, idx) => { row[h] = vals[idx] ?? '' })

    const rowErrs: string[] = []
    const id_number = (row['id_number'] ?? '').trim()
    const name = row['name'] ?? ''
    const age = parseInt(row['age'])
    const monthly_income = parseFloat(row['monthly_income'])
    const monthly_debt = parseFloat(row['monthly_debt'])
    const credit_score = parseInt(row['credit_score'])
    const late_payments = parseInt(row['late_payments'])
    const credit_utilization = parseFloat(row['credit_utilization'])
    const products_of_interest = row['products_of_interest'] ?? ''

    if (!id_number)                               rowErrs.push('Cédula: requerida')
    else if (id_number.length < 4)               rowErrs.push('Cédula: mínimo 4 caracteres')
    if (name.length < 2)                          rowErrs.push('Nombre muy corto (mín 2 caracteres)')
    if (isNaN(age) || age < 18 || age > 100)      rowErrs.push('Edad: 18–100')
    if (isNaN(monthly_income) || monthly_income <= 0) rowErrs.push('Ingreso mensual debe ser > 0')
    if (isNaN(monthly_debt) || monthly_debt < 0)  rowErrs.push('Deuda mensual no puede ser negativa')
    if (isNaN(credit_score) || credit_score < 300 || credit_score > 850)
                                                   rowErrs.push('Score: 300–850')
    if (isNaN(late_payments) || late_payments < 0) rowErrs.push('Pagos tarde no puede ser negativo')
    if (isNaN(credit_utilization) || credit_utilization < 0 || credit_utilization > 100)
                                                   rowErrs.push('Utilización: 0–100%')
    if (products_of_interest.length < 3)          rowErrs.push('Producto de interés muy corto')

    if (rowErrs.length > 0) {
      errors.push({ row: i + 1, name: name || `fila ${i + 1}`, errors: rowErrs })
    } else {
      const seg = getSegment(credit_score)
      segDist[seg] = (segDist[seg] ?? 0) + 1
      valid.push({ id_number, name, age, monthly_income, monthly_debt, credit_score, late_payments, credit_utilization, products_of_interest, existing_products: (row['existing_products'] ?? '').trim() })
    }
  }

  return { valid, errors, total: valid.length + errors.length, segmentDist: segDist }
}

/* ─── Sub-components ──────────────────────────────────────────────────────── */
function StepDot({ n, active, done }: { n: number; active: boolean; done: boolean }) {
  return (
    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
      done ? 'bg-emerald-500 text-white' : active ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'
    }`}>
      {done ? '✓' : n}
    </div>
  )
}

function SegmentBar({ dist, total }: { dist: Record<string, number>; total: number }) {
  const order = ['SUPER-PRIME','PRIME','NEAR-PRIME','SUBPRIME','DEEP-SUBPRIME']
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
        Distribución por segmento
      </p>
      <div className="space-y-2">
        {order.map(seg => {
          const count = dist[seg] ?? 0
          if (count === 0) return null
          const pct = total > 0 ? Math.round((count / total) * 100) : 0
          const m = SEG_META[seg]
          return (
            <div key={seg} className="flex items-center gap-3">
              <span className="text-xs w-28 text-slate-600 font-medium shrink-0">{seg}</span>
              <div className="flex-1 bg-slate-100 rounded-full h-2">
                <div
                  className="h-2 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: m.bar }}
                />
              </div>
              <span className="text-xs text-slate-500 w-14 text-right shrink-0">
                {count} <span className="text-slate-400">({pct}%)</span>
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ─── Main component ──────────────────────────────────────────────────────── */
type Stage = 'idle' | 'parsed' | 'importing' | 'done'

export function CustomerImport() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [stage, setStage] = useState<Stage>('idle')
  const [fileName, setFileName] = useState('')
  const [fileSize, setFileSize] = useState(0)
  const [parsed, setParsed] = useState<ParseResult | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const { mutateAsync: doImport, isPending } = useMutation({
    mutationFn: api.importCustomers,
    onSuccess: (data) => {
      setResult(data)
      setStage('done')
      qc.invalidateQueries({ queryKey: ['customers'] })
    },
  })

  const processFile = useCallback((file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      alert('Solo se aceptan archivos .csv')
      return
    }
    setFileName(file.name)
    setFileSize(file.size)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      const pr = parseCSVText(text)
      setParsed(pr)
      setStage('parsed')
      setShowErrors(false)
      setShowPreview(false)
    }
    reader.readAsText(file, 'utf-8')
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
  }, [processFile])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) processFile(file)
    e.target.value = ''
  }

  const handleImport = async () => {
    if (!fileInputRef.current) return
    const input = document.createElement('input')
    input.type = 'file'; input.accept = '.csv'
    // Re-read from parsed.valid by re-uploading the file
    // We use a hidden file input approach: re-trigger upload with cached file
    // Instead, store the file object in state
  }

  // Store file reference for actual upload
  const fileRef = useRef<File | null>(null)
  const handleFileSelect = useCallback((file: File) => {
    fileRef.current = file
    processFile(file)
  }, [processFile])

  const handleDropWithRef = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileSelect(file)
  }, [handleFileSelect])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileSelect(file)
    e.target.value = ''
  }

  const confirmImport = async () => {
    if (!fileRef.current) return
    setStage('importing')
    try {
      await doImport(fileRef.current)
    } catch {
      setStage('parsed')
    }
  }

  const reset = () => {
    setStage('idle'); setParsed(null); setResult(null)
    setFileName(''); fileRef.current = null
  }

  /* ── render helpers ── */
  const step = stage === 'idle' ? 1 : stage === 'parsed' || stage === 'importing' ? 2 : 3
  const fmtKB = (b: number) => b < 1024 ? `${b} B` : b < 1024*1024 ? `${(b/1024).toFixed(1)} KB` : `${(b/1024/1024).toFixed(1)} MB`

  return (
    <div className="max-w-4xl mx-auto">

      {/* ── Header ── */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="bg-indigo-600 p-2 rounded-lg">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Importar Clientes</h1>
            <p className="text-sm text-slate-500">Paso 1 de 3 — Carga masiva para campañas</p>
          </div>
        </div>
      </div>

      {/* ── Step indicator ── */}
      <div className="flex items-center gap-2 mb-8">
        {[
          [1, 'Cargar CSV'],
          [2, 'Validar y Previsualizar'],
          [3, 'Importar'],
        ].map(([n, label], idx) => (
          <div key={idx} className="flex items-center gap-2">
            {idx > 0 && <div className={`h-px w-8 transition-colors ${step > (n as number) ? 'bg-emerald-400' : step === (n as number) ? 'bg-indigo-400' : 'bg-slate-200'}`} />}
            <StepDot n={n as number} active={step === (n as number)} done={step > (n as number)} />
            <span className={`text-sm ${step === n ? 'font-semibold text-slate-800' : 'text-slate-400'}`}>{label as string}</span>
          </div>
        ))}
      </div>

      {/* ══ STAGE: IDLE ══ */}
      {stage === 'idle' && (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDropWithRef}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all duration-200 ${
              dragging
                ? 'border-indigo-500 bg-indigo-50 scale-[1.01]'
                : 'border-slate-300 bg-slate-50 hover:border-indigo-400 hover:bg-indigo-50/40'
            }`}
          >
            <div className={`mx-auto w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors ${dragging ? 'bg-indigo-100' : 'bg-slate-100'}`}>
              <Upload className={`w-8 h-8 transition-colors ${dragging ? 'text-indigo-600' : 'text-slate-400'}`} />
            </div>
            <p className="text-base font-semibold text-slate-700 mb-1">
              {dragging ? 'Suelta el archivo aquí' : 'Arrastra tu CSV aquí'}
            </p>
            <p className="text-sm text-slate-400">o haz clic para seleccionar · máx 10 MB · 10,000 filas</p>
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleInputChange} />
          </div>

          {/* Format + template */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 flex gap-8">
            <div className="flex-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Columnas requeridas</p>
              <div className="grid grid-cols-2 gap-1.5">
                {REQUIRED.map(col => (
                  <div key={col} className="flex items-center gap-1.5 text-xs text-slate-600">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                    <code className="font-mono">{col}</code>
                  </div>
                ))}
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
                  <code className="font-mono">existing_products</code>
                  <span className="italic">(opcional)</span>
                </div>
              </div>
            </div>
            <div className="flex flex-col justify-between items-end">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Score → Segmento</p>
                <div className="space-y-1">
                  {[['750–850','SUPER-PRIME','#6366f1'],['675–749','PRIME','#0891b2'],['625–674','NEAR-PRIME','#059669'],['580–624','SUBPRIME','#d97706'],['300–579','DEEP-SUBPRIME','#dc2626']].map(([range, seg, color]) => (
                    <div key={seg} className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-slate-400 w-16">{range}</span>
                      <span className="font-semibold" style={{ color }}>{seg}</span>
                    </div>
                  ))}
                </div>
              </div>
              <button
                onClick={e => { e.stopPropagation(); downloadTemplate() }}
                className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors mt-4"
              >
                <Download className="w-4 h-4" />
                Descargar plantilla
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ STAGE: PARSED ══ */}
      {(stage === 'parsed' || stage === 'importing') && parsed && (
        <div className="space-y-4">
          {/* File info */}
          <div className="bg-white rounded-xl border border-slate-200 px-5 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-slate-100 p-2.5 rounded-lg">
                <FileText className="w-5 h-5 text-slate-500" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">{fileName}</p>
                <p className="text-xs text-slate-400">{fmtKB(fileSize)} · {parsed.total} filas detectadas</p>
              </div>
            </div>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors">
              <RotateCcw className="w-3.5 h-3.5" /> Cambiar archivo
            </button>
          </div>

          {/* Validation summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-2xl font-bold text-emerald-700">{parsed.valid.length}</p>
                <p className="text-xs text-emerald-600 font-medium">Filas válidas</p>
                <p className="text-xs text-emerald-500 mt-0.5">Listas para importar</p>
              </div>
            </div>
            <div className={`border rounded-xl p-4 flex items-start gap-3 ${parsed.errors.length > 0 ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'}`}>
              <XCircle className={`w-5 h-5 mt-0.5 shrink-0 ${parsed.errors.length > 0 ? 'text-red-400' : 'text-slate-300'}`} />
              <div>
                <p className={`text-2xl font-bold ${parsed.errors.length > 0 ? 'text-red-600' : 'text-slate-400'}`}>{parsed.errors.length}</p>
                <p className={`text-xs font-medium ${parsed.errors.length > 0 ? 'text-red-500' : 'text-slate-400'}`}>Errores de validación</p>
                <p className={`text-xs mt-0.5 ${parsed.errors.length > 0 ? 'text-red-400' : 'text-slate-300'}`}>Se saltarán al importar</p>
              </div>
            </div>
            <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-2xl font-bold text-slate-600">{parsed.total}</p>
                <p className="text-xs text-slate-500 font-medium">Total filas CSV</p>
                <p className="text-xs text-slate-400 mt-0.5">Sin contar header</p>
              </div>
            </div>
          </div>

          {/* Segment distribution */}
          {parsed.valid.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <SegmentBar dist={parsed.segmentDist} total={parsed.valid.length} />
            </div>
          )}

          {/* Errors accordion */}
          {parsed.errors.length > 0 && (
            <div className="bg-white rounded-xl border border-red-100 overflow-hidden">
              <button
                onClick={() => setShowErrors(v => !v)}
                className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <span>Ver {parsed.errors.length} errores de validación</span>
                {showErrors ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showErrors && (
                <div className="border-t border-red-100 max-h-48 overflow-y-auto">
                  {parsed.errors.map((e, i) => (
                    <div key={i} className="px-5 py-2.5 border-b border-red-50 last:border-0">
                      <p className="text-xs font-semibold text-slate-700">Fila {e.row} — {e.name}</p>
                      {e.errors.map((err, j) => (
                        <p key={j} className="text-xs text-red-500 mt-0.5">• {err}</p>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Preview table accordion */}
          {parsed.valid.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <button
                onClick={() => setShowPreview(v => !v)}
                className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <span>Vista previa — primeras {Math.min(8, parsed.valid.length)} filas válidas</span>
                {showPreview ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showPreview && (
                <div className="overflow-x-auto border-t border-slate-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-100">
                        {['Cédula','Nombre','Edad','Ingreso','Deuda','Score','Segmento','Retrasos','Util%','Producto','Prod. actuales'].map(h => (
                          <th key={h} className="text-left px-3 py-2 font-semibold text-slate-500 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {parsed.valid.slice(0, 8).map((r, i) => {
                        const seg = getSegment(r.credit_score)
                        const m = SEG_META[seg]
                        return (
                          <tr key={i} className="hover:bg-slate-50">
                            <td className="px-3 py-2 font-mono text-xs text-slate-500">{r.id_number}</td>
                            <td className="px-3 py-2 font-medium text-slate-700 max-w-32 truncate">{r.name}</td>
                            <td className="px-3 py-2 text-slate-500">{r.age}</td>
                            <td className="px-3 py-2 text-slate-600">${r.monthly_income.toLocaleString()}</td>
                            <td className="px-3 py-2 text-slate-500">${r.monthly_debt.toLocaleString()}</td>
                            <td className="px-3 py-2 font-mono font-bold text-slate-700">{r.credit_score}</td>
                            <td className="px-3 py-2">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ color: m.color, backgroundColor: m.bg }}>
                                {seg}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-500">{r.late_payments}</td>
                            <td className="px-3 py-2 text-slate-500">{r.credit_utilization}%</td>
                            <td className="px-3 py-2 text-slate-400 max-w-28 truncate">{r.products_of_interest}</td>
                            <td className="px-3 py-2 text-slate-400 max-w-24 truncate">{r.existing_products || '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <button onClick={reset} className="text-sm text-slate-400 hover:text-slate-600 transition-colors">
              ← Cancelar
            </button>
            <button
              onClick={confirmImport}
              disabled={parsed.valid.length === 0 || stage === 'importing'}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-xl transition-colors"
            >
              {stage === 'importing' ? (
                <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Importando…</>
              ) : (
                <>Importar {parsed.valid.length} clientes <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ══ STAGE: DONE ══ */}
      {stage === 'done' && result && (
        <div className="space-y-4">
          {/* Success banner */}
          <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 flex items-start gap-4">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-lg font-bold text-emerald-800">Importación completada</p>
              <p className="text-sm text-emerald-600 mt-0.5">
                {result.imported} clientes nuevos agregados a la base de datos
              </p>
            </div>
          </div>

          {/* Result stats */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Importados', value: result.imported, color: 'text-emerald-600', bg: 'bg-emerald-50' },
              { label: 'Duplicados saltados', value: result.duplicates, color: 'text-amber-600', bg: 'bg-amber-50' },
              { label: 'Errores validación', value: result.validation_errors.length, color: 'text-red-500', bg: 'bg-red-50' },
              { label: 'Total filas CSV', value: result.total_rows, color: 'text-slate-600', bg: 'bg-slate-50' },
            ].map(({ label, value, color, bg }) => (
              <div key={label} className={`${bg} rounded-xl p-4 text-center`}>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-slate-500 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* CTAs */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={reset}
              className="flex items-center gap-2 px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-xl transition-colors"
            >
              <Upload className="w-4 h-4" /> Importar otro archivo
            </button>
            <button
              onClick={() => navigate('/campaigns/new')}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl transition-colors"
            >
              Crear campaña ahora <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 px-5 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-600 text-sm font-medium rounded-xl transition-colors"
            >
              Ver clientes
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
