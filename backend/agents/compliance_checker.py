"""
Compliance Checker Agent

Mandatory final gate. Reviews every campaign for fair lending, APR disclosure,
messaging standards, channel consent, and product suitability.
DEEP-SUBPRIME short-circuits without calling the LLM.
"""

import asyncio
import json
from functools import partial

from config import settings
from db.lookups import get_valid_values
from gemini_client import generate_content
from rag.retriever import retrieve_context

_SYSTEM_PROMPT = """You are a regulatory compliance officer for a financial institution.
You review credit campaigns for legal and regulatory compliance.
Be strict — when in doubt, flag for REVIEW.
Always return valid JSON and nothing else.

Key regulations to enforce:
- Fair Lending: No discriminatory language; no targeting by protected class.
- TILA equivalent: APR/rate range must be clearly disclosed.
- UDAP: No unfair, deceptive, or abusive acts or practices.
- Channel consent: WhatsApp/SMS requires opt-in; email requires unsubscribe link.
- Product suitability: Campaign must match the customer's actual credit segment."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "fair_lending":  {"type": "string", "enum": ["PASS", "REVIEW", "FAIL"]},
        "apr_disclosure":{"type": "string", "enum": ["PASS", "REVIEW", "FAIL"]},
        "messaging":     {"type": "string", "enum": ["PASS", "REVIEW", "FAIL"]},
        "channel":       {"type": "string", "enum": ["PASS", "REVIEW", "FAIL"]},
        "overall_verdict":{
            "type": "string",
            "enum": ["APPROVED", "APPROVED_WITH_WARNINGS", "REVIEW", "REJECTED"],
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "human_review_required": {"type": "boolean"},
        "confidence": {
            "type": "number",
            "description": (
                "Your confidence in this compliance verdict (0.0–1.0). "
                "Use 0.95 when all individual checks clearly PASS with no ambiguity. "
                "Use 0.80 for APPROVED_WITH_WARNINGS (minor warnings, no failures). "
                "Use 0.60 for REVIEW verdicts (at least one check is uncertain). "
                "Use 0.35 for REJECTED (a hard failure was detected). "
                "Reduce further if the campaign message was ambiguous or context was insufficient."
            ),
        },
    },
    "required": [
        "fair_lending", "apr_disclosure", "messaging", "channel",
        "overall_verdict", "warnings", "human_review_required", "confidence",
    ],
}

_DEEP_SUBPRIME_RESPONSE = {
    "fair_lending": "REVIEW",
    "apr_disclosure": "REVIEW",
    "messaging": "REVIEW",
    "channel": "REVIEW",
    "overall_verdict": "REVIEW",
    "warnings": [
        "DEEP-SUBPRIME segment requires mandatory human underwriter review.",
        "Campaign must not be delivered without explicit approval from the credit team.",
    ],
    "human_review_required": True,
    "confidence": 0.90,  # high confidence in the DEEP-SUBPRIME classification itself
}


class ComplianceCheckerAgent:

    async def check(
        self,
        customer_profile: dict,
        risk_assessment: dict,
        campaign: dict,
    ) -> dict:
        segment = risk_assessment.get("segment", "")
        if segment == "DEEP-SUBPRIME":
            return _DEEP_SUBPRIME_RESPONSE

        channel = campaign.get("channel", "email")

        compliance_ctx, channel_ctx = await asyncio.gather(
            retrieve_context(
                "politicas cumplimiento normativo divulgacion APR canales comunicacion restricciones"
            ),
            retrieve_context(
                f"requisitos consentimiento canal {channel} opt-in baja politica comunicacion"
            ),
        )

        prompt = f"""
{compliance_ctx}

{channel_ctx}

Customer Context:
- Segment: {segment}
- Risk Level: {risk_assessment.get('risk_level')}
- Eligible for Credit: {risk_assessment.get('eligible_for_credit')}

Campaign to Review:
- Product: {campaign.get('product_name')}
- Message: {campaign.get('campaign_message')}
- Key Benefits: {campaign.get('key_benefits')}
- CTA: {campaign.get('cta')}
- Channel: {channel}
- Rates Disclosed: {campaign.get('rates')}

Check each item:
1. FAIR_LENDING: Any discriminatory language or prohibited targeting?
2. APR_DISCLOSURE: Is the rate range "{campaign.get('rates')}" clearly disclosed?
3. MESSAGING: Any guaranteed approval language or predatory terms?
4. CHANNEL: Does "{channel}" require opt-in/unsubscribe that must be verified?
5. PRODUCT_ELIGIBILITY: Is this product appropriate for a {segment} customer?

Return verdict for each check and an overall_verdict.
Individual checks must be exactly: PASS, REVIEW, or FAIL.
overall_verdict must be exactly one of: APPROVED, APPROVED_WITH_WARNINGS, REVIEW, REJECTED.
  - APPROVED: all checks PASS
  - APPROVED_WITH_WARNINGS: all PASS but with minor warnings
  - REVIEW: one or more checks are REVIEW (no FAIL)
  - REJECTED: any check is FAIL
Set human_review_required=true if any check is FAIL or if multiple checks are REVIEW.
Set confidence to reflect how certain you are of this verdict:
  0.95 = clear APPROVED with no doubts | 0.80 = APPROVED_WITH_WARNINGS | 0.60 = REVIEW | 0.35 = REJECTED
"""
        loop = asyncio.get_running_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                partial(
                    generate_content,
                    prompt,
                    settings.compliance_model,
                    _SYSTEM_PROMPT,
                    0.1,
                    512,
                    "application/json",
                    _RESPONSE_SCHEMA,
                ),
            ),
            timeout=45.0,
        )
        result = json.loads(text)

        # Normalize individual checks against lookup table (fallback to hardcoded if cache empty)
        _valid_checks = set(get_valid_values("compliance_check_result")) or {"PASS", "REVIEW", "FAIL"}
        _check_alias = {"OK": "PASS", "APPROVED": "PASS", "PASS": "PASS", "REVIEW": "REVIEW", "FAIL": "FAIL"}
        for field in ("fair_lending", "apr_disclosure", "messaging", "channel"):
            raw = result.get(field, "REVIEW")
            normalized = _check_alias.get(raw, "REVIEW")
            result[field] = normalized if normalized in _valid_checks else "REVIEW"

        # Normalize overall_verdict against lookup table
        _valid_verdicts = set(get_valid_values("compliance_overall_verdict")) or {"APPROVED", "APPROVED_WITH_WARNINGS", "REVIEW", "REJECTED"}
        if result.get("overall_verdict") not in _valid_verdicts:
            # Re-derive from individual checks
            checks = [result.get(f) for f in ("fair_lending", "apr_disclosure", "messaging", "channel")]
            if "FAIL" in checks:
                result["overall_verdict"] = "REJECTED"
            elif checks.count("REVIEW") >= 2:
                result["overall_verdict"] = "REVIEW"
            elif "REVIEW" in checks:
                result["overall_verdict"] = "APPROVED_WITH_WARNINGS"
            else:
                result["overall_verdict"] = "APPROVED"

        # Force human review on hard failures
        if (
            result.get("overall_verdict") in {"REVIEW", "REJECTED"}
            or result.get("fair_lending") == "FAIL"
        ):
            result["human_review_required"] = True

        return result


compliance_checker_agent = ComplianceCheckerAgent()
