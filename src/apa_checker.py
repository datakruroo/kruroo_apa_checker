"""
apa_checker.py
ส่งข้อความไปยัง OpenAI API พร้อม APA checklist และรับ structured JSON กลับ
"""

import json
from pathlib import Path
from openai import OpenAI


def load_checklist(checklist_path: str) -> str:
    """โหลด APA checklist จาก markdown file"""
    return Path(checklist_path).read_text(encoding="utf-8")


def _call_openai(client: OpenAI, system_prompt: str, user_prompt: str, model: str) -> str:
    """เรียก OpenAI API และคืน content string"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,  # ต่ำ = deterministic สูง เหมาะกับการตรวจสอบกฎ
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def check_references(
    client: OpenAI,
    references_text: str,
    checklist: str,
    model: str = "gpt-4o",
    brave_key: str = "",
) -> dict:
    """
    ตรวจสอบรายการอ้างอิงตาม APA checklist

    Returns:
        dict: {
            "summary": {"total": int, "issues_found": int, "issue_types": list},
            "issues": [{"reference_number": int, "original": str, "issues": list,
                        "corrected": str, "explanation": str}]
        }
    """
    from .pdf_extractor import parse_individual_references
    from .apa_formatter import (
        format_book_chapter,
        format_conference_paper,
        format_journal_article,
        format_working_paper,
    )
    from .apa_format_linter import lint_reference_format
    from .bibliographic_verifier import verify_reference
    from .format_validation import FormatStatus, post_format_validator
    from .metadata_comparator import compare_exact_doi_metadata
    from .parse_quality import classify_parse_warnings
    from .safe_fixes import build_safe_fix

    individual_refs = parse_individual_references(references_text)
    issues = []
    verified_count = 0
    parser_warning_count = 0

    for idx, ref in enumerate(individual_refs, start=1):
        verification = verify_reference(ref, brave_key=brave_key)
        parsed = verification.parsed
        parse_warnings = classify_parse_warnings(ref)
        parser_warning_count += len(parse_warnings)
        format_findings = lint_reference_format(ref, parsed)
        safe_format_findings = [finding for finding in format_findings if finding.safe_to_apply]
        metadata_findings = []

        row_issues: list[str] = []
        severity = "UNVERIFIED"
        status = verification.status
        corrected = ""
        suggestion_label = "ข้อเสนอเบื้องต้น"
        auto_fixable = False
        evidence = list(verification.evidence)
        identity_status = "unverified"
        metadata_status = "incomplete"
        formatting_status = "unsafe_output"
        action = "human_review_required"
        validation_errors: list[str] = []
        safe_fix = build_safe_fix(parsed)

        if parse_warnings:
            severity = "PARSER_WARNING"
            status = "parser_warning"
            row_issues.extend(w.message for w in parse_warnings)
            evidence.extend(w.evidence for w in parse_warnings)
            formatting_status = "parser_warning"
            action = "blocked"

        if verification.status == "verified" and verification.record:
            verified_count += 1
            identity_status = "verified_exact_doi"
            metadata_findings = compare_exact_doi_metadata(parsed, verification.record)
            record_type = (verification.record.record_type or "").lower()
            if record_type == "book-chapter":
                formatted = format_book_chapter(verification.record)
            elif record_type in {"conference-paper", "proceedings-article"}:
                formatted = format_conference_paper(verification.record)
            elif record_type in {"working-paper", "report", "book", "webpage", "dataset"}:
                formatted = format_working_paper(verification.record)
            else:
                formatted = format_journal_article(verification.record)

            validation = post_format_validator(
                verification.record,
                formatted,
                parsed_title=parsed.title,
                identity_status=identity_status,
            )
            metadata_status = validation.metadata_status
            formatting_status = validation.formatting_status.value
            action = "blocked" if parse_warnings else validation.action
            validation_errors = validation.errors

            row_issues.append("ยืนยันตัวตน record ได้ด้วย exact DOI แต่ output ต้องผ่าน post-format validation แยกต่างหาก")
            if validation.formatting_status == FormatStatus.VALID and not parse_warnings:
                corrected = safe_fix.output if safe_fix.has_changes else ""
                suggestion_label = "ข้อเสนอ safe fix" if safe_fix.has_changes else "ไม่มีข้อเสนอแก้อัตโนมัติ"
                severity = "VERIFIED"
                action = "auto_fix_safe" if safe_fix.has_changes else validation.action
                auto_fixable = safe_fix.has_changes
                row_issues.append("metadata-generated canonical reference ถูกปิดไว้; แสดงเฉพาะ safe fixes ที่ตรวจได้เท่านั้น")
                row_issues.extend(f"safe_fix:{change}" for change in safe_fix.changes)
                row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)
                row_issues.extend(f"metadata:{finding.rule_id}" for finding in metadata_findings)
            else:
                corrected = ""
                severity = "PARSER_WARNING" if parse_warnings else "ERROR"
                status = "unsafe_output"
                row_issues.append("formatted output ถูก block เพราะไม่ผ่าน validation จึงไม่แสดงรายการสำหรับคัดลอก")
                row_issues.extend(validation.errors)
                row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)
                row_issues.extend(f"metadata:{finding.rule_id}" for finding in metadata_findings)

            status = "verified"
        elif verification.status == "unable_to_verify_doi":
            identity_status = "unverified"
            severity = "UNVERIFIED" if not parse_warnings else severity
            row_issues.append("ไม่สามารถยืนยัน DOI ได้ จึงไม่ค้นหา/แทนที่ด้วย fuzzy search result อื่น")
            corrected = safe_fix.output if safe_fix.has_changes else ""
            auto_fixable = safe_fix.has_changes
            action = "auto_fix_safe" if safe_fix.has_changes else action
            row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)
        elif verification.status == "doi_conflict":
            identity_status = "conflicting"
            metadata_status = "conflicting"
            severity = "ERROR"
            row_issues.append("DOI conflict: metadata ที่ได้ไม่ตรงกับ DOI เดิม ต้องให้มนุษย์ตรวจ")
            corrected = ""
            action = "human_review_required"
            row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)
        elif verification.status in {"human_review_required", "possible_match", "low_confidence_possible_match"}:
            identity_status = "possible_match"
            severity = "WARNING" if not parse_warnings else severity
            row_issues.append("พบ candidate จาก title search แต่ยังไม่ใช่ exact DOI match จึงไม่แสดงเป็น verified")
            corrected = ""
            action = "human_review_required"
            row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)
        else:
            identity_status = "unverified"
            severity = "UNVERIFIED" if not parse_warnings else severity
            row_issues.append("ยังไม่มีหลักฐาน metadata เพียงพอ ตรวจได้เฉพาะรูปแบบ APA ความเสี่ยงต่ำ")
            corrected = safe_fix.output if safe_fix.has_changes else ""
            auto_fixable = safe_fix.has_changes
            action = "auto_fix_safe" if safe_fix.has_changes else action
            row_issues.extend(f"format:{finding.rule_id}" for finding in format_findings)

        if safe_format_findings:
            auto_fixable = True
            if action == "human_review_required" and not parse_warnings:
                action = "auto_fix_safe"

        original_doi = parsed.doi
        if original_doi and f"https://doi.org/{original_doi}" not in ref.lower() and not verification.record:
            row_issues.append("รูปแบบ DOI ควรเป็น https://doi.org/...")
            auto_fixable = True

        if row_issues:
            record = verification.record
            issues.append(
                {
                    "reference_number": idx,
                    "original": ref,
                    "issues": row_issues,
                    "corrected": corrected,
                    "suggestion_label": suggestion_label,
                    "explanation": "ระบบแยก APA formatting ออกจาก bibliographic verification และไม่แทนที่รายการเดิมด้วย record คนละ DOI",
                    "severity": severity,
                    "status": status,
                    "identity_status": identity_status,
                    "metadata_status": metadata_status,
                    "formatting_status": formatting_status,
                    "action": action,
                    "validation_errors": validation_errors,
                    "evidence": evidence,
                    "metadata_source": record.source if record else verification.source,
                    "source_record_id": record.source_record_id if record else "",
                    "doi": record.doi if record else parsed.doi,
                    "confidence": verification.confidence,
                    "auto_fixable": auto_fixable,
                    "safe_fix_details": safe_fix.details,
                    "format_findings": [
                        {
                            "rule_id": finding.rule_id,
                            "field": finding.field,
                            "message": finding.message,
                            "original_text": finding.original_text,
                            "proposed_text": finding.proposed_text,
                            "detail": finding.detail,
                            "confidence": finding.confidence,
                            "safe_to_apply": finding.safe_to_apply,
                            "human_review_required": finding.human_review_required,
                        }
                        for finding in format_findings
                    ],
                    "format_finding_details": [finding.detail for finding in format_findings],
                    "metadata_findings": [
                        {
                            "rule_id": finding.rule_id,
                            "field": finding.field,
                            "message": finding.message,
                            "original_text": finding.original_text,
                            "metadata_text": finding.metadata_text,
                            "detail": finding.detail,
                            "confidence": finding.confidence,
                        }
                        for finding in metadata_findings
                    ],
                    "metadata_finding_details": [finding.detail for finding in metadata_findings],
                    "human_review_required": action in {"human_review_required", "blocked"},
                    "field_provenance": {
                        name: {
                            "source": provenance.source,
                            "source_record_id": provenance.source_record_id,
                            "fetched_at": provenance.fetched_at,
                        }
                        for name, provenance in (record.field_provenance.items() if record else [])
                    },
                }
            )

    issue_types = sorted({issue for row in issues for issue in row.get("issues", [])})
    return {
        "summary": {
            "total_references": len(individual_refs),
            "issues_found": len(issues),
            "issue_types": issue_types,
            "verified": verified_count,
            "parser_warnings": parser_warning_count,
            "unverified": len(individual_refs) - verified_count,
            "verified_no_change_needed": sum(1 for row in issues if row.get("identity_status") == "verified_exact_doi" and row.get("formatting_status") == "valid" and row.get("action") == "no_change_needed"),
            "verified_with_low_risk_formatting_fix": sum(1 for row in issues if row.get("identity_status") == "verified_exact_doi" and row.get("formatting_status") == "low_risk_fix_available"),
            "bibliographic_conflicts": sum(1 for row in issues if row.get("identity_status") == "conflicting"),
            "possible_matches_requiring_review": sum(1 for row in issues if row.get("identity_status") == "possible_match"),
            "unsafe_generated_outputs": sum(1 for row in issues if row.get("formatting_status") == "unsafe_output"),
            "unverified_references": sum(1 for row in issues if row.get("identity_status") == "unverified"),
        },
        "issues": issues,
    }


def check_intext_citations(
    client: OpenAI,
    citation_excerpts: list[str],
    checklist: str,
    model: str = "gpt-4o",
    references_text: str = "",
    body_text: str = "",
) -> dict:
    """
    ตรวจสอบ in-text citation จาก excerpts ที่ดึงมาจาก body text

    Returns:
        dict: {
            "summary": {"total_checked": int, "issues_found": int},
            "issues": [{"excerpt": str, "issues": list, "corrected": str, "explanation": str}]
        }
    """
    if not citation_excerpts:
        return {"summary": {"total_checked": 0, "issues_found": 0}, "issues": []}
    from .citation_checker import validate_intext_citation_excerpts

    return validate_intext_citation_excerpts(citation_excerpts, references_text=references_text, body_text=body_text)


def run_full_check(
    client: OpenAI,
    sections: dict,
    checklist: str,
    model: str = "gpt-4o",
) -> dict:
    """
    รัน check ทั้งหมด: references + in-text citations

    Args:
        sections: output จาก pdf_extractor.split_document()
        checklist: เนื้อหาของ checklist file
        model: OpenAI model ที่ใช้

    Returns:
        dict รวม results ทั้งหมด
    """
    from .pdf_extractor import extract_intext_citations

    results = {
        "ref_check": None,
        "intext_check": None,
        "ref_found": sections.get("ref_found", False),
    }

    # 1. ตรวจ references section
    if sections.get("references"):
        results["ref_check"] = check_references(
            client, sections["references"], checklist, model
        )

    # 2. ตรวจ in-text citations
    if sections.get("body"):
        excerpts = extract_intext_citations(sections["body"])
        # จำกัด 80 excerpts เพื่อควบคุม cost
        excerpts = excerpts[:80]
        results["intext_check"] = check_intext_citations(
            client, excerpts, checklist, model, references_text=sections.get("references", ""), body_text=sections.get("body", "")
        )

    return results
