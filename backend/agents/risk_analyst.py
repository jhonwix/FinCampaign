"""
Risk Analyst Agent

Retrieves credit scoring/segmentation policies from RAG, then calls Gemini
via the Vertex AI REST endpoint (API key) to classify the customer.
"""

import asyncio
import json
from functools import partial

from config import settings
from gemini_client import generate_content
from rag.retriever import retrieve_context

_SYSTEM_PROMPT = """You are a credit risk analyst specialized in consumer lending.
For every customer profile you receive:
1. Calculate DTI = (monthly_debt / monthly_income) * 100
2. Use the segmentation rules in the provided policy context
3. Classify segment: SUPER-PRIME / PRIME / NEAR-PRIME / SUBPRIME / DEEP-SUBPRIME
4. Determine risk level: VERY LOW / LOW / MEDIUM / HIGH / CRITICAL
5. Check product eligibility based on segment and policies

Use ONLY the policies provided in the context. If context is insufficient, apply conservative defaults.
Always return a valid JSON object and nothing else."""

_FALLBACK_RULES = """
Fallback segmentation (use only if context is insufficient):
Credit Score:  750+ = SUPER-PRIME (VERY LOW) | 700-749 = PRIME (LOW)
               650-699 = NEAR-PRIME (MEDIUM) | 600-649 = SUBPRIME (HIGH) | <600 = DEEP-SUBPRIME (CRITICAL)
DTI:           <20% = excellent | 20-35% = good | 36-45% = limited | 46-50% = marginal | >50% = ineligible
DEEP-SUBPRIME: always ineligible for automated products.
"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "segment": {"type": "string"},
        "risk_level": {"type": "string"},
        "dti": {"type": "number"},
        "eligible_for_credit": {"type": "boolean"},
        "recommended_products": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": [
        "segment", "risk_level", "dti",
        "eligible_for_credit", "recommended_products", "rationale",
    ],
}


class RiskAnalystAgent:

    async def analyze(self, customer_profile: dict) -> dict:
        credit_score = customer_profile.get("credit_score", 0)
        monthly_income = customer_profile.get("monthly_income", 1)
        monthly_debt = customer_profile.get("monthly_debt", 0)
        dti_hint = round((monthly_debt / monthly_income) * 100, 2)

        risk_ctx, product_ctx = await asyncio.gather(
            retrieve_context(
                f"segmentacion crediticia score {credit_score} reglas DTI clasificacion riesgo"
            ),
            retrieve_context(
                f"elegibilidad productos credito score {credit_score} requisitos minimos"
            ),
        )

        prompt = f"""
{risk_ctx}

{product_ctx}

{_FALLBACK_RULES}

Customer Profile:
- Name: {customer_profile.get('name')}
- Age: {customer_profile.get('age')}
- Monthly Income: ${monthly_income:,.2f}
- Monthly Debt: ${monthly_debt:,.2f}
- Pre-calculated DTI: {dti_hint}% (verify against policies)
- Credit Score: {credit_score}
- Late Payments (last 12 months): {customer_profile.get('late_payments', 0)}
- Credit Utilization: {customer_profile.get('credit_utilization', 0)}%
- Products of Interest: {customer_profile.get('products_of_interest', 'N/A')}

Return the complete risk assessment JSON.
"""
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            partial(
                generate_content,
                prompt,
                settings.risk_analyst_model,
                _SYSTEM_PROMPT,
                0.1,
                1024,
                "application/json",
                _RESPONSE_SCHEMA,
            ),
        )
        return json.loads(text)


risk_analyst_agent = RiskAnalystAgent()
