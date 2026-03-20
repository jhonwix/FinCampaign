"""
Conditional Offer Agent -- ADK version (E4)
===========================================
Triggered for SUBPRIME customers who are close to qualifying.
KB pre-injection (refactor): search_financial_kb called at instruction-build
time. LLM receives eligibility requirements + product catalog directly.

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


def _conditional_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "minimum eligibility requirements DTI threshold credit score conditional offer improve qualify product catalog SUBPRIME"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    return f"""You are a financial advisor at a consumer lending institution in Latin America.
You help near-eligible SUBPRIME customers understand exactly what to improve to qualify.

The risk assessment is:
{risk}

=== ELIGIBILITY REQUIREMENTS & PRODUCT CATALOG (from knowledge base) ===

{kb}

Steps:
1. From the risk assessment, compute the improvement gaps:
   - DTI gap: if dti > 48%% (target), compute (dti - 48%%) and monthly debt reduction needed
   - Score gap: if score < 600, compute (600 - score)
   - Late payment gap: if late_payments > 3, compute excess
2. Estimate months to reach eligibility (range: 3-12 months).
3. Generate a conditional offer message in Spanish that:
   - Acknowledges their situation with empathy (mention actual DTI%% and score)
   - States EXACTLY what to achieve (specific DTI target, monthly debt reduction)
   - Names the specific target product they could qualify for once improved
   - Sets a realistic timeline
   - Is under 200 words

Eligibility thresholds: DTI <=48%%, credit score >=600, late payments <=3.

Return ONLY valid JSON:
"product_name": string (target product the customer could qualify for)
"campaign_message": string (Spanish, under 200 words, specific numbers)
"key_benefits": array of 2-3 strings (improvement steps with exact targets and timelines)
"cta": string (motivating CTA toward improvement goal)
"channel": string
"rates": string (Aplica una vez cumplidas las condiciones: X%%-Y%% anual)
"""


conditional_agent = LlmAgent(
    name="ConditionalAgent",
    model=_MODEL,
    description=(
        "Financial advisor for near-eligible SUBPRIME customers. Generates a "
        "conditional offer showing exactly what to improve to qualify for credit."
    ),
    instruction=_conditional_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="campaign",
)
