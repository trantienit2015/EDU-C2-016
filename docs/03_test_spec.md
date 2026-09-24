# EDU-C2-016 — Test Specification

## Test Strategy

Deterministic-core: no LLM dependency; the full suite runs offline.

## Unit Tests (`tests/unit/test_nodes.py`)

| Node | Cases |
|---|---|
| ProposalParseNode | success; malformed draft→ERROR; 要配慮個人情報 in draft→ERROR |
| ConsentElementCheckRiskClassifyNode | consent elements detected; missing elements detected; greater-than-minimal risk classified |
| DataProtectionRetrieveNode | passages retrieved for risk tier |
| ComplianceCheckNode | missing consent element flagged; missing 要配慮個人情報 handling flagged (greater-than-minimal risk); fires with fully-compliant proposal (zero flags) |
| IRBGapReportNode | success; upstream error short-circuit; non-suppressible hook blocks verbatim sensitive-info reproduction |

## Integration Tests (`tests/integration/test_graph.py`)

| ID | Test | Expected |
|---|---|---|
| I-1 | fully compliant proposal | SUCCESS; ≥5 nodes; compliance_flags empty |
| I-2 | missing consent element | compliance_flags non-empty |
| I-3 | 要配慮個人情報 in draft | error (rejected at pre_process) |
| I-4 | malformed draft | error |

## Proof-of-Boundary Tests (`tests/proof_of_boundary/`)

| PB | File | Verifies |
|---|---|---|
| PB-2 | `test_state_safety.py` | state holds only JSON-serializable primitives |
| PB-4 | `test_import_isolation.py` | no agenticstar / mediator / other-agent imports |
| PB-6 | `test_pb_invoke_order.py` | S-1 → node_start → S-2 → execute → S-3 → node_complete per node under src/nodes/ |

## Non-suppressible compliance gate tests (critical)

- Missing consent elements + 要配慮個人情報-handling gaps are always detected regardless of other flags (unit + I-2).
- The post_process S-3 hook checks the report's own text for verbatim sensitive-info reproduction only - never cross-references separate state fields.
