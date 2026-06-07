"""
Post-format validation and immutable-field policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import html
import re
import unicodedata

from .reference_parser import normalize_doi


UNICODE_DASHES = {"\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"}
HTML_ENTITY_RE = re.compile(r"&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);", re.IGNORECASE)


class FormatStatus(StrEnum):
    VALID = "valid"
    LOW_RISK_FIX_AVAILABLE = "low_risk_fix_available"
    UNSAFE_OUTPUT = "unsafe_output"
    PARSER_WARNING = "parser_warning"


@dataclass(frozen=True)
class FormatValidationResult:
    identity_status: str = "unverified"
    metadata_status: str = "incomplete"
    formatting_status: FormatStatus = FormatStatus.UNSAFE_OUTPUT
    action: str = "blocked"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ready_to_use: bool = False


def sanitize_text_field(value: str) -> str:
    value = html.unescape(value or "")
    value = unicodedata.normalize("NFC", value)
    return "".join(ch for ch in value if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C")).strip()


def contains_unicode_dash(value: str) -> bool:
    return any(ch in value for ch in UNICODE_DASHES)


def extract_output_doi(output: str) -> str:
    match = re.search(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s,;]+)", output, re.IGNORECASE)
    return normalize_doi(match.group(1)) if match else ""


def extract_output_urls(output: str) -> list[str]:
    return re.findall(r"https?://[^\s)]+", output)


def _required_field_errors(record) -> list[str]:
    errors: list[str] = []
    record_type = (record.record_type or "unknown").lower()

    requires_authors = {
        "journal-article",
        "book-chapter",
        "conference-paper",
        "working-paper",
        "report",
        "book",
        "webpage",
        "dataset",
    }
    if record_type in requires_authors and not record.authors:
        errors.append("missing_required_authors")
    if not record.year:
        errors.append("missing_required_year")
    if not record.title:
        errors.append("missing_required_title")

    if record_type == "journal-article" and not record.container_title:
        errors.append("missing_required_container_title")
    if record_type == "book-chapter" and not record.container_title:
        errors.append("missing_required_book_title")
    if record_type == "working-paper" and not (record.publisher or record.container_title):
        errors.append("missing_required_series_or_publisher")
    if record_type == "conference-paper" and not record.container_title:
        errors.append("missing_required_proceedings_title")
    return errors


def _title_truncated(parsed_title: str, output: str) -> bool:
    if not parsed_title or ":" not in parsed_title:
        return False
    subtitle = parsed_title.split(":", 1)[1].strip().casefold()
    return bool(subtitle) and subtitle not in output.casefold()


def post_format_validator(
    record,
    formatted_output: str,
    *,
    parsed_title: str = "",
    identity_status: str = "unverified",
) -> FormatValidationResult:
    output = formatted_output or ""
    errors = _required_field_errors(record)
    warnings: list[str] = []

    if HTML_ENTITY_RE.search(output):
        errors.append("html_entity_not_decoded")
    if re.search(r"[?!]\.", output):
        errors.append("duplicate_terminal_punctuation")
    if re.search(r"\b[a-z]+[A-Z]{2,}[a-z]+\b", output):
        errors.append("midword_case_corruption")

    if record.doi:
        output_doi = extract_output_doi(output)
        if not output_doi:
            errors.append("missing_output_doi")
        elif output_doi != normalize_doi(record.doi):
            errors.append("doi_integrity")
        doi_url_match = re.search(r"https?://(?:dx\.)?doi\.org/[^\s,;]+", output, re.IGNORECASE)
        if doi_url_match and contains_unicode_dash(doi_url_match.group(0)):
            errors.append("unicode_dash_in_doi")

    expected_url = getattr(record, "url", "")
    if expected_url:
        if expected_url not in output:
            errors.append("url_integrity")
        for url in extract_output_urls(output):
            if contains_unicode_dash(url):
                errors.append("unicode_dash_in_url")

    if _title_truncated(parsed_title, output):
        errors.append("title_truncated")

    for editor in getattr(record, "editors", []) or []:
        if editor and editor not in output:
            errors.append("dropped_editors")
            break
    if getattr(record, "publisher", "") and record.record_type == "conference-paper" and record.publisher not in output:
        errors.append("dropped_publisher")

    metadata_status = "complete" if not _required_field_errors(record) else "incomplete"
    if errors:
        return FormatValidationResult(
            identity_status=identity_status,
            metadata_status=metadata_status,
            formatting_status=FormatStatus.UNSAFE_OUTPUT,
            action="blocked",
            errors=sorted(set(errors)),
            warnings=warnings,
            ready_to_use=False,
        )

    return FormatValidationResult(
        identity_status=identity_status,
        metadata_status=metadata_status,
        formatting_status=FormatStatus.VALID,
        action="no_change_needed",
        errors=[],
        warnings=warnings,
        ready_to_use=True,
    )
