"""AgentCore Platform v1.0 - EDU-C2-016 ConsentElementCheckRiskClassifyNode (inner subgraph, step 1)."""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import check_consent_elements, classify_risk


class ConsentElementCheckRiskClassifyNode(FunctionNode):
    """Check consent documentation elements + classify study risk tier."""

    # S-1 (proactive audit): inner-subgraph node - trust already verified at the
    # outer backbone boundary; ANONYMOUS here (not VERIFIED_EXTERNAL) per
    # security-5layer-checklist.md, no domain reason to re-require a higher level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        proposal = from_json(state.get("user_input"), None)
        if not isinstance(proposal, dict):
            emit_trace_event(
                "consent_risk_classify_missing_input",
                {"correlation_id": state.get("correlation_id", "")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ConsentElementCheckRiskClassifyNode: missing parsed proposal"],
            }

        consent_elements = check_consent_elements(proposal.get("consent_form_text", ""))
        risk_classification = classify_risk(proposal.get("study_description", ""))

        emit_trace_event(
            "consent_risk_classified",
            {"risk_classification": risk_classification, "correlation_id": state.get("correlation_id", "")},
            state,
        )

        return {
            "consent_elements": to_json(consent_elements),
            "risk_classification": risk_classification,
            "status": AgentStatus.SUCCESS.value,
        }
