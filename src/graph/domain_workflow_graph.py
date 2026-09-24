"""AgentCore Platform v1.0 - EDU-C2-016 inner domain workflow graph.

Cat 2 inner graph: consent-element check + risk classify + data-protection
retrieve + compliance check/gate. Instantiated by
IRBComplianceGraphNode.get_subgraph() in graph.py.

Pipeline (linear, fail-fast on ERROR):
    START -> consent_element_check_risk_classify -> data_protection_retrieve -> compliance_check -> END

Note: compliance_check runs even when consent_element_check_risk_classify
finds zero issues - the non-suppressible consent-element/要配慮個人情報
check must fire on every proposal regardless of other flags.
"""

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.compliance_check_node import ComplianceCheckNode
from src.nodes.consent_element_check_risk_classify_node import ConsentElementCheckRiskClassifyNode
from src.nodes.data_protection_retrieve_node import DataProtectionRetrieveNode
from src.schemas.state import State


class IRBComplianceWorkflowGraph(BaseGraph):
    """Inner graph for the EDU-C2-016 IRB compliance-check workflow."""

    @property
    def name(self) -> str:
        return "irb-compliance-workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config: kb is optional (empty KB yields no citations).
        pass

    def register_nodes(self) -> None:
        # No super() - BaseGraph.register_nodes() is abstract.
        kb = self.config.get("kb")

        self._nodes["consent_element_check_risk_classify"] = ConsentElementCheckRiskClassifyNode()
        self._nodes["data_protection_retrieve"] = DataProtectionRetrieveNode(kb=kb)
        self._nodes["compliance_check"] = ComplianceCheckNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "consent_element_check_risk_classify")
        self._sg.add_conditional_edges(
            "consent_element_check_risk_classify",
            lambda s: END if self._is_error(s) else "data_protection_retrieve",
            {"data_protection_retrieve": "data_protection_retrieve", END: END},
        )
        self._sg.add_conditional_edges(
            "data_protection_retrieve",
            lambda s: END if self._is_error(s) else "compliance_check",
            {"compliance_check": "compliance_check", END: END},
        )
        self._sg.add_edge("compliance_check", END)

    @staticmethod
    def _is_error(state: AgentState) -> bool:
        return state.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR.value)

    def route(self, state: AgentState) -> str:
        return END if self._is_error(state) else "compliance_check"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "consent_elements": state.get("consent_elements"),
            "risk_classification": state.get("risk_classification"),
            "retrieved_passages": state.get("retrieved_passages"),
            "compliance_flags": state.get("compliance_flags"),
            "gap_report": state.get("gap_report"),
            "output": state.get("gap_report"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
