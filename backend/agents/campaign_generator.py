"""
Campaign Generator Agent

Generates a personalized, segment-appropriate credit campaign using
product catalog data from RAG, calling Gemini via Vertex AI REST API.
"""

import asyncio
import json
from functools import partial

from config import settings
from gemini_client import generate_content
from rag.retriever import retrieve_context

_SYSTEM_PROMPT = """You are a financial marketing specialist for a consumer lending institution.
You generate personalized credit campaign messages in Spanish.
Use the product catalog and tone guide provided in the context.

Tone by segment:
- SUPER-PRIME / PRIME: Premium, exclusive, aspirational tone.
- NEAR-PRIME: Empowering, opportunity-focused tone.
- SUBPRIME: Supportive, trust-building, responsible tone.
- DEEP-SUBPRIME: Never generate a campaign — return placeholder values only.

Rules:
- Always include the specific interest rate range from the catalog.
- Never guarantee approval.
- Keep campaign_message under 150 words.
- CTA must be action-oriented and segment-appropriate.
- Always return valid JSON and nothing else."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {"type": "string"},
        "campaign_message": {"type": "string"},
        "key_benefits": {"type": "array", "items": {"type": "string"}},
        "cta": {"type": "string"},
        "channel": {"type": "string"},
        "rates": {"type": "string"},
    },
    "required": [
        "product_name", "campaign_message", "key_benefits",
        "cta", "channel", "rates",
    ],
}


class CampaignGeneratorAgent:

    async def generate(self, customer_profile: dict, risk_assessment: dict) -> dict:
        segment = risk_assessment.get("segment", "NEAR-PRIME")
        recommended = risk_assessment.get("recommended_products", [])
        products_query = " ".join(recommended) if recommended else "productos credito personal"

        catalog_ctx, tone_ctx = await asyncio.gather(
            retrieve_context(
                f"catalogo productos {products_query} tasas beneficios segmento {segment}",
                num_results=4,
            ),
            retrieve_context(
                f"guia tono comunicacion segmento {segment} mensajes canal WhatsApp email",
                num_results=2,
            ),
        )

        products_hint = ", ".join(recommended) if recommended else "producto adecuado para el perfil"

        prompt = f"""
{catalog_ctx}

{tone_ctx}

Customer Profile:
- Name: {customer_profile.get('name')}
- Segment: {segment}
- Risk Level: {risk_assessment.get('risk_level')}
- DTI: {risk_assessment.get('dti')}%
- Products of Interest: {customer_profile.get('products_of_interest')}
- Recommended Products (from risk analysis): {products_hint}
- Eligible for Credit: {risk_assessment.get('eligible_for_credit')}

Write the campaign message in Spanish using the segment-appropriate tone from the catalog.
Include specific rates from the catalog. Only offer products the customer is eligible for.
Return the complete campaign JSON.
"""
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            partial(
                generate_content,
                prompt,
                settings.campaign_model,
                _SYSTEM_PROMPT,
                0.7,
                1024,
                "application/json",
                _RESPONSE_SCHEMA,
            ),
        )
        return json.loads(text)


campaign_generator_agent = CampaignGeneratorAgent()
