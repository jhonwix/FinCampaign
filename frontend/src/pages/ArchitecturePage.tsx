import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

/* ─────────────────────── canvas ─────────────────────── */
const VW = 1200
const VH = 780
const NW = 152
const NH = 54

/* ─────────────────────── types ─────────────────────── */
type NK = 'user' | 'api' | 'orch' | 'hist'
        | 'risk' | 'camp' | 'edu' | 'cond' | 'comp'
        | 'rag'  | 'gem'
        | 'db'   | 'gcs'

interface NodeDef { x: number; y: number; label: string; sub: string; group: string }
interface View    { id: string; label: string; title: string; desc: string; nodes: NK[]; edges: string[] }

/* ─────────────────────── nodes ─────────────────────── */
const NODES: Record<NK, NodeDef> = {
  user: { x: 18,   y: 350, label: 'React UI',            sub: 'Vite · Tailwind v4',       group: 'frontend' },
  api:  { x: 208,  y: 350, label: 'FastAPI Backend',      sub: 'Python 3.11 · :8081',      group: 'backend'  },
  orch: { x: 400,  y: 210, label: 'Orchestrator',         sub: 'Dynamic Router',           group: 'backend'  },
  hist: { x: 400,  y: 430, label: 'Memory + History',     sub: 'Memory card · 6m history', group: 'tools'    },
  risk: { x: 610,  y:  50, label: 'Risk Analyst',         sub: 'Agent #1 · Segment + DTI', group: 'agent'    },
  camp: { x: 610,  y: 185, label: 'Campaign Generator',   sub: 'Agent #2 · STANDARD/FAST', group: 'agent'    },
  edu:  { x: 610,  y: 320, label: 'Financial Education',  sub: 'Agent #3 · EDUCATIONAL',   group: 'agent'    },
  cond: { x: 610,  y: 455, label: 'Conditional Offer',    sub: 'Agent #4 · CONDITIONAL',   group: 'agent'    },
  comp: { x: 610,  y: 590, label: 'Compliance Checker',   sub: 'Agent #5 · Always runs',   group: 'agent'    },
  rag:  { x: 838,  y: 155, label: 'Vertex AI Search',     sub: 'Discovery Engine · RAG',   group: 'ai'       },
  gem:  { x: 838,  y: 470, label: 'Gemini 2.5 Flash',     sub: 'Lite · Vertex AI',         group: 'ai'       },
  db:   { x: 1038, y: 255, label: 'PostgreSQL',           sub: 'asyncpg · 6 tables',       group: 'storage'  },
  gcs:  { x: 1038, y: 495, label: 'Cloud Storage',        sub: 'GCS · JSON audit trail',   group: 'storage'  },
}

/* ─────────────────────── colors ─────────────────────── */
const COLORS: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  frontend: { bg: '#1e1b4b', border: '#6366f1', text: '#a5b4fc', glow: 'rgba(99,102,241,0.55)'  },
  backend:  { bg: '#082f49', border: '#0891b2', text: '#67e8f9', glow: 'rgba(8,145,178,0.55)'   },
  tools:    { bg: '#1a0533', border: '#7c3aed', text: '#c4b5fd', glow: 'rgba(124,58,237,0.55)'  },
  agent:    { bg: '#052e16', border: '#059669', text: '#6ee7b7', glow: 'rgba(5,150,105,0.55)'   },
  ai:       { bg: '#1c1408', border: '#d97706', text: '#fcd34d', glow: 'rgba(217,119,6,0.55)'   },
  storage:  { bg: '#2d0a1e', border: '#db2777', text: '#f9a8d4', glow: 'rgba(219,39,119,0.55)'  },
}

const EMOJI: Record<string, string> = {
  frontend: '🖥️', backend: '⚡', tools: '🔧', agent: '🤖', ai: '✨', storage: '🗄️',
}

/* ─────────────────────── helpers ─────────────────────── */
const cx = (k: NK) => NODES[k].x + NW / 2
const cy = (k: NK) => NODES[k].y + NH / 2

function bez(a: NK, b: NK): string {
  const x1 = cx(a), y1 = cy(a), x2 = cx(b), y2 = cy(b)
  const cp = Math.abs(x2 - x1) * 0.44
  return `M${x1},${y1} C${x1 + cp},${y1} ${x2 - cp},${y2} ${x2},${y2}`
}

/* ─────────────────────── edges ─────────────────────── */
const EDGES: Array<{ id: string; from: NK; to: NK; d: string }> = [
  // User ↔ API
  { id: 'u-a',   from: 'user', to: 'api',  d: bez('user', 'api')  },
  // API → Orchestrator
  { id: 'a-o',   from: 'api',  to: 'orch', d: bez('api',  'orch') },
  // Orchestrator → agents
  { id: 'o-ri',  from: 'orch', to: 'risk', d: bez('orch', 'risk') },
  { id: 'o-ca',  from: 'orch', to: 'camp', d: bez('orch', 'camp') },
  { id: 'o-ed',  from: 'orch', to: 'edu',  d: bez('orch', 'edu')  },
  { id: 'o-cn',  from: 'orch', to: 'cond', d: bez('orch', 'cond') },
  { id: 'o-co',  from: 'orch', to: 'comp', d: bez('orch', 'comp') },
  // Orchestrator ↔ Memory Tool ↔ DB
  { id: 'o-ht',  from: 'orch', to: 'hist', d: bez('orch', 'hist') },
  { id: 'ht-db', from: 'hist', to: 'db',   d: bez('hist', 'db')   },
  // Agents → RAG
  { id: 'ri-r',  from: 'risk', to: 'rag',  d: bez('risk', 'rag')  },
  { id: 'ca-r',  from: 'camp', to: 'rag',  d: bez('camp', 'rag')  },
  { id: 'ed-r',  from: 'edu',  to: 'rag',  d: bez('edu',  'rag')  },
  { id: 'cn-r',  from: 'cond', to: 'rag',  d: bez('cond', 'rag')  },
  { id: 'co-r',  from: 'comp', to: 'rag',  d: bez('comp', 'rag')  },
  // Agents → Gemini
  { id: 'ri-g',  from: 'risk', to: 'gem',  d: bez('risk', 'gem')  },
  { id: 'ca-g',  from: 'camp', to: 'gem',  d: bez('camp', 'gem')  },
  { id: 'ed-g',  from: 'edu',  to: 'gem',  d: bez('edu',  'gem')  },
  { id: 'cn-g',  from: 'cond', to: 'gem',  d: bez('cond', 'gem')  },
  { id: 'co-g',  from: 'comp', to: 'gem',  d: bez('comp', 'gem')  },
  // Persistence — Orchestrator → GCS (JSON audit, written inside analyze_customer)
  { id: 'o-gc',  from: 'orch', to: 'gcs',  d: bez('orch', 'gcs')  },
  // Persistence — API → DB (campaign_results, written by main.py after orchestrator returns)
  { id: 'a-db',  from: 'api',  to: 'db',   d: bez('api',  'db')   },
  // Self-correction loop: Compliance → Campaign Generator
  {
    id: 'co-ca', from: 'comp', to: 'camp',
    d: `M${cx('comp')},${cy('comp')} C490,${cy('comp')} 490,${cy('camp')} ${cx('camp')},${cy('camp')}`,
  },
]

/* ─────────────────────── views ─────────────────────── */
const VIEW_COLOR: Record<string, string> = {
  overview:    '#6366f1',
  routing:     '#7c3aed',
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
    title: '13 Actores · 6 Capas · Todos los canales de comunicación',
    desc: 'Mapa de topología completa. Los actores se organizan en 6 capas de responsabilidad: USER LAYER (presentación), API LAYER (enrutamiento HTTP), ORCHESTRATION (coordinación + memoria), AGENT LAYER (inteligencia especializada), AI SERVICES (RAG + LLM compartidos), PERSISTENCE (GCS + PostgreSQL). Las conexiones representan canales estables — no invocaciones secuenciales. Selecciona una vista temática para profundizar en un aspecto arquitectónico específico.',
    nodes: ['user','api','orch','hist','risk','camp','edu','cond','comp','rag','gem','db','gcs'],
    edges: ['u-a','a-o','o-ri','o-ca','o-ed','o-cn','o-co','o-ht','ht-db','ri-r','ca-r','ed-r','cn-r','co-r','ri-g','ca-g','ed-g','cn-g','co-g','a-db','o-gc','co-ca'],
  },
  {
    id: 'routing',
    label: 'Routing Dinámico',
    title: 'Orchestrator → 4 Rutas especializadas por segmento de riesgo',
    desc: 'El Orchestrator evalúa el output del Risk Analyst (segmento + elegibilidad) y activa exactamente uno de los 4 agentes de campaña:\n• EDUCATIONAL → DEEP-SUBPRIME: plan de rehabilitación crediticia, sin oferta de crédito.\n• PREMIUM_FAST → SUPER-PRIME: camino directo, compliance se ejecuta una sola vez.\n• CONDITIONAL → SUBPRIME inelegible: "Reduce tu DTI en $X para calificar al producto Y".\n• STANDARD → PRIME / NEAR-PRIME / SUBPRIME elegible: pipeline completo con bucle de auto-corrección.\nCompliance Checker (#5) siempre se ejecuta sin excepción — en las 4 rutas.',
    nodes: ['orch','risk','camp','edu','cond','comp'],
    edges: ['o-ri','o-ca','o-ed','o-cn','o-co'],
  },
  {
    id: 'rag-llm',
    label: 'RAG + LLM',
    title: 'Patrón RAG + LLM — Los 5 agentes comparten la misma arquitectura de inferencia',
    desc: 'Cada agente implementa el mismo patrón de dos fases independientes:\n(1) RETRIEVAL — consulta semántica a Vertex AI Search (Discovery Engine). Los 3 documentos indexados son: reglamento_scoring · catalogo_productos · politicas_credito. La búsqueda semántica garantiza que siempre se apliquen las políticas vigentes en la fuente de verdad.\n(2) GENERATION — Gemini 2.5 Flash Lite recibe perfil + contexto RAG y devuelve JSON estructurado. El schema de respuesta está fijado (response_mime_type=application/json) para garantizar parseo confiable sin procesamiento adicional.',
    nodes: ['risk','camp','edu','cond','comp','rag','gem'],
    edges: ['ri-r','ca-r','ed-r','cn-r','co-r','ri-g','ca-g','ed-g','cn-g','co-g'],
  },
  {
    id: 'memory',
    label: 'Memoria de Cliente',
    title: 'Tool Use — Orchestrator ↔ Memory Tool ↔ PostgreSQL',
    desc: 'El Orchestrator invoca el Memory Tool en dos momentos del análisis:\n(1) ANTES de la campaña — lee customer_memory (tarjeta agregada: segment trend, DTI trend, products offered, verdict counts). Si no existe aún, hace fallback a los últimos 6 meses de customer_interactions. El contexto se inyecta en el prompt del agente de campaña para personalizar mensajes y evitar ofertas repetidas.\n(2) DESPUÉS del análisis — escribe la nueva interacción (save_customer_interaction) y actualiza la tarjeta (refresh_customer_memory: rebuild determinístico desde historial raw). El ciclo se cierra por cliente.',
    nodes: ['orch','hist','db'],
    edges: ['o-ht','ht-db'],
  },
  {
    id: 'compliance',
    label: 'Auto-corrección',
    title: 'Bucle Compliance → Campaign — Corrección automática con feedback estructurado',
    desc: 'Compliance Checker (#5) es el único agente que siempre corre en todas las rutas. En la ruta STANDARD, si el veredicto es REJECTED o cualquier check individual es FAIL, el Orchestrator retroalimenta al Campaign Generator con los warnings específicos y solicita regeneración (máx. 2 intentos, temperature=0.4 para precisión dirigida).\nCada ciclo de corrección implica 4 llamadas adicionales al stack de IA: Campaign→RAG (catálogo actualizado) + Campaign→Gemini (regeneración) + Compliance→RAG (políticas) + Compliance→Gemini (re-verificación). Si los intentos se agotan → human_review_required = True (escalación automática sin intervención manual en el código).',
    nodes: ['orch','camp','comp','rag','gem'],
    edges: ['o-ca','o-co','co-ca','ca-r','ca-g','co-r','co-g'],
  },
  {
    id: 'confidence',
    label: 'Confianza',
    title: 'Confidence Scoring — Agregación determinista sobre outputs ya disponibles',
    desc: 'Cálculo 100% en memoria — sin llamadas adicionales al LLM, RAG ni BD. El Orchestrator lee los scores auto-reportados por Risk Analyst y Compliance Checker (ya disponibles en memoria) y aplica:\nbase = min(risk_confidence, compliance_confidence)\nCaps deterministas: REJECTED ≤ 0.40 · REVIEW ≤ 0.65 · 3+ warnings ≤ 0.65 · DTI 43–53% ≤ 0.72 · APPROVED_WITH_WARNINGS ≤ 0.82\nSi pipeline_confidence < 65%: el Orchestrator muta directamente compliance_data → human_review_required = True. La decisión se propaga a la persistencia sin re-invocar ningún agente. EDUCATIONAL siempre requiere revisión humana por diseño — excluida del umbral.',
    nodes: ['orch','risk','comp'],
    edges: [],
  },
  {
    id: 'persistence',
    label: 'Persistencia',
    title: 'Persistencia — 4 escrituras · 3 destinos · 2 actores responsables',
    desc: 'El Orchestrator escribe dentro de analyze_customer() antes de retornar al API:\n① GCS ← Orchestrator: JSON enriquecido de auditoría (perfil, ruta, resultado, pipeline_confidence, correction_attempts).\n② DB.customer_interactions ← Orchestrator → Memory Tool: log permanente del contacto con el cliente.\n③ DB.customer_memory ← Orchestrator → Memory Tool: upsert de la tarjeta agregada (rebuild determinístico).\n\nLuego main.py escribe al recibir la respuesta del Orchestrator:\n④ DB.campaign_results ← API: registro vinculado a la campaña con correction_attempts, pipeline_route y review_status para el flujo de aprobación humana.',
    nodes: ['orch','hist','api','db','gcs'],
    edges: ['o-gc','o-ht','ht-db','a-db'],
  },
]

/* ─────────────────────── lane labels ─────────────────────── */
const LANE_LABELS = [
  { x: 18,   label: 'USER LAYER'    },
  { x: 200,  label: 'API LAYER'     },
  { x: 388,  label: 'ORCHESTRATION' },
  { x: 592,  label: 'AGENT LAYER'   },
  { x: 820,  label: 'AI SERVICES'   },
  { x: 1020, label: 'PERSISTENCE'   },
]

/* ─────────────────────── component ─────────────────────── */
export function ArchitecturePage() {
  const [viewIdx, setViewIdx] = useState(0)

  const view       = VIEWS[viewIdx]
  const activeNodes = new Set(view.nodes)
  const activeEdges = new Set(view.edges)
  const isOverview  = view.id === 'overview'
  const accent      = VIEW_COLOR[view.id]

  return (
    <div style={{ margin: '-24px -16px', backgroundColor: '#020617', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <style>{`
        @keyframes fc-draw {
          from { stroke-dashoffset: 2000; }
          to   { stroke-dashoffset: 0; }
        }
        @keyframes fc-glow-pulse {
          0%, 100% { opacity: 0.55; }
          50%      { opacity: 1; }
        }
        @keyframes fc-slide-up {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .fc-edge-draw   { stroke-dasharray: 2000; stroke-dashoffset: 2000; animation: fc-draw 0.75s ease-out forwards; }
        .fc-edge-glow   { animation: fc-glow-pulse 1.6s ease-in-out infinite; }
        .fc-desc-in     { animation: fc-slide-up 0.25s ease-out; }
        .fc-particle    { animation: fc-glow-pulse 0.9s ease-in-out infinite; }
        .fc-view-btn    { transition: all 0.18s ease; }
        .fc-view-btn:hover { opacity: 0.85; transform: translateY(-1px); }
      `}</style>

      {/* ── Header ── */}
      <div style={{ borderBottom: '1px solid #1e293b', padding: '14px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f1f5f9' }}>
            Arquitectura del Sistema
          </h1>
          <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#475569' }}>
            FinCampaign · 5 Agentes · RAG + LLM · Routing Dinámico · Memory Card · Auto-corrección · Confidence Scoring
          </p>
        </div>
        {/* Legend */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          {Object.entries(COLORS).map(([group, c]) => (
            <div key={group} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: c.border }} />
              <span style={{ color: '#64748b', textTransform: 'capitalize' }}>{group}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Diagram ── */}
      <div key={viewIdx} style={{ flex: 1, padding: '8px 0', position: 'relative', overflow: 'hidden' }}>
        <div style={{ width: '100%', paddingBottom: `${(VH / VW) * 100}%`, position: 'relative' }}>

          {/* SVG — edges */}
          <svg
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
            viewBox={`0 0 ${VW} ${VH}`}
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <marker id="fc-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#1e293b" />
              </marker>
              <marker id="fc-arr-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
              </marker>
              {/* Vertical lane separators */}
              {[195, 388, 600, 830, 1030].map(x => (
                <line key={x} x1={x} y1={0} x2={x} y2={VH} stroke="#0f172a" strokeWidth="1" />
              ))}
            </defs>

            {/* Lane labels */}
            {LANE_LABELS.map(l => (
              <text key={l.x} x={l.x} y={22} fontSize="9" fill="#1e293b" fontFamily="monospace" textAnchor="start" letterSpacing="1.5">
                {l.label}
              </text>
            ))}

            {/* Background edges — brighter in overview so the full topology is readable */}
            {EDGES.map(e => (
              <path key={e.id} d={e.d} fill="none"
                stroke={isOverview ? '#1e3450' : '#111827'}
                strokeWidth="1.5"
                markerEnd="url(#fc-arr)"
              />
            ))}

            {/* Active edges — animated */}
            {EDGES.filter(e => activeEdges.has(e.id)).map(e => {
              const col = COLORS[NODES[e.from].group].border
              return (
                <g key={`ae-${e.id}`}>
                  <path d={e.d} fill="none" stroke={col} strokeWidth="10" opacity="0.12" className="fc-edge-glow" />
                  <path d={e.d} fill="none" stroke={col} strokeWidth="2"  markerEnd="url(#fc-arr-active)" className="fc-edge-draw" />
                  <circle r="5" fill={col} opacity="0.9" className="fc-particle">
                    <animateMotion dur="1.8s" repeatCount="indefinite" path={e.d} />
                  </circle>
                  <circle r="10" fill={col} opacity="0.18" className="fc-particle">
                    <animateMotion dur="1.8s" repeatCount="indefinite" path={e.d} />
                  </circle>
                </g>
              )
            })}

            {/* Self-correction label */}
            {activeEdges.has('co-ca') && (
              <text
                x={484} y={cy('camp') + (cy('comp') - cy('camp')) / 2}
                fontSize="9" fill="#f59e0b" fontFamily="monospace" textAnchor="middle"
                transform={`rotate(-90, 484, ${cy('camp') + (cy('comp') - cy('camp')) / 2})`}
              >
                CORRECCIÓN
              </text>
            )}
          </svg>

          {/* HTML Nodes */}
          {(Object.entries(NODES) as [NK, NodeDef][]).map(([key, node]) => {
            const c      = COLORS[node.group]
            const active = activeNodes.has(key)
            // In overview all nodes are "visible" (no dimming). In specific views non-selected nodes dim out.
            const dimmed = !isOverview && !active

            return (
              <div
                key={key}
                style={{
                  position: 'absolute',
                  left:   `${(node.x / VW) * 100}%`,
                  top:    `${(node.y / VH) * 100}%`,
                  width:  `${(NW / VW) * 100}%`,
                  height: `${(NH / VH) * 100}%`,
                  background: active
                    ? `linear-gradient(135deg, ${c.bg}f0, ${c.bg}cc)`
                    : dimmed ? '#05090f' : '#0d1526',
                  border: `1.5px solid ${active ? c.border : dimmed ? '#0d1526' : '#1e3048'}`,
                  borderRadius: '12px',
                  boxShadow: active
                    ? `0 0 20px ${c.glow}, 0 0 40px ${c.glow}44, inset 0 1px 0 ${c.border}33`
                    : 'none',
                  transform: active ? 'scale(1.06)' : 'scale(1)',
                  transition: 'all 0.38s cubic-bezier(0.34,1.56,0.64,1)',
                  opacity: dimmed ? 0.2 : 1,
                  zIndex: active ? 20 : 5,
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 10px',
                  gap: '8px',
                  cursor: 'default',
                }}
              >
                <span style={{ fontSize: '16px', flexShrink: 0 }}>{EMOJI[node.group]}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: '10.5px', fontWeight: 600,
                    color: active ? c.text : dimmed ? '#1e293b' : '#2d4a6a',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    transition: 'color 0.3s',
                  }}>
                    {node.label}
                  </div>
                  <div style={{
                    fontSize: '9px',
                    color: active ? `${c.text}88` : dimmed ? '#0f172a' : '#1e3048',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    transition: 'color 0.3s', marginTop: '1px',
                  }}>
                    {node.sub}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Bottom Panel ── */}
      <div style={{ borderTop: '1px solid #1e293b', backgroundColor: '#03071a', flexShrink: 0 }}>

        {/* View tab bar */}
        <div style={{ padding: '10px 32px 0', display: 'flex', gap: '6px', alignItems: 'center' }}>
          {VIEWS.map((v, i) => {
            const color   = VIEW_COLOR[v.id]
            const isActive = i === viewIdx
            return (
              <button
                key={v.id}
                className="fc-view-btn"
                onClick={() => setViewIdx(i)}
                style={{
                  padding: '5px 13px',
                  borderRadius: '7px',
                  border: `1px solid ${isActive ? color : '#1e293b'}`,
                  backgroundColor: isActive ? `${color}1e` : 'transparent',
                  color: isActive ? color : '#475569',
                  fontSize: '11.5px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {v.label}
              </button>
            )
          })}

          {/* View counter + prev/next */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', color: '#334155' }}>
              {viewIdx + 1}&thinsp;/&thinsp;{VIEWS.length}
            </span>
            <button
              onClick={() => setViewIdx(i => Math.max(0, i - 1))}
              disabled={viewIdx === 0}
              style={navBtn}
            >
              <ChevronLeft size={14} />
            </button>
            <button
              onClick={() => setViewIdx(i => Math.min(VIEWS.length - 1, i + 1))}
              disabled={viewIdx === VIEWS.length - 1}
              style={navBtn}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>

        {/* Description */}
        <div key={viewIdx} className="fc-desc-in" style={{ padding: '10px 32px 16px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
          <span style={{
            flexShrink: 0,
            fontSize: '10px', fontWeight: 700,
            padding: '3px 8px', borderRadius: '5px',
            backgroundColor: `${accent}1e`,
            color: accent,
            border: `1px solid ${accent}44`,
            whiteSpace: 'nowrap',
            marginTop: '2px',
            letterSpacing: '0.5px',
          }}>
            {view.id.toUpperCase().replace('-', '+')}
          </span>
          <div>
            <p style={{ margin: 0, fontSize: '12.5px', fontWeight: 600, color: '#e2e8f0' }}>
              {view.title}
            </p>
            <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: '#64748b', lineHeight: 1.65, whiteSpace: 'pre-line' }}>
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
  width: '28px', height: '28px', borderRadius: '7px', border: 'none',
  backgroundColor: '#0f172a', color: '#334155', cursor: 'pointer',
}
