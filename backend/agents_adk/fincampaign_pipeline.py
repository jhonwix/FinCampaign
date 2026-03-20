"""
FinCampaign Pipeline — Top-level ADK SequentialAgent (E4 + C4)
==============================================================
The root agent for `adk web`. Three declarative steps:

  Step 1 — RiskAnalystAgent       : assess customer → session.state["risk_assessment"]
  Step 2 — FinCampaignOrchestrator: read assessment → transfer_to_agent(correct_pipeline)
                                    any route writes → session.state["campaign"]
  Step 3 — ExplainabilityAgent    : read risk+campaign → session.state["explanation"]
                                    customer-facing justification in plain Spanish

C4: ExplainabilityAgent added as final step. It runs after ANY of the 4 routes
completes, reading the already-finalized campaign from session.state.
No tools required — pure LLM reasoning from pipeline outputs.

Complete agent hierarchy:
  FinCampaignPipeline (SequentialAgent)  ← ROOT
  ├── RiskAnalystAgent (LlmAgent)         → risk_assessment  [VertexAiSearch + preload_memory]
  ├── FinCampaignOrchestrator (LlmAgent)  ← reads {risk_assessment}, routes via transfer_to_agent
  │    ├── EducationalAgent (LlmAgent)    → DEEP-SUBPRIME  → campaign
  │    ├── PremiumPipeline (Sequential)   → SUPER-PRIME
  │    │   ├── PremiumCampaignAgent       → campaign
  │    │   └── PremiumComplianceAgent     → compliance_result
  │    ├── ConditionalAgent (LlmAgent)    → SUBPRIME ineligible → campaign
  │    └── CorrectionLoop (LoopAgent)     → PRIME/NEAR-PRIME
  │        ├── CampaignVariantStep (Sequential)
  │        │   ├── CampaignVariants (Parallel) → campaign_formal/friendly/urgent
  │        │   └── CampaignEvaluatorAgent      → campaign (best of 3)
  │        └── ComplianceGateAgent             → compliance_result + exit_loop
  └── ExplainabilityAgent (LlmAgent)      → explanation  [no tools — reads state only]
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import SequentialAgent  # noqa: E402

from agents_adk.risk_analyst import risk_analyst_agent        # noqa: E402
from agents_adk.orchestrator import orchestrator              # noqa: E402
from agents_adk.explainability_agent import explainability_agent  # noqa: E402

# ── FinCampaignPipeline ───────────────────────────────────────────────────────
fincampaign_pipeline = SequentialAgent(
    name="FinCampaignPipeline",
    description=(
        "End-to-end financial campaign pipeline. "
        "Step 1: credit risk assessment. "
        "Step 2: LLM-driven routing to the appropriate campaign pipeline. "
        "Step 3: customer-facing explanation of the decision in plain Spanish."
    ),
    sub_agents=[
        risk_analyst_agent,     # → session.state["risk_assessment"]
        orchestrator,           # → transfer_to_agent → session.state["campaign"]
        explainability_agent,   # → session.state["explanation"]  (C4)
    ],
)
