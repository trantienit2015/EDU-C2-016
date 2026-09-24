"""AgentCore Platform v1.0 - EDU-C2-016 DataProtectionRetrieveNode (inner subgraph, step 2)."""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import to_json
from src.services.service import retrieve_guideline_passages


class DataProtectionRetrieveNode(FunctionNode):
    """Retrieve 生命科学・医学系研究倫理指針 + data-protection provisions for the risk tier."""

    # S-1 (proactive audit): inner-subgraph node - trust already verified at the
    # outer backbone boundary; ANONYMOUS here (not VERIFIED_EXTERNAL) per
    # security-5layer-checklist.md, no domain reason to re-require a higher level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, kb: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._kb = kb or []

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        risk_classification = state.get("risk_classification", "minimal")

        passages = retrieve_guideline_passages(risk_classification, self._kb)

        emit_trace_event(
            "guideline_passages_retrieved",
            {"passage_count": len(passages), "correlation_id": state.get("correlation_id", "")},
            state,
        )

        return {
            "retrieved_passages": to_json(passages),
            "status": AgentStatus.SUCCESS.value,
        }
