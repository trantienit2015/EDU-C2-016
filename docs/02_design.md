# EDU-C2-016 — Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `IRBEthicsComplianceCheckGraph` (module `src.graph`, alias `Graph`) — inherits **L1 Base: AgentBaseGraph** (L1 direct)
- **Category**: Cat 2 — university research ethics & IRB compliance check
- **Pattern**: RAGAgent + Comply; Cat 2 composition = outer `AgentBaseGraph` + `GraphNode`(main) + inner `BaseGraph`
- **Industry**: EDU
- **Trust level (agent default)**: `VERIFIED_EXTERNAL`
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Canonical Node Flow (per scaffold issue)

```
[ProposalParse] -> [ConsentElementCheck] -> [RiskClassify] -> [DataProtectionRetrieve]
  -> [ComplianceCheck] -> [ComplianceGate] -> [IRBGapReport]
```

Mapped onto the fixed 5-node AgentBaseGraph backbone via Cat 2 GraphNode composition:

```
OUTER (AgentBaseGraph - src/graph/graph.py):
  initialize -> pre_process(ProposalParse) -> main(IRBComplianceGraphNode) -> post_process(IRBGapReport) -> finalize

INNER (BaseGraph - src/graph/domain_workflow_graph.py):
  START -> consent_element_check_risk_classify -> data_protection_retrieve -> compliance_check -> END
```

`IRBComplianceGraphNode` lives in `graph.py`, not `src/nodes/` (PB-6 safety). The
`ComplianceCheck`/`ComplianceGate` steps are combined into `ComplianceCheckNode` (which
also assembles the gap report), since `ComplianceGate` is the non-suppressible logic
inside the compliance check, not a separate framework gate.

## Compliance Gate (node business logic, not a framework S-3 gate)

`ComplianceCheckNode` (missing consent elements + 要配慮個人情報-handling gaps) is
domain business logic, NOT a framework S-3 gate (S-3 is secret isolation, see the
§3). It runs unconditionally on every proposal regardless of other flags.

## S-2 / S-3 Sensitive-Info Handling

- **S-2 (input)**: `ProposalParseNode` scans the submitted draft for residual 要配慮
  個人情報 (yohairyo-kojinjoho) BEFORE processing — reject rather than silently proceed.
- **S-3 (output)**: `IRBGapReportNode._extra_security_gate_output` is a non-suppressible
  re-check that the assembled gap report's own text does NOT verbatim-reproduce a
  sensitive-info pattern — checked against the SAME report dict's own field values only
  (never cross-referencing separately-read sibling `state` fields, per the CI
  lesson).

## State Schema (`src/schemas/state.py`)

`class State(AgentState)` — flat, all agent-specific fields `NotRequired`. Fields:
`consent_elements`, `risk_classification`, `retrieved_passages`, `compliance_flags`,
`gap_report`.

## Nodes

| Slot / step | Node | Responsibility |
|---|---|---|
| outer pre_process | `ProposalParseNode` | Parse IRB draft; S-2 要配慮個人情報 pre-scan/reject |
| inner 1 | `ConsentElementCheckRiskClassifyNode` | Check consent documentation elements; classify study risk tier |
| inner 2 | `DataProtectionRetrieveNode` | Retrieve 生命科学・医学系研究倫理指針 (2021+2023) + data-protection provisions |
| inner 3 | `ComplianceCheckNode` | Non-suppressible consent-element/要配慮個人情報 compliance check; assembles gap report |
| outer post_process | `IRBGapReportNode` | Format final gap report; non-suppressible verbatim-reproduction re-check |

## Framework Utilization

- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [x] S-2: explicit 要配慮個人情報 pre-scan in `ProposalParseNode` (ahead of the default gate).
- [x] S-3: `IRBGapReportNode._extra_security_gate_output()` — non-suppressible verbatim-reproduction re-check (see above).
- [x] S-4: `emit_trace_event()` in every node's `execute()`; GraphNode wrapper emits via `extract_input`/`merge_output`.

## Composition Pattern

- **Pattern**: GraphNode (subgraph) — `IRBComplianceGraphNode` wraps `IRBComplianceWorkflowGraph`
- **Error propagation strategy**: propagate (fail-fast; default `error_strategy = "propagate"`)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed multi-step compliance-check workflow, no autonomous loop needed |
| Composition pattern | Flat (Cat 1 style) | GraphNode + inner BaseGraph | GraphNode + inner BaseGraph | Cat 2 multi-step domain workflow (never flat) |
| ComplianceGate placement | Separate node | Combined with ComplianceCheckNode | Combined | ComplianceGate is the non-suppressible logic inside the compliance check, not a distinct framework gate |

## Dependencies

Deterministic-core: consent-element checking, risk classification, and compliance
checks require no external LLM — no `NarrativeExplain`/LLM-essential step in this
template (unlike the anomaly-detection siblings). `dependencies = []` (framework from
wheel).
