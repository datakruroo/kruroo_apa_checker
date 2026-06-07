"""
Document parsing quality layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParseWarning:
    severity: str
    category: str
    message: str
    evidence: str
    confidence: float


def classify_parse_warnings(text: str) -> list[ParseWarning]:
    warnings: list[ParseWarning] = []

    if "\ufffd" in text or "�" in text:
        warnings.append(
            ParseWarning(
                severity="PARSER_WARNING",
                category="damaged_character",
                message="The parsed text contains replacement characters.",
                evidence="�",
                confidence=0.95,
            )
        )

    for match in re.finditer(r"\b(an improved|a|the)\s{2,}(for|of|in|to)\b", text, re.IGNORECASE):
        warnings.append(
            ParseWarning(
                severity="PARSER_WARNING",
                category="possible_missing_formula_or_token",
                message="The parsed text appears to be missing an inline token or formula.",
                evidence=match.group(0),
                confidence=0.9,
            )
        )

    if re.search(r"\w-\s+\w", text):
        warnings.append(
            ParseWarning(
                severity="PARSER_WARNING",
                category="possible_line_break_artifact",
                message="A word may have been split by a line-break hyphen.",
                evidence="hyphenated line break",
                confidence=0.65,
            )
        )

    return warnings


def document_parse_quality_check(text: str) -> list[ParseWarning]:
    return classify_parse_warnings(text)


def reference_section_parse_quality_check(references_text: str) -> list[ParseWarning]:
    return classify_parse_warnings(references_text)


def in_text_citation_parse_quality_check(body_text: str) -> list[ParseWarning]:
    return classify_parse_warnings(body_text)
