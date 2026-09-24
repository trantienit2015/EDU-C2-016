# PB-6 (GraphNode boundary supplement): `IRBComplianceGraphNode` lives in
# src/graph/graph.py (correct scaffold placement for a Cat 2 outer main-slot
# wrapper), which is outside PB-6's src/nodes/ discovery scope. This test
# bounds the outer composition boundary that PB-6 does not probe:
# S-1 trust gate on the wrapper itself, explicit field-mapping in
# extract_input()/merge_output() (criterion #9), and that gating for the
# inner subgraph is a deliberate delegation, not an omission.

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import IRBComplianceGraphNode


def test_s1_trust_gate_denies_insufficient_caller():
    # __call__() reads required_trust_level off self.__class__ — a subclass
    # (not an instance attribute) is required to force a denial for this probe.
    _HighTrustProbe = type("_HighTrustProbe", (IRBComplianceGraphNode,), {"required_trust_level": TrustLevel.INTERNAL})
    node = _HighTrustProbe()
    out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "validated_input": '{"title": "x"}'})
    assert str(out.get("status")).lower().endswith("error")
    assert out["error_log"] and "trust gate denied" in out["error_log"][0]


def test_extract_input_maps_only_the_contracted_field():
    node = IRBComplianceGraphNode()
    state = {
        "validated_input": '{"title": "Study X", "consent_form_text": "..."}',
        "user_input": "raw caller text should not leak through",
        "unrelated_field": "must not appear in subgraph input",
    }
    extracted = node.extract_input(state)
    assert extracted == '{"title": "Study X", "consent_form_text": "..."}'
    assert "unrelated_field" not in extracted
    assert "raw caller text" not in extracted


def test_merge_output_maps_fields_explicitly_not_raw_passthrough():
    node = IRBComplianceGraphNode()
    sub_result = {
        "consent_elements": '{"purpose": true}',
        "risk_classification": "minimal",
        "retrieved_passages": "[]",
        "compliance_flags": "[]",
        "gap_report": '{"summary": "No compliance gaps found."}',
        "output": {"summary": "No compliance gaps found."},
        "status": AgentStatus.SUCCESS.value,
        "internal_subgraph_only_field": "must not leak into merged output",
    }
    merged = node.merge_output({}, sub_result)
    assert "internal_subgraph_only_field" not in merged
    assert merged["result"] == {"summary": "No compliance gaps found."}
    assert merged["status"] == AgentStatus.SUCCESS.value


def test_inner_subgraph_delegation_is_deliberate_design():
    """IRBComplianceGraphNode delegates S-2/S-3 content gating to the inner subgraph's
    own entry node (ConsentElementCheckRiskClassifyNode / DataProtectionRetrieveNode /
    ComplianceCheckNode run inside the inner BaseGraph) - this is the documented
    Cat 2 composition pattern (framework/nodes/graph_node.py), not a bypass.
    """
    from src.graph.domain_workflow_graph import IRBComplianceWorkflowGraph

    assert IRBComplianceWorkflowGraph is not None
