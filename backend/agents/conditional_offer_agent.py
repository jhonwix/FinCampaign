"""
Conditional Offer Agent

Triggered for SUBPRIME customers who are currently ineligible (DTI > 48% or
too many late payments) but whose profile suggests they COULD qualify with
moderate, realistic improvement.

Instead of a flat rejection or a phantom campaign offer, this agent produces
a "conditional improvement path": the customer is told exactly what metrics
to hit and by how much to become eligible for a specific product.

Example output:
  "Si reduces tu deuda mensual en $320 para llevar tu DTI de 54% a 46%,
   podrías calificar para un Crédito Personal Básico de hasta $5.000.000
   en un plazo de 4 meses."

Why this matters for production:
  - Retains the customer relationship instead of losing them to a competitor.
  - Provides a clear, measurable target — behaviorally more effective than
    a generic "improve your credit" message.
  - Reduces re-application rates by setting accurate expectations.
  - Can be paired with a 3-month follow-up campaign (future Phase 3).
"""

import asyncio
import json
from functools import partial

from config import settings
from gemini_client import generate_content
from rag.retriever import retrieve_context

_SYSTEM_PROMPT = """You are a financial advisor at a consumer lending institution in Latin America.
You specialize in helping borderline-ineligible customers understand exactly what they need to improve
to qualify for a credit product in the near future.

CRITICAL RULES:
- Be very specific: state the exact DTI reduction needed, the exact monthly debt payment
  the customer must reach, and/or how many late payment incidents to resolve.
- Reference actual product eligibility thresholds from the context.
- Give 2-3 concrete, time-bound improvement steps (e.g., "in the next 3 months").
- Name a specific target product the customer could qualify for once improved.
- Tone: encouraging, direct, realistic. Not condescending. This IS a future offer.
- campaign_message must be in Spanish, under 200 words.
- The rates field must be conditional: "Aplica una vez cumplidas las condiciones: X%–Y% anual"
- Always return valid JSON and nothing else."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {
            "type": "string",
            "description": "Target product the customer could qualify for, e.g. 'Crédito Personal Básico'",
        },
        "campaign_message": {
            "type": "string",
            "description": (
                "Conditional improvement path message in Spanish, under 200 words. "
                "Must reference specific numbers: current DTI, target DTI, monthly debt reduction needed."
            ),
        },
        "key_benefits": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 concrete steps: what to improve, by how much, by when",
        },
        "cta": {
            "type": "string",
            "description": "Motivating CTA, e.g. 'Solicita asesoría gratuita para alcanzar tu meta'",
        },
        "channel": {"type": "string"},
        "rates": {
            "type": "string",
            "description": "Conditional rate range: 'Aplica una vez cumplidas las condiciones: X%–Y% anual'",
        },
    },
    "required": ["product_name", "campaign_message", "key_benefits", "cta", "channel", "rates"],
}

# Eligibility thresholds (must match risk analyst logic)
_DTI_THRESHOLD = 48.0
_MAX_LATE_PAYMENTS = 3


class ConditionalOfferAgent:
    """
    Generates conditional improvement offers for near-qualifying SUBPRIME customers.

    Instead of a flat rejection, tells the customer exactly which metrics to improve
    and by how much to become eligible for a specific product.
    """

    async def generate_conditional(
        self, customer_profile: dict, risk_assessment: dict
    ) -> dict:
        """
        Generate a conditional path offer for an ineligible SUBPRIME customer.

        Args:
            customer_profile: Customer data dict.
            risk_assessment:  Risk analysis output.

        Returns:
            Dict matching Campaign schema with conditional offer content.
        """
        dti = risk_assessment.get("dti", 0)
        credit_score = customer_profile.get("credit_score", 0)
        late_payments = customer_profile.get("late_payments", 0)
        monthly_debt = customer_profile.get("monthly_debt", 0)
        monthly_income = customer_profile.get("monthly_income", 1)
        recommended = risk_assessment.get("recommended_products", [])
        # Campaign constraints
        rate_min    = customer_profile.get("rate_min")
        rate_max    = customer_profile.get("rate_max")
        max_amount  = customer_profile.get("max_amount")
        term_months = customer_profile.get("term_months")
        cta_text    = customer_profile.get("cta_text")

        # Quantify the improvement gap
        dti_gap = max(0.0, dti - _DTI_THRESHOLD)
        late_gap = max(0, late_payments - _MAX_LATE_PAYMENTS)

        # How much monthly debt reduction is needed to hit DTI target?
        target_debt = (_DTI_THRESHOLD / 100) * monthly_income
        debt_reduction_needed = max(0.0, monthly_debt - target_debt)

        # Estimate months to reach target (heuristic: $100/month is realistic)
        months_to_target = max(3, min(12, int(debt_reduction_needed / 100) + (late_gap * 2)))

        products_query = " ".join(recommended) if recommended else "credito personal basico subprime"

        catalog_ctx, policy_ctx = await asyncio.gather(
            retrieve_context(
                f"catalogo productos {products_query} requisitos elegibilidad subprime SUBPRIME",
                num_results=3,
            ),
            retrieve_context(
                f"condiciones minimas credito DTI {dti} score {credit_score} pagos tardios",
                num_results=2,
            ),
        )

        # Build a list of specific improvement actions for the prompt
        needed_actions = []
        if dti_gap > 0:
            needed_actions.append(
                f"Reduce monthly debt by ${debt_reduction_needed:,.2f} "
                f"to bring DTI from {dti:.1f}% to {_DTI_THRESHOLD}%"
            )
        if late_gap > 0:
            needed_actions.append(
                f"Resolve {late_gap} outstanding late payment(s) "
                f"(currently {late_payments}, maximum allowed: {_MAX_LATE_PAYMENTS})"
            )

        # Build constraints block if campaign rates are defined
        constraints_lines = []
        if rate_min is not None and rate_max is not None:
            constraints_lines.append(f"  - Target product rate: {rate_min}%–{rate_max}% annual (use in 'rates' field as: 'Aplica una vez cumplidas las condiciones: {rate_min}%–{rate_max}% anual')")
        if max_amount:
            constraints_lines.append(f"  - Maximum loan amount: ${max_amount:,.2f}")
        if term_months:
            constraints_lines.append(f"  - Maximum term: {term_months} months")
        if cta_text:
            constraints_lines.append(f"  - CTA text MUST be exactly: '{cta_text}'")
        constraints_section = (
            "\n=== CAMPAIGN PRODUCT CONSTRAINTS (MANDATORY) ===\n"
            + "\n".join(constraints_lines)
            + "\n=== END CONSTRAINTS ===\n"
        ) if constraints_lines else ""

        prompt = f"""
{catalog_ctx}

{policy_ctx}
{constraints_section}
Customer Profile (SUBPRIME — currently ineligible, close to qualifying):
- Name: {customer_profile.get('name')}
- Age: {customer_profile.get('age')}
- Monthly Income: ${monthly_income:,.2f}
- Monthly Debt: ${monthly_debt:,.2f}
- Current DTI: {dti:.1f}% (maximum allowed: {_DTI_THRESHOLD}%)
- DTI gap: {dti_gap:.1f}% above threshold
- Monthly debt reduction needed: ${debt_reduction_needed:,.2f}
- Credit Score: {credit_score}
- Late Payments: {late_payments} (maximum: {_MAX_LATE_PAYMENTS}, gap: {late_gap})
- Credit Utilization: {customer_profile.get('credit_utilization', 0)}%
- Products of Interest: {customer_profile.get('products_of_interest', 'N/A')}
- Target products from risk analysis: {', '.join(recommended) if recommended else 'Crédito Personal Básico'}

Specific improvements needed before this customer can qualify:
{chr(10).join(f'- {a}' for a in needed_actions)}

Estimated timeline to reach eligibility: ~{months_to_target} months

Generate a conditional offer message that:
1. Acknowledges their current situation with empathy (mention their DTI {dti:.1f}%)
2. Tells them EXACTLY what to achieve (specific DTI target, debt reduction amount)
3. Names the specific target product they could qualify for
4. Sets a realistic timeline ({months_to_target} months)
5. Ends with an encouraging, action-oriented CTA

Write in Spanish. Be specific with numbers. This is a future offer, not a rejection.
Return the complete conditional offer JSON.
"""
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            partial(
                generate_content,
                prompt,
                settings.campaign_model,
                _SYSTEM_PROMPT,
                0.5,   # lower temperature for precise numerical guidance
                1024,
                "application/json",
                _RESPONSE_SCHEMA,
            ),
        )
        return json.loads(text)


conditional_offer_agent = ConditionalOfferAgent()
