"""
Researcher-facing report writer.

LLM usage in this module is limited to rewriting explanation text. It must not
create bibliographic facts or change original/proposed reference strings.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class ResearcherReportRow:
    severity_level: str
    item_label: str
    original_text: str
    proposed_text: str
    reason: str
    next_action: str
    technical_note: str = ""


PROBLEM_REASONS = {
    "title_truncated": "ชื่อเรื่องที่ค้นได้ไม่ครบ จึงไม่เสนอให้แก้ชื่อเรื่อง",
    "missing_required_authors": "ข้อมูลผู้แต่งไม่ครบ จึงไม่เสนอให้แก้ข้อมูลผู้แต่ง",
    "missing_required_year": "ข้อมูลปีพิมพ์ไม่ครบ ต้องตรวจจากแหล่งต้นทาง",
    "missing_required_title": "ข้อมูลชื่อเรื่องไม่ครบ ต้องตรวจจากแหล่งต้นทาง",
    "missing_required_container_title": "ข้อมูลชื่อวารสารหรือชื่อแหล่งพิมพ์ไม่ครบ",
    "missing_required_book_title": "ข้อมูลชื่อหนังสือไม่ครบ",
    "missing_required_series_or_publisher": "ข้อมูลชุดรายงานหรือหน่วยงานเผยแพร่ไม่ครบ",
    "missing_required_proceedings_title": "ข้อมูลชื่อ proceedings ไม่ครบ",
    "doi_integrity": "DOI ที่ระบบจะสร้างไม่ตรงกับ DOI เดิม จึงถูกบล็อก",
    "url_integrity": "URL ที่ระบบจะสร้างไม่ตรงกับ URL เดิม จึงถูกบล็อก",
    "unicode_dash_in_doi": "DOI มีเครื่องหมาย dash ที่ไม่ควรอยู่ใน DOI",
    "unicode_dash_in_url": "URL มีเครื่องหมาย dash ที่ไม่ควรอยู่ใน URL",
    "dropped_editors": "ข้อมูลบรรณาธิการหายไปจากรายการที่ระบบจะสร้าง",
    "dropped_publisher": "ข้อมูลสำนักพิมพ์หรือหน่วยงานเผยแพร่หายไปจากรายการที่ระบบจะสร้าง",
    "html_entity_not_decoded": "มีอักขระที่ควรแปลงเป็นตัวอักษรปกติ เช่น &amp; เป็น &",
    "duplicate_terminal_punctuation": "มีเครื่องหมายวรรคตอนซ้ำ",
    "midword_case_corruption": "พบตัวพิมพ์ใหญ่แทรกกลางคำผิดปกติ",
    "safe_fix:normalize_page_range": "ปรับรูปแบบช่วงหน้า",
    "safe_fix:normalize_doi_wrapper": "ปรับรูปแบบ DOI ให้เป็น https://doi.org/...",
    "safe_fix:sanitize_text": "แปลงอักขระที่อ่านมาเป็นรูปแบบปกติ เช่น &amp; เป็น &",
    "safe_fix:collapse_whitespace": "ลดช่องว่างซ้ำให้เหลือช่องว่างเดียว",
    "possible_year_mismatch": "ปีใน citation ไม่ตรงกับปีใน References",
    "possible_unmatched_citation": "พบ citation ที่อาจยังจับคู่กับ References ไม่ได้",
    "listed_but_not_cited": "ยังไม่พบการอ้างถึงรายการนี้ในเนื้อหา",
    "unable_to_parse_citation_token": "อ่านรูปแบบ citation ไม่ได้ชัดเจน",
    "The parsed text appears to be missing an inline token or formula.": "ข้อความที่อ่านจากไฟล์อาจขาดบางส่วน เช่น สูตรหรือสัญลักษณ์",
}


USER_LEVEL_LABELS = {
    "ERROR": "ต้องแก้ก่อนส่งบทความ",
    "WARNING": "ควรตรวจสอบก่อนแก้",
    "STYLE_FIX": "ปรับรูปแบบใน Word",
    "AUTO_FIX": "แก้ได้เลย",
    "PARSER_WARNING": "ตรวจคุณภาพข้อความที่อ่านจากไฟล์",
    "UNVERIFIED": "ยังยืนยันจากแหล่งภายนอกไม่ได้",
}


def user_level_label(level: str) -> str:
    return USER_LEVEL_LABELS.get(str(level), str(level))


def _reason_from_issue(issue: dict) -> str:
    if issue.get("grouped_subissues"):
        lines = []
        for subissue in issue["grouped_subissues"]:
            reason = subissue.get("reason", "")
            if reason:
                lines.append(f"{user_level_label(subissue.get('level', ''))}: {reason}")
        return "\n".join(lines)

    format_findings = issue.get("format_findings", [])
    has_doi_error = any(
        isinstance(finding, dict) and finding.get("rule_id") == "apa_doi_duplicate_prefix"
        for finding in format_findings
    )
    if has_doi_error:
        messages = []
        for finding in format_findings:
            message = finding.get("message") if isinstance(finding, dict) else ""
            if message and message not in messages:
                messages.append(message)
        for finding in issue.get("metadata_findings", []):
            message = finding.get("message") if isinstance(finding, dict) else ""
            if message and message not in messages:
                messages.append(message)
        if messages:
            return " / ".join(messages[:3])

    metadata_findings = issue.get("metadata_findings", [])
    if metadata_findings:
        messages = []
        for finding in metadata_findings:
            message = finding.get("message") if isinstance(finding, dict) else ""
            if message and message not in messages:
                messages.append(message)
        if messages:
            return " / ".join(messages[:3])

    if issue.get("format_finding_details") and any(problem in issue.get("issues", []) for problem in ("possible_year_mismatch", "possible_unmatched_citation")):
        details = _actionable_intext_details(issue)
        if details:
            return " / ".join(details)
    if "listed_but_not_cited" in issue.get("issues", []) and issue.get("format_finding_details"):
        return " / ".join(str(detail) for detail in issue.get("format_finding_details", []) if detail)

    if format_findings:
        messages = []
        for finding in format_findings:
            message = finding.get("message") if isinstance(finding, dict) else ""
            if message and message not in messages:
                messages.append(message)
        if messages:
            return " / ".join(messages[:3])

    reasons = []
    for problem in issue.get("issues", []):
        label = PROBLEM_REASONS.get(str(problem))
        if label and label not in reasons:
            reasons.append(label)
    if reasons:
        return " / ".join(reasons[:3])

    identity = issue.get("identity_status")
    if identity == "possible_match":
        return "ยังยืนยันจากแหล่งภายนอกไม่ได้ จึงตรวจได้เฉพาะรูปแบบ"
    if identity == "unverified":
        return "ยังยืนยันจากแหล่งภายนอกไม่ได้ จึงตรวจได้เฉพาะรูปแบบ"
    if identity == "verified_exact_doi":
        return "ยืนยัน DOI ได้ แต่ไม่เสนอแก้ข้อมูลสำคัญจากฐานข้อมูลโดยอัตโนมัติ"
    return "ต้องตรวจรายการนี้เพิ่มเติม"


def _severity_level(issue: dict) -> str:
    if issue.get("report_level_override"):
        return str(issue["report_level_override"])
    issue_codes = {str(code) for code in issue.get("issues", [])}
    format_rules = {
        finding.get("rule_id")
        for finding in issue.get("format_findings", [])
        if isinstance(finding, dict)
    }
    if "possible_year_mismatch" in issue_codes:
        return "ERROR"
    if "possible_unmatched_citation" in issue_codes:
        return "WARNING"
    if "apa_doi_duplicate_prefix" in format_rules:
        return "ERROR"
    if issue.get("metadata_findings"):
        return "WARNING"
    if issue.get("format_findings"):
        if all(
            finding.get("safe_to_apply")
            for finding in issue.get("format_findings", [])
            if isinstance(finding, dict)
        ):
            return "AUTO_FIX"
        return "WARNING"
    if issue.get("action") == "auto_fix_safe":
        return "AUTO_FIX"
    return "WARNING"


def _next_action(issue: dict) -> str:
    if issue.get("report_action_override"):
        return str(issue["report_action_override"])

    format_rules = {
        finding.get("rule_id")
        for finding in issue.get("format_findings", [])
        if isinstance(finding, dict)
    }
    if "apa_doi_duplicate_prefix" in format_rules:
        if issue.get("metadata_findings"):
            return "แก้ DOI ที่เสียรูปแบบก่อน แล้วตรวจผู้แต่งหรือชื่อเรื่องกับหน้า DOI"
        return "แก้ DOI ที่เสียรูปแบบก่อนส่งบทความ"

    if issue.get("metadata_findings"):
        return "ตรวจเทียบกับ DOI หรือหน้า publisher ก่อนแก้ผู้แต่งหรือชื่อเรื่อง"

    if "possible_year_mismatch" in issue.get("issues", []):
        return "แก้ให้ citation ในเนื้อหาจับคู่กับรายการอ้างอิงได้ชัดเจน ก่อนส่งบทความ"
    if "possible_unmatched_citation" in issue.get("issues", []):
        return "ตรวจทานว่ามีรายการอ้างอิงรองรับ citation นี้หรือไม่"
    if "listed_but_not_cited" in issue.get("issues", []):
        return "ตรวจว่ามีการอ้างรายการนี้ในเนื้อหาจริงหรือไม่ หากใช้จริงให้เพิ่ม citation ในตำแหน่งที่เกี่ยวข้อง หากไม่ใช้ให้พิจารณาลบเอง"

    format_findings = issue.get("format_findings", [])
    if format_findings:
        if all(finding.get("safe_to_apply") for finding in format_findings if isinstance(finding, dict)):
            return "แก้ได้เฉพาะจุดที่แสดงไว้"
        return "ตรวจทานเฉพาะจุดที่แสดงไว้ก่อนแก้ โดยเฉพาะชื่อเรื่องและตัวเอียง"

    action = issue.get("action")
    if action == "auto_fix_safe":
        return "แก้ได้เฉพาะจุดที่แสดงไว้ เช่น รูปแบบ DOI ช่วงหน้า หรือช่องว่าง"
    if action == "blocked":
        return "ตรวจเองกับรายการต้นฉบับหรือแหล่งเผยแพร่ก่อนแก้ ห้ามใช้รายการที่ระบบสร้างอัตโนมัติ"
    if action == "human_review_required":
        return "ตรวจเทียบกับแหล่งต้นทางก่อน อย่าเพิ่งแก้ผู้แต่ง ปี ชื่อเรื่อง หรือแหล่งพิมพ์"
    if action == "no_change_needed":
        return "ยังไม่ต้องแก้จากหลักฐานที่ระบบตรวจได้"
    return "ตรวจด้วยมนุษย์ก่อนปรับแก้"


def _proposed_text(issue: dict) -> str:
    if issue.get("corrected"):
        return issue["corrected"]
    if issue.get("action") == "no_change_needed":
        return "ไม่ต้องปรับจากผลตรวจนี้"
    return "ไม่เสนอข้อความใหม่ เพราะยังยืนยันข้อมูลไม่ได้"


def _has_researcher_format_finding(issue: dict) -> bool:
    if issue.get("metadata_findings"):
        return True
    if issue.get("format_findings"):
        return True
    if issue.get("action") != "auto_fix_safe" or not issue.get("corrected"):
        return False
    return any(str(problem).startswith("safe_fix:") for problem in issue.get("issues", []))


def _is_actionable_intext_issue(issue: dict) -> bool:
    if not issue.get("issues"):
        return False
    issue_codes = {str(problem) for problem in issue.get("issues", [])}
    if issue_codes == {"possible_unmatched_citation"}:
        return False
    return bool(
        issue.get("corrected")
        or issue.get("format_finding_details")
        or "possible_year_mismatch" in issue_codes
    )


def rows_from_results(results: dict) -> list[ResearcherReportRow]:
    rows: list[ResearcherReportRow] = []

    for issue in results.get("ref_check", {}).get("issues", []):
        if not _has_researcher_format_finding(issue):
            continue
        number = issue.get("reference_number", "?")
        row_issue = _group_reference_issue_for_report(issue)
        rows.append(
            ResearcherReportRow(
                severity_level=_severity_level(row_issue),
                item_label=f"รายการที่ {number}",
                original_text=row_issue.get("original", ""),
                proposed_text=_safe_fix_proposed_text(row_issue),
                reason=_reason_from_issue(row_issue),
                next_action=_next_action(row_issue),
                technical_note=" | ".join(
                    str(row_issue.get(key, ""))
                    for key in ("identity_status", "metadata_status", "formatting_status", "action")
                    if row_issue.get(key)
                ),
            )
        )

    for issue in results.get("intext_check", {}).get("issues", []):
        if not _is_actionable_intext_issue(issue):
            continue
        if issue.get("reference_number") and "listed_but_not_cited" in issue.get("issues", []):
            if _merge_uncited_issue_into_reference_row(rows, issue):
                continue
        if issue.get("reference_number"):
            item_label = f"รายการอ้างอิงที่ {issue.get('reference_number')}"
        else:
            item_label = f"ประโยคที่ {issue.get('excerpt_number', '?')}"
        rows.append(
            ResearcherReportRow(
                severity_level=_severity_level(issue),
                item_label=item_label,
                original_text=issue.get("excerpt", ""),
                proposed_text=issue.get("corrected") or _intext_proposed_text(issue),
                reason=_reason_from_issue(issue),
                next_action=_next_action(issue),
                technical_note=issue.get("status", ""),
            )
        )

    return rows


def _merge_uncited_issue_into_reference_row(rows: list[ResearcherReportRow], issue: dict) -> bool:
    item_label = f"รายการที่ {issue.get('reference_number')}"
    for index, row in enumerate(rows):
        if row.item_label != item_label:
            continue
        detail = " / ".join(str(detail) for detail in issue.get("format_finding_details", []) if detail)
        if not detail:
            detail = _reason_from_issue(issue)
        proposed = row.proposed_text + f"\n- {user_level_label('WARNING')}: {detail}"
        reason = row.reason + f"\n{user_level_label('WARNING')}: {detail}"
        next_action = (
            row.next_action
            + "\nตรวจว่ามีการอ้างรายการนี้ในเนื้อหาจริงหรือไม่ หากใช้จริงให้เพิ่ม citation ในตำแหน่งที่เกี่ยวข้อง หากไม่ใช้ให้พิจารณาลบเอง"
        )
        severity = max(
            [row.severity_level, "WARNING"],
            key=lambda level: LEVEL_PRIORITY.get(level, 0),
        )
        rows[index] = ResearcherReportRow(
            severity_level=severity,
            item_label=row.item_label,
            original_text=row.original_text,
            proposed_text=proposed,
            reason=reason,
            next_action=next_action,
            technical_note=row.technical_note,
        )
        return True
    return False


STYLE_FORMAT_RULES = {
    "apa_source_italic_missing",
    "apa_volume_italic_missing",
    "apa_issue_should_not_be_italic",
}

LEVEL_PRIORITY = {"AUTO_FIX": 1, "STYLE_FIX": 2, "WARNING": 3, "ERROR": 4}


def _group_reference_issue_for_report(issue: dict) -> dict:
    subissues = _reference_subissues(issue)
    if not subissues:
        return issue
    row_issue = dict(issue)
    top_level = max((sub["level"] for sub in subissues), key=lambda level: LEVEL_PRIORITY.get(level, 0))
    row_issue["report_level_override"] = top_level
    row_issue["report_action_override"] = _grouped_next_action(subissues)
    row_issue["grouped_subissues"] = subissues
    return row_issue


def _reference_subissues(issue: dict) -> list[dict]:
    format_findings = [finding for finding in issue.get("format_findings", []) if isinstance(finding, dict)]
    metadata_findings = [finding for finding in issue.get("metadata_findings", []) if isinstance(finding, dict)]
    subissues: list[dict] = []

    for finding in format_findings:
        rule_id = finding.get("rule_id")
        if rule_id == "apa_doi_duplicate_prefix":
            level = "ERROR"
        elif finding.get("safe_to_apply"):
            level = "AUTO_FIX"
        elif rule_id in STYLE_FORMAT_RULES:
            level = "STYLE_FIX"
        else:
            level = "WARNING"
        subissues.append(
            {
                "level": level,
                "detail": str(finding.get("detail") or finding.get("message") or ""),
                "reason": str(finding.get("message") or finding.get("detail") or ""),
            }
        )

    for finding in metadata_findings:
        subissues.append(
            {
                "level": "WARNING",
                "detail": "ตรวจ metadata: " + str(finding.get("detail") or finding.get("message") or ""),
                "reason": str(finding.get("message") or finding.get("detail") or ""),
            }
        )

    return [subissue for subissue in subissues if subissue["detail"] or subissue["reason"]]


def _grouped_next_action(subissues: list[dict]) -> str:
    levels = {subissue["level"] for subissue in subissues}
    if "ERROR" in levels and "WARNING" in levels:
        return "แก้ DOI หรือจุดที่แก้ได้ชัดเจนก่อน แล้วตรวจประเด็นที่เกี่ยวกับผู้แต่ง ชื่อเรื่อง ปี หรือแหล่งพิมพ์กับ DOI หรือแหล่งต้นทางก่อนแก้"
    if "ERROR" in levels:
        return "แก้จุดนี้ก่อนส่งบทความ"
    if "WARNING" in levels:
        return "ตรวจเทียบกับ DOI หรือแหล่งต้นทางก่อนแก้ข้อมูลสำคัญ"
    if "STYLE_FIX" in levels:
        return "แก้รูปแบบตัวเอียงในไฟล์ Word แล้วตรวจดูด้วยตาอีกครั้ง"
    return "แก้ได้เฉพาะจุดที่แสดงไว้"


def _split_reference_issue_for_report(issue: dict) -> list[dict]:
    format_findings = [finding for finding in issue.get("format_findings", []) if isinstance(finding, dict)]
    metadata_findings = [finding for finding in issue.get("metadata_findings", []) if isinstance(finding, dict)]
    rows: list[dict] = []

    doi_findings = [finding for finding in format_findings if finding.get("rule_id") == "apa_doi_duplicate_prefix"]
    safe_findings = [
        finding
        for finding in format_findings
        if finding.get("safe_to_apply") and finding.get("rule_id") != "apa_doi_duplicate_prefix"
    ]
    style_findings = [finding for finding in format_findings if finding.get("rule_id") in STYLE_FORMAT_RULES]
    review_findings = [
        finding
        for finding in format_findings
        if not finding.get("safe_to_apply") and finding.get("rule_id") not in STYLE_FORMAT_RULES
    ]

    if doi_findings:
        rows.append(
            _filtered_reference_issue(
                issue,
                format_findings=doi_findings,
                metadata_findings=[],
                level="ERROR",
                action="แก้ DOI ที่เสียรูปแบบก่อนส่งบทความ",
            )
        )
    if safe_findings:
        rows.append(
            _filtered_reference_issue(
                issue,
                format_findings=safe_findings,
                metadata_findings=[],
                level="AUTO_FIX",
                action="แก้ได้เฉพาะจุดที่แสดงไว้",
            )
        )
    if style_findings:
        rows.append(
            _filtered_reference_issue(
                issue,
                format_findings=style_findings,
                metadata_findings=[],
                level="STYLE_FIX",
                action="แก้ที่รูปแบบตัวเอียงในไฟล์ Word แล้วตรวจดูด้วยตาอีกครั้ง",
            )
        )
    if review_findings:
        rows.append(
            _filtered_reference_issue(
                issue,
                format_findings=review_findings,
                metadata_findings=[],
                level="WARNING",
                action="ตรวจทานเฉพาะจุดที่แสดงไว้ก่อนแก้",
            )
        )
    if metadata_findings:
        rows.append(
            _filtered_reference_issue(
                issue,
                format_findings=[],
                metadata_findings=metadata_findings,
                level="WARNING",
                action="ตรวจเทียบกับ DOI หรือหน้า publisher ก่อนแก้ผู้แต่งหรือชื่อเรื่อง",
            )
        )

    return rows or [issue]


def _filtered_reference_issue(
    issue: dict,
    format_findings: list[dict],
    metadata_findings: list[dict],
    level: str,
    action: str,
) -> dict:
    row_issue = dict(issue)
    row_issue["format_findings"] = format_findings
    row_issue["metadata_findings"] = metadata_findings
    row_issue["format_finding_details"] = [str(finding.get("detail", "")) for finding in format_findings if finding.get("detail")]
    row_issue["metadata_finding_details"] = [str(finding.get("detail", "")) for finding in metadata_findings if finding.get("detail")]
    row_issue["report_level_override"] = level
    row_issue["report_action_override"] = action
    return row_issue


def _safe_fix_proposed_text(issue: dict) -> str:
    if issue.get("grouped_subissues"):
        lines = []
        for subissue in issue["grouped_subissues"]:
            detail = subissue.get("detail", "")
            if detail:
                lines.append(f"- {user_level_label(subissue.get('level', ''))}: {detail}")
        return "ประเด็นที่ต้องตรวจหรือแก้:\n" + "\n".join(lines)

    finding_details = [str(detail) for detail in issue.get("format_finding_details", []) if detail]
    has_doi_error = any(
        isinstance(finding, dict) and finding.get("rule_id") == "apa_doi_duplicate_prefix"
        for finding in issue.get("format_findings", [])
    )
    if has_doi_error and finding_details:
        metadata_details = [str(detail) for detail in issue.get("metadata_finding_details", []) if detail]
        lines = [f"- {detail}" for detail in finding_details]
        lines.extend(f"- ตรวจ metadata: {detail}" for detail in metadata_details)
        return "แก้ DOI ก่อน แล้วตรวจรายการนี้:\n" + "\n".join(lines)

    metadata_details = [str(detail) for detail in issue.get("metadata_finding_details", []) if detail]
    if metadata_details:
        return "ตรวจสอบกับ DOI ก่อนแก้:\n" + "\n".join(f"- {detail}" for detail in metadata_details)
    if finding_details:
        return "ตรวจหรือแก้เฉพาะจุดนี้:\n" + "\n".join(f"- {detail}" for detail in finding_details)
    details = [str(detail) for detail in issue.get("safe_fix_details", []) if detail]
    if details:
        return "แก้เฉพาะจุดนี้:\n" + "\n".join(f"- {detail}" for detail in details)
    return _proposed_text(issue)


def _intext_proposed_text(issue: dict) -> str:
    details = _actionable_intext_details(issue)
    if details:
        return "ตรวจจุดนี้:\n" + "\n".join(f"- {detail}" for detail in details)
    return "ตรวจ citation นี้กับรายการอ้างอิง"


def _actionable_intext_details(issue: dict) -> list[str]:
    details = [str(detail) for detail in issue.get("format_finding_details", []) if detail]
    issue_codes = {str(problem) for problem in issue.get("issues", [])}
    if "possible_year_mismatch" in issue_codes:
        return [detail for detail in details if "ปี" in detail or "year" in detail.lower()]
    if issue_codes == {"possible_unmatched_citation"}:
        return []
    return details


def polish_rows_with_llm_output(
    rows: list[ResearcherReportRow],
    llm_payload: dict[str, Any],
) -> list[ResearcherReportRow]:
    payload_rows = llm_payload.get("rows", []) if isinstance(llm_payload, dict) else []
    by_label = {row.get("item_label"): row for row in payload_rows if isinstance(row, dict)}

    polished: list[ResearcherReportRow] = []
    for row in rows:
        candidate = by_label.get(row.item_label, {})
        polished.append(
            ResearcherReportRow(
                severity_level=row.severity_level,
                item_label=row.item_label,
                original_text=row.original_text,
                proposed_text=row.proposed_text,
                reason=str(candidate.get("reason") or row.reason),
                next_action=str(candidate.get("next_action") or row.next_action),
                technical_note=row.technical_note,
            )
        )
    return polished


def polish_rows_with_llm(
    client,
    rows: list[ResearcherReportRow],
    model: str,
) -> list[ResearcherReportRow]:
    if not client or not rows:
        return rows

    payload = {
        "rows": [
            {
                "item_label": row.item_label,
                "original_text": row.original_text,
                "proposed_text": row.proposed_text,
                "reason": row.reason,
                "next_action": row.next_action,
            }
            for row in rows
        ]
    }
    system_prompt = (
        "You rewrite APA checker report explanations for Thai researchers. "
        "Do not create, verify, or alter bibliographic facts. "
        "Do not change original_text or proposed_text. "
        "Use plain, direct Thai. Avoid technical terms such as metadata, canonical, unsafe_output, blocked. "
        "If a record is unverified, say only that format can be checked. "
        "Return JSON only with rows containing item_label, reason, next_action."
    )
    user_prompt = (
        "ปรับภาษาในช่อง reason และ next_action ให้สั้น ตรง และอ่านรู้เรื่องสำหรับผู้วิจัย "
        "ห้ามเปลี่ยน original_text และ proposed_text เด็ดขาด\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
    except Exception:
        return rows
    try:
        llm_payload = json.loads(content)
    except json.JSONDecodeError:
        return rows
    return polish_rows_with_llm_output(rows, llm_payload)
