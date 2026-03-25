"""
Campaign Evaluator Agent — ADK LlmAgent (C3)
============================================
Fan-in step after CampaignVariants (ParallelAgent).

Reads the 3 campaign variants generated in parallel and selects the best one
based on: clarity, CTA strength, tone-segment fit, and compliance alignment.

This implements the LLM-as-Judge agentic pattern:
  - The LLM objectively scores each variant on multiple dimensions
  - Picks the winner and writes it to output_key="campaign"
  - The compliance gate then evaluates that selected campaign

On correction iterations: also considers compliance feedback to prefer
the variant that best addresses the previously flagged issues.

State consumed : session.state["campaign_formal"]    (FormalCampaignAgent)
                 session.state["campaign_friendly"]  (FriendlyCampaignAgent)
                 session.state["campaign_urgent"]    (UrgentCampaignAgent)
                 session.state["compliance_result"]  (previous iteration, may be empty)
                 session.state["risk_assessment"]    (RiskAnalystAgent)
State produced : output_key="campaign"  (the selected best variant)
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
from agents_adk.callbacks import log_evaluator_selection, route_to_pro_if_borderline  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _evaluator_instruction(ctx: ReadonlyContext) -> str:
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    formal = ctx.state.get("campaign_formal", "(not generated)")
    friendly = ctx.state.get("campaign_friendly", "(not generated)")
    urgent = ctx.state.get("campaign_urgent", "(not generated)")
    compliance = (ctx.state.get("compliance_result") or "").strip()

    correction_criterion = ""
    correction_rule = ""
    if compliance and ("REJECTED" in compliance or "REVIEW" in compliance):
        correction_criterion = (
            "\n6. Issue resolution: Does the variant fix ALL the specific issues "
            "mentioned in the compliance warnings?\n"
            "   (A variant that ignores the compliance warnings should score 0 here)"
        )
        correction_rule = (
            f"\nCompliance feedback from previous attempt:\n{compliance}\n"
            "\nHeavily favor the variant that resolves ALL compliance warnings."
        )

    return f"""\
You are a senior financial marketing evaluator. Your job is to objectively score
3 campaign variants and select the best one for this specific customer.

=== CUSTOMER CONTEXT ===
Risk assessment:
{risk}
{correction_rule}

=== THE 3 VARIANTS ===

VARIANT A — Formal tone:
{formal}

VARIANT B — Friendly tone:
{friendly}

VARIANT C — Urgent tone:
{urgent}

=== EVALUATION CRITERIA ===

Score each variant 1–10 on:
1. Clarity        : Is the message clear and easy to understand?
2. CTA strength   : Is the call-to-action compelling and specific?
3. Tone-fit       : Does the tone match the customer's segment and risk profile?
                    (SUPER-PRIME/PRIME: formal or urgent | NEAR-PRIME: friendly or formal |
                     SUBPRIME: friendly, supportive)
4. Compliance     : Does it avoid guaranteed-approval language? Are rates stated?
5. Differentiation: Is it memorable and distinct from a generic offer?{correction_criterion}

=== SELECTION RULE ===
Pick the variant with the highest TOTAL score.
If two variants tie, prefer the one with higher Tone-fit + Compliance scores.

=== OUTPUT ===
Return ONLY the JSON of the WINNING variant — exactly as it was in the input,
with no modifications. Do not merge variants. Do not add commentary.
Just copy the JSON of the selected variant as-is.

The output must be valid JSON with these exact fields:
"product_name": string
"campaign_message": string
"key_benefits": array of strings
"cta": string
"channel": string
"rates": string
"""


# ── CampaignEvaluatorAgent ────────────────────────────────────────────────────
campaign_evaluator = LlmAgent(
    name="CampaignEvaluatorAgent",
    model=_MODEL,
    description=(
        "LLM-as-Judge: evaluates 3 campaign variants (formal, friendly, urgent) "
        "and selects the best one for the customer's profile. "
        "Implements the fan-in step of the A/B campaign pattern."
    ),
    instruction=_evaluator_instruction,
    # No tools needed — evaluator reasons purely from session state
    output_key="campaign",
    before_model_callback=route_to_pro_if_borderline,
    after_agent_callback=log_evaluator_selection,
)
