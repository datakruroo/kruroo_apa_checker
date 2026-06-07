import tempfile
import unittest
from pathlib import Path

from docx import Document

from src.report_generator import generate_report


class HumanReadableReportTests(unittest.TestCase):
    def test_report_translates_internal_status_codes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.docx"
            generate_report(
                results={
                    "ref_found": True,
                    "ref_check": {
                        "summary": {
                            "total_references": 1,
                            "verified_no_change_needed": 0,
                            "verified_with_low_risk_formatting_fix": 0,
                            "bibliographic_conflicts": 0,
                            "possible_matches_requiring_review": 0,
                            "parser_warnings": 0,
                            "unsafe_generated_outputs": 1,
                            "unverified_references": 0,
                            "issues_found": 1,
                            "issue_types": ["title_truncated", "formatted output ถูก block เพราะไม่ผ่าน validation จึงไม่แสดงรายการสำหรับคัดลอก"],
                        },
                        "issues": [
                            {
                                "reference_number": 14,
                                "original": "Siemens, G. (2013). Learning analytics: The emergence of a discipline.",
                                "issues": [
                                    "formatted output ถูก block เพราะไม่ผ่าน validation จึงไม่แสดงรายการสำหรับคัดลอก",
                                    "title_truncated",
                                ],
                                "corrected": "",
                                "severity": "ERROR",
                                "status": "verified",
                                "identity_status": "verified_exact_doi",
                                "metadata_status": "complete",
                                "formatting_status": "unsafe_output",
                                "action": "blocked",
                                "metadata_source": "crossref",
                                "source_record_id": "10.1177/0002764213498851",
                                "doi": "10.1177/0002764213498851",
                                "confidence": 1.0,
                                "auto_fixable": False,
                                "evidence": ["Exact DOI match from crossref: 10.1177/0002764213498851."],
                                "explanation": "internal explanation",
                            }
                        ],
                    },
                    "intext_check": {"summary": {"total_checked": 0, "issues_found": 0}, "issues": []},
                },
                article_filename="fixture.docx",
                output_path=str(output),
                include_technical_section=True,
            )
            text = "\n".join(p.text for p in Document(output).paragraphs)

        self.assertIn("ยืนยัน DOI แล้ว", text)
        self.assertIn("ห้ามใช้รายการที่ระบบสร้างอัตโนมัติ", text)
        self.assertIn("ชื่อเรื่องที่ค้นได้ไม่ครบ", text)
        self.assertIn("ยังไม่แสดงรายการสำหรับคัดลอก", text)
        self.assertNotIn("unsafe_output", text)
        self.assertNotIn("verified_exact_doi", text)
        self.assertNotIn("title_truncated", text)
        self.assertNotIn("confidence=", text)


if __name__ == "__main__":
    unittest.main()
