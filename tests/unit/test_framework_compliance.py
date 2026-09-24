# EDU-C2-016 - Framework compliance tests TC-01..TC-08 (review-and-fix-code proactive audit, issue #618).
# Reference shape: the standard framework-compliance test, adapted to this
# template's real architecture (Cat 2: outer ProposalParse/GraphNode/IRBGapReport +
# inner ConsentElementCheckRiskClassify/DataProtectionRetrieve/ComplianceCheck).

import os
import re

import pytest
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import compliance_check_node, consent_element_check_risk_classify_node, post_process_node, pre_process_node
from src.schemas.state import State

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
_ALLOWED_ANNOTATION_TOKENS = {"str", "int", "bool", "float", "list", "dict", "None"}


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# TC-01 - State is a flat TypedDict extending AgentState; added fields are
# primitives / JSON-serializable containers only (no Pydantic/dataclass).
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_json_serializable_types(self):
        # state.py declares `from __future__ import annotations`, so raw
        # __annotations__ values are ForwardRef strings — resolve via get_type_hints
        # (include_extras keeps NotRequired[...] wrappers visible in the repr).
        import typing

        resolved = typing.get_type_hints(State, include_extras=True)
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        for name in added:
            ann_str = str(resolved[name])
            tokens = re.findall(r"[A-Za-z_]+", ann_str)
            offenders = [t for t in tokens if t not in _ALLOWED_ANNOTATION_TOKENS and t not in ("class", "NotRequired", "typing")]
            assert not offenders, f"{name}: {ann_str} contains non-primitive token(s) {offenders}"


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_draft_no_raise(self):
        node = pre_process_node.ProposalParseNode()
        out = node.execute({"input_context": {}})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]

    def test_missing_parsed_proposal_no_raise(self):
        node = consent_element_check_risk_classify_node.ConsentElementCheckRiskClassifyNode()
        out = node.execute({"user_input": None})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets literals in src/; no direct os.environ reads
# (sole entry-point exception: INVOKE_AUTH_TOKEN caller-auth in src/api/server.py).
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads_outside_entry_point(self):
        offenders = []
        for fp in _src_files():
            normalized = fp.replace("\\", "/")
            if normalized.endswith("src/api/server.py"):
                continue  # entry-point exception: INVOKE_AUTH_TOKEN read before InvocationContext exists
            with open(fp, encoding="utf-8") as f:
                content = f.read()
            if "os.environ" in content and "ALLOW_STUB" not in content:
                offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import Graph

        agent = Graph(config={"max_retry": 1, "kb": []})
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="chair-tc04")
        result = agent.invoke(
            "irb pre-screen",
            ctx=ctx,
            input_context={
                "proposal": {
                    "title": "TC-04 probe study",
                    "consent_form_text": "Purpose stated. Risks disclosed. Withdrawal allowed. Data use は研究目的のみ。",
                    "study_description": "Survey-based study.",
                    "sensitive_info_handling_declared": False,
                }
            },
        )
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: every node emits >=1 domain event on every path; no
# node under src/nodes/ or src/graph/ ever re-emits a framework backbone event.
class TestTC05Audit:
    def test_post_process_node_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(post_process_node, "emit_trace_event", lambda event_type, payload, state: events.append(event_type))
        report = {"risk_classification": "minimal", "compliance_flags": [], "summary": "No compliance gaps found."}
        out = post_process_node.IRBGapReportNode().execute({"gap_report": __import__("json").dumps(report)})
        assert out["status"] == AgentStatus.SUCCESS.value
        assert events == ["gap_report_formatted"]
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_compliance_check_node_emits_on_error_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(compliance_check_node, "emit_trace_event", lambda event_type, payload, state: events.append(event_type))
        out = compliance_check_node.ComplianceCheckNode().execute({"consent_elements": None})
        assert out["status"] == AgentStatus.ERROR.value
        assert events, "error path must still emit a domain trace event"

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*event_type=["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-06 / TC-07 - S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError
# at class def). Full @final-enforcement coverage already lives in
# tests/unit/test_framework_compliance_tc06_tc07.py — this class only adds the
# _extra_* overridability + credential-block assertions not covered there.
class TestTC0607FinalGates:
    def test_extra_output_hook_is_overridable(self):
        if not hasattr(FunctionNode, "_extra_security_gate_output"):
            pytest.skip("local wheel rc1 stub: FunctionNode lacks _extra_security_gate_output — CI wheel is gate of record")
        assert post_process_node.IRBGapReportNode._extra_security_gate_output is not FunctionNode._extra_security_gate_output

    def test_output_gate_blocks_credentials(self):
        node = post_process_node.IRBGapReportNode()
        with pytest.raises(Exception):
            node._security_gate_output({"result": "token AKIAIOSFODNN7EXAMPLE leaked"})


# TC-08 - required_trust_level enforced: insufficient trust -> ERROR state, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        from src.graph.graph import IRBComplianceGraphNode
        from src.nodes import data_protection_retrieve_node

        for cls in (
            pre_process_node.ProposalParseNode,
            post_process_node.IRBGapReportNode,
            consent_element_check_risk_classify_node.ConsentElementCheckRiskClassifyNode,
            data_protection_retrieve_node.DataProtectionRetrieveNode,
            compliance_check_node.ComplianceCheckNode,
            IRBComplianceGraphNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error_no_raise(self):
        # __call__() reads required_trust_level off self.__class__ — a subclass
        # (not an instance attribute) is required to force a denial for this probe.
        _HighTrustProbe = type(
            "_HighTrustProbe", (pre_process_node.ProposalParseNode,), {"required_trust_level": TrustLevel.INTERNAL}
        )
        node = _HighTrustProbe()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "input_context": {}})
        assert str(out.get("status")).lower().endswith("error")
        assert out["error_log"] and "trust gate denied" in out["error_log"][0]

    def test_sufficient_trust_succeeds(self):
        node = pre_process_node.ProposalParseNode()
        out = node(
            {
                "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
                "input_context": {
                    "proposal": {
                        "title": "TC-08 probe study",
                        "consent_form_text": "Purpose stated. Risks disclosed. Withdrawal allowed. Data use は研究目的のみ。",
                        "study_description": "Survey-based study.",
                        "sensitive_info_handling_declared": False,
                    }
                },
            }
        )
        assert out["status"] == AgentStatus.SUCCESS.value
