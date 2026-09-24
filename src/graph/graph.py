"""AgentCore Platform v1.0 - EDU-C2-016 outer graph (Cat 2).

Cat 2: outer AgentBaseGraph with the fixed 5-node backbone. Domain complexity
is encapsulated in IRBComplianceGraphNode (the `main` slot), which wraps the
inner IRBComplianceWorkflowGraph. Do NOT override add_edges().

Backbone: initialize -> pre_process(ProposalParse) -> main(GraphNode)
          -> post_process(IRBGapReport) -> finalize

IRBComplianceGraphNode lives here (not under src/nodes/) - the PB-6
invoke-order test only discovers BaseNode subclasses under src/nodes/, and a
GraphNode's __call__ intentionally skips the standard S-2/S-4/S-3 lifecycle
(gating is delegated to the inner subgraph).
"""

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.post_process_node import IRBGapReportNode
from src.nodes.pre_process_node import ProposalParseNode
from src.schemas.state import State


class IRBComplianceGraphNode(GraphNode):
    """Wraps the inner IRB compliance-check workflow (Cat 2 composition)."""

    # S-1 (proactive audit): outer main-slot GraphNode is the first node to receive
    # caller input at this boundary - must declare required_trust_level explicitly,
    # matching config/agent.yaml's agent-level default.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    # "propagate": re-raise inner errors as SubgraphError (fail fast - default).
    error_strategy: ClassVar[str] = "propagate"
    # No HITL in this template.
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, kb: Any = None) -> None:
        super().__init__()
        self._kb = kb or []

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import IRBComplianceWorkflowGraph

        sg = IRBComplianceWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        emit_trace_event(
            "irb_compliance_workflow_dispatched", {"correlation_id": state.get("correlation_id", "")}, state
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        emit_trace_event(
            "irb_compliance_workflow_completed",
            {"correlation_id": state.get("correlation_id", ""), "status": str(sub_result.get("status"))},
            state,
        )
        return {
            "consent_elements": sub_result.get("consent_elements"),
            "risk_classification": sub_result.get("risk_classification"),
            "retrieved_passages": sub_result.get("retrieved_passages"),
            "compliance_flags": sub_result.get("compliance_flags"),
            "gap_report": sub_result.get("gap_report"),
            "result": sub_result.get("output"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"kb": self._kb}


class IRBEthicsComplianceCheckGraph(AgentBaseGraph):
    """EDU-C2-016 - University Research Ethics & IRB Compliance Check Agent (Cat 2)."""

    @property
    def name(self) -> str:
        return "edu-c2-016"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects initialize + finalize

        kb = self.config.get("kb")

        self._nodes["pre_process"] = ProposalParseNode()
        self._nodes["main"] = IRBComplianceGraphNode(kb=kb)
        self._nodes["post_process"] = IRBGapReportNode()

    # add_edges() is NOT overridden - backbone wiring belongs to the framework.


# Alias for agent.yaml module:"src.graph" resolution (AgentRegistry / api/server.py).
Graph = IRBEthicsComplianceCheckGraph
