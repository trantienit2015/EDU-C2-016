# EDU-C2-016 - Integration test: full graph compile + invoke (Cat 2 outer + inner).

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph

COMPLIANT_PROPOSAL = {
    "title": "Study of exercise habits",
    "consent_form_text": "This study's purpose is X. Risks include Y. You may withdraw at any time. Data use は研究目的のみ。",
    "study_description": "Survey-based study on exercise habits.",
    "sensitive_info_handling_declared": False,
}

KB = [{"source": "MEXT-guideline", "section": "consent", "content": "Consent must address purpose, risk, and withdrawal.", "applies_to": "all"}]


class TestAgentIntegration:
    def test_fully_compliant_proposal(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="chair")
        result = agent.invoke("irb pre-screen", ctx=ctx, input_context={"proposal": COMPLIANT_PROPOSAL})

        assert result["status"] == "success"
        assert len(result.get("node_history", [])) >= 5

    def test_missing_consent_element(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-2", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="chair")
        incomplete = {**COMPLIANT_PROPOSAL, "consent_form_text": "Nothing relevant."}
        result = agent.invoke("irb pre-screen", ctx=ctx, input_context={"proposal": incomplete})
        assert result["status"] == "success"

    def test_sensitive_info_in_draft_rejected(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-3", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="chair")
        bad = {**COMPLIANT_PROPOSAL, "study_description": "Study of patients with 統合失調症."}
        result = agent.invoke("irb pre-screen", ctx=ctx, input_context={"proposal": bad})
        assert result["status"] in ("error", "cancelled")

    def test_malformed_draft_error(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-4", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="chair")
        result = agent.invoke("irb pre-screen", ctx=ctx, input_context={"proposal": {"title": "x"}})
        assert result["status"] in ("error", "cancelled")
