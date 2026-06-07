"""
Bibliographic verification layer with DOI-first invariants and provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .reference_parser import ParsedReference, normalize_doi, parse_reference


@dataclass(frozen=True)
class FieldProvenance:
    source: str
    source_record_id: str
    fetched_at: str


@dataclass
class VerifiedRecord:
    source: str
    source_record_id: str
    doi: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    title: str = ""
    container_title: str = ""
    editors: list[str] = field(default_factory=list)
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    url: str = ""
    isbn: str = ""
    issn: str = ""
    record_type: str = ""
    fetched_at: str = ""
    field_provenance: dict[str, FieldProvenance] = field(default_factory=dict)
    conflict_log: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.doi = normalize_doi(self.doi) if self.doi else ""
        if not self.fetched_at:
            self.fetched_at = datetime.now(timezone.utc).isoformat()
        if not self.field_provenance:
            provenance = FieldProvenance(
                source=self.source,
                source_record_id=self.source_record_id,
                fetched_at=self.fetched_at,
            )
            self.field_provenance = {
                field_name: provenance
                for field_name in (
                    "doi",
                    "authors",
                    "year",
                    "title",
                    "container_title",
                    "editors",
                    "volume",
                    "issue",
                    "pages",
                    "publisher",
                    "url",
                    "isbn",
                    "issn",
                    "record_type",
                )
            }


@dataclass(frozen=True)
class VerificationResult:
    parsed: ParsedReference
    status: str
    record: VerifiedRecord | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    source: str = ""


@dataclass(frozen=True)
class VerificationAction:
    status: str
    auto_correct: bool
    reasons: list[str]
    confidence: float


def _record_from_legacy(source: str, data: dict) -> VerifiedRecord:
    doi = data.get("doi", "")
    source_record_id = normalize_doi(doi) if doi else data.get("id", "") or data.get("title", "")
    return VerifiedRecord(
        source=source,
        source_record_id=source_record_id,
        doi=doi,
        authors=data.get("authors", []),
        year=data.get("year"),
        title=data.get("title", ""),
        container_title=data.get("journal", "") or data.get("container_title", ""),
        editors=data.get("editors", []),
        volume=data.get("volume", ""),
        issue=data.get("issue", ""),
        pages=data.get("pages", ""),
        publisher=data.get("publisher", ""),
        url=data.get("url", ""),
        isbn=data.get("isbn", ""),
        issn=data.get("issn", ""),
        record_type=data.get("type", "") or data.get("record_type", ""),
    )


def resolve_exact_doi(doi: str) -> VerifiedRecord | None:
    from .crossref_verifier import _lookup_crossref_doi

    data = _lookup_crossref_doi(normalize_doi(doi))
    if not data:
        return None
    return _record_from_legacy("crossref", data)


def search_title_candidates(parsed: ParsedReference) -> list[tuple[VerifiedRecord, float]]:
    if not parsed.title:
        return []

    from .crossref_verifier import _search_crossref_title, _search_openalex

    candidates: list[tuple[VerifiedRecord, float]] = []
    for source, lookup in (("openalex", _search_openalex), ("crossref", _search_crossref_title)):
        data = lookup(parsed.title)
        if not data or not data.get("title"):
            continue
        record = _record_from_legacy(source, data)
        confidence = SequenceMatcher(
            None,
            parsed.title.casefold(),
            record.title.casefold(),
        ).ratio()
        candidates.append((record, confidence))
    return candidates


def choose_verification_action(
    parsed: ParsedReference,
    candidate: VerifiedRecord,
    candidate_confidence: float,
) -> VerificationAction:
    reasons: list[str] = []

    if parsed.doi and candidate.doi and normalize_doi(parsed.doi) != normalize_doi(candidate.doi):
        reasons.append("doi_conflict")

    if candidate_confidence < 0.85:
        reasons.append("low_confidence_candidate")

    if parsed.title and candidate.title:
        title_similarity = SequenceMatcher(
            None,
            parsed.title.casefold(),
            candidate.title.casefold(),
        ).ratio()
        if title_similarity < 0.82:
            reasons.append("title_mismatch")

    parsed_type = parsed.fields.get("record_type")
    if (
        parsed_type
        and parsed_type.value != "unknown"
        and candidate.record_type
        and parsed_type.value != candidate.record_type
    ):
        reasons.append("record_type_conflict")

    if reasons:
        return VerificationAction(
            status="human_review_required",
            auto_correct=False,
            reasons=reasons,
            confidence=candidate_confidence,
        )

    return VerificationAction(
        status="possible_match",
        auto_correct=False,
        reasons=[],
        confidence=candidate_confidence,
    )


def candidate_display_status(confidence: float) -> str:
    if confidence >= 0.90:
        return "possible_match"
    if confidence >= 0.75:
        return "low_confidence_possible_match"
    return "debug_log_only"


def verify_reference(ref_text: str, brave_key: str = "") -> VerificationResult:
    del brave_key
    parsed = parse_reference(ref_text)

    if parsed.doi:
        record = resolve_exact_doi(parsed.doi)
        if not record:
            return VerificationResult(
                parsed=parsed,
                status="unable_to_verify_doi",
                confidence=0.0,
                evidence=[f"DOI lookup failed for {parsed.doi}; fuzzy replacement was not attempted."],
            )
        if normalize_doi(record.doi) != normalize_doi(parsed.doi):
            return VerificationResult(
                parsed=parsed,
                status="doi_conflict",
                record=record,
                confidence=1.0,
                evidence=[f"Resolved DOI {record.doi} does not match original DOI {parsed.doi}."],
                source=record.source,
            )
        return VerificationResult(
            parsed=parsed,
            status="verified",
            record=record,
            confidence=1.0,
            evidence=[f"Exact DOI match from {record.source}: {record.doi}."],
            source=record.source,
        )

    candidates = search_title_candidates(parsed)
    if not candidates:
        return VerificationResult(
            parsed=parsed,
            status="unverified",
            confidence=0.0,
            evidence=["No DOI and no sufficiently attributable metadata candidate."],
        )

    candidate, confidence = max(candidates, key=lambda item: item[1])
    display_status = candidate_display_status(confidence)
    if display_status == "debug_log_only":
        return VerificationResult(
            parsed=parsed,
            status="unverified",
            confidence=confidence,
            evidence=["Low-confidence candidate suppressed from report; debug only."],
        )
    action = choose_verification_action(parsed, candidate, confidence)
    return VerificationResult(
        parsed=parsed,
        status=display_status if action.status == "possible_match" else action.status,
        record=candidate,
        confidence=confidence,
        evidence=action.reasons or [f"Candidate from {candidate.source}."],
        source=candidate.source,
    )
