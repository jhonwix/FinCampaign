import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

/* ─────────────────────── canvas ─────────────────────── */
const VW = 1200
const VH = 780
const NW  = 152
const NH  = 52

/* ─────────────────────── types ─────────────────────── */
type NK = 'user' | 'api' | 'orch' | 'hist'
        | 'risk' | 'camp' | 'edu'  | 'cond' | 'comp'
        | 'rag'  | 'gem'
        | 'db'   | 'gcs'

interface NodeDef { x: number; y: number; label: string; sub: string; group: string }
interface View    { id: string; label: string; title: string; desc: string; nodes: NK[]; edges: string[] }

/* ─────────────────────── nodes ─────────────────────── */
const NODES: Record<NK, NodeDef> = {
  user: { x: 18,   y: 350, label: 'React UI',            sub: 'Vite 7 · Tailwind v4',        group: 'frontend' },
  api:  { x: 208,  y: 350, label: 'FastAPI Backend',      sub: 'Python 3.11 · Port 8081',     group: 'backend'  },
  orch: { x: 400,  y: 210, label: 'ADK Orchestrator',     sub: 'Dynamic Router · 4 routes',   group: 'backend'  },
  hist: { x: 400,  y: 430, label: 'Memory Service',       sub: 'Memory card · 6m history',    group: 'tools'    },
  risk: { x: 610,  y:  50, label: 'Risk Analyst',         sub: 'Segment · DTI · Confidence',  group: 'agent'    },
  camp: { x: 610,  y: 185, label: 'Campaign Pipeline',    sub: 'Variants · Evaluator · Loop', group: 'agent'    },
  edu:  { x: 610,  y: 320, label: 'Educational Agent',    sub: 'DEEP-SUBPRIME · Rehab plan',  group: 'agent'    },
  cond: { x: 610,  y: 455, label: 'Conditional Agent',    sub: 'SUBPRIME · Gap analysis',     group: 'agent'    },
  comp: { x: 610,  y: 590, label: 'Compliance Gate',      sub: 'All routes · exit_loop tool', group: 'agent'    },
  rag:  { x: 838,  y: 155, label: 'Vertex AI Search',     sub: 'Discovery Engine · 3 docs',   group: 'ai'       },
  gem:  { x: 838,  y: 470, label: 'Gemini 2.5 Flash',     sub: 'Lite · Vertex AI',            group: 'ai'       },
  db:   { x: 1038, y: 255, label: 'PostgreSQL',           sub: 'asyncpg · 6 tables + memory', group: 'storage'  },
  gcs:  { x: 1038, y: 495, label: 'Cloud Storage',        sub: 'GCS · JSON audit trail',      group: 'storage'  },
}

/* ─────────────────────── colors ─────────────────────── */
const COLORS: Record<string, { bg: string; border: string; text: string; glow: string; dimBg: string; dimBorder: string; dimText: string }> = {
  frontend: { bg: '#1e1b4b', border: '#6366f1', text: '#a5b4fc', glow: 'rgba(99,102,241,0.5)',  dimBg: '#12113a', dimBorder: '#2d2f6b', dimText: '#4b4e8a' },
  backend:  { bg: '#082f49', border: '#0891b2', text: '#67e8f9', glow: 'rgba(8,145,178,0.5)',   dimBg: '#061e30', dimBorder: '#0c3d5c', dimText: '#1a6080' },
  tools:    { bg: '#1a0533', border: '#7c3aed', text: '#c4b5fd', glow: 'rgba(124,58,237,0.5)',  dimBg: '#110228', dimBorder: '#3d1a70', dimText: '#5b3a8a' },
  agent:    { bg: '#052e16', border: '#059669', text: '#6ee7b7', glow: 'rgba(5,150,105,0.5)',   dimBg: '#031d0e', dimBorder: '#0a4a28', dimText: '#145e35' },
  ai:       { bg: '#1c1408', border: '#d97706', text: '#fcd34d', glow: 'rgba(217,119,6,0.5)',   dimBg: '#130e05', dimBorder: '#6b3d05', dimText: '#8a5210' },
  storage:  { bg: '#2d0a1e', border: '#db2777', text: '#f9a8d4', glow: 'rgba(219,39,119,0.5)',  dimBg: '#1c0512', dimBorder: '#6b1040', dimText: '#8a1a55' },
}

const ICON: Record<string, string> = {
  frontend: '▣', backend: '◈', tools: '◎', agent: '◆', ai: '◉', storage: '▤',
}

/* ─────────────────────── geometry helpers ─────────────────────── */
const cy  = (k: NK) => NODES[k].y + NH / 2
const rx  = (k: NK) => NODES[k].x + NW   // right edge
const lx  = (k: NK) => NODES[k].x        // left edge

/* Orthogonal path — exits right of A, enters left of B, all right-angle corners */
function orth(a: NK, b: NK): string {
  const x1 = rx(a), y1 = cy(a)
  const x2 = lx(b), y2 = cy(b)

  // Same column or backward: detour right to avoid overlap
  if (x1 >= x2 - 5) {
    const det = Math.max(x1, x2) + 38
    return `M${x1},${y1} H${det} V${y2} H${x2}`
  }
  const mx = Math.round((x1 + x2) / 2)
  if (Math.abs(y1 - y2) < 3) return `M${x1},${y1} H${x2}`
  return `M${x1},${y1} H${mx} V${y2} H${x2}`
}

/* ─────────────────────── edges ─────────────────────── */
const EDGES: Array<{ id: string; from: NK; to: NK; d: string }> = [
  { id: 'u-a',   from: 'user', to: 'api',  d: orth('user','api')  },
  { id: 'a-o',   from: 'api',  to: 'orch', d: orth('api', 'orch') },
  { id: 'o-ri',  from: 'orch', to: 'risk', d: orth('orch','risk') },
  { id: 'o-ca',  from: 'orch', to: 'camp', d: orth('orch','camp') },
  { id: 'o-ed',  from: 'orch', to: 'edu',  d: orth('orch','edu')  },
  { id: 'o-cn',  from: 'orch', to: 'cond', d: orth('orch','cond') },
  { id: 'o-co',  from: 'orch', to: 'comp', d: orth('orch','comp') },
  { id: 'o-ht',  from: 'orch', to: 'hist', d: orth('orch','hist') },
  { id: 'ht-db', from: 'hist', to: 'db',   d: orth('hist','db')   },
  { id: 'ri-r',  from: 'risk', to: 'rag',  d: orth('risk','rag')  },
  { id: 'ca-r',  from: 'camp', to: 'rag',  d: orth('camp','rag')  },
  { id: 'ed-r',  from: 'edu',  to: 'rag',  d: orth('edu', 'rag')  },
  { id: 'cn-r',  from: 'cond', to: 'rag',  d: orth('cond','rag')  },
  { id: 'co-r',  from: 'comp', to: 'rag',  d: orth('comp','rag')  },
  { id: 'ri-g',  from: 'risk', to: 'gem',  d: orth('risk','gem')  },
  { id: 'ca-g',  from: 'camp', to: 'gem',  d: orth('camp','gem')  },
  { id: 'ed-g',  from: 'edu',  to: 'gem',  d: orth('edu', 'gem')  },
  { id: 'cn-g',  from: 'cond', to: 'gem',  d: orth('cond','gem')  },
  { id: 'co-g',  from: 'comp', to: 'gem',  d: orth('comp','gem')  },
  { id: 'o-gc',  from: 'orch', to: 'gcs',  d: orth('orch','gcs')  },
  { id: 'a-db',  from: 'api',  to: 'db',   d: orth('api', 'db')   },
  // Self-correction: exits left of comp, routes up via x=558, enters left of camp
  {
    id: 'co-ca', from: 'comp', to: 'camp',
    d: `M${lx('comp')},${cy('comp')} H558 V${cy('camp')} H${lx('camp')}`,
  },
]

/* ─────────────────────── views ─────────────────────── */
const VIEW_COLOR: Record<string, string> = {
  overview:    '#6366f1',
  routing:     '#059669',
  'rag-llm':   '#d97706',
  memory:      '#7c3aed',
  compliance:  '#f59e0b',
  confidence:  '#10b981',
  persistence: '#db2777',
}

const VIEWS: View[] = [
  {
    id: 'overview',
    label: 'Sistema Completo',
    title: '13 Agentes ADK · 6 Capas · Todos los canales',
    desc: 'Topología completa del sistema. 6 capas de responsabilidad: USER LAYER (presentación React), API LAYER (FastAPI + rutas HTTP), ORCHESTRATION (coordinación ADK + memoria persistente), AGENT LAYER (5 pipelines especializados: Risk, Campaign, Educational, Conditional, Compliance), AI SERVICES (RAG Vertex AI Search + Gemini 2.5 Flash compartidos por todos los agentes), PERSISTENCE (PostgreSQL 6 tablas + GCS audit trail). Las conexiones representan canales estables — no invocaciones secuenciales.',
    nodes: ['user','api','orch','hist','risk','camp','edu','cond','comp','rag','gem','db','gcs'],
    edges: ['u-a','a-o','o-ri','o-ca','o-ed','o-cn','o-co','o-ht','ht-db','ri-r','ca-r','ed-r','cn-r','co-r','ri-g','ca-g','ed-g','cn-g','co-g','a-db','o-gc','co-ca'],
  },
  {
    id: 'routing',
    label: 'Routing Dinámico',
    title: 'Orchestrator → 4 rutas especializadas por segmento crediticio',
    desc: 'El ADK Orchestrator lee el output del Risk Analyst (segment + eligible_for_credit) y activa exactamente uno de los 4 pipelines:\n• EDUCATIONAL → DEEP-SUBPRIME: plan de rehabilitación, sin oferta de crédito.\n• PREMIUM_FAST → SUPER-PRIME: Campaign + Compliance una vez, sin loop de corrección.\n• CONDITIONAL → SUBPRIME inelegible: "Reduce tu DTI en $X para calificar al producto Y".\n• STANDARD → PRIME / NEAR-PRIME / SUBPRIME elegible: CorrectionLoop con ParallelAgent (3 tonos) + LLM-as-Judge + ComplianceGate (máx 3 iteraciones).\nCompliance Gate siempre corre — en las 4 rutas sin excepción.',
    nodes: ['orch','risk','camp','edu','cond','comp'],
    edges: ['o-ri','o-ca','o-ed','o-cn','o-co'],
  },
  {
    id: 'rag-llm',
    label: 'RAG + LLM',
    title: 'Patrón RAG + LLM — Los 5 agentes comparten la misma arquitectura de inferencia',
    desc: 'Cada agente implementa el mismo patrón en dos fases independientes:\n(1) RETRIEVAL — KB pre-inyectado en el instruction callable. Consulta semántica a Vertex AI Search (Discovery Engine) con self-signed JWT — sin oauth2.googleapis.com. Los 3 documentos indexados: reglamento_scoring · catalogo_productos · politicas_credito.\n(2) GENERATION — Gemini 2.5 Flash Lite recibe perfil + contexto RAG y devuelve JSON estructurado. Schema fijo garantiza parseo confiable. retry_options=3 en todos los agentes.',
    nodes: ['risk','camp','edu','cond','comp','rag','gem'],
    edges: ['ri-r','ca-r','ed-r','cn-r','co-r','ri-g','ca-g','ed-g','cn-g','co-g'],
  },
  {
    id: 'memory',
    label: 'Memoria',
    title: 'Memory Service — Tool use en dos momentos del análisis por cliente',
    desc: 'El Orchestrator invoca el Memory Service en dos momentos:\n(1) ANTES de la campaña — lee customer_memory (tarjeta agregada: segment trend, DTI trend, products offered, verdict counts). Fallback a últimos 6 meses de customer_interactions si aún no existe tarjeta. El contexto se inyecta en el prompt de Campaign para personalizar y evitar ofertas repetidas.\n(2) DESPUÉS del análisis — save_customer_interaction (log permanente) + refresh_customer_memory (rebuild determinístico desde historial raw). Ciclo cerrado por cliente.',
    nodes: ['orch','hist','db'],
    edges: ['o-ht','ht-db'],
  },
  {
    id: 'compliance',
    label: 'Auto-corrección',
    title: 'LoopAgent Compliance → Campaign — Corrección automática con feedback estructurado',
    desc: 'Compliance Gate es el único agente que siempre corre en todas las rutas. En la ruta STANDARD (CorrectionLoop), si el veredicto es REJECTED o cualquier check es FAIL:\n→ Los warnings específicos se pasan a Campaign Generator con instruction de corrección dirigida.\n→ Nuevo ciclo: CampaignVariants genera 3 variantes · CampaignEvaluator selecciona la mejor · Compliance vuelve a verificar.\n→ Máximo 3 iteraciones. Si se agotan → human_review_required = True (escalación automática).\nCada iteración extra suma 4 llamadas adicionales al stack de IA.',
    nodes: ['orch','camp','comp','rag','gem'],
    edges: ['o-ca','o-co','co-ca','ca-r','ca-g','co-r','co-g'],
  },
  {
    id: 'confidence',
    label: 'Confianza',
    title: 'Confidence Scoring — Agregación determinista, cero llamadas adicionales al LLM',
    desc: 'Cálculo 100% en memoria — sin LLM, sin RAG, sin BD extra. El Orchestrator lee los confidence scores ya disponibles en session.state:\nbase = min(risk_confidence, compliance_confidence)\nCaps deterministas aplicados en cascada:\n  REJECTED → ≤ 0.40 · REVIEW → ≤ 0.65 · 3+ warnings → ≤ 0.65\n  DTI 43–53% → ≤ 0.72 · APPROVED_WITH_WARNINGS → ≤ 0.82\nSi pipeline_confidence < 0.65: muta compliance_data → human_review_required = True sin reinvocar ningún agente. EDUCATIONAL siempre requiere revisión humana por diseño.',
    nodes: ['orch','risk','comp'],
    edges: [],
  },
  {
    id: 'persistence',
    label: 'Persistencia',
    title: 'Persistencia — 4 escrituras · 3 destinos · 2 actores',
    desc: 'El Orchestrator escribe dentro de analyze_customer() antes de retornar:\n① GCS ← Orchestrator: JSON de auditoría (perfil, ruta, resultado, confidence, correction_attempts).\n② DB.customer_interactions ← Orchestrator → Memory Service: log permanente del contacto.\n③ DB.customer_memory ← Orchestrator → Memory Service: upsert de la tarjeta agregada.\n\nLuego FastAPI escribe al recibir la respuesta:\n④ DB.campaign_results ← API: registro vinculado a campaña con correction_attempts, pipeline_route, pipeline_confidence y review_status para el flujo de aprobación humana.',
    nodes: ['orch','hist','api','db','gcs'],
    edges: ['o-gc','o-ht','ht-db','a-db'],
  },
]

/* ─────────────────────── lane config ─────────────────────── */
const LANES = [
  { x: 18,   w: 177,  label: 'USER LAYER'    },
  { x: 200,  w: 188,  label: 'API LAYER'     },
  { x: 393,  w: 205,  label: 'ORCHESTRATION' },
  { x: 603,  w: 225,  label: 'AGENT LAYER'   },
  { x: 833,  w: 195,  label: 'AI SERVICES'   },
  { x: 1033, w: 162,  label: 'PERSISTENCE'   },
]

/* ─────────────────────── component ─────────────────────── */
export function ArchitecturePage() {
  const [viewIdx, setViewIdx] = useState(0)

  const view        = VIEWS[viewIdx]
  const activeNodes = new Set(view.nodes)
  const activeEdges = new Set(view.edges)
  const isOverview  = view.id === 'overview'
  const accent      = VIEW_COLOR[view.id]

  return (
    <div style={{
      margin: '-24px -16px',
      backgroundColor: '#020b18',
      height: '100vh',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'ui-monospace, "Cascadia Code", "Source Code Pro", monospace',
    }}>
      <style>{`
        @keyframes fc-draw {
          from { stroke-dashoffset: 2000; }
          to   { stroke-dashoffset: 0; }
        }
        @keyframes fc-pulse {
          0%, 100% { opacity: 0.45; }
          50%      { opacity: 1; }
        }
        @keyframes fc-travel {
          0%   { offset-distance: 0%; }
          100% { offset-distance: 100%; }
        }
        @keyframes fc-slide {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .fc-draw   { stroke-dasharray: 2000; stroke-dashoffset: 2000; animation: fc-draw 0.6s ease-out forwards; }
        .fc-pulse  { animation: fc-pulse 1.8s ease-in-out infinite; }
        .fc-slide  { animation: fc-slide 0.22s ease-out; }
        .fc-btn    { transition: all 0.15s; }
        .fc-btn:hover { opacity: 0.8; transform: translateY(-1px); }
      `}</style>

      {/* ── Header ── */}
      <div style={{
        borderBottom: '1px solid #0e2038',
        padding: '12px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        backgroundColor: '#030e1e',
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '0.3px' }}>
            Arquitectura del Sistema — FinCampaign ADK
          </h1>
          <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#94a3b8', letterSpacing: '0.5px' }}>
            13 AGENTES · RAG + LLM · ROUTING DINÁMICO · MEMORY CARD · AUTO-CORRECCIÓN · CONFIDENCE SCORING
          </p>
        </div>
        <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
          {Object.entries(COLORS).map(([group, c]) => (
            <div key={group} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10px' }}>
              <div style={{ width: 7, height: 7, backgroundColor: c.border }} />
              <span style={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.8px' }}>{group}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Diagram ── */}
      <div key={viewIdx} style={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>

          {/* SVG — lanes + edges */}
          <svg
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
            viewBox={`0 0 ${VW} ${VH}`}
            preserveAspectRatio="none"
          >
            <defs>
              {/* Arrow for background edges */}
              <marker id="fc-arr-bg" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4" markerHeight="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#0e2540" />
              </marker>
              {/* Arrow for active edges */}
              <marker id="fc-arr-on" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#94a3b8" />
              </marker>
              {/* Glow filter */}
              <filter id="fc-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Lane backgrounds */}
            {LANES.map((l, i) => (
              <rect key={i} x={l.x} y={0} width={l.w} height={VH}
                fill={i % 2 === 0 ? '#020b18' : '#030f20'}
                opacity={1}
              />
            ))}

            {/* Lane separator lines */}
            {LANES.slice(1).map((l, i) => (
              <line key={i} x1={l.x} y1={28} x2={l.x} y2={VH}
                stroke="#0a1e34" strokeWidth="1" strokeDasharray="3,4" />
            ))}

            {/* Lane header labels */}
            {LANES.map(l => (
              <text key={l.x} x={l.x + 6} y={18} fontSize="8.5"
                fill="#1a3550" fontFamily="inherit" letterSpacing="1.8" fontWeight="600">
                {l.label}
              </text>
            ))}

            {/* Background edges — visible even when inactive */}
            {EDGES.map(e => (
              <path key={e.id} d={e.d} fill="none"
                stroke={isOverview ? '#0e2a48' : '#091825'}
                strokeWidth="1.5"
                strokeLinejoin="miter"
                markerEnd="url(#fc-arr-bg)"
              />
            ))}

            {/* Active edges — animated with particle travel */}
            {EDGES.filter(e => activeEdges.has(e.id)).map(e => {
              const col = COLORS[NODES[e.from].group].border
              return (
                <g key={`ae-${e.id}`}>
                  {/* Glow halo */}
                  <path d={e.d} fill="none"
                    stroke={col} strokeWidth="8" opacity="0.10"
                    strokeLinejoin="miter"
                    className="fc-pulse"
                    filter="url(#fc-glow)"
                  />
                  {/* Main line — animated draw */}
                  <path d={e.d} fill="none"
                    stroke={col} strokeWidth="1.8"
                    strokeLinejoin="miter"
                    markerEnd="url(#fc-arr-on)"
                    className="fc-draw"
                  />
                  {/* Traveling dot */}
                  <circle r="4" fill={col} opacity="0.95" className="fc-pulse">
                    <animateMotion dur="2s" repeatCount="indefinite" path={e.d} rotate="auto" />
                  </circle>
                  <circle r="9" fill={col} opacity="0.12" className="fc-pulse">
                    <animateMotion dur="2s" repeatCount="indefinite" path={e.d} rotate="auto" />
                  </circle>
                </g>
              )
            })}

            {/* Self-correction label — shown when that edge is active */}
            {activeEdges.has('co-ca') && (
              <text
                x={552} y={cy('camp') + (cy('comp') - cy('camp')) / 2}
                fontSize="8" fill="#f59e0b" fontFamily="inherit"
                textAnchor="middle" letterSpacing="1.5"
                transform={`rotate(-90 552 ${cy('camp') + (cy('comp') - cy('camp')) / 2})`}
              >
                AUTO-CORRECCIÓN
              </text>
            )}
          </svg>

          {/* HTML Nodes */}
          {(Object.entries(NODES) as [NK, NodeDef][]).map(([key, node]) => {
            const c      = COLORS[node.group]
            const active = activeNodes.has(key)
            const dimmed = !isOverview && !active

            return (
              <div
                key={key}
                style={{
                  position:  'absolute',
                  left:      `${(node.x / VW) * 100}%`,
                  top:       `${(node.y / VH) * 100}%`,
                  width:     `${(NW / VW) * 100}%`,
                  height:    `${(NH / VH) * 100}%`,

                  /* Active: full group color + glow. Dimmed: subdued group tint. Inactive overview: medium tint. */
                  background: active
                    ? `linear-gradient(135deg, ${c.bg}f8, ${c.bg}d0)`
                    : dimmed
                      ? c.dimBg
                      : `${c.bg}c0`,

                  border: active
                    ? `1.5px solid ${c.border}`
                    : dimmed
                      ? `1px solid ${c.dimBorder}`
                      : `1px solid ${c.border}50`,

                  borderRadius: '3px',

                  boxShadow: active
                    ? `0 0 18px ${c.glow}, 0 0 36px ${c.glow}40, inset 0 1px 0 ${c.border}30`
                    : 'none',

                  transform: active ? 'scale(1.05)' : 'scale(1)',
                  transition: 'all 0.3s ease',
                  opacity: dimmed ? 0.45 : 1,
                  zIndex: active ? 20 : 5,
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 9px',
                  gap: '7px',
                  cursor: 'default',
                  userSelect: 'none',
                }}
              >
                {/* Icon */}
                <span style={{
                  fontSize: '13px',
                  flexShrink: 0,
                  color: active ? c.border : dimmed ? c.dimBorder : `${c.border}70`,
                  lineHeight: 1,
                }}>
                  {ICON[node.group]}
                </span>

                {/* Text */}
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '0.2px',
                    color: active
                      ? c.text
                      : dimmed
                        ? c.dimText
                        : `${c.text}80`,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    transition: 'color 0.3s',
                  }}>
                    {node.label}
                  </div>
                  <div style={{
                    fontSize: '8.5px',
                    marginTop: '1px',
                    color: active
                      ? `${c.text}90`
                      : dimmed
                        ? `${c.dimText}bb`
                        : `${c.text}50`,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    transition: 'color 0.3s',
                    letterSpacing: '0.1px',
                  }}>
                    {node.sub}
                  </div>
                </div>
              </div>
            )
          })}
      </div>

      {/* ── Bottom Panel ── */}
      <div style={{ borderTop: '1px solid #0e2038', backgroundColor: '#020e1c', flexShrink: 0 }}>

        {/* Tab bar */}
        <div style={{ padding: '10px 28px 0', display: 'flex', gap: '4px', alignItems: 'center' }}>
          {VIEWS.map((v, i) => {
            const color    = VIEW_COLOR[v.id]
            const isActive = i === viewIdx
            return (
              <button
                key={v.id}
                className="fc-btn"
                onClick={() => setViewIdx(i)}
                style={{
                  padding: '4px 12px',
                  borderRadius: '3px',
                  border: `1px solid ${isActive ? color : '#0e2038'}`,
                  backgroundColor: isActive ? `${color}18` : 'transparent',
                  color: isActive ? color : '#475569',
                  fontSize: '11px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                  fontFamily: 'inherit',
                  letterSpacing: '0.3px',
                }}
              >
                {v.label}
              </button>
            )
          })}

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ fontSize: '10px', color: '#475569', fontFamily: 'inherit' }}>
              {viewIdx + 1}&thinsp;/&thinsp;{VIEWS.length}
            </span>
            <button onClick={() => setViewIdx(i => Math.max(0, i - 1))} disabled={viewIdx === 0} style={navBtn}>
              <ChevronLeft size={13} />
            </button>
            <button onClick={() => setViewIdx(i => Math.min(VIEWS.length - 1, i + 1))} disabled={viewIdx === VIEWS.length - 1} style={navBtn}>
              <ChevronRight size={13} />
            </button>
          </div>
        </div>

        {/* Description */}
        <div key={viewIdx} className="fc-slide" style={{ padding: '10px 28px 14px', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <span style={{
            flexShrink: 0,
            fontSize: '9px',
            fontWeight: 700,
            padding: '3px 7px',
            borderRadius: '2px',
            backgroundColor: `${accent}18`,
            color: accent,
            border: `1px solid ${accent}35`,
            whiteSpace: 'nowrap',
            marginTop: '2px',
            letterSpacing: '1px',
            fontFamily: 'inherit',
          }}>
            {view.id.toUpperCase().replace('-', '+')}
          </span>
          <div>
            <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#cbd5e1', letterSpacing: '0.2px' }}>
              {view.title}
            </p>
            <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#64748b', lineHeight: 1.7, whiteSpace: 'pre-line', fontFamily: 'inherit' }}>
              {view.desc}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────── styles ─────────────────────── */
const navBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '26px', height: '26px',
  borderRadius: '3px', border: '1px solid #0e2038',
  backgroundColor: '#030e1e', color: '#475569',
  cursor: 'pointer',
}
