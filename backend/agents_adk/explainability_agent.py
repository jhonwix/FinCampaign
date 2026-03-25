"""
Explainability Agent — ADK LlmAgent (C4)
=========================================
Final step in the FinCampaignPipeline. Generates a customer-facing explanation
in plain Spanish: why they qualify (or don't), why this product, and what to do next.

Agentic pattern: Explainability / Transparency
  The LLM reads the risk assessment and the selected campaign (already chosen
  by the pipeline) and produces a human-readable justification — not for the
  analyst, but for the customer themselves.

Key design decisions:
  - No tools: all context is already in session.state (risk_assessment, campaign).
    Zero RAG calls. Zero web search. Pure LLM reasoning from pipeline outputs.
  - Uses InstructionProvider callable to read state safely — avoids KeyError
    if risk_assessment or campaign are not yet written (e.g. partial pipeline run).
  - Handles all 4 routes contextually:
      EDUCATIONAL  → encouragement + concrete credit improvement steps
      PREMIUM      → exclusive tone, highlights earned benefits
      CONDITIONAL  → exact conditions the customer must meet to qualify
      STANDARD     → clear, direct explanation of why they qualify now
  - Output stored as JSON so the frontend can render each field independently.

State consumed : session.state["risk_assessment"]   (RiskAnalystAgent)
                 session.state["campaign"]           (any route's campaign agent)
State produced : output_key="explanation"
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
from agents_adk.callbacks import log_pipeline_summary  # noqa: E402

_MODEL = Gemini(
    model="gemini-2.5-flash-lite",
    retry_options=types.HttpRetryOptions(attempts=3),
)

_STATIC_INSTRUCTION = """\

=== YOUR TASK ===

Read both inputs carefully and generate a customer-facing explanation.

Determine the scenario from the risk assessment:
  - product_name == "NO_OFFER" or "Plan de Mejora Crediticia"
      EDUCATIONAL scenario: customer is not yet eligible
  - segment == "SUPER-PRIME"
      PREMIUM scenario: customer has excellent profile
  - eligible_for_credit == false (but not DEEP-SUBPRIME)
      CONDITIONAL scenario: customer needs to meet specific conditions
  - All other cases (PRIME, NEAR-PRIME, eligible SUBPRIME)
      STANDARD scenario: customer qualifies for the offer

Write the explanation matching the scenario:

EDUCATIONAL (not eligible yet):
  - Acknowledge their situation with empathy, no condescension
  - Explain concretely which factors limit eligibility (score, DTI, late payments)
  - Give 2-3 specific, actionable steps to improve
  - Close with encouragement

PREMIUM (SUPER-PRIME):
  - Open by acknowledging their excellent financial profile
  - Explain specifically what earned them this exclusive offer
  - Highlight 1-2 concrete benefits of the product
  - CTA that feels like an earned reward, not a sales pitch

CONDITIONAL (near-eligible):
  - Be honest: "you don't qualify today, but you're close"
  - State the EXACT gap (e.g. "your DTI is X%%, the threshold is Y%%")
  - Give 1 concrete action to close the gap with a realistic timeline

STANDARD (eligible):
  - Open with a clear positive statement about their qualification
  - Explain which 2-3 factors made them eligible
  - Connect the product features to their specific profile
  - Simple, action-oriented CTA

Rules for ALL scenarios:
  - Write in Spanish, 2nd person singular (tu/usted — match the campaign tone)
  - Keep body under 150 words — clear and direct, not exhaustive
  - next_steps must be concrete actions, not generic advice
  - Never use internal jargon (DTI, PRIME, compliance, pipeline)
  - Never guarantee approval if it hasn't happened yet
  - Never sound like a rejection letter — always forward-looking

Return ONLY valid JSON — no markdown, no explanation outside the JSON:
"headline": string (1 sentence, direct and engaging, under 15 words)
"body": string (main explanation in Spanish, 100-150 words)
"next_steps": array of 2-3 strings (concrete, specific, actionable)
"tone": string (one of: formal | friendly | encouraging | exclusive)
"""


def _explain_instruction(ctx: ReadonlyContext) -> str:
    risk = ctx.state.get("risk_assessment", "(no risk assessment available)")
    campaign = ctx.state.get("campaign", "(no campaign generated yet)")
    return (
        "You are a financial advisor who explains credit decisions to customers in plain,\n"
        "respectful Spanish. Your goal is transparency — the customer should fully understand\n"
        "why they received this specific offer (or why they didn't qualify yet).\n\n"
        "=== PIPELINE OUTPUTS TO EXPLAIN ===\n\n"
        f"Risk assessment (internal analysis):\n{risk}\n\n"
        f"Campaign generated for this customer:\n{campaign}\n"
        + _STATIC_INSTRUCTION
    )


# ── ExplainabilityAgent ───────────────────────────────────────────────────────
explainability_agent = LlmAgent(
    name="ExplainabilityAgent",
    model=_MODEL,
    description=(
        "Generates a transparent, customer-facing explanation of the campaign decision. "
        "Explains in plain Spanish why the customer qualifies (or doesn't), why this "
        "specific product was chosen, and what concrete steps to take next."
    ),
    instruction=_explain_instruction,
    # No tools: reads purely from session.state — zero extra API calls
    output_key="explanation",
    after_agent_callback=log_pipeline_summary,
)
