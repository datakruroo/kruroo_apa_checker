import unittest
from unittest.mock import patch

from src.apa_checker import check_references
from src.apa_format_linter import lint_reference_format
from src.researcher_report_writer import rows_from_results


class ApaFormatLinterTests(unittest.TestCase):
    def test_year_must_be_followed_by_period(self):
        findings = lint_reference_format(
            "Brown, T. (2008) Design thinking. Harvard Business Review, 86(6), 84–92."
        )

        self.assertIn("apa_year_period", {finding.rule_id for finding in findings})
        finding = next(f for f in findings if f.rule_id == "apa_year_period")
        self.assertEqual(finding.field, "year")
        self.assertIn("(2008).", finding.proposed_text)
        self.assertTrue(finding.safe_to_apply)

    def test_author_block_must_end_with_period_before_year(self):
        findings = lint_reference_format(
            "ณัฐวุฒิ อรุณรัตน์ และ ปราวีณยา สุวรรณณัฐโชติ (2562). "
            "การออกแบบการเรียนรู้. วารสารครุศาสตร์, 47(1), 1–10."
        )

        finding = next(f for f in findings if f.rule_id == "apa_author_period_before_year")
        self.assertIn("สุวรรณณัฐโชติ. (2562)", finding.proposed_text)
        self.assertTrue(finding.safe_to_apply)

    def test_author_block_period_rule_does_not_flag_initials(self):
        findings = lint_reference_format(
            "Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84–92."
        )

        self.assertNotIn("apa_author_period_before_year", {finding.rule_id for finding in findings})

    def test_doi_and_url_terminal_period_is_removed(self):
        findings = lint_reference_format(
            "Author, A. (2020). A title. Journal, 1(1), 1–9. https://doi.org/10.1000/test."
        )

        finding = next(f for f in findings if f.rule_id == "apa_locator_terminal_period")
        self.assertEqual(finding.field, "doi")
        self.assertIn("10.1000/test", finding.proposed_text)
        self.assertTrue(finding.safe_to_apply)

    def test_duplicate_doi_prefix_is_error(self):
        findings = lint_reference_format(
            "Treffinger, D. J., Edwin, C. S., & Scott, G. I. (2008). A title. "
            "Journal, 18(4), 390–401. https://doi.org/https://doi.org/10.1016/j.lindif.2007.11.007"
        )

        finding = next(f for f in findings if f.rule_id == "apa_doi_duplicate_prefix")
        self.assertEqual(finding.field, "doi")
        self.assertIn("https://doi.org/10.1016/j.lindif.2007.11.007", finding.proposed_text)
        self.assertTrue(finding.safe_to_apply)

    def test_duplicate_doi_prefix_flows_to_researcher_row_as_error(self):
        ref = (
            "Treffinger, D. J., Edwin, C. S., & Scott, G. I. (2008). A title. "
            "Journal, 18(4), 390–401. https://doi.org/https://doi.org/10.1016/j.lindif.2007.11.007"
        )

        with patch("src.bibliographic_verifier.search_title_candidates", return_value=[]):
            result = check_references(None, ref, "", brave_key="")

        rows = rows_from_results({"ref_check": result})

        self.assertEqual(rows[0].severity_level, "ERROR")
        self.assertIn("DOI:", rows[0].proposed_text)

    def test_duplicate_question_mark_period_is_removed(self):
        findings = lint_reference_format(
            "Author, A. (2020). Automate or collaborate?. Journal, 1(1), 1–9."
        )

        finding = next(f for f in findings if f.rule_id == "apa_duplicate_terminal_punctuation")
        self.assertEqual(finding.original_text, "?.")
        self.assertEqual(finding.proposed_text, "?")
        self.assertIn("จุดเกิน", finding.message)
        self.assertTrue(finding.safe_to_apply)

    def test_journal_source_italic_warning_uses_docx_markdown(self):
        findings = lint_reference_format(
            "Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84–92."
        )

        finding = next(f for f in findings if f.rule_id == "apa_source_italic_missing")
        self.assertEqual(finding.field, "source")
        self.assertFalse(finding.safe_to_apply)
        self.assertTrue(finding.human_review_required)

    def test_italicized_journal_source_does_not_warn(self):
        findings = lint_reference_format(
            "Brown, T. (2008). Design thinking. *Harvard Business Review, 86*(6), 84–92."
        )

        self.assertNotIn("apa_source_italic_missing", {finding.rule_id for finding in findings})
        self.assertNotIn("apa_volume_italic_missing", {finding.rule_id for finding in findings})
        self.assertNotIn("apa_issue_should_not_be_italic", {finding.rule_id for finding in findings})

    def test_journal_volume_should_be_italic_but_issue_should_not(self):
        findings = lint_reference_format(
            "Brown, T. (2008). Design thinking. *Harvard Business Review,* 86*(6)*, 84-92."
        )

        rule_ids = {finding.rule_id for finding in findings}
        self.assertIn("apa_volume_italic_missing", rule_ids)
        self.assertIn("apa_issue_should_not_be_italic", rule_ids)

    def test_journal_volume_warning_survives_split_italic_runs(self):
        findings = lint_reference_format(
            "DeHaan, R. L. (2009). Teaching creativity. "
            "*CBE—Life Sciences Education*,* *8(3), 172-181. https://doi.org/10.1187/cbe.08-12-0081"
        )

        self.assertIn("apa_volume_italic_missing", {finding.rule_id for finding in findings})

    def test_title_case_article_title_requires_review_not_autofix(self):
        findings = lint_reference_format(
            "Author, A. (2020). The Effects Of Assessment Instruction On Creative Problem Solving. "
            "*Journal Name, 1*(1), 1–9."
        )

        finding = next(f for f in findings if f.rule_id == "apa_title_sentence_case_review")
        self.assertEqual(finding.field, "title")
        self.assertIn("The effects of assessment instruction", finding.proposed_text)
        self.assertFalse(finding.safe_to_apply)
        self.assertTrue(finding.human_review_required)

    def test_page_range_hyphen_is_format_finding(self):
        findings = lint_reference_format(
            "Brown, T. (2008). Design thinking. *Harvard Business Review, 86*(6), 84-92."
        )

        finding = next(f for f in findings if f.rule_id == "apa_page_range_en_dash")
        self.assertEqual(finding.original_text, "84-92")
        self.assertEqual(finding.proposed_text, "84–92")
        self.assertTrue(finding.safe_to_apply)

    def test_layout_indentation_spaces_are_not_user_facing_whitespace_fix(self):
        findings = lint_reference_format(
            "Author, A. (2020). A long title         continued after a DOCX line wrap. Journal, 1, 1–9."
        )

        self.assertNotIn("apa_collapse_whitespace", {finding.rule_id for finding in findings})

    def test_format_findings_flow_to_researcher_rows_without_metadata(self):
        ref = (
            "Author, A. (2020) The Effects Of Assessment Instruction On Creative Problem Solving. "
            "Journal Name, 1(1), 1-9."
        )

        with patch("src.bibliographic_verifier.search_title_candidates", return_value=[]):
            result = check_references(None, ref, "", brave_key="")

        issue = result["issues"][0]
        rule_ids = {finding["rule_id"] for finding in issue["format_findings"]}
        self.assertIn("apa_year_period", rule_ids)
        self.assertIn("apa_page_range_en_dash", rule_ids)
        self.assertIn("apa_source_italic_missing", rule_ids)

        rows = rows_from_results({"ref_check": result})

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].severity_level, "STYLE_FIX")
        self.assertIn("แก้ได้เลย: ช่วงหน้า: 1-9 → 1–9", rows[0].proposed_text)
        self.assertIn("ปรับรูปแบบใน Word", rows[0].proposed_text)
        self.assertNotIn("[AUTO_FIX]", rows[0].proposed_text)
        self.assertNotIn("[STYLE_FIX]", rows[0].proposed_text)
        self.assertIn("ตัวเอียง", rows[0].next_action)


if __name__ == "__main__":
    unittest.main()
