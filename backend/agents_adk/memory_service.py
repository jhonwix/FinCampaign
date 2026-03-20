"""
Memory Service — ADK (E7)
==========================
Provides customer long-term memory for the FinCampaign agent system.

Replaces:
  - backend/tools/customer_memory.py   (151 lines — manual memory card builder)
  - customer_interactions table        (raw event log)
  - customer_memory table              (aggregated memory card)

ADK handles memory automatically:
  - After each session, Runner.add_session_to_memory() extracts key facts and
    stores them (structured extraction by Gemini for Vertex, keyword index for
    InMemory).
  - During a session, LlmAgent with load_memory tool calls
    memory_service.search_memory(user_id=customer_id) to retrieve past context.

Memory backend selection (set env var to switch):
  - VERTEX_AI_MEMORY_AGENT_ENGINE_ID not set → InMemoryMemoryService (local dev)
  - VERTEX_AI_MEMORY_AGENT_ENGINE_ID set → VertexAiMemoryBankService (production)

Usage in adk web (with persistent Vertex memory):
  adk web agents_adk --memory_service_uri vertex://projects/{PROJECT}/locations/{LOC}/reasoningEngines/{ID}

Or set VERTEX_AI_MEMORY_AGENT_ENGINE_ID in .env and the memory_service exported
here will be used when building a custom Runner programmatically.
"""
import os
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.memory import BaseMemoryService, InMemoryMemoryService  # noqa: E402

_agent_engine_id: str = os.environ.get("VERTEX_AI_MEMORY_AGENT_ENGINE_ID", "").strip()

if _agent_engine_id:
    # Production: Vertex AI Memory Bank Service (requires Agent Engine — E8)
    from google.adk.memory import VertexAiMemoryBankService  # noqa: E402

    memory_service: BaseMemoryService = VertexAiMemoryBankService(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        agent_engine_id=_agent_engine_id,
    )
    _memory_backend = "VertexAiMemoryBankService"
else:
    # Local dev / CI: in-memory keyword matching — zero config, zero cost
    memory_service = InMemoryMemoryService()
    _memory_backend = "InMemoryMemoryService"
