"""
Compliance Checker Agent -- ADK version (E2)
=============================================
Mandatory final gate. Reads risk_assessment and campaign from session.state
and reviews the campaign for regulatory compliance.

KB pre-injection (refactor): search_financial_kb called at instruction-build
time. LLM receives all compliance policies directly -- no tool call needed.

State consumed : session.state["risk_assessment"]  (RiskAnalystAgent)
                 session.state["campaign"]          (CampaignGeneratorAgent)
State produced : output_key="compliance_result"
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
from agents_adk.search_tool import search_financial_kb  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _compliance_check_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "APR disclosure rules fair lending UDAP channel consent compliance policies"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    campaign = ctx.state.get("campaign", "(no campaign generated)")
    return f"""You are a regulatory compliance officer for a financial institution.
Review credit campaigns strictly -- when in doubt, flag REVIEW.

The risk assessment is:
{risk}

The campaign to review is:
{campaign}

=== COMPLIANCE POLICIES (from knowledge base) ===

{kb}

Steps:
1. If the customer segment (from risk_assessment) is DEEP-SUBPRIME, immediately return
   overall_verdict="REVIEW" and human_review_required=true.
2. Otherwise evaluate each compliance dimension:

Regulations to enforce:
- Fair Lending  : No discriminatory language; no targeting by protected class.
- TILA/APR      : Rate range must be clearly stated (e.g. "12%%-18%% annual").
- UDAP          : No unfair, deceptive language; no guaranteed-approval claims.
- Channel       : WhatsApp/SMS requires opt-in consent; email requires unsubscribe link.
- Suitability   : Product must match the customer credit segment.

Verdict rules:
- APPROVED              : all individual checks are PASS, no warnings
- APPROVED_WITH_WARNINGS: all PASS but minor warnings exist
- REVIEW                : one or more checks are REVIEW (no FAIL)
- REJECTED              : any individual check is FAIL

Set human_review_required=true if overall_verdict is REVIEW or REJECTED, or if fair_lending is FAIL.

Confidence scoring:
- 0.95 = clear APPROVED, no ambiguity
- 0.80 = APPROVED_WITH_WARNINGS
- 0.60 = REVIEW (uncertain)
- 0.35 = REJECTED (hard failure found)

Return ONLY valid JSON:
"fair_lending"         : "PASS" | "REVIEW" | "FAIL"
"apr_disclosure"       : "PASS" | "REVIEW" | "FAIL"
"messaging"            : "PASS" | "REVIEW" | "FAIL"
"channel"              : "PASS" | "REVIEW" | "FAIL"
"overall_verdict"      : "APPROVED" | "APPROVED_WITH_WARNINGS" | "REVIEW" | "REJECTED"
"warnings"             : array of strings (empty if none)
"human_review_required": boolean
"confidence"           : number between 0.0 and 1.0
"""


# -- ComplianceCheckerAgent -----------------------------------------------
compliance_agent = LlmAgent(
    name="ComplianceCheckerAgent",
    model=_MODEL,
    description=(
        "Regulatory compliance officer. Reviews a generated campaign against the "
        "customer risk profile for fair lending, APR disclosure, messaging standards, "
        "and channel consent. Returns a structured compliance verdict."
    ),
    instruction=_compliance_check_instruction,
    # search_financial_kb pre-injected at instruction-build time
    tools=[],
    output_key="compliance_result",
)
