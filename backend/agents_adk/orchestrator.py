"""
FinCampaign Orchestrator — ADK LlmAgent (E4) ★ THE SHOWCASE ★
===============================================================
Replaces the hardcoded if/elif routing in orchestrator.py (542 lines).

The LLM reads the risk_assessment from session state and DECIDES which pipeline
to invoke by calling transfer_to_agent(). No hardcoded conditions — the model
reasons about the segment, eligibility, and DTI to pick the right route.

Agentic pattern: LLM-driven dynamic routing
  Before (manual): if segment == "DEEP-SUBPRIME": route = "EDUCATIONAL"
  After (ADK):      LlmAgent reads {risk_assessment} → calls transfer_to_agent()

Available routes:
  EducationalAgent    — DEEP-SUBPRIME: no credit offer, rehabilitation plan
  PremiumPipeline     — SUPER-PRIME: fast-track, single compliance pass
  ConditionalAgent    — SUBPRIME ineligible: exact improvement path to qualify
  CorrectionLoop      — PRIME / NEAR-PRIME / eligible SUBPRIME: full loop

State consumed: session.state["risk_assessment"]  (set by RiskAnalystAgent)
State produced: none (delegates entirely to sub-agent via transfer_to_agent)
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.genai import types  # noqa: E402

from agents_adk.educational_agent import educational_agent  # noqa: E402
from agents_adk.premium_pipeline import premium_pipeline  # noqa: E402
from agents_adk.conditional_agent import conditional_agent  # noqa: E402
from agents_adk.correction_loop import correction_loop  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _orchestrator_instruction(ctx: ReadonlyContext) -> str:
    risk = ctx.state.get("risk_assessment", "")
    return f"""\
You are the FinCampaign routing orchestrator. Your only job is to read the risk
assessment below and use the transfer_to_agent tool to route to the correct sub-agent.

Risk assessment:
{risk}

=== ROUTING DECISION ===

Read the "segment" and "eligible_for_credit" fields from the risk assessment.
Use the transfer_to_agent tool with the agent_name shown below:

- segment is "DEEP-SUBPRIME"
  agent_name: "EducationalAgent"

- segment is "SUPER-PRIME"
  agent_name: "PremiumPipeline"

- segment is "SUBPRIME" AND eligible_for_credit is false
  agent_name: "ConditionalAgent"

- All other cases (PRIME, NEAR-PRIME, eligible SUBPRIME)
  agent_name: "CorrectionLoop"

=== RULES ===
- Use transfer_to_agent immediately. Do not generate campaign content.
- Do not explain or justify the routing. Just transfer.
- Transfer exactly once to exactly one of these agent names:
  EducationalAgent | PremiumPipeline | ConditionalAgent | CorrectionLoop
"""


# ── FinCampaignOrchestrator ───────────────────────────────────────────────────
orchestrator = LlmAgent(
    name="FinCampaignOrchestrator",
    model=_MODEL,
    description=(
        "Dynamic routing orchestrator for financial campaigns. Reads the risk assessment "
        "and routes each customer to the appropriate pipeline: educational rehabilitation, "
        "premium fast-track, conditional improvement offer, or standard with auto-correction."
    ),
    instruction=_orchestrator_instruction,
    sub_agents=[
        educational_agent,   # DEEP-SUBPRIME → rehabilitation plan
        premium_pipeline,    # SUPER-PRIME   → fast-track campaign
        conditional_agent,   # SUBPRIME ineligible → conditional path
        correction_loop,     # PRIME/NEAR-PRIME → full loop
    ],
)
