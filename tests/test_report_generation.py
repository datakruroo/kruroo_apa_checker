import tempfile
import unittest
from pathlib import Path

from docx import Document

from src.report_generator import generate_report


class ReportGenerationTests(unittest.TestCase):
    def test_report_uses_proposal_label_and_shows_confidence_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.docx"
            generate_report(
                results={
                    "ref_found": True,
                    "ref_check": {
                        "summary": {
                            "total_references": 1,
                            "issues_found": 1,
                            "issue_types": ["parser_warning"],
                        },
                        "issues": [
                            {
                                "reference_number": 1,
                                "original": "Example, A. (2020). Broken  title.",
                                "issues": ["The parsed text appears to be missing an inline token or formula."],
                                "corrected": "Example, A. (2020). Broken  title.",
                                "suggestion_label": "ข้อเสนอเบื้องต้น",
                                "explanation": "Parser warning, not APA error.",
                                "severity": "PARSER_WARNING",
                                "status": "parser_warning",
                                "evidence": ["Broken  title"],
                                "metadata_source": "crossref",
                                "source_record_id": "10.1000/example",
                                "doi": "10.1000/example",
                                "confidence": 0.91,
                                "auto_fixable": False,
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

        self.assertIn("ข้อเสนอเบื้องต้น", text)
        self.assertIn("ความมั่นใจของการจับคู่: 91%", text)
        self.assertIn("แหล่งข้อมูล: Crossref", text)
        self.assertNotIn("ที่ถูกต้อง:", text)


if __name__ == "__main__":
    unittest.main()
