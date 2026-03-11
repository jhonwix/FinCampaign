interface BadgeProps {
  value: string
}

const SEGMENT_COLORS: Record<string, string> = {
  'SUPER-PRIME': 'bg-emerald-100 text-emerald-800',
  'PRIME': 'bg-blue-100 text-blue-800',
  'NEAR-PRIME': 'bg-yellow-100 text-yellow-800',
  'SUBPRIME': 'bg-orange-100 text-orange-800',
  'DEEP-SUBPRIME': 'bg-red-100 text-red-800',
}

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-emerald-100 text-emerald-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
}

const VERDICT_COLORS: Record<string, string> = {
  PASS: 'bg-emerald-100 text-emerald-800',
  REVIEW: 'bg-yellow-100 text-yellow-800',
  FAIL: 'bg-red-100 text-red-800',
}

function getColor(value: string): string {
  return (
    SEGMENT_COLORS[value] ??
    RISK_COLORS[value] ??
    VERDICT_COLORS[value] ??
    'bg-slate-100 text-slate-700'
  )
}

export function Badge({ value }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${getColor(value)}`}
    >
      {value}
    </span>
  )
}

export function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 740
      ? 'bg-emerald-100 text-emerald-800'
      : score >= 670
      ? 'bg-blue-100 text-blue-800'
      : score >= 620
      ? 'bg-yellow-100 text-yellow-800'
      : score >= 580
      ? 'bg-orange-100 text-orange-800'
      : 'bg-red-100 text-red-800'

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {score}
    </span>
  )
}
