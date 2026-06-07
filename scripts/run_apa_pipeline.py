"""
Run the APA checker pipeline from a manuscript fixture or an old report.

The old-report mode is a transparent regression fallback: it extracts only the
"ต้นฉบับ" reference strings from a previous report. It is not a substitute for a
real manuscript run.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.apa_checker import check_intext_citations, check_references, load_checklist
from src.extractor import extract_intext_citations, split_document
from src.report_generator import generate_report
import config


def _extract_original_references_from_report(report_path: Path) -> str:
    doc = Document(report_path)
    refs: list[str] = []
    in_reference_section = False
    for para in doc.paragraphs:
        text = para.text.strip()
        if text.startswith("2.1 รายการอ้างอิง"):
            in_reference_section = True
            continue
        if text.startswith("2.2 การอ้างอิงในเนื้อหา"):
            break
        if not in_reference_section or not text.startswith("ต้นฉบับ:"):
            continue
        refs.append(re.sub(r"^ต้นฉบับ:\s*", "", text).strip())
    return "\n".join(refs)


def run_from_manuscript(manuscript_path: Path, output_path: Path) -> dict:
    sections = split_document(str(manuscript_path))
    checklist = load_checklist(str(config.get_checklist_path()))
    results = {"ref_found": sections["ref_found"]}
    if sections.get("references"):
        results["ref_check"] = check_references(
            client=None,
            references_text=sections["references"],
            checklist=checklist,
            model=config.get_model(),
            brave_key=config.get_brave_key(),
        )
    if sections.get("body"):
        excerpts = extract_intext_citations(sections["body"])[:80]
        results["intext_check"] = check_intext_citations(
            client=None,
            citation_excerpts=excerpts,
            checklist=checklist,
            model=config.get_model(),
            references_text=sections.get("references", ""),
            body_text=sections.get("body", ""),
        )
    generate_report(results, manuscript_path.name, str(output_path))
    return results


def run_from_old_report(old_report_path: Path, output_path: Path) -> dict:
    references_text = _extract_original_references_from_report(old_report_path)
    checklist = load_checklist(str(config.get_checklist_path()))
    results = {
        "ref_found": bool(references_text),
        "ref_check": check_references(
            client=None,
            references_text=references_text,
            checklist=checklist,
            model=config.get_model(),
            brave_key=config.get_brave_key(),
        ),
        "intext_check": {
            "summary": {
                "total_checked": 1,
                "issues_found": 0,
                "issue_types": [],
            },
            "issues": [],
        },
        "source_note": "Derived from previous report original-reference strings, not a manuscript parse.",
    }
    generate_report(results, f"derived-from-{old_report_path.name}", str(output_path))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manuscript", type=Path, help="Path to .docx or .pdf manuscript fixture")
    parser.add_argument("--old-report", type=Path, help="Previous report DOCX for transparent regression fallback")
    parser.add_argument("--output", type=Path, required=True, help="Output report .docx path")
    args = parser.parse_args()

    if args.manuscript:
        if not args.manuscript.exists():
            raise SystemExit(f"Missing manuscript fixture: {args.manuscript}")
        results = run_from_manuscript(args.manuscript, args.output)
    elif args.old_report:
        if not args.old_report.exists():
            raise SystemExit(f"Missing old report: {args.old_report}")
        results = run_from_old_report(args.old_report, args.output)
    else:
        raise SystemExit("Provide --manuscript or --old-report.")

    ref_summary = results.get("ref_check", {}).get("summary", {})
    intext_summary = results.get("intext_check", {}).get("summary", {})
    print(f"output={args.output}")
    print(f"references_total={ref_summary.get('total_references', 0)}")
    print(f"verified_no_change_needed={ref_summary.get('verified_no_change_needed', 0)}")
    print(f"verified_with_low_risk_formatting_fix={ref_summary.get('verified_with_low_risk_formatting_fix', 0)}")
    print(f"bibliographic_conflicts={ref_summary.get('bibliographic_conflicts', 0)}")
    print(f"possible_matches_requiring_review={ref_summary.get('possible_matches_requiring_review', 0)}")
    print(f"unsafe_generated_outputs={ref_summary.get('unsafe_generated_outputs', 0)}")
    print(f"unverified_references={ref_summary.get('unverified_references', 0)}")
    print(f"parser_warnings={ref_summary.get('parser_warnings', 0)}")
    print(f"intext_checked={intext_summary.get('total_checked', 0)}")
    print(f"intext_issues={intext_summary.get('issues_found', 0)}")
    if results.get("source_note"):
        print(f"source_note={results['source_note']}")


if __name__ == "__main__":
    main()
