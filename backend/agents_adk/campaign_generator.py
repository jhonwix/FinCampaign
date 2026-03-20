"""
Campaign Generator Agent -- ADK version (E2)
=============================================
Receives the risk assessment from session.state and generates a personalized
credit campaign.

KB pre-injection (refactor): search_financial_kb called at instruction-build
time with a segment-aware query. LLM receives product catalog + tone guidelines
directly -- no tool call round-trip.

State consumed : session.state["risk_assessment"]  (set by RiskAnalystAgent)
State produced : output_key="campaign"             (read by ComplianceCheckerAgent)
"""
import json
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.genai import types  # noqa: E402
from agents_adk.search_tool import search_financial_kb  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _campaign_gen_instruction(ctx: ReadonlyContext) -> str:
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    # Extract segment for a targeted KB query
    try:
        risk_data = json.loads(risk) if isinstance(risk, str) else {}
        segment = risk_data.get("segment", "PRIME") if isinstance(risk_data, dict) else "PRIME"
    except Exception:
        segment = "PRIME"
    kb = search_financial_kb(
        f"product catalog {segment} interest rate ranges campaign tone guidelines"
    )
    return f"""You are a financial marketing specialist for a consumer lending institution.
You generate personalized credit campaign messages in Spanish.

The risk assessment from the credit risk analyst is:
{risk}

=== PRODUCT CATALOG & TONE GUIDELINES (from knowledge base) ===

{kb}

Steps:
1. Extract segment, risk_level, dti, eligible_for_credit, and recommended_products from the risk assessment.
2. If eligible_for_credit is false OR segment is DEEP-SUBPRIME, return a placeholder: product_name="NO_OFFER", empty campaign_message.
3. Generate the campaign in Spanish using the catalog information above.

Tone rules by segment:
- SUPER-PRIME / PRIME  : Premium, exclusive, aspirational tone.
- NEAR-PRIME           : Empowering, opportunity-focused tone.
- SUBPRIME             : Supportive, trust-building, responsible tone.
- DEEP-SUBPRIME        : Return NO_OFFER placeholder.

Campaign rules:
- Always include the specific interest rate range from the catalog.
- Never guarantee approval.
- Keep campaign_message under 150 words.

Return ONLY valid JSON:
"product_name": string
"campaign_message": string (Spanish, under 150 words)
"key_benefits": array of strings
"cta": string
"channel": string (one of: email, whatsapp, sms, push)
"rates": string (e.g. "12%%-18%% annual")
"""


# -- CampaignGeneratorAgent ------------------------------------------------
campaign_agent = LlmAgent(
    name="CampaignGeneratorAgent",
    model=_MODEL,
    description=(
        "Financial marketing specialist. Uses the risk assessment and pre-injected "
        "product catalog to generate a personalized credit campaign in Spanish, "
        "with segment-appropriate tone and disclosed rates."
    ),
    instruction=_campaign_gen_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="campaign",
)
