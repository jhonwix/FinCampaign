"""
Campaign Variants -- ADK ParallelAgent (C3)
===========================================
KB pre-injection: search_financial_kb called at instruction-build time.
LLM receives catalog + policies directly -- no tool call round-trip.

State consumed : session.state["risk_assessment"]   (RiskAnalystAgent)
                 session.state["compliance_result"]  (optional)
State produced : session.state["campaign_formal"]    (FormalCampaignAgent)
                 session.state["campaign_friendly"]  (FriendlyCampaignAgent)
                 session.state["campaign_urgent"]    (UrgentCampaignAgent)
"""
import json
import sys
from pathlib import Path
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
from google.adk.agents import LlmAgent, ParallelAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from agents_adk.search_tool import search_financial_kb  # noqa: E402
from agents_adk.callbacks import _parse_state_json, route_to_pro_if_borderline  # noqa: E402
from google.genai import types  # noqa: E402
from config import settings  # noqa: E402
_MODEL = Gemini(model='gemini-2.5-flash-lite', retry_options=types.HttpRetryOptions(attempts=3))

def _make_variant_instruction(tone_block: str):
    """Returns an InstructionProvider callable. KB pre-fetched at instruction time."""
    def _instruction(ctx: ReadonlyContext) -> str:
        risk = ctx.state.get("risk_assessment", "(no risk assessment available)")
        compliance = (ctx.state.get("compliance_result") or "").strip()
        quality_data = _parse_state_json(ctx.state.get("quality_result") or {})
        quality_score = quality_data.get("quality_score") if quality_data else None
        quality_feedback = quality_data.get("quality_feedback", "")
        try:
            risk_data = json.loads(risk) if isinstance(risk, str) else {}
            segment = risk_data.get("segment", "PRIME") if isinstance(risk_data, dict) else "PRIME"
        except Exception:
            segment = "PRIME"
        kb = search_financial_kb(
            f"product catalog {segment} segment interest rates compliance rules tone guidelines"
        )
        if compliance and ("REJECTED" in compliance or "REVIEW" in compliance):
            mode = (
                "CORRECT mode: the previous campaign was rejected." + chr(10)
                + "Fix EVERY warning listed below." + chr(10) + chr(10)
                + "Compliance feedback:" + chr(10) + compliance
            )
            if quality_score is not None and quality_score < 7:
                mode += (
                    chr(10) + chr(10)
                    + f"Quality feedback (score {quality_score}/10):" + chr(10)
                    + quality_feedback
                )
        elif quality_score is not None and quality_score < 7:
            mode = (
                f"CORRECT mode: the previous campaign failed quality review (score {quality_score}/10)."
                + chr(10) + "Issues to fix:" + chr(10) + quality_feedback
            )
        else:
            mode = "FRESH mode: generate a new campaign from scratch."
        return f"""You are a financial marketing specialist for a consumer lending institution.
You generate personalized credit campaign messages in Spanish.

=== INPUTS ===

Risk assessment:
{risk}

=== KNOWLEDGE BASE ===

{kb}

=== MODE ===

{mode}

=== TASK ===

Generate the campaign in YOUR SPECIFIC TONE (see below).

Rules for ALL tones:
  - Always include the specific interest rate range (e.g. 12%%-18%% anual)
  - Never guarantee approval
  - Keep campaign_message under 150 words
  - If segment is DEEP-SUBPRIME: return product_name=NO_OFFER, empty campaign_message

Return ONLY valid JSON:
{tone_block}"""
    return _instruction

_FORMAL_TONE = (
    "=== YOUR TONE: FORMAL ===" + chr(10)
    + "Write in a professional, institutional voice. Use precise financial language." + chr(10)
    + "Focus on: rates, terms, security, and credibility of the institution." + chr(10)
    + "Avoid: colloquialisms, exclamation marks, urgency pressure." + chr(10)
)
_FRIENDLY_TONE = (
    "=== YOUR TONE: FRIENDLY ===" + chr(10)
    + "Write in a warm, conversational voice. Make the customer feel supported." + chr(10)
    + "Focus on: how this product helps them, simplicity of the process." + chr(10)
    + "Avoid: cold financial jargon, hard-sell language." + chr(10)
)
_URGENT_TONE = (
    "=== YOUR TONE: URGENT ===" + chr(10)
    + "Write in an action-oriented, motivating voice. Create a sense of opportunity." + chr(10)
    + "Focus on: timing (ahora, hoy), exclusivity (oferta personalizada para ti)." + chr(10)
    + "Avoid: pressure tactics, false scarcity, guaranteed approval language." + chr(10)
)

_formal_campaign = LlmAgent(
    name="FormalCampaignAgent", model=_MODEL,
    description="Generates a credit campaign in FORMAL tone: institutional, professional.",
    instruction=_make_variant_instruction(_FORMAL_TONE),
    tools=[], output_key="campaign_formal",
    before_model_callback=route_to_pro_if_borderline,
)
_friendly_campaign = LlmAgent(
    name="FriendlyCampaignAgent", model=_MODEL,
    description="Generates a credit campaign in FRIENDLY tone: warm, conversational.",
    instruction=_make_variant_instruction(_FRIENDLY_TONE),
    tools=[], output_key="campaign_friendly",
    before_model_callback=route_to_pro_if_borderline,
)
_urgent_campaign = LlmAgent(
    name="UrgentCampaignAgent", model=_MODEL,
    description="Generates a credit campaign in URGENT tone: action-oriented, motivating.",
    instruction=_make_variant_instruction(_URGENT_TONE),
    tools=[], output_key="campaign_urgent",
    before_model_callback=route_to_pro_if_borderline,
)
campaign_variants = ParallelAgent(
    name="CampaignVariants",
    description=(
        "Fan-out: generates 3 campaign variants simultaneously (formal / friendly / urgent). "
        "CampaignEvaluatorAgent selects the best variant after all 3 complete."
    ),
    sub_agents=[_formal_campaign, _friendly_campaign, _urgent_campaign],
)

