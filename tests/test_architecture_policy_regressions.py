import unittest
from unittest.mock import patch

from docx import Document

from src.apa_checker import check_references
from src.apa_formatter import (
    format_conference_paper,
    format_journal_article,
    format_working_paper,
    sentence_case_title,
)
from src.bibliographic_verifier import VerifiedRecord
from src.format_validation import (
    FormatStatus,
    post_format_validator,
    sanitize_text_field,
)
from src.report_generator import generate_report


class ArchitecturePolicyRegressionTests(unittest.TestCase):
    def test_doi_hyphens_are_never_changed_to_en_dash(self):
        ref = (
            "Gurcan, F., Erol, S., & Seferoglu, S. S. (2022). Twenty-five years of education "
            "and information technologies: Insights from a topic modeling-based bibliometric analysis. "
            "Education and Information Technologies, 27, 11025-11054. "
            "https://doi.org/10.1007/s10639-022-11071-y"
        )
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1007/s10639-022-11071-y",
            doi="10.1007/s10639-022-11071-y",
            authors=["Gurcan, F.", "Erol, S.", "Seferoglu, S. S."],
            year=2022,
            title="Twenty-five years of education and information technologies: Insights from a topic modeling-based bibliometric analysis",
            container_title="Education and Information Technologies",
            volume="27",
            issue="8",
            pages="11025-11054",
            record_type="journal-article",
        )

        with patch("src.bibliographic_verifier.resolve_exact_doi", return_value=record):
            result = check_references(None, ref, "", brave_key="")

        corrected = result["issues"][0]["corrected"]
        self.assertIn("11025–11054", corrected)
        self.assertIn("https://doi.org/10.1007/s10639-022-11071-y", corrected)
        self.assertNotIn("10.1007/s10639–022–11071–y", corrected)

    def test_url_characters_are_immutable(self):
        record = VerifiedRecord(
            source="manual",
            source_record_id="url-test",
            authors=["UNESCO"],
            year=2021,
            title="Reimagining our futures together: A new social contract for education",
            publisher="UNESCO",
            record_type="report",
            url="https://unesdoc.unesco.org/ark:/48223/pf0000379707?download=true&lang=en-us",
        )

        formatted = format_working_paper(record)

        self.assertIn("lang=en-us", formatted)
        self.assertNotIn("lang=en–us", formatted)

    def test_page_range_hyphen_is_changed_only_inside_pages_field(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1007/example-1",
            doi="10.1007/example-1",
            authors=["Author, A."],
            year=2020,
            title="A simple title",
            container_title="Journal Name",
            volume="1",
            pages="10-20",
            record_type="journal-article",
        )

        formatted = format_journal_article(record)

        self.assertIn("10–20", formatted)
        self.assertIn("10.1007/example-1", formatted)

    def test_siemens_subtitle_is_not_truncated(self):
        parsed_title = "Learning analytics: The emergence of a discipline"
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1177/0002764213498851",
            doi="10.1177/0002764213498851",
            authors=["Siemens, G."],
            year=2013,
            title="Learning Analytics",
            container_title="American Behavioral Scientist",
            volume="57",
            issue="10",
            pages="1382-1400",
            record_type="journal-article",
        )
        formatted = format_journal_article(record)

        validation = post_format_validator(record, formatted, parsed_title=parsed_title)

        self.assertEqual(validation.formatting_status, FormatStatus.UNSAFE_OUTPUT)
        self.assertIn("title_truncated", validation.errors)

    def test_lis_acronym_does_not_corrupt_holistic(self):
        formatted = sentence_case_title("Computational psychometrics approach to Holistic Learning and Assessment Systems")

        self.assertIn("holistic", formatted)
        self.assertNotIn("hoLIStic", formatted)

    def test_dirichlet_remains_capitalized(self):
        formatted = sentence_case_title("An analysis based on latent Dirichlet allocation topic model")

        self.assertIn("Dirichlet allocation", formatted)

    def test_html_entities_are_decoded_before_render(self):
        self.assertEqual(sanitize_text_field("Computers &amp; Education"), "Computers & Education")

    def test_question_mark_is_not_followed_by_period(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1609/aaai.v39i27.35083",
            doi="10.1609/aaai.v39i27.35083",
            authors=["Natarajan, S."],
            year=2025,
            title="Human-in-the-loop or AI-in-the-loop? Automate or collaborate?",
            container_title="Proceedings of the AAAI Conference on Artificial Intelligence",
            volume="39",
            issue="27",
            pages="28594-28600",
            record_type="conference-paper",
        )

        formatted = format_conference_paper(record)

        self.assertNotIn("?.", formatted)

    def test_working_paper_without_author_is_blocked(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1787/5d9009ff-en",
            doi="10.1787/5d9009ff-en",
            authors=[],
            year=2023,
            title="The uses of process data in large-scale educational assessments",
            publisher="OECD",
            record_type="working-paper",
        )

        formatted = format_working_paper(record)
        validation = post_format_validator(record, formatted)

        self.assertEqual(validation.formatting_status, FormatStatus.UNSAFE_OUTPUT)
        self.assertIn("missing_required_authors", validation.errors)

    def test_conference_paper_does_not_drop_editors_or_publisher_without_warning(self):
        record = VerifiedRecord(
            source="manual",
            source_record_id="W14-3110",
            doi="10.3115/v1/W14-3110",
            authors=["Sievert, C.", "Shirley, K. E."],
            year=2014,
            title="LDAvis: A method for visualizing and interpreting topics",
            container_title="Proceedings of the workshop on interactive language learning, visualization, and interfaces",
            editors=["J. Chuang", "S. Green", "M. Hearst", "J. Heer", "P. Koehn"],
            pages="63-70",
            publisher="Association for Computational Linguistics",
            record_type="conference-paper",
        )

        formatted = format_conference_paper(record)

        self.assertIn("J. Chuang", formatted)
        self.assertIn("Association for Computational Linguistics", formatted)

    def test_exact_doi_match_does_not_imply_formatted_output_is_valid(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1177/0002764213498851",
            doi="10.1177/0002764213498851",
            authors=["Siemens, G."],
            year=2013,
            title="Learning Analytics",
            container_title="American Behavioral Scientist",
            record_type="journal-article",
        )

        validation = post_format_validator(
            record,
            "Siemens, G. (2013). Learning analytics. American Behavioral Scientist. https://doi.org/10.1177/0002764213498851",
            identity_status="verified_exact_doi",
            parsed_title="Learning analytics: The emergence of a discipline",
        )

        self.assertEqual(validation.identity_status, "verified_exact_doi")
        self.assertEqual(validation.formatting_status, FormatStatus.UNSAFE_OUTPUT)

    def test_unsafe_output_is_never_labeled_ready_to_use(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1/example",
            doi="10.1/example",
            authors=[],
            year=2024,
            title="A title",
            record_type="journal-article",
        )

        validation = post_format_validator(record, "A title.")

        self.assertEqual(validation.action, "blocked")
        self.assertFalse(validation.ready_to_use)

    def test_low_confidence_candidate_is_debug_only(self):
        from src.bibliographic_verifier import candidate_display_status

        self.assertEqual(candidate_display_status(0.32), "debug_log_only")

    def test_possible_match_is_not_called_verified_candidate(self):
        from src.bibliographic_verifier import candidate_display_status

        self.assertEqual(candidate_display_status(0.91), "possible_match")
        self.assertNotEqual(candidate_display_status(0.91), "verified_candidate")

    def test_report_summary_separates_categories(self):
        with self.subTest("docx report summary labels"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "report.docx"
                generate_report(
                    results={
                        "ref_found": True,
                        "ref_check": {
                            "summary": {
                                "total_references": 2,
                                "verified_no_change_needed": 1,
                                "verified_with_low_risk_formatting_fix": 0,
                                "bibliographic_conflicts": 0,
                                "possible_matches_requiring_review": 0,
                                "parser_warnings": 1,
                                "unsafe_generated_outputs": 1,
                                "unverified_references": 0,
                                "issues_found": 2,
                                "issue_types": [],
                            },
                            "issues": [],
                        },
                        "intext_check": {"summary": {"total_checked": 0, "issues_found": 0}, "issues": []},
                    },
                    article_filename="fixture.docx",
                    output_path=str(output),
                    include_technical_section=True,
                )
                text = "\n".join(p.text for p in Document(output).paragraphs)

        self.assertIn("ตรวจยืนยันได้และยังไม่ต้องแก้", text)
        self.assertIn("ระบบไม่แสดงรายการที่สร้างใหม่ เพราะเสี่ยงผิด", text)


if __name__ == "__main__":
    unittest.main()
