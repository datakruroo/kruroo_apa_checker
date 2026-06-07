"""
Low-risk fix layer.

Only transformations in this module are allowed to produce copyable output while
metadata autofix is disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from .apa_formatter import normalize_page_range
from .format_validation import sanitize_text_field
from .reference_parser import ParsedReference


@dataclass(frozen=True)
class SafeFixResult:
    output: str
    has_changes: bool
    changes: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _normalize_doi_wrapper_preserve_suffix(text: str) -> tuple[str, bool, str, str]:
    pattern = re.compile(
        r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s,;]+)",
        re.IGNORECASE,
    )
    replacement_pair = ("", "")

    def repl(match: re.Match) -> str:
        nonlocal replacement_pair
        full = match.group(0)
        suffix = match.group(1).rstrip(".,;)")
        trailing = full[len(full.rstrip(".,;)")) :]
        if full.lower().startswith("https://doi.org/") and full == f"https://doi.org/{suffix}{trailing}":
            return full
        replacement = f"https://doi.org/{suffix}{trailing}"
        replacement_pair = (full, replacement)
        return replacement

    output, count = pattern.subn(repl, text, count=1)
    return output, bool(count and output != text), replacement_pair[0], replacement_pair[1]


def _normalize_pages_only(text: str, parsed: ParsedReference) -> tuple[str, bool, str, str]:
    pages_field = parsed.fields.get("pages")
    if not pages_field or not pages_field.value:
        return text, False, "", ""
    pages = str(pages_field.value)
    normalized = normalize_page_range(pages)
    if normalized == pages:
        return text, False, "", ""
    output = text.replace(pages, normalized, 1)
    return output, output != text, pages, normalized


def build_safe_fix(parsed: ParsedReference) -> SafeFixResult:
    output = sanitize_text_field(parsed.raw_text)
    changes: list[str] = []
    details: list[str] = []
    if output != parsed.raw_text:
        changes.append("sanitize_text")
        details.append("อักขระ: แปลง HTML entity หรืออักขระควบคุมให้เป็นตัวอักษรปกติ")

    output, changed, old_doi, new_doi = _normalize_doi_wrapper_preserve_suffix(output)
    if changed:
        changes.append("normalize_doi_wrapper")
        details.append(f"DOI: {old_doi} → {new_doi}")

    output, changed, old_pages, new_pages = _normalize_pages_only(output, parsed)
    if changed:
        changes.append("normalize_page_range")
        details.append(f"ช่วงหน้า: {old_pages} → {new_pages}")

    return SafeFixResult(output=output, has_changes=bool(changes), changes=changes, details=details)
