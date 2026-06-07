import unittest
from unittest.mock import patch

from src.apa_checker import check_intext_citations
from src.apa_formatter import (
    format_book_chapter,
    format_journal_article,
    sentence_case_title,
)
from src.bibliographic_verifier import (
    VerifiedRecord,
    choose_verification_action,
    verify_reference,
)
from src.parse_quality import classify_parse_warnings
from src.reference_parser import parse_reference


class ApaRegressionTests(unittest.TestCase):
    def test_article_title_uses_sentence_case_not_metadata_title_case(self):
        metadata_title = (
            "The Expanded Evidence-Centered Design (e-ECD) for Learning and "
            "Assessment Systems: A Framework for Incorporating Learning Goals "
            "and Processes Within Assessment Design"
        )

        formatted = sentence_case_title(metadata_title)

        self.assertIn("The expanded Evidence-Centered Design", formatted)
        self.assertIn("e-ECD", formatted)
        self.assertIn("learning goals and processes within assessment design", formatted)
        self.assertNotIn("Assessment Systems: A Framework", formatted)

    def test_exact_doi_resolution_has_priority_over_fuzzy_search(self):
        siemens = (
            "Siemens, G. (2013). Learning analytics: The emergence of a discipline. "
            "American Behavioral Scientist, 57(10), 1382-1400. "
            "https://doi.org/10.1177/0002764213498851"
        )
        resolved = VerifiedRecord(
            source="crossref",
            source_record_id="10.1177/0002764213498851",
            doi="10.1177/0002764213498851",
            authors=["Siemens, G."],
            year=2013,
            title="Learning analytics: The emergence of a discipline",
            container_title="American Behavioral Scientist",
            volume="57",
            issue="10",
            pages="1382-1400",
            record_type="journal-article",
        )

        with patch("src.bibliographic_verifier.resolve_exact_doi", return_value=resolved) as doi_lookup, patch(
            "src.bibliographic_verifier.search_title_candidates"
        ) as fuzzy:
            verification = verify_reference(siemens)

        doi_lookup.assert_called_once_with("10.1177/0002764213498851")
        fuzzy.assert_not_called()
        self.assertEqual(verification.record.doi, "10.1177/0002764213498851")
        self.assertEqual(verification.status, "verified")

    def test_never_replace_reference_with_different_doi(self):
        parsed = parse_reference(
            "Siemens, G. (2013). Learning analytics: The emergence of a discipline. "
            "American Behavioral Scientist, 57(10), 1382-1400. "
            "https://doi.org/10.1177/0002764213498851"
        )
        candidate = VerifiedRecord(
            source="openalex",
            source_record_id="W999",
            doi="10.1007/s11528-014-0822-x",
            authors=["Gašević, D.", "Dawson, S.", "Siemens, G."],
            year=2014,
            title="Let’s not forget: Learning analytics are about learning",
            container_title="TechTrends",
            volume="59",
            issue="1",
            pages="64-71",
            record_type="journal-article",
        )

        action = choose_verification_action(parsed, candidate, candidate_confidence=0.99)

        self.assertFalse(action.auto_correct)
        self.assertEqual(action.status, "human_review_required")
        self.assertIn("doi_conflict", action.reasons)

    def test_metadata_fields_come_from_same_verified_record(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1007/978-1-4614-3305-7_4",
            doi="10.1007/978-1-4614-3305-7_4",
            authors=["Baker, R.", "Inventado, P."],
            year=2014,
            title="Educational data mining and learning analytics",
            container_title="Learning analytics",
            editors=["Larusson, J.", "White, B."],
            pages="61-75",
            record_type="book-chapter",
        )

        for field_name, provenance in record.field_provenance.items():
            self.assertEqual(provenance.source, record.source, field_name)
            self.assertEqual(provenance.source_record_id, record.source_record_id, field_name)

    def test_book_chapter_formatter(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="chapter-1",
            doi="10.1000/example",
            authors=["Baker, R. S.", "Siemens, G."],
            year=2014,
            title="Educational data mining and learning analytics",
            container_title="Cambridge Handbook of the Learning Sciences",
            editors=["R. K. Sawyer"],
            pages="253-272",
            publisher="Cambridge University Press",
            record_type="book-chapter",
        )

        formatted = format_book_chapter(record)

        self.assertIn("Educational data mining and learning analytics.", formatted)
        self.assertIn("In R. K. Sawyer (Ed.),", formatted)
        self.assertIn("(pp. 253–272)", formatted)
        self.assertIn("https://doi.org/10.1000/example", formatted)

    def test_journal_article_with_elocator(self):
        record = VerifiedRecord(
            source="crossref",
            source_record_id="10.1016/j.compedu.2020.103855",
            doi="10.1016/j.compedu.2020.103855",
            authors=["Chen, X.", "Zou, D.", "Cheng, G.", "Xie, H."],
            year=2020,
            title="Detecting latent topics and trends in educational technologies over four decades using structural topic modeling",
            container_title="Computers & Education",
            volume="151",
            issue="",
            pages="103855",
            record_type="journal-article",
        )

        formatted = format_journal_article(record)

        self.assertIn("Computers & Education, 151, 103855.", formatted)
        self.assertNotIn("(,", formatted)

    def test_multiple_in_text_citations_with_different_author_counts_are_valid(self):
        result = check_intext_citations(
            client=None,
            citation_excerpts=["(Baker & Siemens, 2014; Siemens, 2013)"],
            checklist="",
        )

        self.assertEqual(result["summary"]["issues_found"], 0)
        self.assertEqual(result["issues"], [])

    def test_parser_warning_is_not_reported_as_apa_error(self):
        warnings = classify_parse_warnings(
            "Vehtari, A., Gelman, A., Simpson, D., Carpenter, B., & Bürkner, P.-C. "
            "(2021). Rank-normalization, folding, and localization: An improved  "
            "for assessing convergence of MCMC. Bayesian Analysis, 16(2), 667–718."
        )

        self.assertTrue(warnings)
        self.assertEqual(warnings[0].severity, "PARSER_WARNING")
        self.assertNotEqual(warnings[0].severity, "ERROR")

    def test_reference_raw_text_is_preserved(self):
        raw = (
            "Baker, R. S., & Siemens, G. (2014). Educational data mining and "
            "learning analytics. Cambridge Handbook of the Learning Sciences, 2, 253–272."
        )

        parsed = parse_reference(raw)

        self.assertEqual(parsed.raw_text, raw)
        self.assertEqual(parsed.fields["title"].value, "Educational data mining and learning analytics")

    def test_low_confidence_candidate_requires_human_review(self):
        parsed = parse_reference(
            "Baker, R. S., & Siemens, G. (2014). Educational data mining and learning analytics. "
            "Cambridge Handbook of the Learning Sciences, 2, 253–272."
        )
        candidate = VerifiedRecord(
            source="openalex",
            source_record_id="W123",
            doi="",
            authors=["Baker, R.", "Inventado, P."],
            year=2014,
            title="Educational data mining and learning analytics",
            container_title="Learning analytics",
            record_type="book-chapter",
        )

        action = choose_verification_action(parsed, candidate, candidate_confidence=0.62)

        self.assertFalse(action.auto_correct)
        self.assertEqual(action.status, "human_review_required")
        self.assertIn("low_confidence_candidate", action.reasons)


if __name__ == "__main__":
    unittest.main()
