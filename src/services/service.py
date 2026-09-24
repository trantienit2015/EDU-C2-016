"""AgentCore Platform v1.0 - EDU-C2-016 domain services.

Deterministic helpers only: IRB proposal parsing, yohairyo-kojinjoho
(要配慮個人情報) scan (both input pre-scan and output verbatim-reproduction
check), consent-element checking, risk classification, guideline KB
retrieval (mock with a real interface), compliance-gap detection, and gap
report assembly. No agenticstar imports.
"""

from __future__ import annotations

from typing import Any
import re

REQUIRED_CONSENT_ELEMENTS = ("purpose", "risks", "voluntary_withdrawal", "data_use")

# 要配慮個人情報 markers: health condition / genomic / demographic sensitive terms.
SENSITIVE_INFO_PATTERNS = [
    re.compile(r"\b(HIV|AIDS|統合失調症|うつ病|遺伝子検査結果)\b"),
    re.compile(r"\bgenomic (test|sequencing) result\b", re.IGNORECASE),
]

GREATER_THAN_MINIMAL_KEYWORDS = ("invasive", "genomic", "biological sample", "vulnerable population", "minor")


def parse_proposal(raw_proposal: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Schema-validate the submitted IRB application draft."""
    if not isinstance(raw_proposal, dict) or not raw_proposal:
        return {}, "proposal draft is empty or not an object"
    required = ("title", "consent_form_text", "study_description")
    missing = [f for f in required if f not in raw_proposal]
    if missing:
        return {}, f"proposal missing required fields: {missing}"
    return raw_proposal, None


def scan_sensitive_info(text: str) -> list[str]:
    """S-2 input scan: detect residual 要配慮個人情報 in the submitted draft."""
    return [pat.pattern for pat in SENSITIVE_INFO_PATTERNS if pat.search(text)]


def check_consent_elements(consent_form_text: str) -> dict[str, Any]:
    """Deterministic check of consent documentation elements (keyword-based)."""
    text_lower = consent_form_text.lower()
    return {
        "purpose": "purpose" in text_lower or "目的" in consent_form_text,
        "risks": "risk" in text_lower or "リスク" in consent_form_text,
        "voluntary_withdrawal": "withdraw" in text_lower or "撤回" in consent_form_text,
        "data_use": "data use" in text_lower
        or "データ利用" in consent_form_text
        or "データの利用" in consent_form_text,
    }


def classify_risk(study_description: str) -> str:
    """Deterministic risk classification (minimal / greater_than_minimal)."""
    desc_lower = study_description.lower()
    if any(kw in desc_lower for kw in GREATER_THAN_MINIMAL_KEYWORDS):
        return "greater_than_minimal"
    return "minimal"


def retrieve_guideline_passages(
    risk_classification: str, kb: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Deterministic mock retriever with a real interface: 生命科学・医学系研究倫理指針
    (2021+2023 revision) + data-protection provisions relevant to the risk tier."""
    kb = kb or []
    matches = []
    for doc in kb:
        if doc.get("applies_to", "all") in (risk_classification, "all"):
            matches.append(
                {
                    "source": doc.get("source", "MEXT-guideline"),
                    "section": doc.get("section", ""),
                    "snippet": doc.get("content", "")[:200],
                }
            )
    return matches


def check_compliance(
    consent_elements: dict[str, Any], risk_classification: str, sensitive_info_handling_declared: bool
) -> list[dict[str, Any]]:
    """Non-suppressible node business logic: missing consent elements +
    要配慮個人情報 handling gaps. Fires on every proposal regardless of other flags."""
    flags = []
    for element, present in consent_elements.items():
        if not present:
            flags.append(
                {
                    "flag": "missing_consent_element",
                    "requirement": element,
                    "description": f"consent form does not address '{element}'",
                }
            )

    if risk_classification == "greater_than_minimal" and not sensitive_info_handling_declared:
        flags.append(
            {
                "flag": "missing_sensitive_info_handling",
                "requirement": "yohairyo_kojinjoho_handling",
                "description": "greater-than-minimal-risk study does not declare 要配慮個人情報 handling provisions",
            }
        )

    return flags


def scan_output_for_verbatim_sensitive_reproduction(report_text: str, original_sensitive_hits: list[str]) -> bool:
    """S-3 output gate: the gap report must NOT reproduce verbatim 要配慮個人情報 from input."""
    return any(re.search(pat, report_text) for pat in original_sensitive_hits)


def build_gap_report(
    consent_elements: dict[str, Any],
    risk_classification: str,
    compliance_flags: list[dict[str, Any]],
    passages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the final IRB gap report."""
    return {
        "risk_classification": risk_classification,
        "consent_elements": consent_elements,
        "compliance_flags": compliance_flags,
        "citations": [{"source": p["source"], "section": p["section"]} for p in passages],
        "summary": "No compliance gaps found."
        if not compliance_flags
        else f"{len(compliance_flags)} compliance gap(s) found - see flags.",
    }
