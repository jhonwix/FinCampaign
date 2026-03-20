"""
Financial Education Agent

Triggered for DEEP-SUBPRIME customers — the highest-risk tier who cannot
receive a credit product offer. Generates a personalized financial improvement
plan using RAG-retrieved rehabilitation guidelines and Gemini.

This is an agent, not a static rejection template: it consults the knowledge
base for relevant financial-health policies, then produces a customized plan
based on the customer's specific profile weaknesses (DTI, late payments, score).

Why this matters for production:
  - Prevents predatory messaging toward the most vulnerable customers.
  - Builds long-term brand trust: a rejected customer today can become an
    approved customer in 6-12 months if properly guided.
  - Regulators (e.g. CFPB, SFC Colombia) expect responsible treatment of
    high-risk applicants; this agent documents that treatment.
"""

import asyncio
import json
from functools import partial

from config import settings
from gemini_client import generate_content
from rag.retriever import retrieve_context

_SYSTEM_PROMPT = """You are a compassionate financial counselor specializing in credit rehabilitation
for Latin American consumers. You work for a responsible lending institution.

Your role is to help DEEP-SUBPRIME customers understand their situation and take concrete
steps to improve their financial health. You do NOT offer credit products.

CRITICAL RULES:
- Never offer a credit product or imply one is coming soon.
- Be specific: reference the customer's actual numbers (DTI, credit score, late payments, income).
- Give 3-4 actionable improvement steps tailored to their specific weaknesses.
- Set a realistic re-evaluation timeline (3-12 months depending on severity).
- Tone: warm, honest, non-judgmental. This customer deserves respect and real guidance.
- campaign_message must be in Spanish and under 200 words.
- key_benefits must contain the concrete improvement steps, not generic advice.
- Always return valid JSON and nothing else."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {
            "type": "string",
            "description": "Educational label, e.g. 'Plan de Mejora Crediticia'",
        },
        "campaign_message": {
            "type": "string",
            "description": "Personalized educational message in Spanish, under 200 words",
        },
        "key_benefits": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-4 concrete improvement steps tailored to this customer's actual numbers",
        },
        "cta": {
            "type": "string",
            "description": "Call to action for financial counseling, not product acquisition",
        },
        "channel": {"type": "string"},
        "rates": {
            "type": "string",
            "description": "Always 'N/A - Sin oferta de crédito'",
        },
    },
    "required": ["product_name", "campaign_message", "key_benefits", "cta", "channel", "rates"],
}


class FinancialEducationAgent:
    """
    Generates personalized financial improvement plans for DEEP-SUBPRIME customers.

    Uses RAG to retrieve credit rehabilitation guidelines and financial health
    best practices, then generates a customized plan using Gemini.
    """

    async def educate(self, customer_profile: dict, risk_assessment: dict) -> dict:
        """
        Generate a financial improvement plan for an ineligible customer.

        Args:
            customer_profile: Customer data dict.
            risk_assessment:  Risk analysis output (segment, DTI, risk factors).

        Returns:
            Dict matching Campaign schema — educational content, no credit offer.
        """
        dti = risk_assessment.get("dti", 0)
        credit_score = customer_profile.get("credit_score", 0)
        late_payments = customer_profile.get("late_payments", 0)
        monthly_income = customer_profile.get("monthly_income", 1)
        monthly_debt = customer_profile.get("monthly_debt", 0)
        credit_utilization = customer_profile.get("credit_utilization", 0)
        # Campaign tone/cta overrides (optional)
        msg_tone = customer_profile.get("message_tone")
        cta_text = customer_profile.get("cta_text")

        # Identify primary weaknesses to target the RAG query
        weaknesses = []
        if late_payments > 0:
            weaknesses.append("pagos tardios historial crediticio")
        if dti > 50:
            weaknesses.append("alto DTI reduccion deuda mensual")
        if credit_score < 580:
            weaknesses.append("puntaje crediticio bajo rehabilitacion")
        if credit_utilization > 80:
            weaknesses.append("alta utilizacion tarjeta credito")

        weakness_query = " ".join(weaknesses) if weaknesses else "mejora perfil crediticio subprime"

        rehab_ctx, policy_ctx = await asyncio.gather(
            retrieve_context(
                f"rehabilitacion crediticia {weakness_query} pasos plan mejora financiero",
                num_results=3,
            ),
            retrieve_context(
                f"requisitos minimos credito personal score {credit_score} DTI elegibilidad",
                num_results=2,
            ),
        )

        # Pre-compute improvement targets so the agent has them explicitly
        target_dti = 48.0
        target_score = 600
        dti_gap = max(0, dti - target_dti)
        score_gap = max(0, target_score - credit_score)
        target_debt = (target_dti / 100) * monthly_income
        debt_reduction = max(0, monthly_debt - target_debt)

        # Build tone/cta overrides block
        tone_lines = []
        if msg_tone:
            tone_lines.append(f"  - Tone override: {msg_tone}")
        if cta_text:
            tone_lines.append(f"  - CTA text MUST be exactly: '{cta_text}'")
        tone_section = (
            "\n=== CAMPAIGN CONSTRAINTS ===\n"
            + "\n".join(tone_lines)
            + "\n=== END CONSTRAINTS ===\n"
        ) if tone_lines else ""

        prompt = f"""
{rehab_ctx}

{policy_ctx}
{tone_section}
Customer Profile (DEEP-SUBPRIME — NOT eligible for credit):
- Name: {customer_profile.get('name')}
- Age: {customer_profile.get('age')}
- Monthly Income: ${monthly_income:,.2f}
- Monthly Debt: ${monthly_debt:,.2f}
- DTI: {dti:.1f}% (eligibility threshold: ≤{target_dti}% — gap: {dti_gap:.1f}%)
- Monthly debt reduction needed to reach DTI target: ${debt_reduction:,.2f}
- Credit Score: {credit_score} (minimum required: {target_score} — gap: {score_gap} points)
- Late Payments (last 12 months): {late_payments} (maximum allowed: 3)
- Credit Utilization: {credit_utilization}%
- Products of Interest: {customer_profile.get('products_of_interest', 'N/A')}

Primary weaknesses identified:
{chr(10).join(f'- {w}' for w in weaknesses) if weaknesses else '- Multiple risk factors present'}

Generate a personalized financial improvement plan in Spanish.
Use the rehabilitation guidelines from the context above.
Reference the customer's actual numbers in the message (DTI {dti:.1f}%, score {credit_score}).
The key_benefits array must contain 3-4 concrete, numbered action steps.
Set a realistic re-evaluation date in the message (based on severity: {3 if dti_gap < 10 and score_gap < 50 else 6 if dti_gap < 20 else 12} months).
Return the complete educational plan JSON.
"""
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            partial(
                generate_content,
                prompt,
                settings.campaign_model,
                _SYSTEM_PROMPT,
                0.6,
                1024,
                "application/json",
                _RESPONSE_SCHEMA,
            ),
        )
        return json.loads(text)


financial_education_agent = FinancialEducationAgent()
