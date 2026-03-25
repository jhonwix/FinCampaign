"""
ADK Lifecycle Callbacks — FinCampaign Pipeline
===============================================
Lifecycle callbacks for business-level observability and guardrails.
All callbacks use the ADK CallbackContext API.

Callbacks registered:
  before_model_callback (B5 — model routing):
    route_to_pro_if_borderline → FormalCampaignAgent, FriendlyCampaignAgent,
                                  UrgentCampaignAgent, CampaignEvaluatorAgent,
                                  QualityGateAgent, ComplianceGateAgent
                                : upgrades model to gemini-2.5-pro when
                                  DTI 43-53% OR confidence < 0.65

  after_agent_callback:
    log_risk_assessment    → RiskAnalystAgent       : segment, risk_level, dti, confidence
    log_routing_decision   → FinCampaignOrchestrator: route taken (EDUCATIONAL/PREMIUM_FAST/CONDITIONAL/STANDARD)
    log_evaluator_selection→ CampaignEvaluatorAgent : A/B variant selection preview
    log_quality_verdict    → QualityGateAgent (C1)  : quality score + 4 dimensions + passed flag
    log_compliance_verdict → ComplianceGateAgent    : per-dimension verdicts + overall
    log_pipeline_summary   → ExplainabilityAgent    : pipeline-level summary (last step)

  before_agent_callback (guardrails):
    guard_quality_input    → QualityGateAgent (C1)  : short-circuits if no campaign in state
    guard_compliance_input → ComplianceGateAgent    : short-circuits if no campaign in state
                                                       OR if quality_score < 7 (C1 integration)

Log format: JSON records emitted via logger "fincampaign.adk"
  grep-able: jq 'select(.event=="model_upgraded")'
"""
import json
import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# ── B5 constants ──────────────────────────────────────────────────────────────
_PRO_MODEL = "gemini-2.5-pro"
_BORDERLINE_DTI_LOW    = 43.0
_BORDERLINE_DTI_HIGH   = 53.0
_BORDERLINE_CONFIDENCE = 0.65

logger = logging.getLogger("fincampaign.adk")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_state_json(value) -> dict:
    """Safely parse a state value that may be a JSON string or a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


# ── B5 — before_model_callback: dynamic model routing ────────────────────────

def route_to_pro_if_borderline(
    *, callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    B5 — Upgrade to Gemini 2.5 Pro for borderline customers.
    Conditions (either triggers upgrade):
      - DTI in 43–53% range (borderline eligibility threshold)
      - Risk confidence < 0.65 (ambiguous assessment)
    Mutates llm_request.model in-place and returns None so the (upgraded) request proceeds.
    """
    risk = _parse_state_json(callback_context.state.get("risk_assessment"))
    if not risk:
        return None

    dti = float(risk.get("dti") or 0)
    confidence = float(risk.get("confidence") or 1.0)
    borderline_dti  = _BORDERLINE_DTI_LOW <= dti <= _BORDERLINE_DTI_HIGH
    borderline_conf = confidence < _BORDERLINE_CONFIDENCE

    if borderline_dti or borderline_conf:
        from_model = llm_request.model or "gemini-2.5-flash-lite"
        llm_request.model = _PRO_MODEL
        logger.info(json.dumps({
            "event":      "model_upgraded",
            "agent":      callback_context.agent_name,
            "from_model": from_model,
            "to_model":   _PRO_MODEL,
            "dti":        dti,
            "confidence": confidence,
            "reason":     "borderline_dti" if borderline_dti else "low_confidence",
        }))

    return None


# ── After-agent callbacks (logging) ──────────────────────────────────────────

def log_risk_assessment(ctx: CallbackContext) -> Optional[types.Content]:
    """Log segment, risk level, DTI, eligibility, and confidence after RiskAnalystAgent."""
    data = _parse_state_json(ctx.state.get("risk_assessment"))
    logger.info(json.dumps({
        "event": "risk_assessment_complete",
        "agent": ctx.agent_name,
        "segment": data.get("segment"),
        "risk_level": data.get("risk_level"),
        "dti": data.get("dti"),
        "eligible": data.get("eligible_for_credit"),
        "confidence": data.get("confidence"),
    }))
    return None


def log_routing_decision(ctx: CallbackContext) -> Optional[types.Content]:
    """Log the routing decision inferred from risk_assessment after FinCampaignOrchestrator."""
    data = _parse_state_json(ctx.state.get("risk_assessment"))
    segment = data.get("segment", "UNKNOWN")
    eligible = data.get("eligible_for_credit", None)

    if segment == "DEEP-SUBPRIME":
        route = "EDUCATIONAL"
    elif segment == "SUPER-PRIME":
        route = "PREMIUM_FAST"
    elif segment == "SUBPRIME" and not eligible:
        route = "CONDITIONAL"
    else:
        route = "STANDARD"

    logger.info(json.dumps({
        "event": "routing_decision",
        "agent": ctx.agent_name,
        "segment": segment,
        "eligible": eligible,
        "route": route,
    }))
    return None


def log_evaluator_selection(ctx: CallbackContext) -> Optional[types.Content]:
    """Log A/B variant availability and the winning campaign preview after CampaignEvaluatorAgent."""
    chosen = ctx.state.get("campaign", "")
    logger.info(json.dumps({
        "event": "ab_variant_selected",
        "agent": ctx.agent_name,
        "variants_generated": {
            "formal":   bool(ctx.state.get("campaign_formal")),
            "friendly": bool(ctx.state.get("campaign_friendly")),
            "urgent":   bool(ctx.state.get("campaign_urgent")),
        },
        "chosen_preview": (chosen[:80] if isinstance(chosen, str) else ""),
    }))
    return None


def log_compliance_verdict(ctx: CallbackContext) -> Optional[types.Content]:
    """Log per-dimension compliance verdicts and overall result after ComplianceGateAgent."""
    data = _parse_state_json(ctx.state.get("compliance_result"))
    logger.info(json.dumps({
        "event": "compliance_verdict",
        "agent": ctx.agent_name,
        "fair_lending":    data.get("fair_lending"),
        "apr_disclosure":  data.get("apr_disclosure"),
        "messaging":       data.get("messaging"),
        "channel":         data.get("channel"),
        "overall_verdict": data.get("overall_verdict"),
        "human_review":    data.get("human_review_required"),
        "confidence":      data.get("confidence"),
        "warnings_count":  len(data.get("warnings", [])),
    }))
    return None


def log_pipeline_summary(ctx: CallbackContext) -> Optional[types.Content]:
    """Log a pipeline-level summary after ExplainabilityAgent (final step)."""
    risk = _parse_state_json(ctx.state.get("risk_assessment"))
    compliance = _parse_state_json(ctx.state.get("compliance_result"))
    logger.info(json.dumps({
        "event": "pipeline_complete",
        "segment":               risk.get("segment"),
        "risk_confidence":       risk.get("confidence"),
        "final_verdict":         compliance.get("overall_verdict"),
        "human_review":          compliance.get("human_review_required"),
        "explanation_generated": bool(ctx.state.get("explanation")),
    }))
    return None


# ── C1 Quality Gate callbacks ─────────────────────────────────────────────────

def guard_quality_input(ctx: CallbackContext) -> Optional[types.Content]:
    """
    Guardrail for QualityGateAgent (C1).
    If no campaign was written to session state, short-circuit and return a
    zero-score quality result instead of sending an empty prompt to the LLM.
    """
    campaign = ctx.state.get("campaign", "")
    if not campaign or (isinstance(campaign, str) and not campaign.strip()):
        logger.warning(json.dumps({
            "event": "quality_guard_triggered",
            "agent": ctx.agent_name,
            "reason": "no_campaign_in_state",
        }))
        fallback = json.dumps({
            "quality_score":   0,
            "clarity":         0,
            "cta_strength":    0,
            "tone_fit":        0,
            "offer_relevance": 0,
            "quality_feedback": "Quality skipped: no campaign was generated upstream.",
            "recommendations": [],
        })
        return types.Content(parts=[types.Part(text=fallback)])
    return None


def log_quality_verdict(ctx: CallbackContext) -> Optional[types.Content]:
    """Log quality score and all 4 dimensions after QualityGateAgent (C1)."""
    data = _parse_state_json(ctx.state.get("quality_result"))
    score = data.get("quality_score") or 0
    logger.info(json.dumps({
        "event":           "quality_verdict",
        "agent":           ctx.agent_name,
        "quality_score":   score,
        "clarity":         data.get("clarity"),
        "cta_strength":    data.get("cta_strength"),
        "tone_fit":        data.get("tone_fit"),
        "offer_relevance": data.get("offer_relevance"),
        "passed":          score >= 7,
    }))
    return None


# ── Before-agent callback (guardrail) ─────────────────────────────────────────

def guard_compliance_input(ctx: CallbackContext) -> Optional[types.Content]:
    """
    Guardrail for ComplianceGateAgent.

    Check 1: campaign must be present in state.
    Check 2 (C1): quality_score must be >= 7. If the QualityGateAgent flagged the
      campaign as low quality, compliance is skipped and a REJECTED fallback is
      injected — causing the LoopAgent to iterate and regenerate with quality
      feedback incorporated into the next CampaignVariants correction prompt.
    """
    campaign = ctx.state.get("campaign", "")
    if not campaign or (isinstance(campaign, str) and not campaign.strip()):
        logger.warning(json.dumps({
            "event": "compliance_guard_triggered",
            "agent": ctx.agent_name,
            "reason": "no_campaign_in_state",
        }))
        fallback = json.dumps({
            "fair_lending":          "REVIEW",
            "apr_disclosure":        "REVIEW",
            "messaging":             "REVIEW",
            "channel":               "REVIEW",
            "overall_verdict":       "REVIEW",
            "warnings":              ["Compliance skipped: no campaign was generated upstream."],
            "human_review_required": True,
            "confidence":            0.0,
        })
        return types.Content(parts=[types.Part(text=fallback)])

    # C1: skip compliance when quality gate failed (score < 7)
    quality = _parse_state_json(ctx.state.get("quality_result"))
    score = quality.get("quality_score") if quality else None
    if score is not None and score < 7:
        feedback = quality.get("quality_feedback", "")
        recommendations = quality.get("recommendations", [])
        logger.warning(json.dumps({
            "event":         "compliance_skipped_quality_failed",
            "agent":         ctx.agent_name,
            "quality_score": score,
        }))
        fallback = json.dumps({
            "fair_lending":          "REVIEW",
            "apr_disclosure":        "REVIEW",
            "messaging":             "REVIEW",
            "channel":               "REVIEW",
            "overall_verdict":       "REJECTED",
            "warnings":              [
                f"Campaign failed quality gate (score {score}/10). Issues: {feedback}",
                *recommendations,
            ],
            "human_review_required": False,
            "confidence":            0.0,
        })
        return types.Content(parts=[types.Part(text=fallback)])

    return None  # proceed normally
