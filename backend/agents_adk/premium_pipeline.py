"""
Premium Pipeline -- ADK SequentialAgent (E4 route: SUPER-PRIME)
================================================================
Fast-track pipeline for SUPER-PRIME customers.
KB pre-injection (refactor): both agents receive catalog/policy context
without a tool call.

State consumed : session.state["risk_assessment"]  (RiskAnalystAgent)
State produced : session.state["campaign"]          (PremiumCampaignAgent)
                 session.state["compliance_result"] (PremiumComplianceAgent)
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LlmAgent, SequentialAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from agents_adk.search_tool import search_financial_kb  # noqa: E402
from google.genai import types  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _premium_campaign_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "premium product catalog SUPER-PRIME exclusive rates aspirational tone guidelines"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    return f"""You are a financial marketing specialist. Generate a premium credit campaign for a SUPER-PRIME customer.

The risk assessment is:
{risk}

=== KNOWLEDGE BASE ===

{kb}

Instructions:
1. Generate a campaign in Spanish with premium, exclusive, aspirational tone.
2. Always include specific interest rates from the catalog above.
3. Never guarantee approval. Keep campaign_message under 150 words.

Return ONLY valid JSON:
"product_name": string
"campaign_message": string (Spanish, premium tone, under 150 words)
"key_benefits": array of strings
"cta": string (exclusive, aspirational)
"channel": string
"rates": string (e.g. "8%%-12%% annual -- exclusive SUPER-PRIME rate")
"""


def _premium_compliance_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "APR disclosure fair lending compliance rules premium credit products"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    campaign = ctx.state.get("campaign", "(no campaign generated)")
    return f"""You are a regulatory compliance officer. Review this campaign for a SUPER-PRIME customer.

Risk assessment:
{risk}

Campaign to review:
{campaign}

=== COMPLIANCE POLICIES ===

{kb}

Evaluate each compliance dimension:
  - fair_lending  : No discriminatory language; product appropriate for SUPER-PRIME
  - apr_disclosure: Premium rate range clearly stated (e.g. 8%%-12%% annual)
  - messaging     : No guaranteed-approval language
  - channel       : WhatsApp/SMS opt-in; email unsubscribe if applicable

SUPER-PRIME campaigns rarely fail -- be thorough but efficient.

Return ONLY valid JSON:
"fair_lending": "PASS" | "REVIEW" | "FAIL"
"apr_disclosure": "PASS" | "REVIEW" | "FAIL"
"messaging": "PASS" | "REVIEW" | "FAIL"
"channel": "PASS" | "REVIEW" | "FAIL"
"overall_verdict": "APPROVED" | "APPROVED_WITH_WARNINGS" | "REVIEW" | "REJECTED"
"warnings": array of strings
"human_review_required": boolean
"confidence": number (0.0-1.0)
"""


# -- Dedicated agent instances for this pipeline --------------------------
_premium_campaign = LlmAgent(
    name="PremiumCampaignAgent",
    model=_MODEL,
    description="Generates a premium, aspirational campaign for SUPER-PRIME customers.",
    instruction=_premium_campaign_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="campaign",
)
_premium_compliance = LlmAgent(
    name="PremiumComplianceAgent",
    model=_MODEL,
    description=(
        "Single-pass compliance check for SUPER-PRIME campaigns. "
        "Grounds decisions against pre-injected knowledge base context."
    ),
    instruction=_premium_compliance_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="compliance_result",
)

# -- PremiumPipeline -------------------------------------------------------
premium_pipeline = SequentialAgent(
    name="PremiumPipeline",
    description=(
        "Fast-track pipeline for SUPER-PRIME customers. Runs campaign generation "
        "then a single compliance check -- no retry loop needed for premium profiles."
    ),
    sub_agents=[_premium_campaign, _premium_compliance],
)
