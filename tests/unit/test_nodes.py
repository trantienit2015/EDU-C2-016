# EDU-C2-016 - Unit tests: per-node success + error/edge paths.

from framework.schemas.agent_status import AgentStatus

import src.nodes.compliance_check_node as compliance_check_node
import src.nodes.consent_element_check_risk_classify_node as consent_element_check_risk_classify_node
import src.nodes.post_process_node as post_process_node
from src.nodes.compliance_check_node import ComplianceCheckNode
from src.nodes.consent_element_check_risk_classify_node import ConsentElementCheckRiskClassifyNode
from src.nodes.data_protection_retrieve_node import DataProtectionRetrieveNode
from src.nodes.post_process_node import IRBGapReportNode
from src.nodes.pre_process_node import ProposalParseNode
from src.schemas.state import from_json, to_json

COMPLIANT_PROPOSAL = {
    "title": "Study of exercise habits",
    "consent_form_text": "This study's purpose is X. Risks include Y. You may withdraw at any time. Data use は研究目的のみ。",
    "study_description": "Survey-based study on exercise habits.",
    "sensitive_info_handling_declared": False,
}

KB = [{"source": "MEXT-guideline", "section": "consent", "content": "Consent must address purpose, risk, and withdrawal.", "applies_to": "all"}]


class TestProposalParseNode:
    def test_success(self):
        state = {"input_context": {"proposal": COMPLIANT_PROPOSAL}}
        r = ProposalParseNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS

    def test_malformed_draft(self):
        state = {"input_context": {"proposal": {"title": "x"}}}
        assert ProposalParseNode().execute(state)["status"] == AgentStatus.ERROR

    def test_sensitive_info_rejected(self):
        bad = {**COMPLIANT_PROPOSAL, "study_description": "Study of patients with 統合失調症."}
        state = {"input_context": {"proposal": bad}}
        assert ProposalParseNode().execute(state)["status"] == AgentStatus.ERROR


def _inner_state(proposal):
    return {"user_input": to_json(proposal)}


class TestConsentElementCheckRiskClassifyNode:
    def test_consent_elements_detected(self):
        r = ConsentElementCheckRiskClassifyNode().execute(_inner_state(COMPLIANT_PROPOSAL))
        assert r["status"] == AgentStatus.SUCCESS
        elements = from_json(r["consent_elements"], {})
        assert elements["purpose"] is True
        assert elements["voluntary_withdrawal"] is True

    def test_missing_input_emits_trace_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            consent_element_check_risk_classify_node,
            "emit_trace_event",
            lambda event_type, payload, state: events.append(event_type),
        )
        r = ConsentElementCheckRiskClassifyNode().execute({"user_input": None})
        assert r["status"] == AgentStatus.ERROR
        assert "consent_risk_classify_missing_input" in events

    def test_missing_elements_detected(self):
        bad = {**COMPLIANT_PROPOSAL, "consent_form_text": "Nothing relevant here."}
        r = ConsentElementCheckRiskClassifyNode().execute(_inner_state(bad))
        elements = from_json(r["consent_elements"], {})
        assert elements["purpose"] is False

    def test_greater_than_minimal_risk_classified(self):
        risky = {**COMPLIANT_PROPOSAL, "study_description": "Invasive genomic sequencing study."}
        r = ConsentElementCheckRiskClassifyNode().execute(_inner_state(risky))
        assert r["risk_classification"] == "greater_than_minimal"


class TestDataProtectionRetrieveNode:
    def test_passages_retrieved(self):
        state = {"risk_classification": "minimal"}
        r = DataProtectionRetrieveNode(kb=KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        passages = from_json(r["retrieved_passages"], [])
        assert len(passages) >= 1


class TestComplianceCheckNode:
    def test_missing_consent_element_flagged(self):
        state = {
            "consent_elements": to_json({"purpose": False, "risks": True, "voluntary_withdrawal": True, "data_use": True}),
            "risk_classification": "minimal",
            "retrieved_passages": to_json([]),
            "user_input": to_json(COMPLIANT_PROPOSAL),
        }
        r = ComplianceCheckNode().execute(state)
        flags = from_json(r["compliance_flags"], [])
        assert any(f["flag"] == "missing_consent_element" for f in flags)

    def test_missing_sensitive_info_handling_flagged(self):
        state = {
            "consent_elements": to_json({"purpose": True, "risks": True, "voluntary_withdrawal": True, "data_use": True}),
            "risk_classification": "greater_than_minimal",
            "retrieved_passages": to_json([]),
            "user_input": to_json({**COMPLIANT_PROPOSAL, "sensitive_info_handling_declared": False}),
        }
        r = ComplianceCheckNode().execute(state)
        flags = from_json(r["compliance_flags"], [])
        assert any(f["flag"] == "missing_sensitive_info_handling" for f in flags)

    def test_fires_with_compliant_proposal(self):
        state = {
            "consent_elements": to_json({"purpose": True, "risks": True, "voluntary_withdrawal": True, "data_use": True}),
            "risk_classification": "minimal",
            "retrieved_passages": to_json([]),
            "user_input": to_json(COMPLIANT_PROPOSAL),
        }
        r = ComplianceCheckNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert from_json(r["compliance_flags"], []) == []

    def test_missing_input_emits_trace_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            compliance_check_node,
            "emit_trace_event",
            lambda event_type, payload, state: events.append(event_type),
        )
        r = ComplianceCheckNode().execute({"consent_elements": None})
        assert r["status"] == AgentStatus.ERROR
        assert "compliance_check_missing_input" in events

    def test_gap_report_citations_track_retrieved_passages(self):
        # 2-response regression: an empty KB vs a populated KB must produce
        # different citations in the assembled gap report (passages is not a
        # write-only signature param — build_gap_report() actually consumes it).
        base_state = {
            "consent_elements": to_json({"purpose": True, "risks": True, "voluntary_withdrawal": True, "data_use": True}),
            "risk_classification": "minimal",
            "user_input": to_json(COMPLIANT_PROPOSAL),
        }
        no_passages = ComplianceCheckNode().execute({**base_state, "retrieved_passages": to_json([])})
        with_passages = ComplianceCheckNode().execute(
            {**base_state, "retrieved_passages": to_json([{"source": "MEXT-guideline", "section": "consent", "content": "..."}])}
        )
        assert from_json(no_passages["gap_report"], {})["citations"] == []
        assert from_json(with_passages["gap_report"], {})["citations"] == [{"source": "MEXT-guideline", "section": "consent"}]


class TestIRBGapReportNode:
    def test_success(self):
        report = {"risk_classification": "minimal", "compliance_flags": [], "summary": "No compliance gaps found."}
        state = {"gap_report": to_json(report)}
        r = IRBGapReportNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS

    def test_upstream_error_short_circuits(self):
        assert IRBGapReportNode().execute({"status": AgentStatus.ERROR})["status"] == AgentStatus.ERROR

    def test_upstream_error_emits_trace_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            post_process_node,
            "emit_trace_event",
            lambda event_type, payload, state: events.append(event_type),
        )
        IRBGapReportNode().execute({"status": AgentStatus.ERROR.value})
        assert "gap_report_upstream_error_short_circuit" in events

    def test_missing_gap_report_emits_trace_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            post_process_node,
            "emit_trace_event",
            lambda event_type, payload, state: events.append(event_type),
        )
        r = IRBGapReportNode().execute({"gap_report": None})
        assert r["status"] == AgentStatus.ERROR
        assert "gap_report_missing_input" in events

    def test_extra_gate_blocks_verbatim_sensitive_reproduction(self):
        bad = to_json({"summary": "Patient has 統合失調症 per description."})
        out = IRBGapReportNode()._extra_security_gate_output({"result": bad})
        assert out["status"] == AgentStatus.ERROR

    def test_extra_gate_passthrough_when_clean(self):
        good = to_json({"summary": "No compliance gaps found."})
        state = {"result": good}
        assert IRBGapReportNode()._extra_security_gate_output(state) is state
