"""AgentCore Platform v1.0 - EDU-C2-016 IRBGapReportNode (outer post_process slot).

Assemble the final IRB gap report. S-3 output gate: the compliance gap
report must NOT reproduce verbatim 要配慮個人情報 (yohairyo-kojinjoho) from
the input, even accidentally (e.g. via a quoted excerpt in a summary field).
The non-suppressible re-check verifies the assembled report's OWN text does
not match a sensitive pattern from the original input consent form -
never cross-referencing separately-read sibling `state` fields (see the
CI lesson: it re-derives the sensitive-pattern check from the SAME report
text field only).
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import SENSITIVE_INFO_PATTERNS


class IRBGapReportNode(FunctionNode):
    """Assemble the final IRB gap report; non-suppressible verbatim-reproduction re-check."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("status") == AgentStatus.ERROR.value:
            emit_trace_event(
                "gap_report_upstream_error_short_circuit",
                {"correlation_id": state.get("correlation_id", "")},
                state,
            )
            return {"status": AgentStatus.ERROR.value}

        report = from_json(state.get("gap_report"), None)
        if not isinstance(report, dict):
            emit_trace_event(
                "gap_report_missing_input",
                {"correlation_id": state.get("correlation_id", "")},
                state,
            )
            return {"status": AgentStatus.ERROR.value, "error_log": ["IRBGapReportNode: missing assembled gap report"]}

        emit_trace_event(
            "gap_report_formatted",
            {
                "flag_count": len(report.get("compliance_flags") or []),
                "correlation_id": state.get("correlation_id", ""),
            },
            state,
        )

        return {
            "formatted_output": report,
            "result": to_json(report),
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Non-suppressible re-check: report text must not verbatim-reproduce sensitive patterns."""
        report = from_json(state.get("result"), None)
        if not isinstance(report, dict):
            return state

        report_text = " ".join(str(v) for v in report.values())
        for pat in SENSITIVE_INFO_PATTERNS:
            if pat.search(report_text):
                emit_trace_event("output_gate_sensitive_info_leak_blocked", {}, state)
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["Output gate: gap report reproduces a 要配慮個人情報 pattern verbatim - blocked"],
                }

        return state
