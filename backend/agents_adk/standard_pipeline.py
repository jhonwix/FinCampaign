"""
Standard Pipeline — ADK SequentialAgent (E2 + E3)
===================================================
Replaces the manual Risk→Campaign→Compliance pipeline in orchestrator.py.

Before (manual): imperative Python in orchestrator.py — explicit await chains,
                 manual state passing, manual while-loop for corrections
After (ADK):     declarative SequentialAgent + nested LoopAgent for auto-correction

Agentic patterns demonstrated:
  - Orchestration  : SequentialAgent runs Risk → CorrectionLoop in order
  - Reflection     : LoopAgent(CampaignCorrector + ComplianceGate) auto-corrects

State flow:
  user message
    → RiskAnalystAgent                        → session.state["risk_assessment"]
    → CorrectionLoop (LoopAgent, max 3 iter)
        → CampaignCorrectorAgent              → session.state["campaign"]
        → ComplianceGateAgent                 → session.state["compliance_result"]
             if APPROVED → calls exit_loop()  → loop exits, pipeline completes
             if REJECTED → no exit_loop       → next iteration corrects campaign
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import SequentialAgent  # noqa: E402

from agents_adk.risk_analyst import risk_analyst_agent  # noqa: E402
from agents_adk.correction_loop import correction_loop   # noqa: E402

# ── StandardPipeline ──────────────────────────────────────────────────────────
# Used for PRIME / NEAR-PRIME / SUBPRIME customers (eligible segments).
# E4 will wrap this inside the Orchestrator LlmAgent for dynamic routing.
standard_pipeline = SequentialAgent(
    name="StandardPipeline",
    description=(
        "Full campaign pipeline for eligible customers (PRIME / NEAR-PRIME / SUBPRIME). "
        "Runs: risk assessment → correction loop (campaign + compliance, up to 3 attempts). "
        "The correction loop exits automatically when the campaign passes compliance."
    ),
    sub_agents=[
        risk_analyst_agent,  # → session.state["risk_assessment"]
        correction_loop,     # LoopAgent: campaign ↔ compliance until approved or max 3 iter
    ],
)
