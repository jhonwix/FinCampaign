# FinCampaign — ADK Web UI launcher (PowerShell)
# ================================================
# Runs `adk web` with persistent SQLite sessions (T1).
# Sessions survive between restarts — run the same customer twice
# to see preload_memory inject past campaign history automatically.
#
# Usage:
#   cd backend
#   .\run_adk.ps1
#
# Opens: http://localhost:8000
#
# Session storage: backend/sessions.db (SQLite, local, zero GCP cost)
# Memory service:  InMemoryMemoryService (default) — or VertexAiMemoryBankService
#                  if VERTEX_AI_MEMORY_AGENT_ENGINE_ID is set in .env

$env:PYTHONIOENCODING = "utf-8"

adk web --session_service_uri "sqlite:///./sessions.db"
