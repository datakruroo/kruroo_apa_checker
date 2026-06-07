"""
APA 7 formatting layer.
"""

from __future__ import annotations

import re

from .bibliographic_verifier import VerifiedRecord
from .format_validation import sanitize_text_field


PRESERVE_PHRASES = {
    "ai": "AI",
    "covid-19": "COVID-19",
    "ldavis": "LDAvis",
    "openalex": "OpenAlex",
    "oecd": "OECD",
    "e-ecd": "e-ECD",
    "mcmc": "MCMC",
    "lis": "LIS",
    "dirichlet": "Dirichlet",
    "bayesian": "Bayesian",
    "crossref": "Crossref",
    "computers & education": "Computers & Education",
    "r-hat": "R-hat",
    "evidence-centered design": "Evidence-Centered Design",
}


def _protect_phrases(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}
    ordered = sorted(PRESERVE_PHRASES.items(), key=lambda item: len(item[0]), reverse=True)
    output = text
    for idx, (needle, replacement) in enumerate(ordered):
        token = f"__APA_PROTECTED_{idx}__"
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        output, count = pattern.subn(token, output)
        if count:
            protected[token] = replacement
    return output, protected


def _restore_phrases(text: str, protected: dict[str, str]) -> str:
    for token, value in protected.items():
        text = text.replace(token, value)
        text = text.replace(token.lower(), value)
    return text


def sentence_case_title(title: str) -> str:
    title = re.sub(r"\s+", " ", sanitize_text_field(title))
    if not title:
        return title

    protected_text, protected = _protect_phrases(title)
    lowered = protected_text.lower()
    lowered = lowered[:1].upper() + lowered[1:]

    def cap_after_boundary(match: re.Match) -> str:
        return match.group(1) + match.group(2).upper()

    lowered = re.sub(r"([:!?]\s+)([a-z])", cap_after_boundary, lowered)
    return _restore_phrases(lowered, protected)


def normalize_page_range(pages: str) -> str:
    return re.sub(r"(?<=\d)-(?=\d)", "–", pages.strip())


def normalize_doi_url(doi: str) -> str:
    doi = sanitize_text_field(doi).rstrip(".,;)")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return f"https://doi.org/{doi.lower()}" if doi else ""


def format_authors(authors: list[str]) -> str:
    if not authors:
        return ""
    clean_authors = [sanitize_text_field(author) for author in authors if sanitize_text_field(author)]
    if not clean_authors:
        return ""
    if len(clean_authors) == 1:
        return clean_authors[0]
    return ", ".join(clean_authors[:-1]) + ", & " + clean_authors[-1]


def _terminal_punctuated(text: str) -> str:
    text = sanitize_text_field(text)
    if not text:
        return ""
    return text if text[-1] in ".?!" else f"{text}."


def format_journal_article(record: VerifiedRecord) -> str:
    authors = format_authors(record.authors)
    title = sentence_case_title(record.title)
    pages = normalize_page_range(record.pages)
    container_title = sanitize_text_field(record.container_title)
    volume_issue = sanitize_text_field(record.volume)
    if record.issue:
        volume_issue += f"({sanitize_text_field(record.issue)})"
    source_bits = [container_title, volume_issue, pages]
    source = ", ".join(bit for bit in source_bits if bit)
    doi = normalize_doi_url(record.doi)
    parts = [
        f"{authors} ({record.year})." if authors else f"({record.year}).",
        _terminal_punctuated(title),
        _terminal_punctuated(source),
    ]
    if doi:
        parts.append(doi)
    return " ".join(part for part in parts if part and part != ".")


def format_book_chapter(record: VerifiedRecord) -> str:
    authors = format_authors(record.authors)
    title = sentence_case_title(record.title)
    editors = ", ".join(sanitize_text_field(editor) for editor in record.editors)
    editor_label = "Eds." if len(record.editors) > 1 else "Ed."
    pages = normalize_page_range(record.pages)
    in_part = ""
    if editors:
        in_part = f"In {editors} ({editor_label}), {sanitize_text_field(record.container_title)}"
    elif record.container_title:
        in_part = f"In {sanitize_text_field(record.container_title)}"
    if pages:
        in_part += f" (pp. {pages})"
    doi = normalize_doi_url(record.doi)
    parts = [
        f"{authors} ({record.year})." if authors else f"({record.year}).",
        _terminal_punctuated(title),
        _terminal_punctuated(in_part),
        _terminal_punctuated(sanitize_text_field(record.publisher)),
    ]
    if doi:
        parts.append(doi)
    return " ".join(part for part in parts if part and part != ".")


def format_conference_paper(record: VerifiedRecord) -> str:
    authors = format_authors(record.authors)
    title = sentence_case_title(record.title)
    editors = ", ".join(sanitize_text_field(editor) for editor in record.editors)
    editor_label = "Eds." if len(record.editors) > 1 else "Ed."
    proceedings = sanitize_text_field(record.container_title)
    pages = normalize_page_range(record.pages)
    in_part = proceedings
    if editors:
        in_part = f"In {editors} ({editor_label}), {proceedings}"
    if pages:
        in_part += f" (pp. {pages})"
    doi = normalize_doi_url(record.doi)
    parts = [
        f"{authors} ({record.year})." if authors else f"({record.year}).",
        _terminal_punctuated(title),
        _terminal_punctuated(in_part),
        _terminal_punctuated(sanitize_text_field(record.publisher)),
    ]
    if doi:
        parts.append(doi)
    return " ".join(part for part in parts if part and part != ".")


def format_working_paper(record: VerifiedRecord) -> str:
    authors = format_authors(record.authors)
    title = sentence_case_title(record.title)
    source = sanitize_text_field(record.container_title or record.publisher)
    doi = normalize_doi_url(record.doi)
    url = sanitize_text_field(getattr(record, "url", ""))
    parts = [
        f"{authors} ({record.year})." if authors else f"({record.year}).",
        _terminal_punctuated(title),
        _terminal_punctuated(source),
    ]
    if doi:
        parts.append(doi)
    elif url:
        parts.append(url)
    return " ".join(part for part in parts if part and part != ".")
