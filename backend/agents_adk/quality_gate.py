"""
Quality Gate Agent — ADK LlmAgent (C1)
=======================================
Pre-compliance quality evaluator inserted between CampaignEvaluatorAgent and
ComplianceGateAgent in the CorrectionLoop.

Agentic pattern: Quality Gate / Reflection
  The LLM objectively scores the selected campaign on 4 dimensions (1-10).
  If quality_score < 7, guard_compliance_input (before_agent_callback on
  ComplianceGateAgent) intercepts the compliance step and returns a REJECTED
  fallback — causing the LoopAgent to iterate and regenerate with quality
  feedback incorporated.

State consumed : session.state["campaign"]         (CampaignEvaluatorAgent)
                 session.state["risk_assessment"]  (RiskAnalystAgent)
State produced : output_key="quality_result"
                   quality_score     : float (avg of 4 dims, 1-10)
                   clarity           : int   (1-10)
                   cta_strength      : int   (1-10)
                   tone_fit          : int   (1-10)
                   offer_relevance   : int   (1-10)
                   quality_feedback  : str   (issues if score < 7, empty otherwise)
                   recommendations   : list  (improvements if score < 7)

Loop control:
  QualityGateAgent does NOT call exit_loop.
  guard_compliance_input in callbacks.py reads quality_result and short-circuits
  ComplianceGateAgent when quality_score < 7, injecting a REJECTED compliance
  result so the loop naturally continues to the next iteration.
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

from agents_adk.callbacks import guard_quality_input, log_quality_verdict, route_to_pro_if_borderline  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _quality_instruction(ctx: ReadonlyContext) -> str:
    campaign = ctx.state.get("campaign", "(no campaign generated)")
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    return f"""\
You are a senior financial marketing quality reviewer.
Your task is to evaluate the campaign below and assign an objective quality score.

=== CUSTOMER CONTEXT ===

Risk assessment:
{risk}

=== CAMPAIGN TO EVALUATE ===

{campaign}

=== SCORING DIMENSIONS ===

Score each dimension 1-10 (be strict — 7 means "good enough to send to a customer"):

1. clarity (1-10)
   - 9-10: crystal clear, zero ambiguity, customer instantly understands the offer
   - 7-8 : clear, minor wording issues that don't affect understanding
   - 5-6 : some confusing phrases or financial jargon a customer wouldn't understand
   - 1-4 : unclear message, hard to understand what is being offered

2. cta_strength (1-10)
   - 9-10: specific action, concrete next step, urgent without pressure
   - 7-8 : good CTA with clear direction, minor improvements possible
   - 5-6 : vague CTA ("contact us", "learn more") or missing urgency
   - 1-4 : no clear CTA or it is confusing/contradictory

3. tone_fit (1-10)
   Tone requirements by segment:
   - SUPER-PRIME / PRIME  : formal or aspirational, institutional credibility
   - NEAR-PRIME           : friendly-professional, supportive, approachable
   - SUBPRIME             : warm, empathetic, non-condescending, hope-oriented
   - 9-10: tone is exactly right for the segment
   - 7-8 : mostly correct, minor mismatches
   - 5-6 : noticeable tone mismatch (e.g. urgent language for SUBPRIME)
   - 1-4 : completely wrong tone (e.g. cold/formal for SUBPRIME)

4. offer_relevance (1-10)
   - 9-10: product is a perfect match for the customer profile (segment, DTI, score)
   - 7-8 : good match, minor gaps between product features and customer needs
   - 5-6 : product is generic, not clearly tailored to this specific profile
   - 1-4 : product seems mismatched (e.g. premium product offered to SUBPRIME)

=== CALCULATION ===

quality_score = round((clarity + cta_strength + tone_fit + offer_relevance) / 4, 1)

=== OUTPUT RULES ===

- Return ONLY valid JSON. No markdown, no explanation outside the JSON.
- Do NOT call any function or tool. Your only output is the JSON object below.
- If quality_score >= 7: quality_feedback must be an empty string and recommendations an empty array.
- If quality_score < 7: quality_feedback must list the specific issues found (1-3 sentences).
  recommendations must list 2-4 concrete, actionable improvements.

Return ONLY valid JSON:
{{
  "quality_score"    : number (average, 1 decimal),
  "clarity"          : integer (1-10),
  "cta_strength"     : integer (1-10),
  "tone_fit"         : integer (1-10),
  "offer_relevance"  : integer (1-10),
  "quality_feedback" : string (empty if score >= 7, specific issues if < 7),
  "recommendations"  : array of strings (empty if score >= 7, 2-4 items if < 7)
}}
"""


# ── QualityGateAgent ──────────────────────────────────────────────────────────
quality_gate = LlmAgent(
    name="QualityGateAgent",
    model=_MODEL,
    description=(
        "Pre-compliance quality evaluator. Scores the generated campaign 1-10 "
        "on clarity, CTA strength, tone-segment fit, and offer appropriateness. "
        "Campaigns scoring below 7 trigger automatic regeneration via the "
        "guard_compliance_input callback, which injects a REJECTED compliance result "
        "to continue the correction loop without calling the LLM compliance agent."
    ),
    instruction=_quality_instruction,
    tools=[],  # No exit_loop — loop control handled by guard_compliance_input callback
    output_key="quality_result",
    before_model_callback=route_to_pro_if_borderline,
    before_agent_callback=guard_quality_input,
    after_agent_callback=log_quality_verdict,
)
