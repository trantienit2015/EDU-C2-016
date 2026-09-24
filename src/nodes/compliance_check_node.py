"""AgentCore Platform v1.0 - EDU-C2-016 ComplianceCheckNode (inner subgraph, step 3).

Non-suppressible node business logic (NOT a framework S-* gate; see the
S3 which defines S-3 as secret isolation): missing consent elements +
要配慮個人情報 (yohairyo-kojinjoho) handling gaps vs guideline requirements.
Fires on every proposal regardless of other flags.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import build_gap_report, check_compliance


class ComplianceCheckNode(FunctionNode):
    """Non-suppressible consent-element + 要配慮個人情報-handling compliance check (ComplianceGate) + gap report assembly."""

    # S-1 (proactive audit): inner-subgraph node - trust already verified at the
    # outer backbone boundary; ANONYMOUS here (not VERIFIED_EXTERNAL) per
    # security-5layer-checklist.md, no domain reason to re-require a higher level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        consent_elements = from_json(state.get("consent_elements"), None)
        if not isinstance(consent_elements, dict):
            emit_trace_event(
                "compliance_check_missing_input",
                {"correlation_id": state.get("correlation_id", "")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ComplianceCheckNode: missing consent-element check result"],
            }

        risk_classification = state.get("risk_classification", "minimal")
        passages = from_json(state.get("retrieved_passages"), [])
        parsed = from_json(state.get("user_input"), {})
        sensitive_info_handling_declared = (
            bool(parsed.get("sensitive_info_handling_declared", False)) if isinstance(parsed, dict) else False
        )

        flags = check_compliance(consent_elements, risk_classification, sensitive_info_handling_declared)
        gap_report = build_gap_report(consent_elements, risk_classification, flags, passages)

        emit_trace_event(
            "compliance_checked",
            {"flag_count": len(flags), "correlation_id": state.get("correlation_id", "")},
            state,
        )

        return {
            "compliance_flags": to_json(flags),
            "gap_report": to_json(gap_report),
            "status": AgentStatus.SUCCESS.value,
        }
