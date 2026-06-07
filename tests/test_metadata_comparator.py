import unittest
from unittest.mock import patch

from src.apa_checker import check_references
from src.bibliographic_verifier import VerifiedRecord
from src.metadata_comparator import compare_exact_doi_metadata
from src.reference_parser import parse_reference
from src.researcher_report_writer import rows_from_results


class MetadataComparatorTests(unittest.TestCase):
    def test_exact_doi_author_mismatch_is_warning_not_autofix(self):
        raw = (
            "Treffinger, D. J., Edwin, C. S., & Scott, G. I. (2008). "
            "Understanding individual problem-solving style: A key to learning and applying creative problem solving. "
            "Learning and Individual Differences, 18(4), 390–401. https://doi.org/10.1016/j.lindif.2007.11.007"
        )
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1016/j.lindif.2007.11.007",
            doi="10.1016/j.lindif.2007.11.007",
            authors=["Treffinger, D. J.", "Selby, E. C.", "Isaksen, S. G."],
            year=2008,
            title="Understanding individual problem-solving style: A key to learning and applying creative problem solving",
            container_title="Learning and Individual Differences",
            volume="18",
            issue="4",
            pages="390-401",
            record_type="journal-article",
        )

        findings = compare_exact_doi_metadata(parse_reference(raw), record)

        self.assertIn("external_metadata_author_mismatch", {finding.rule_id for finding in findings})

    def test_exact_doi_title_typo_flows_to_researcher_row(self):
        raw = (
            "Metwaly, S., Fernández-Castilla, B., Kyndt, E., & Van den Noortgate, W. (2020). "
            "Testing conditions and creative cerformance: Meta-analyses of the impact of time limits and instructions. "
            "Psychology of Aesthetics, Creativity, and the Arts, 14(1), 15–38. https://doi.org/10.1037/aca0000244"
        )
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1037/aca0000244",
            doi="10.1037/aca0000244",
            authors=["Metwaly, S.", "Fernández-Castilla, B.", "Kyndt, E.", "Van den Noortgate, W."],
            year=2020,
            title="Testing conditions and creative performance: Meta-analyses of the impact of time limits and instructions",
            container_title="Psychology of Aesthetics, Creativity, and the Arts",
            volume="14",
            issue="1",
            pages="15-38",
            record_type="journal-article",
        )

        with patch("src.bibliographic_verifier.resolve_exact_doi", return_value=record):
            result = check_references(None, raw, "", brave_key="")

        rows = rows_from_results({"ref_check": result})

        self.assertTrue(rows)
        metadata_row = next(row for row in rows if row.severity_level == "WARNING")
        self.assertIn("creative cerformance", metadata_row.proposed_text)
        self.assertIn("creative performance", metadata_row.proposed_text)
        self.assertIn("DOI", metadata_row.next_action)

    def test_title_comparison_ignores_case_and_hyphen_variants(self):
        raw = (
            "Willemsen, R. H. (2024). Strengthening creative problem-solving within upper-elementary science education. "
            "The Journal of Creative Behavior, 58(1), 137–150. https://doi.org/10.1002/jocb.639"
        )
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1002/jocb.639",
            doi="10.1002/jocb.639",
            authors=["Willemsen, R. H."],
            year=2024,
            title="Strengthening Creative Problem‐Solving within Upper‐Elementary Science Education",
            container_title="The Journal of Creative Behavior",
            volume="58",
            issue="1",
            pages="137-150",
            record_type="journal-article",
        )

        findings = compare_exact_doi_metadata(parse_reference(raw), record)

        self.assertNotIn("external_metadata_title_possible_typo", {finding.rule_id for finding in findings})
        self.assertNotIn("external_metadata_title_mismatch", {finding.rule_id for finding in findings})

    def test_duplicate_doi_prefix_stays_error_when_metadata_mismatch_exists(self):
        raw = (
            "Treffinger, D. J., Edwin, C. S., & Scott, G. I. (2008). "
            "Understanding individual problem-solving style: A key to learning and applying creative problem solving. "
            "Learning and Individual Differences, 18(4), 390-401. "
            "https://doi.org/https://doi.org/10.1016/j.lindif.2007.11.007"
        )
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1016/j.lindif.2007.11.007",
            doi="10.1016/j.lindif.2007.11.007",
            authors=["Treffinger, D. J.", "Selby, E. C.", "Isaksen, S. G."],
            year=2008,
            title="Understanding individual problem-solving style: A key to learning and applying creative problem solving",
            container_title="Learning and Individual Differences",
            volume="18",
            issue="4",
            pages="390-401",
            record_type="journal-article",
        )

        with patch("src.bibliographic_verifier.resolve_exact_doi", return_value=record):
            result = check_references(None, raw, "", brave_key="")

        rows = rows_from_results({"ref_check": result})

        self.assertTrue(rows)
        self.assertEqual(rows[0].severity_level, "ERROR")
        self.assertIn("แก้ DOI", rows[0].next_action)


if __name__ == "__main__":
    unittest.main()
