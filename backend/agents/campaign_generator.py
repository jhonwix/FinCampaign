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

Campaign intent:
- NEW: The customer does NOT have the product. Focus on acquisition — highlight benefits and ease of onboarding.
- RENEWAL: The customer ALREADY has the product. Focus on renewal — highlight loyalty rewards, better rates, and continuity.
- CROSS: Mixed audience. Tailor message to acknowledge existing relationship without assuming ownership.

Rules:
- Always include the specific interest rate range from the catalog.
- Never guarantee approval.
- Keep campaign_message under 150 words.
- CTA must be action-oriented, segment-appropriate, and aligned with the campaign intent.
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

    async def generate(
        self,
        customer_profile: dict,
        risk_assessment: dict,
        customer_history: str = "",
    ) -> dict:
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
        existing_products = customer_profile.get("existing_products") or "Ninguno"
        campaign_intent = customer_profile.get("campaign_intent") or "NEW"

        intent_instruction = {
            "NEW":     "The customer does NOT currently have this product. Write an acquisition-focused message.",
            "RENEWAL": "The customer ALREADY has this product. Write a renewal/loyalty-focused message emphasizing better rates or extended terms.",
            "CROSS":   "Write a message that works for both new and existing customers of this product.",
        }.get(campaign_intent, "Write an acquisition-focused message.")

        # Include history section only when available
        history_section = f"\n{customer_history}\n" if customer_history else ""

        # Build mandatory campaign constraints block
        constraints_lines = []
        rate_min    = customer_profile.get("rate_min")
        rate_max    = customer_profile.get("rate_max")
        max_amount  = customer_profile.get("max_amount")
        term_months = customer_profile.get("term_months")
        msg_tone    = customer_profile.get("message_tone")
        cta_text    = customer_profile.get("cta_text")
        if rate_min is not None and rate_max is not None:
            constraints_lines.append(f"  - Interest rate MUST be: {rate_min}%–{rate_max}% annual (use this exact range in the 'rates' field)")
        if max_amount:
            constraints_lines.append(f"  - Maximum loan amount: ${max_amount:,.2f} (do not exceed this in the message)")
        if term_months:
            constraints_lines.append(f"  - Maximum term: {term_months} months")
        if msg_tone:
            constraints_lines.append(f"  - Tone override: {msg_tone} (this overrides general segment tone guidance)")
        if cta_text:
            constraints_lines.append(f"  - CTA text MUST be exactly: '{cta_text}'")
        constraints_section = (
            "\n=== CAMPAIGN PRODUCT CONSTRAINTS (MANDATORY — follow exactly) ===\n"
            + "\n".join(constraints_lines)
            + "\n=== END CONSTRAINTS ===\n"
        ) if constraints_lines else ""

        prompt = f"""
{catalog_ctx}

{tone_ctx}
{constraints_section}{history_section}
Customer Profile:
- Name: {customer_profile.get('name')}
- Segment: {segment}
- Risk Level: {risk_assessment.get('risk_level')}
- DTI: {risk_assessment.get('dti')}%
- Products of Interest: {customer_profile.get('products_of_interest')}
- Existing Products (already owns): {existing_products}
- Recommended Products (from risk analysis): {products_hint}
- Eligible for Credit: {risk_assessment.get('eligible_for_credit')}
- Campaign Intent: {campaign_intent}

Intent instruction: {intent_instruction}

Write the campaign message in Spanish using the segment-appropriate tone from the catalog.
{"Follow the CAMPAIGN PRODUCT CONSTRAINTS above — use the exact rates and CTA specified." if constraints_lines else "Include specific rates from the catalog."}
Only offer products the customer is eligible for.
{"If the customer has previous interactions (see history above), acknowledge their relationship and avoid repeating identical offers. Build on prior context." if customer_history else ""}
Return the complete campaign JSON.
"""
        loop = asyncio.get_running_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(
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
            ),
            timeout=45.0,
        )
        return json.loads(text)


    async def regenerate(
        self,
        customer_profile: dict,
        risk_assessment: dict,
        previous_campaign: dict,
        compliance_feedback: dict,
        customer_history: str = "",
    ) -> dict:
        """
        Regenerate a campaign after a compliance rejection.
        Receives the previous campaign and the specific compliance failures
        so the agent can correct them rather than starting from scratch.
        """
        segment = risk_assessment.get("segment", "NEAR-PRIME")
        recommended = risk_assessment.get("recommended_products", [])
        products_query = " ".join(recommended) if recommended else "productos credito personal"

        catalog_ctx = await retrieve_context(
            f"catalogo productos {products_query} tasas beneficios segmento {segment}",
            num_results=4,
        )

        warnings = compliance_feedback.get("warnings", [])
        failed_checks = [
            k for k in ("fair_lending", "apr_disclosure", "messaging", "channel")
            if compliance_feedback.get(k) in ("FAIL", "REVIEW")
        ]
        existing_products = customer_profile.get("existing_products") or "Ninguno"
        campaign_intent = customer_profile.get("campaign_intent") or "NEW"

        intent_instruction = {
            "NEW":     "The customer does NOT currently have this product. Write an acquisition-focused message.",
            "RENEWAL": "The customer ALREADY has this product. Write a renewal/loyalty-focused message.",
            "CROSS":   "Write a message that works for both new and existing customers.",
        }.get(campaign_intent, "Write an acquisition-focused message.")

        history_section = f"\n{customer_history}\n" if customer_history else ""

        # Build mandatory campaign constraints block (same as generate())
        constraints_lines = []
        rate_min    = customer_profile.get("rate_min")
        rate_max    = customer_profile.get("rate_max")
        max_amount  = customer_profile.get("max_amount")
        term_months = customer_profile.get("term_months")
        msg_tone    = customer_profile.get("message_tone")
        cta_text    = customer_profile.get("cta_text")
        if rate_min is not None and rate_max is not None:
            constraints_lines.append(f"  - Interest rate MUST be: {rate_min}%–{rate_max}% annual (use this exact range in the 'rates' field)")
        if max_amount:
            constraints_lines.append(f"  - Maximum loan amount: ${max_amount:,.2f} (do not exceed this in the message)")
        if term_months:
            constraints_lines.append(f"  - Maximum term: {term_months} months")
        if msg_tone:
            constraints_lines.append(f"  - Tone override: {msg_tone} (this overrides general segment tone guidance)")
        if cta_text:
            constraints_lines.append(f"  - CTA text MUST be exactly: '{cta_text}'")
        constraints_section = (
            "\n=== CAMPAIGN PRODUCT CONSTRAINTS (MANDATORY — follow exactly) ===\n"
            + "\n".join(constraints_lines)
            + "\n=== END CONSTRAINTS ===\n"
        ) if constraints_lines else ""

        prompt = f"""
{catalog_ctx}
{constraints_section}{history_section}
COMPLIANCE CORRECTION — Previous campaign was REJECTED. You must fix the issues below.

Failed compliance checks: {', '.join(failed_checks) if failed_checks else 'general rejection'}
Compliance warnings:
{chr(10).join(f'- {w}' for w in warnings)}

Previous campaign (DO NOT reuse verbatim — rewrite to fix the issues above):
- Product: {previous_campaign.get('product_name')}
- Message: {previous_campaign.get('campaign_message')}
- Rates disclosed: {previous_campaign.get('rates')}
- CTA: {previous_campaign.get('cta')}
- Channel: {previous_campaign.get('channel')}

Customer Profile:
- Name: {customer_profile.get('name')}
- Segment: {segment}
- Risk Level: {risk_assessment.get('risk_level')}
- DTI: {risk_assessment.get('dti')}%
- Products of Interest: {customer_profile.get('products_of_interest')}
- Existing Products (already owns): {existing_products}
- Eligible for Credit: {risk_assessment.get('eligible_for_credit')}
- Campaign Intent: {campaign_intent}

Intent instruction: {intent_instruction}

Rewrite the campaign to pass compliance. Address every warning above.
Include specific rates from the catalog. Never guarantee approval.
Return the complete corrected campaign JSON.
"""
        loop = asyncio.get_running_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                partial(
                    generate_content,
                    prompt,
                    settings.campaign_model,
                    _SYSTEM_PROMPT,
                    0.4,   # lower temperature for targeted correction
                    1024,
                    "application/json",
                    _RESPONSE_SCHEMA,
                ),
            ),
            timeout=45.0,
        )
        return json.loads(text)


campaign_generator_agent = CampaignGeneratorAgent()
