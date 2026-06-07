import unittest
from unittest.mock import patch

from src.apa_checker import check_references
from src.bibliographic_verifier import VerifiedRecord
from src.reference_parser import parse_reference
from src.safe_fixes import build_safe_fix


class SafeFixPolicyTests(unittest.TestCase):
    def test_exact_doi_verified_does_not_emit_metadata_canonical_output(self):
        ref = (
            "Siemens, G. (2013). Learning analytics: The emergence of a discipline. "
            "American Behavioral Scientist, 57(10), 1382-1400. "
            "https://doi.org/10.1177/0002764213498851"
        )
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

        with patch("src.bibliographic_verifier.resolve_exact_doi", return_value=record):
            result = check_references(None, ref, "", brave_key="")

        issue = result["issues"][0]
        self.assertEqual(issue["identity_status"], "verified_exact_doi")
        self.assertEqual(issue["formatting_status"], "unsafe_output")
        self.assertEqual(issue["action"], "blocked")
        self.assertEqual(issue["corrected"], "")
        self.assertIn("ไม่แสดงรายการสำหรับคัดลอก", " ".join(issue["issues"]))

    def test_safe_fix_only_changes_page_field_and_doi_wrapper(self):
        raw = (
            "Author, A. (2020). A title. Journal Name, 1(2), 10-20. "
            "doi:10.1007/example-1"
        )

        safe_fix = build_safe_fix(parse_reference(raw))

        self.assertTrue(safe_fix.has_changes)
        self.assertIn("10–20", safe_fix.output)
        self.assertIn("https://doi.org/10.1007/example-1", safe_fix.output)
        self.assertNotIn("10.1007/example–1", safe_fix.output)
        self.assertIn("DOI: doi:10.1007/example-1 → https://doi.org/10.1007/example-1", safe_fix.details)
        self.assertIn("ช่วงหน้า: 10-20 → 10–20", safe_fix.details)

    def test_safe_fix_decodes_html_without_metadata_changes(self):
        raw = (
            "Chen, X., & Xie, H. (2020). Detecting latent topics. "
            "Computers &amp; Education, 151, 103855. https://doi.org/10.1016/j.compedu.2020.103855"
        )

        safe_fix = build_safe_fix(parse_reference(raw))

        self.assertIn("Computers & Education", safe_fix.output)
        self.assertNotIn("&amp;", safe_fix.output)

    def test_safe_fix_does_not_collapse_layout_indentation_spaces(self):
        raw = "Author, A. (2020). A long title         continued after DOCX layout spacing. Journal, 1, 1–9."

        safe_fix = build_safe_fix(parse_reference(raw))

        self.assertNotIn("collapse_whitespace", safe_fix.changes)
        self.assertFalse(any("ช่องว่าง" in detail for detail in safe_fix.details))


if __name__ == "__main__":
    unittest.main()
