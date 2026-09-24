"""AgentCore Platform v1.0 - EDU-C2-016 ProposalParseNode (outer pre_process slot).

Parse the IRB application draft (title, consent_form_text, study_description).
S-2 input gate: flag residual 要配慮個人情報 (yohairyo-kojinjoho) in the
submitted draft before processing — reject rather than silently proceed.
"""

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import to_json
from src.services.service import parse_proposal, scan_sensitive_info


def _proposal_from_user_input(user_input: Any) -> dict[str, Any]:
    """Build the proposal draft from the caller's `user_input` string.

    Two accepted shapes, both arriving through the entry point's `input` field:

    * a JSON object carrying the draft fields (`title`, `consent_form_text`,
      `study_description`) — used verbatim;
    * a plain-text draft — treated as the study description, so a smoke-test
      style single string still exercises the pipeline instead of failing at
      the schema check.

    Returns ``{}`` when nothing usable is present, letting the caller fall back
    to ``input_context`` and then emit the existing validation error.
    """
    if not isinstance(user_input, str) or not user_input.strip():
        return {}

    text = user_input.strip()
    try:
        decoded = json.loads(text)
    except (ValueError, TypeError):
        decoded = None

    if isinstance(decoded, dict):
        # A caller sending structured JSON may nest the draft under "proposal".
        inner = decoded.get("proposal")
        return inner if isinstance(inner, dict) and inner else decoded

    return {
        "title": text[:120],
        "consent_form_text": text,
        "study_description": text,
    }


class ProposalParseNode(FunctionNode):
    """Parse the IRB proposal draft + S-2 sensitive-info pre-scan."""

    # S-1: explicit by design, not inherited implicitly.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # An in-process caller (GraphNode parent, tests) may hand the draft over
        # in `input_context`; when present that is deliberate and wins.
        #
        # An HTTP caller has no such channel: the standalone entry point
        # (src/api/server.py, matching the scaffold blueprint) accepts only
        # `{"input": str, "session_id": str}` and never populates
        # `input_context` from the request body. For that caller the draft
        # arrives in `user_input` — as a JSON object, or as a plain-text draft.
        input_context = state.get("input_context", {})  # read-only [C1]
        raw_proposal = input_context.get("proposal", {}) if isinstance(input_context, dict) else {}
        if not raw_proposal:
            raw_proposal = _proposal_from_user_input(state.get("user_input", ""))

        emit_trace_event("proposal_received", {"correlation_id": state.get("correlation_id", "")}, state)

        proposal, error = parse_proposal(raw_proposal)
        if error:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"ProposalParseNode: {error}"],
            }

        sensitive_hits = scan_sensitive_info(
            proposal.get("consent_form_text", "") + " " + proposal.get("study_description", "")
        )
        if sensitive_hits:
            emit_trace_event(
                "sensitive_info_prescan_blocked",
                {"hit_count": len(sensitive_hits), "correlation_id": state.get("correlation_id", "")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "ProposalParseNode: submitted draft contains residual 要配慮個人情報 (yohairyo-kojinjoho) - remove before submission"
                ],
            }

        return {
            "validated_input": to_json(proposal),
            "status": AgentStatus.SUCCESS.value,
        }
