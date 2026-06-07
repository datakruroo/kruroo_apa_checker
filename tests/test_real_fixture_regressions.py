import unittest

from tests.fixture_loader import fixture_path


class RealFixtureRegressionTests(unittest.TestCase):
    def test_real_manuscript_fixture_location_is_reserved(self):
        self.assertEqual(
            fixture_path("JESCU284604_prefinal.docx").as_posix().split("/")[-3:],
            ["tests", "fixtures", "JESCU284604_prefinal.docx"],
        )

    @unittest.skipUnless(
        fixture_path("JESCU284604_prefinal.docx").exists(),
        "Put JESCU284604_prefinal.docx in tests/fixtures/ to enable full regression.",
    )
    def test_real_manuscript_fixture_exists(self):
        self.assertTrue(fixture_path("JESCU284604_prefinal.docx").exists())

    @unittest.skipUnless(
        fixture_path("APA_Report_JESCU284604_prefinal (5).docx").exists(),
        "Put APA_Report_JESCU284604_prefinal (5).docx in tests/fixtures/ to compare old report.",
    )
    def test_old_report_fixture_exists(self):
        self.assertTrue(fixture_path("APA_Report_JESCU284604_prefinal (5).docx").exists())


if __name__ == "__main__":
    unittest.main()
