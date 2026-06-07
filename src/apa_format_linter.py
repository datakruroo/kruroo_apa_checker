"""
APA 7 format linting layer.

This module checks format signals available in the original reference text. It
does not verify bibliographic identity and does not synthesize full references.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .apa_formatter import normalize_page_range, sentence_case_title
from .format_validation import sanitize_text_field
from .reference_parser import ParsedReference, parse_reference, strip_markdown


@dataclass(frozen=True)
class ApaFormatFinding:
    rule_id: str
    field: str
    message: str
    original_text: str
    proposed_text: str
    detail: str
    confidence: float
    safe_to_apply: bool
    human_review_required: bool = False


DOI_OR_URL_AT_END_RE = re.compile(
    r"(?P<locator>(?:https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[^\s.]+|https?://[^\s.]+))\.$",
    re.IGNORECASE,
)
DUPLICATE_DOI_PREFIX_RE = re.compile(
    r"https?://(?:dx\.)?doi\.org/https?://(?:dx\.)?doi\.org/(?P<doi>10\.\d{4,9}/[^\s,;)]+)",
    re.IGNORECASE,
)


def _add_unique(findings: list[ApaFormatFinding], finding: ApaFormatFinding) -> None:
    key = (finding.rule_id, finding.field, finding.original_text, finding.proposed_text)
    if key not in {(f.rule_id, f.field, f.original_text, f.proposed_text) for f in findings}:
        findings.append(finding)


def _title_case_needs_review(title: str) -> bool:
    if not re.search(r"[A-Za-z]", title):
        return False
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", title)
    if len(words) < 4:
        return False
    suspicious = 0
    for index, word in enumerate(words):
        if index == 0:
            continue
        if word.isupper() or len(word) <= 2:
            continue
        if word[:1].isupper() and any(ch.islower() for ch in word[1:]):
            suspicious += 1
    return suspicious >= 2


def _source_segment_looks_like_journal(text: str) -> str:
    pattern = re.compile(
        r"(?P<source>[^.\n]*?[A-Za-zก-ฮ][^.\n]*?,\s*(?:\*\s*)*\d+[^,\n]*,\s*[\deE]\s*\d*[^.\n]*?(?:[-–]\s*[\deE]?\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    return matches[-1].group("source").strip()


def _is_italic_at(markdown_text: str, index: int) -> bool:
    return markdown_text[:index].count("*") % 2 == 1


def _page_range_from_raw(text: str) -> str:
    clean = strip_markdown(text)
    match = re.search(r",\s*(\d+\s*[-–]\s*\d+)(?=\.?\s+(?:https?://|doi:|$)|\.$|$)", clean)
    return match.group(1).replace(" ", "") if match else ""


def lint_reference_format(raw_text: str, parsed: ParsedReference | None = None) -> list[ApaFormatFinding]:
    parsed = parsed or parse_reference(raw_text)
    raw = raw_text.strip()
    normalized_raw = sanitize_text_field(raw)
    findings: list[ApaFormatFinding] = []

    if normalized_raw != raw:
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_text_sanitization",
                field="text",
                message="มีอักขระที่ควรแปลงเป็นตัวอักษรปกติ",
                original_text=raw,
                proposed_text=normalized_raw,
                detail="แปลง HTML entity หรืออักขระควบคุมให้เป็นตัวอักษรปกติ",
                confidence=0.99,
                safe_to_apply=True,
            ),
        )

    duplicate_doi = DUPLICATE_DOI_PREFIX_RE.search(raw)
    if duplicate_doi:
        original = duplicate_doi.group(0).rstrip(".")
        proposed = f"https://doi.org/{duplicate_doi.group('doi').rstrip('.')}"
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_doi_duplicate_prefix",
                field="doi",
                message="DOI URL มี prefix ซ้ำ ทำให้เปิดใช้งานไม่ได้",
                original_text=original,
                proposed_text=proposed,
                detail=f"DOI: {original} → {proposed}",
                confidence=0.99,
                safe_to_apply=True,
            ),
        )

    year_spacing = re.search(r"(?<!\s)\((?:19|20|25)\d{2}[a-z]?\)", raw)
    if year_spacing:
        original = year_spacing.group(0)
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_author_year_spacing",
                field="year",
                message="ควรมีช่องว่างก่อนปีพิมพ์",
                original_text=original,
                proposed_text=f" {original}",
                detail=f"เพิ่มช่องว่างก่อน {original}",
                confidence=0.95,
                safe_to_apply=True,
            ),
        )

    author_year = re.match(r"(?P<author>.+?)\s+(?P<year>\((?:19|20|25)\d{2}[a-z]?\))", raw)
    if author_year:
        author = author_year.group("author").strip()
        year = author_year.group("year")
        if author and not author.endswith((".", "!", "?", ")", "]")):
            original = f"{author} {year}"
            proposed = f"{author}. {year}"
            _add_unique(
                findings,
                ApaFormatFinding(
                    rule_id="apa_author_period_before_year",
                    field="author",
                    message="หลังชื่อผู้แต่งก่อนปีพิมพ์ควรมีจุด",
                    original_text=original,
                    proposed_text=proposed,
                    detail=f"ชื่อผู้แต่ง/ปี: {original} → {proposed}",
                    confidence=0.97,
                    safe_to_apply=True,
                ),
            )

    year_without_period = re.search(r"\((?:19|20|25)\d{2}[a-z]?\)(?!\.)", raw)
    if year_without_period:
        original = year_without_period.group(0)
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_year_period",
                field="year",
                message="หลังปีพิมพ์ในวงเล็บควรมีจุด",
                original_text=original,
                proposed_text=f"{original}.",
                detail=f"ปีพิมพ์: {original} → {original}.",
                confidence=0.97,
                safe_to_apply=True,
            ),
        )

    for match in re.finditer(r"[?!]\.", raw):
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_duplicate_terminal_punctuation",
                field="punctuation",
                message="มีจุดเกินหลังเครื่องหมายคำถามหรือเครื่องหมายตกใจ",
                original_text=match.group(0),
                proposed_text=match.group(0)[0],
                detail=f"วรรคตอน: {match.group(0)} → {match.group(0)[0]}",
                confidence=0.98,
                safe_to_apply=True,
            ),
        )

    locator_match = DOI_OR_URL_AT_END_RE.search(raw)
    if locator_match:
        locator = locator_match.group("locator")
        field = "doi" if "doi.org/" in locator.lower() else "url"
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_locator_terminal_period",
                field=field,
                message="ท้าย DOI หรือ URL ไม่ควรมีจุด",
                original_text=f"{locator}.",
                proposed_text=locator,
                detail=f"{field.upper()}: ลบจุดท้ายรายการ",
                confidence=0.98,
                safe_to_apply=True,
            ),
        )

    doi_wrapper = re.search(r"doi:\s*(10\.\d{4,9}/[^\s,;]+)", raw, re.IGNORECASE)
    if doi_wrapper:
        original = doi_wrapper.group(0).rstrip(".")
        proposed = f"https://doi.org/{doi_wrapper.group(1).rstrip('.').lower()}"
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_doi_url_format",
                field="doi",
                message="DOI ควรอยู่ในรูปแบบ https://doi.org/...",
                original_text=original,
                proposed_text=proposed,
                detail=f"DOI: {original} → {proposed}",
                confidence=0.99,
                safe_to_apply=True,
            ),
        )

    pages = parsed.fields.get("pages")
    original_pages = str(pages.value) if pages and pages.value else _page_range_from_raw(raw)
    if original_pages:
        normalized_pages = normalize_page_range(original_pages)
        if original_pages != normalized_pages:
            _add_unique(
                findings,
                ApaFormatFinding(
                    rule_id="apa_page_range_en_dash",
                    field="pages",
                    message="ช่วงหน้าควรใช้ en dash (–) แทน hyphen (-)",
                    original_text=original_pages,
                    proposed_text=normalized_pages,
                    detail=f"ช่วงหน้า: {original_pages} → {normalized_pages}",
                    confidence=0.99,
                    safe_to_apply=True,
                ),
            )

    title = parsed.title
    if title and _title_case_needs_review(title):
        proposed_title = sentence_case_title(title)
        if proposed_title != title:
            _add_unique(
                findings,
                ApaFormatFinding(
                    rule_id="apa_title_sentence_case_review",
                    field="title",
                    message="ชื่อบทความหรือบทควรใช้ sentence case",
                    original_text=title,
                    proposed_text=proposed_title,
                    detail="ชื่อเรื่อง: ตรวจว่าควรปรับเป็น sentence case โดยรักษาชื่อเฉพาะและตัวย่อ",
                    confidence=0.72,
                    safe_to_apply=False,
                    human_review_required=True,
                ),
            )

    source_segment = _source_segment_looks_like_journal(raw)
    if source_segment and "*" not in source_segment:
        _add_unique(
            findings,
            ApaFormatFinding(
                rule_id="apa_source_italic_missing",
                field="source",
                message="ชื่อวารสารและ volume ควรเป็นตัวเอียง",
                original_text=source_segment,
                proposed_text="ทำตัวเอียงเฉพาะชื่อวารสารและ volume",
                detail="รูปแบบวารสาร: ตรวจ italic ของชื่อวารสารและ volume ในไฟล์ Word",
                confidence=0.78,
                safe_to_apply=False,
                human_review_required=True,
            ),
        )
    elif source_segment:
        volume_issue_match = re.search(
            r",\s*(?:\*\s*)*(?P<volume>\d+)(?:\s*\*)*\s*(?P<issue>\(\d+\))?",
            source_segment,
        )
        if volume_issue_match:
            volume_start = volume_issue_match.start("volume")
            if not _is_italic_at(source_segment, volume_start):
                volume = volume_issue_match.group("volume")
                _add_unique(
                    findings,
                    ApaFormatFinding(
                        rule_id="apa_volume_italic_missing",
                        field="source",
                        message="volume ของวารสารควรเป็นตัวเอียง",
                        original_text=volume,
                        proposed_text=f"ทำตัวเอียงที่ volume {volume}",
                        detail=f"รูปแบบวารสาร: ทำ volume {volume} เป็นตัวเอียง",
                        confidence=0.82,
                        safe_to_apply=False,
                        human_review_required=True,
                    ),
                )
            if volume_issue_match.group("issue"):
                issue_start = volume_issue_match.start("issue")
                issue = volume_issue_match.group("issue")
                if _is_italic_at(source_segment, issue_start):
                    _add_unique(
                        findings,
                        ApaFormatFinding(
                            rule_id="apa_issue_should_not_be_italic",
                            field="source",
                            message="issue number ไม่ควรเป็นตัวเอียง",
                            original_text=issue,
                            proposed_text=f"เอาตัวเอียงออกจาก issue {issue}",
                            detail=f"รูปแบบวารสาร: เอาตัวเอียงออกจาก issue {issue}",
                            confidence=0.82,
                            safe_to_apply=False,
                            human_review_required=True,
                        ),
                    )

    return findings
