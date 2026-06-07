"""
In-text citation cross-checking layer.
"""

from __future__ import annotations

import re


YEAR_RE = r"(?:19|20|25)\d{2}"
PAREN_CITATION_RE = re.compile(rf"\(([^()]*?{YEAR_RE}[^()]*)\)")
NARRATIVE_CITATION_RE = re.compile(
    rf"\b([A-Zก-ฮ][A-Za-zก-ฮ'’.-]+(?:\s+(?:and|&|และ)\s+[A-Zก-ฮ][A-Za-zก-ฮ'’.-]+)?(?:\s+et\s+al\.|และคณะ)?)\s+\(({YEAR_RE})\)"
)


def _citation_tokens(excerpt: str) -> list[str]:
    tokens: list[str] = []

    def add_token(token: str) -> None:
        token = token.strip().rstrip(")")
        if token and token not in tokens:
            tokens.append(token)

    for match in PAREN_CITATION_RE.finditer(excerpt):
        content = match.group(1)
        if re.fullmatch(rf"\s*{YEAR_RE}\s*", content):
            continue
        for part in content.split(";"):
            add_token(part)
    for match in NARRATIVE_CITATION_RE.finditer(excerpt):
        add_token(f"{match.group(1)}, {match.group(2)}")
    for match in re.finditer(rf"([A-Zก-ฮ][^();]{{0,100}}?,\s*{YEAR_RE})", excerpt):
        add_token(match.group(1))
    return tokens


def _normalize_key(text: str) -> str:
    text = re.sub(r"\bet\s+al\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"และคณะ", "", text)
    text = text.replace("&", " ")
    text = re.sub(r"[\s,.;:()]+", " ", text)
    return text.strip().casefold()


def _first_author_key(author_text: str) -> str:
    author_text = author_text.strip().strip(".")
    if not author_text:
        return ""
    first_author = re.split(r"\s+และ\s+|,\s+และ\s+|,\s*&\s*|,\s*", author_text, maxsplit=1)[0]
    if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ'’.-]+,\s*", author_text):
        first_author = author_text.split(",", 1)[0]
    return _normalize_key(first_author)


def _token_author_year(token: str) -> tuple[str, str]:
    year_match = re.search(YEAR_RE, token)
    if not year_match:
        return "", ""
    year = year_match.group(0)
    before_year = token[: year_match.start()]
    before_year = before_year.rstrip(" ,;(").strip()
    if re.search(r"\s+(?:and|&)\s+", before_year, flags=re.IGNORECASE):
        pieces = re.split(r"\s+(?:and|&)\s+", before_year, flags=re.IGNORECASE)
        surnames = []
        for piece in pieces:
            piece = piece.strip(" ,;")
            if piece:
                surnames.append(_normalize_key(piece.split()[-1]))
        if surnames:
            return " ".join(surnames), year
    return _first_author_key(before_year), year


def _reference_author_keys(author_text: str) -> set[str]:
    keys: set[str] = set()
    first_key = _first_author_key(author_text)
    if first_key:
        keys.add(first_key)

    # English APA references: Surname, Initials., & Surname, Initials.
    surnames = []
    for surname in re.findall(r"([^,]+),\s*(?:[A-Z]\.)", author_text):
        surname = re.sub(r"^\s*(?:&|และ)\s*", "", surname).strip()
        if surname:
            surnames.append(surname)
    normalized_surnames = [_normalize_key(surname) for surname in surnames if surname]
    if normalized_surnames:
        keys.add(normalized_surnames[0])
    if len(normalized_surnames) == 2:
        keys.add(" ".join(normalized_surnames))

    # Thai two-author form in references and citations.
    if " และ " in author_text and "," not in author_text:
        parts = [part.strip() for part in author_text.split(" และ ") if part.strip()]
        if len(parts) == 2:
            keys.add(" ".join(_normalize_key(part) for part in parts))
    return {key for key in keys if key}


def _reference_entries(references_text: str = "") -> list[dict]:
    if not references_text:
        return []

    from .pdf_extractor import parse_individual_references
    from .reference_parser import parse_reference

    entries: list[dict] = []
    for number, raw_ref in enumerate(parse_individual_references(references_text), start=1):
        parsed = parse_reference(raw_ref)
        if not parsed.year:
            continue
        author_text = raw_ref.split("(", 1)[0].strip()
        keys = _reference_author_keys(author_text)
        first_key = _first_author_key(author_text)
        if keys:
            entries.append(
                {
                    "reference_number": number,
                    "raw_reference": raw_ref,
                    "author_text": author_text,
                    "year": str(parsed.year),
                    "keys": keys,
                    "first_key": first_key,
                }
            )
    return entries


def _build_reference_index(references_text: str = "") -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for entry in _reference_entries(references_text):
        for key in entry["keys"]:
            index.setdefault(key, set()).add(str(entry["year"]))
    return index


def validate_intext_citation_excerpts(
    citation_excerpts: list[str],
    references: list[dict] | None = None,
    references_text: str = "",
    body_text: str = "",
) -> dict:
    del references
    reference_entries = _reference_entries(references_text)
    reference_index: dict[str, set[str]] = {}
    for entry in reference_entries:
        for key in entry["keys"]:
            reference_index.setdefault(key, set()).add(str(entry["year"]))
    cited_pairs: set[tuple[str, str]] = set()
    cited_author_keys: set[str] = set()
    matched_reference_pairs: set[tuple[str, str]] = set()
    issues = []

    for idx, excerpt in enumerate(citation_excerpts, start=1):
        excerpt_issues = []
        explanations = []
        tokens = _citation_tokens(excerpt)
        if not tokens:
            excerpt_issues.append("unable_to_parse_citation_token")

        for token in tokens:
            if not re.search(YEAR_RE, token):
                excerpt_issues.append("missing_year")
                continue
            if "," not in token and "&" not in token and "et al." not in token and re.search(YEAR_RE, token):
                # Narrative citations such as Han (2020) are valid and skip this condition.
                pass
            author_key, year = _token_author_year(token)
            if author_key and year:
                cited_pairs.add((author_key, year))
                cited_author_keys.add(author_key)
            if reference_index and author_key:
                reference_years = reference_index.get(author_key)
                if reference_years and year not in reference_years:
                    excerpt_issues.append("possible_year_mismatch")
                    explanations.append(
                        f"พบ citation ปี {year} แต่ References ของผู้แต่งนี้มีปี {', '.join(sorted(reference_years))}"
                    )
                elif not reference_years:
                    excerpt_issues.append("possible_unmatched_citation")
                    explanations.append("พบ citation ที่ยังจับคู่กับ References ไม่ได้")
                else:
                    matched_reference_pairs.add((author_key, year))

        if excerpt_issues:
            unique_issues = sorted(set(excerpt_issues))
            issues.append(
                {
                    "excerpt_number": idx,
                    "excerpt": excerpt,
                    "issues": unique_issues,
                    "corrected": "",
                    "explanation": "; ".join(explanations)
                    or "Citation tokens are checked independently; differing author counts across semicolon-separated citations are not an error.",
                    "severity": "ERROR" if "possible_year_mismatch" in unique_issues else "WARNING",
                    "status": "human_review_required",
                    "format_finding_details": explanations,
                }
            )

    evidence_text = body_text or "\n".join(citation_excerpts)
    for entry in reference_entries:
        if not matched_reference_pairs:
            break
        if any(key in cited_author_keys for key in entry["keys"]) or _has_reference_citation_evidence(entry, evidence_text):
            continue
        detail = f"ยังไม่พบ citation ในเนื้อหาที่ตรงกับ {entry['author_text']} ({entry['year']})"
        issues.append(
            {
                "reference_number": entry["reference_number"],
                "excerpt": entry["raw_reference"],
                "issues": ["listed_but_not_cited"],
                "corrected": "",
                "explanation": detail,
                "severity": "WARNING",
                "status": "human_review_required",
                "format_finding_details": [detail],
            }
        )

    return {
        "summary": {
            "total_checked": len(citation_excerpts),
            "issues_found": len(issues),
            "issue_types": sorted({issue for row in issues for issue in row["issues"]}),
        },
        "issues": issues,
    }


def _has_reference_citation_evidence(entry: dict, text: str) -> bool:
    if not text:
        return False
    year = re.escape(str(entry.get("year", "")))
    first_key = str(entry.get("first_key", "")).strip()
    if not first_key:
        return False
    first_author = re.escape(first_key).replace(r"\ ", r"\s+")
    patterns = [
        rf"\b{first_author}\s+et\s+al\.?\s*\(\s*{year}\s*\)",
        rf"\b{first_author}\s*\(\s*{year}\s*\)",
        rf"\(\s*{first_author}\s*,\s*{year}",
        rf"\b{first_author}\s+และคณะ\s*,?\s*{year}",
        rf"\(\s*{first_author}\s+และคณะ\s*,\s*{year}",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
