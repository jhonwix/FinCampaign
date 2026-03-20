"""
Compliance Gate -- ADK LlmAgent with exit_loop (E3)
====================================================
KB pre-injection (refactor):
  search_financial_kb called at instruction-build time.
  exit_loop is the only tool kept (ADK loop control primitive).

State consumed : session.state["risk_assessment"] (RiskAnalystAgent)
                 session.state["campaign"]         (CampaignVariants -> Evaluator)
State produced : output_key="compliance_result"
                 exit_loop() call -> stops CorrectionLoop when compliant
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.tools import exit_loop  # noqa: E402
from agents_adk.search_tool import search_financial_kb  # noqa: E402
from google.genai import types  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _compliance_gate_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "APR disclosure requirements fair lending rules UDAP channel consent WhatsApp email SMS"
    )
    risk = ctx.state.get("risk_assessment", "(no risk assessment)")
    campaign = ctx.state.get("campaign", "(no campaign generated)")
    return f"""You are a regulatory compliance officer for a financial institution.
Review credit campaigns strictly -- when in doubt, flag REVIEW.

=== INPUTS FROM PIPELINE ===

Risk assessment:
{risk}

Campaign to review:
{campaign}

=== COMPLIANCE POLICIES (from knowledge base) ===

{kb}

=== YOUR TASK ===

Evaluate each compliance dimension:
  - fair_lending  : No discriminatory language; no targeting by protected class
  - apr_disclosure: Rate range must be clearly stated (e.g. 12%%-18%% annual)
  - messaging     : No guaranteed-approval language (garantizado, sin requisitos, etc.)
  - channel       : WhatsApp/SMS requires opt-in; email requires unsubscribe link

Determine overall_verdict:
  - APPROVED              : all individual checks are PASS, no warnings
  - APPROVED_WITH_WARNINGS: all PASS but minor warnings exist
  - REVIEW                : one or more checks are REVIEW (no FAIL)
  - REJECTED              : any individual check is FAIL

TOOL RULES -- the ONLY function you may call is exit_loop():
  - Do NOT call review_campaign, check_compliance, validate, or any other function.
  - exit_loop() is the ONLY valid function call. Calling any other function will cause an error.

STEP 1 -- Return ONLY valid JSON (your compliance verdict as text, see schema below).
STEP 2 -- AFTER the JSON, call exit_loop() ONLY IF overall_verdict is APPROVED or APPROVED_WITH_WARNINGS.
          If overall_verdict is REVIEW or REJECTED: do NOT call exit_loop; write actionable warnings.

Set human_review_required=true if any individual check is FAIL, or if multiple checks are REVIEW.

Confidence scoring:
  0.95 = clear APPROVED, no ambiguity
  0.80 = APPROVED_WITH_WARNINGS
  0.60 = REVIEW
  0.35 = REJECTED

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


compliance_gate = LlmAgent(
    name="ComplianceGateAgent",
    model=_MODEL,
    description=(
        "Regulatory compliance officer. Reviews the generated campaign against the "
        "customer risk profile. Calls exit_loop when the campaign passes compliance. "
        "Returns detailed feedback when it fails, enabling automatic correction."
    ),
    instruction=_compliance_gate_instruction,
    # search_financial_kb pre-injected; exit_loop is an ADK loop-control primitive.
    tools=[exit_loop],
    output_key="compliance_result",
)
