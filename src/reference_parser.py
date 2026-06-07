"""
Reference parsing layer.

This module keeps raw reference text immutable and extracts conservative fields
with confidence scores. It is intentionally not a source of bibliographic truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s,;]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedField:
    value: Any
    confidence: float
    source: str = "parser"
    source_span: tuple[int, int] | None = None


@dataclass(frozen=True)
class ParsedReference:
    raw_text: str
    fields: dict[str, ParsedField] = field(default_factory=dict)
    parse_confidence: float = 0.0
    parser_warnings: list[str] = field(default_factory=list)

    @property
    def doi(self) -> str:
        field_value = self.fields.get("doi")
        return field_value.value if field_value else ""

    @property
    def title(self) -> str:
        field_value = self.fields.get("title")
        return field_value.value if field_value else ""

    @property
    def year(self) -> int | None:
        field_value = self.fields.get("year")
        return field_value.value if field_value else None

    @property
    def authors(self) -> list[str]:
        field_value = self.fields.get("authors")
        return field_value.value if field_value else []


def strip_markdown(text: str) -> str:
    return re.sub(r"[*_`#]+", "", text).strip()


def normalize_doi(doi: str) -> str:
    doi = doi.strip().rstrip(".,;)")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.lower()


def extract_doi(text: str) -> str:
    match = DOI_RE.search(text)
    return normalize_doi(match.group(1)) if match else ""


def _parse_authors(author_text: str) -> list[str]:
    author_text = author_text.replace(" & ", ", & ")
    if ", & " in author_text:
        left, last = author_text.rsplit(", & ", 1)
        pieces = [p.strip() for p in left.split(".,") if p.strip()]
        authors = [p + "." if not p.endswith(".") else p for p in pieces]
        authors.append(last.strip())
        return [a for a in authors if a]
    return [author_text.strip()] if author_text.strip() else []


def _infer_record_type(text: str, fields: dict[str, ParsedField]) -> str:
    lower = strip_markdown(text).lower()
    if " in " in lower and "(ed" in lower:
        return "book-chapter"
    if fields.get("doi") and re.search(r",\s*\d+(\(\d+\))?,\s*[\deE]", text):
        return "journal-article"
    if "proceedings" in lower:
        return "conference-paper"
    if "working paper" in lower or "[report]" in lower:
        return "report"
    return "unknown"


def parse_reference(raw_text: str) -> ParsedReference:
    clean = strip_markdown(raw_text)
    fields: dict[str, ParsedField] = {}
    warnings: list[str] = []

    doi = extract_doi(clean)
    if doi:
        match = DOI_RE.search(clean)
        fields["doi"] = ParsedField(doi, 0.99, source_span=match.span() if match else None)

    year_match = re.search(r"\((\d{4}[a-z]?)\)", clean)
    if year_match:
        year_text = year_match.group(1)
        fields["year"] = ParsedField(int(year_text[:4]), 0.98, source_span=year_match.span())
        author_text = clean[: year_match.start()].strip().rstrip(".")
        fields["authors"] = ParsedField(_parse_authors(author_text), 0.78)

        after_year = clean[year_match.end() :].lstrip()
        title_match = re.match(r"\.\s+(.+?)(?<!\b[A-Z])\.\s+", after_year)
        if title_match:
            fields["title"] = ParsedField(title_match.group(1).strip(), 0.84)
        else:
            title_match = re.match(r"\.\s+(.+?)\.\s*(?:https?://|$)", after_year)
            if title_match:
                fields["title"] = ParsedField(title_match.group(1).strip(), 0.68)
            else:
                warnings.append("unable_to_parse_title")
    else:
        warnings.append("missing_year")

    fields["record_type"] = ParsedField(_infer_record_type(clean, fields), 0.55)

    pages_match = re.search(r",\s*(\d+\s*[-–]\s*\d+)(?=\.?\s+(?:https?://|doi:|$))", clean)
    if pages_match:
        fields["pages"] = ParsedField(pages_match.group(1).replace(" ", ""), 0.9, source_span=pages_match.span(1))

    confidence = min([f.confidence for f in fields.values()], default=0.0)
    if warnings:
        confidence = min(confidence, 0.5)

    return ParsedReference(
        raw_text=raw_text,
        fields=fields,
        parse_confidence=confidence,
        parser_warnings=warnings,
    )
