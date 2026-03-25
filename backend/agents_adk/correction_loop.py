"""
Correction Loop — ADK LoopAgent (E3 + C3 + C1)
===============================================
Replaces the manual while-loop correction in orchestrator.py.

C3 upgrade: CampaignCorrectorAgent replaced by CampaignVariantStep:
  CampaignVariantStep (SequentialAgent)
    ├── CampaignVariants (ParallelAgent)     ← fan-out: 3 tones simultaneously
    │   ├── FormalCampaignAgent              → campaign_formal
    │   ├── FriendlyCampaignAgent            → campaign_friendly
    │   └── UrgentCampaignAgent              → campaign_urgent
    └── CampaignEvaluatorAgent              ← fan-in: LLM-as-Judge picks best
                                              → campaign

C1 upgrade: QualityGateAgent inserted before ComplianceGateAgent:
  QualityGateAgent scores campaign 1-10 (clarity, CTA, tone, relevance).
  If score < 7: guard_compliance_input callback injects a REJECTED compliance
  result → loop iterates with quality feedback. ComplianceGate never called.
  If score >= 7: ComplianceGateAgent runs normally.

Agentic patterns demonstrated:
  - Reflection / Self-Correction : LoopAgent auto-corrects on quality or compliance rejection
  - Fan-out / Fan-in             : ParallelAgent + EvaluatorAgent for A/B selection
  - LLM-as-Judge                 : EvaluatorAgent (C3) + QualityGateAgent (C1) score objectively
  - Quality Gate                 : Pre-compliance quality threshold (C1)

State flow per iteration:
  CampaignVariantStep
    → CampaignVariants (parallel) → campaign_formal, campaign_friendly, campaign_urgent
    → CampaignEvaluatorAgent      → campaign  (best of 3)
  QualityGateAgent                → quality_result (score + feedback)
    → if score < 7: guard_compliance_input injects REJECTED → loop continues
  ComplianceGateAgent             → compliance_result
    → if APPROVED: calls exit_loop → LoopAgent stops
    → if REJECTED: loop continues with combined quality+compliance feedback

Loop termination:
  - ComplianceGateAgent calls exit_loop() → campaign approved
  - max_iterations=3 reached → exit (prevents infinite correction)
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from google.adk.agents import LoopAgent, SequentialAgent  # noqa: E402

from agents_adk.campaign_variants import campaign_variants    # noqa: E402
from agents_adk.campaign_evaluator import campaign_evaluator  # noqa: E402
from agents_adk.quality_gate import quality_gate              # noqa: E402
from agents_adk.compliance_gate import compliance_gate        # noqa: E402

# ── CampaignVariantStep ───────────────────────────────────────────────────────
# Wraps ParallelAgent + EvaluatorAgent so they run as a single unit inside
# the LoopAgent. SequentialAgent ensures the evaluator always runs AFTER
# all 3 parallel variants have completed.
campaign_variant_step = SequentialAgent(
    name="CampaignVariantStep",
    description=(
        "A/B campaign generation step: runs 3 tone variants in parallel "
        "(fan-out), then selects the best with LLM-as-Judge (fan-in). "
        "Outputs the winning campaign to session.state['campaign']."
    ),
    sub_agents=[
        campaign_variants,   # ParallelAgent → campaign_formal/friendly/urgent
        campaign_evaluator,  # LlmAgent      → campaign (best of 3)
    ],
)

# ── CorrectionLoop ────────────────────────────────────────────────────────────
correction_loop = LoopAgent(
    name="CorrectionLoop",
    description=(
        "Auto-correction loop with A/B variant selection and quality gate. Each iteration: "
        "generates 3 campaign tones in parallel, evaluates and selects the best, "
        "scores quality 1-10, then checks compliance. Exits when approved or after 3 attempts."
    ),
    max_iterations=3,
    sub_agents=[
        campaign_variant_step,  # fan-out/fan-in → output_key="campaign"
        quality_gate,           # C1: quality score 1-10 → output_key="quality_result"
        compliance_gate,        # check + exit_loop if approved → output_key="compliance_result"
    ],
)
