"""
FinCampaign — ADK Multi-Agent System
=====================================
Punto de entrada para `adk web agents_adk` (ejecutar desde backend/).

Fase E — Migración a Google ADK (Agent Development Kit):
  E1   RiskAnalystAgent       — LlmAgent + VertexAiSearchTool              ✅
  E2   StandardPipeline       — SequentialAgent (Risk→Campaign→Compliance)  ✅
  E3   CorrectionLoop         — LoopAgent (Campaign↔Compliance, max 3 iter) ✅
  EA1  Gemini() + retry       — modelo con retry_options en todos agentes    ✅
  EA2  App wrapper            — App(root_agent=...) para Agent Engine (E8)   ✅
  E4   Orchestrator           — LlmAgent con transfer_to_agent (routing)     ✅
  E5   VertexAiSearchTool     — reemplaza retriever.py manual (impl. en E1)  ✅
  E6   google_search          — grounding para Compliance                    ✅
  E7   MemoryBankService      — reemplaza customer_memory.py                 ✅
  E8   Agent Engine           — deploy serverless en Vertex AI

Fase C — Patrones Agénticos Avanzados:
  C3   ParallelAgent A/B      — 3 variantes en paralelo + LLM-as-Judge       ✅

TIER 1 — Production hardening:
  T1   SQLiteSessionService   — sesiones persistentes entre reinicios         ✅ (CLI flag)
  T2   ReflectAndRetryPlugin  — auto-retry con reflexión LLM en tool failures ✅
  T3   preload_memory         — memoria inyectada automáticamente en sesión    ✅

Uso estándar (sesiones en RAM, se pierden al reiniciar):
  cd backend
  adk web

Uso recomendado (sesiones persistentes — SQLiteSessionService):
  cd backend
  adk web --session_service_uri sqlite:///./sessions.db

Uso con script (PowerShell):
  .\\run_adk.ps1

Uso (memoria persistente Vertex — después de E8):
  Agregar al .env: VERTEX_AI_MEMORY_AGENT_ENGINE_ID=<id del reasoning engine>
  Luego: adk web agents_adk --session_service_uri sqlite:///./sessions.db
"""
import sys
from pathlib import Path

# ── Ensure backend/ is on sys.path so config, models, etc. are importable ────
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ── Load .env from project root (parent of backend/) ─────────────────────────
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_backend_dir.parent / ".env", override=False)

# ── Credentials + backend ─────────────────────────────────────────────────────
import os  # noqa: E402

# Service account for Vertex AI Search (VertexAiSearchTool / Discovery Engine).
_sa_path = _backend_dir / "service-account.json"
if _sa_path.exists():
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(_sa_path))

# LLM backend: Vertex AI global endpoint via API key (same as FastAPI backend).
# With GOOGLE_GENAI_USE_VERTEXAI=1 + GOOGLE_API_KEY set, google-genai uses:
#   POST https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent?key={KEY}
# This is the global endpoint — no project-specific Model Garden required.
# GOOGLE_API_KEY is loaded from .env by load_dotenv() above.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"

import vertexai  # noqa: E402  — still needed for VertexAiSearchTool

vertexai.init(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "the-bird-364803"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

# ── Plugins ───────────────────────────────────────────────────────────────────
# T2 — ReflectAndRetryToolPlugin: when a tool call fails, the LLM receives
#      structured error feedback and retries up to max_retries times.
#      Handles transient errors (network, rate limits, malformed responses)
#      without crashing the pipeline. @experimental in ADK 1.27.2.
#
# DebugLoggingPlugin: logs every tool call + result as structured JSON.
#      Zero overhead in production — purely additive logging.
from google.adk.plugins import ReflectAndRetryToolPlugin, DebugLoggingPlugin  # noqa: E402

_plugins = [
    ReflectAndRetryToolPlugin(max_retries=2),
    DebugLoggingPlugin(),
]

# ── Root agent + App wrapper ──────────────────────────────────────────────────
from google.adk.apps import App  # noqa: E402

from agents_adk.fincampaign_pipeline import fincampaign_pipeline  # noqa: E402
from agents_adk.memory_service import memory_service, _memory_backend  # noqa: E402

root_agent = fincampaign_pipeline  # used by `adk web`

app = App(
    name="agents_adk",          # must match the directory name for adk web
    root_agent=fincampaign_pipeline,
    plugins=_plugins,
    # plugins can also include BigQueryAgentAnalyticsPlugin for D1 observability
)

# ── Exports ───────────────────────────────────────────────────────────────────
# memory_service: use when building a custom Runner programmatically
#   runner = Runner(agent=root_agent, memory_service=memory_service, ...)
# After E8: set VERTEX_AI_MEMORY_AGENT_ENGINE_ID in .env to auto-upgrade to Vertex.
__all__ = ["root_agent", "app", "memory_service"]
