"""
Risk Analyst Agent — ADK version (E1 + E7 + T3)
=================================================
Replaces the manual RiskAnalystAgent class with an ADK LlmAgent that uses
search_financial_kb to retrieve credit scoring policies natively.

E7 — Memory:
  Customer history is recalled before each assessment.

T3 — preload_memory (upgrade from load_memory):
  preload_memory is a PreloadMemoryTool that automatically injects past
  session memories into the LLM context BEFORE each request — without the
  agent needing to explicitly call a tool.

  Difference vs load_memory:
    load_memory   : the LLM must decide to call it (can "forget")
    preload_memory: always runs, always injects → guaranteed context

  The tool searches memory using the user's first message (customer profile)
  and prepends relevant past interactions as a <PAST_CONVERSATIONS> block
  in the system instruction automatically.

KB pre-injection (refactor):
  search_financial_kb is called ONCE at instruction-build time and the result
  is embedded directly in the instruction text. The LLM no longer needs to
  call it as a tool — eliminating one round-trip per customer.

Before (manual): 120 lines — explicit RAG calls + httpx Gemini invocation
After (ADK):      ~50 lines — LlmAgent with pre-injected KB + memory recall
"""
import json
import sys
from pathlib import Path

# ── sys.path guard (when loaded standalone, e.g. during tests) ───────────────
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.readonly_context import ReadonlyContext  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.tools import preload_memory  # noqa: E402
from agents_adk.search_tool import search_financial_kb  # noqa: E402
from agents_adk.callbacks import log_risk_assessment  # noqa: E402
from google.genai import types  # noqa: E402

from config import settings  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)


def _risk_instruction(ctx: ReadonlyContext) -> str:
    kb = search_financial_kb(
        "credit score segmentation rules DTI thresholds product eligibility criteria"
    )
    return f"""You are a credit risk analyst specialized in consumer lending.

When you receive a customer profile, analyze it using the policies below.

Knowledge Base (credit policies):
{kb}

Steps:
1. Check past interactions: your context may include a <PAST_CONVERSATIONS> block
   with this customer's previous campaign history. If present, note any trends.
   If absent, this is a new customer — proceed normally.
2. Compute DTI in your reasoning: DTI = (monthly_debt / monthly_income) × 100
   Example: $1,200 debt / $4,500 income = 26.7%
3. Classify the customer:
   - Segment:    SUPER-PRIME | PRIME | NEAR-PRIME | SUBPRIME | DEEP-SUBPRIME
   - Risk level: VERY LOW | LOW | MEDIUM | HIGH | CRITICAL
4. Determine product eligibility and recommend suitable products.
   If past history shows a product was previously rejected by compliance,
   avoid recommending it again.
5. Assign a confidence score (0.0–1.0):
   - 0.90–0.95  clear-cut segmentation, no borderline signals
   - 0.70–0.85  credit score within 20 pts of segment boundary
   - 0.55–0.65  DTI near eligibility threshold (±5%) or contradictory signals
   - Never above 0.99 or below 0.30

Memory note: if memory shows the customer has IMPROVED their segment since the last
interaction (e.g. SUBPRIME → NEAR-PRIME), mention this trend in the rationale.
It signals responsible financial behavior worth noting in the campaign.

Fallback segmentation (use only if knowledge base has no results):
  750+: SUPER-PRIME | 700-749: PRIME | 650-699: NEAR-PRIME
  600-649: SUBPRIME | <600: DEEP-SUBPRIME
  DTI > 50%: ineligible | DEEP-SUBPRIME: always ineligible

Return ONLY valid JSON with these fields:
  segment            : one of SUPER-PRIME | PRIME | NEAR-PRIME | SUBPRIME | DEEP-SUBPRIME
  risk_level         : one of VERY LOW | LOW | MEDIUM | HIGH | CRITICAL
  dti                : number (e.g. 26.7)
  eligible_for_credit: true or false
  recommended_products: array of strings
  rationale          : string — brief explanation
  confidence         : number between 0.30 and 0.99"""


# ── RiskAnalystAgent ─────────────────────────────────────────────────────────
risk_analyst_agent = LlmAgent(
    name="RiskAnalystAgent",
    model=_MODEL,
    description=(
        "Credit risk analyst for consumer lending. "
        "Given a customer profile, uses pre-injected credit scoring policies from "
        "the knowledge base to classify the customer segment and risk level, "
        "determine product eligibility, and return a structured JSON assessment."
    ),
    instruction=_risk_instruction,
    # search_financial_kb is called at instruction-build time (pre-injected).
    # preload_memory (T3): automatically injects past session memories BEFORE
    # the LLM request — the model does NOT need to call it explicitly.
    tools=[preload_memory],
    output_key="risk_assessment",
    after_agent_callback=log_risk_assessment,
)
