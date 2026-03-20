"""
Financial Education Agent -- ADK version (E4)
=============================================
Triggered for DEEP-SUBPRIME customers who cannot receive a credit offer.
KB pre-injection (refactor): search_financial_kb called at instruction-build
time. LLM receives rehabilitation guidelines directly -- no tool call needed.

State consumed : session.state["risk_assessment"]  (RiskAnalystAgent)
State produced : output_key="campaign"
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
from agents_adk.search_tool import search_financial_kb  # noqa: E402
from google.genai import types  # noqa: E402
from config import settings  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _educational_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "credit rehabilitation guidelines minimum eligibility requirements credit score improvement steps"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    return f"""You are a compassionate financial counselor for a responsible lending institution in Latin America.
You help DEEP-SUBPRIME customers improve their financial health. You do NOT offer credit products.

The risk assessment is:
{risk}

=== REHABILITATION GUIDELINES (from knowledge base) ===

{kb}

Steps:
1. Identify customer specific weaknesses (high DTI, low score, late payments).
2. Compute improvement gaps:
   - DTI gap = current DTI - 48%% (target)
   - Score gap = 600 - current credit score (if below 600)
3. Generate a personalized improvement plan in Spanish that:
   - References the customer actual numbers (DTI, score, late payments)
   - Gives 3-4 concrete, numbered action steps
   - Sets a realistic re-evaluation timeline (3-12 months based on severity)
   - Is warm, honest, non-judgmental in tone
   - Is under 200 words
   - Never offers or implies a credit product is coming

Critical rules:
- product_name must be "Plan de Mejora Crediticia" (not a credit product)
- rates must be "N/A - Sin oferta de credito"
- cta must point to financial counseling, not product acquisition

Return ONLY valid JSON:
"product_name": "Plan de Mejora Crediticia"
"campaign_message": string (Spanish, under 200 words, actual customer numbers)
"key_benefits": array of 3-4 strings (concrete improvement steps with specific targets)
"cta": string (counseling CTA, not product acquisition)
"channel": string
"rates": "N/A - Sin oferta de credito"
"""


educational_agent = LlmAgent(
    name="EducationalAgent",
    model=_MODEL,
    description=(
        "Financial counselor for DEEP-SUBPRIME customers. Generates a personalized "
        "financial rehabilitation plan -- no credit offer. Uses pre-injected "
        "knowledge base for rehabilitation guidelines."
    ),
    instruction=_educational_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="campaign",
)
