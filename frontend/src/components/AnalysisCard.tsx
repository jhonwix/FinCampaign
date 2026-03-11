import { CheckCircle, AlertTriangle, XCircle, Shield, Megaphone, TrendingUp } from 'lucide-react'
import type { AnalysisResult } from '../api/types'
import { Badge } from './Badge'

interface Props {
  result: AnalysisResult
}

function VerdictIcon({ verdict }: { verdict: string }) {
  if (verdict === 'PASS') return <CheckCircle className="w-5 h-5 text-emerald-500" />
  if (verdict === 'REVIEW') return <AlertTriangle className="w-5 h-5 text-yellow-500" />
  return <XCircle className="w-5 h-5 text-red-500" />
}

export function AnalysisCard({ result }: Props) {
  const { risk_assessment: risk, campaign, compliance } = result

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-400 font-mono">{result.request_id}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            Processed in {(result.processing_time_ms / 1000).toFixed(1)}s
          </p>
        </div>
        <div className="flex gap-2">
          <Badge value={risk.segment} />
          <Badge value={compliance.overall_verdict} />
        </div>
      </div>

      {/* Risk Assessment */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-slate-600" />
          <h3 className="text-sm font-semibold text-slate-700">Risk Assessment</h3>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <p className="text-xs text-slate-500">Risk Level</p>
            <Badge value={risk.risk_level} />
          </div>
          <div>
            <p className="text-xs text-slate-500">DTI Ratio</p>
            <p className="text-sm font-semibold text-slate-800">{risk.dti.toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Eligible</p>
            <p className={`text-sm font-semibold ${risk.eligible_for_credit ? 'text-emerald-600' : 'text-red-600'}`}>
              {risk.eligible_for_credit ? 'Yes' : 'No'}
            </p>
          </div>
        </div>
        {risk.recommended_products.length > 0 && (
          <div className="mb-3">
            <p className="text-xs text-slate-500 mb-1">Recommended Products</p>
            <div className="flex flex-wrap gap-1">
              {risk.recommended_products.map((p) => (
                <span key={p} className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full">{p}</span>
              ))}
            </div>
          </div>
        )}
        <p className="text-xs text-slate-600 leading-relaxed">{risk.rationale}</p>
      </div>

      {/* Campaign */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center gap-2 mb-3">
          <Megaphone className="w-4 h-4 text-slate-600" />
          <h3 className="text-sm font-semibold text-slate-700">Campaign</h3>
          {campaign.product_name !== 'N/A' && (
            <span className="ml-auto text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
              {campaign.product_name}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-700 leading-relaxed mb-3 italic">"{campaign.campaign_message}"</p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-slate-500">Channel</p>
            <p className="font-medium text-slate-700">{campaign.channel}</p>
          </div>
          <div>
            <p className="text-slate-500">Rates</p>
            <p className="font-medium text-slate-700">{campaign.rates}</p>
          </div>
          <div>
            <p className="text-slate-500">CTA</p>
            <p className="font-medium text-slate-700">{campaign.cta}</p>
          </div>
        </div>
        {campaign.key_benefits && campaign.key_benefits.length > 0 && (
          <ul className="mt-3 space-y-1">
            {campaign.key_benefits.map((b) => (
              <li key={b} className="text-xs text-slate-600 flex items-start gap-1.5">
                <span className="text-emerald-500 mt-0.5">✓</span> {b}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Compliance */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-slate-600" />
          <h3 className="text-sm font-semibold text-slate-700">Compliance</h3>
          <div className="ml-auto flex items-center gap-1.5">
            <VerdictIcon verdict={compliance.overall_verdict} />
            <span className="text-sm font-semibold text-slate-700">{compliance.overall_verdict}</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mb-3">
          {(['fair_lending', 'apr_disclosure', 'messaging', 'channel'] as const).map((key) => (
            <div key={key} className="flex items-center justify-between bg-white rounded-lg px-3 py-1.5 border border-slate-200">
              <span className="text-xs text-slate-500 capitalize">{key.replace('_', ' ')}</span>
              <Badge value={compliance[key]} />
            </div>
          ))}
        </div>
        {compliance.warnings.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-yellow-800 mb-1">Warnings</p>
            {compliance.warnings.map((w) => (
              <p key={w} className="text-xs text-yellow-700">• {w}</p>
            ))}
          </div>
        )}
        {compliance.human_review_required && (
          <div className="mt-2 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
            <p className="text-xs font-semibold text-red-700">Human underwriter review required</p>
          </div>
        )}
      </div>

      {/* GCS link */}
      <p className="text-xs text-slate-400 font-mono truncate">
        Stored: {result.stored_at}
      </p>
    </div>
  )
}
