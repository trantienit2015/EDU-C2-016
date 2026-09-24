"""AgentCore Platform v1.0 - EDU-C2-016 state schema."""

# ADR-005: State must be a flat TypedDict - never Pydantic BaseModel.
# LangGraph checkpoints use msgpack serialization; Pydantic objects (and nested
# dict/list containers) are not msgpack-safe. Extend AgentState with agent-specific
# fields only. Nested list/dict fields are stored as JSON strings and
# (de)serialized at the node boundary via to_json/from_json below. Do NOT add
# credentials, secrets, or Pydantic models.

from __future__ import annotations

import json
from typing import Any, NotRequired, Optional

from framework.schemas.agent_state import AgentState


def to_json(value: Any) -> Optional[str]:
    """Serialize a list/dict State value to a compact JSON string (ADR-005, msgpack-safe)."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(value: Any, default: Any) -> Any:
    """Deserialize a JSON-string State value back to its list/dict form (tolerant)."""
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to Any
# and reports every NotRequired below as valid-type. The fields are correct (the state contract
# requires NotRequired) -- the report is a packaging artifact, suppressed per field.
# Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """University research ethics & IRB compliance check state.

    Shared fields (user_input, validated_input, status, session_id, node_history,
    error_log, result, formatted_output, hitl_*, etc.) are inherited from AgentState.
    Only agent-specific, flat, JSON-serializable fields are declared below; all are
    NotRequired (written mid-pipeline - C8).
    """

    # JSON dict{purpose, risks, voluntary_withdrawal, data_use} - consent-element presence flags.
    consent_elements: NotRequired[str | None]  # type: ignore[valid-type]
    risk_classification: NotRequired[str]  # type: ignore[valid-type]  # "minimal" | "greater_than_minimal"
    # JSON list[{source, section, snippet}] - retrieved guideline passages.
    retrieved_passages: NotRequired[str | None]  # type: ignore[valid-type]
    # JSON list[{flag, requirement, description}] - non-suppressible compliance gaps.
    compliance_flags: NotRequired[str | None]  # type: ignore[valid-type]
    gap_report: NotRequired[str | None]  # type: ignore[valid-type]  # JSON final IRB gap report
