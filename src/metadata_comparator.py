"""
Compare parsed reference fields with exact-DOI metadata.

Findings from this module are warnings only. They must not be auto-applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .bibliographic_verifier import VerifiedRecord
from .format_validation import sanitize_text_field
from .reference_parser import ParsedReference


@dataclass(frozen=True)
class MetadataFinding:
    rule_id: str
    field: str
    message: str
    original_text: str
    metadata_text: str
    detail: str
    confidence: float


def _normalize_text(text: str) -> str:
    text = sanitize_text_field(text)
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"-\s+", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _title_words(text: str) -> list[str]:
    text = _normalize_text(text)
    text = re.sub(r"[-/]", " ", text)
    text = re.sub(r"[^0-9a-zÀ-ÖØ-öø-ÿก-๙]+", " ", text)
    return [word for word in text.split() if word]


def _surname(author: str) -> str:
    author = sanitize_text_field(author)
    if "," in author:
        return author.split(",", 1)[0].strip().casefold()
    pieces = author.split()
    return pieces[-1].casefold() if pieces else ""


def _author_surnames(authors: list[str]) -> list[str]:
    return [surname for surname in (_surname(author) for author in authors) if surname]


def _surnames_equivalent(left: str, right: str) -> bool:
    if left == right:
        return True
    return left.endswith(f"-{right}") or right.endswith(f"-{left}")


def compare_exact_doi_metadata(parsed: ParsedReference, record: VerifiedRecord) -> list[MetadataFinding]:
    findings: list[MetadataFinding] = []

    parsed_surnames = _author_surnames(parsed.authors)
    record_surnames = _author_surnames(record.authors)
    author_lists_differ = bool(parsed_surnames and record_surnames) and (
        len(parsed_surnames) != len(record_surnames)
        or any(not _surnames_equivalent(left, right) for left, right in zip(parsed_surnames, record_surnames))
    )
    if author_lists_differ:
        findings.append(
            MetadataFinding(
                rule_id="external_metadata_author_mismatch",
                field="authors",
                message="ผู้แต่งในรายการอ้างอิงไม่ตรงกับ metadata ของ DOI",
                original_text=", ".join(parsed.authors),
                metadata_text=", ".join(record.authors),
                detail=(
                    "ผู้แต่ง: รายการเดิมคือ "
                    f"{', '.join(parsed.authors)}; metadata ของ DOI คือ {', '.join(record.authors)}"
                ),
                confidence=0.92,
            )
        )

    parsed_title = _normalize_text(parsed.title)
    metadata_title = _normalize_text(record.title)
    if parsed_title and metadata_title and parsed_title != metadata_title:
        parsed_words = _title_words(parsed.title)
        metadata_words = _title_words(record.title)
        if parsed_words == metadata_words:
            return findings

        similarity = SequenceMatcher(None, parsed_title, metadata_title).ratio()
        likely_word_typo = False
        if len(parsed_words) == len(metadata_words):
            differing_pairs = [
                (left, right)
                for left, right in zip(parsed_words, metadata_words)
                if left != right
            ]
            likely_word_typo = bool(differing_pairs) and len(differing_pairs) <= 2 and all(
                min(len(left), len(right)) >= 5 and SequenceMatcher(None, left, right).ratio() >= 0.72
                for left, right in differing_pairs
            )

        if likely_word_typo:
            rule_id = "external_metadata_title_possible_typo"
            message = "ชื่อเรื่องในรายการอ้างอิงคล้าย metadata ของ DOI แต่ไม่ตรงกัน"
        elif similarity < 0.70:
            rule_id = "external_metadata_title_mismatch"
            message = "ชื่อเรื่องในรายการอ้างอิงไม่ตรงกับ metadata ของ DOI"
        else:
            return findings
        findings.append(
            MetadataFinding(
                rule_id=rule_id,
                field="title",
                message=message,
                original_text=parsed.title,
                metadata_text=record.title,
                detail=f"ชื่อเรื่อง: รายการเดิมคือ “{parsed.title}”; metadata ของ DOI คือ “{record.title}”",
                confidence=round(similarity, 3),
            )
        )

    return findings
