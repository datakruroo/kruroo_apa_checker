import unittest

from src.citation_checker import validate_intext_citation_excerpts
from src.pdf_extractor import extract_intext_citations


class CitationCrosscheckTests(unittest.TestCase):
    def test_extract_intext_citations_detects_buddhist_year(self):
        body = "ข้อความตัวอย่าง (กวินนาฏ พลอยกระจ่าง และคณะ, 2564) ต่อท้ายประโยค"

        excerpts = extract_intext_citations(body)

        self.assertEqual(excerpts, [body])

    def test_buddhist_year_mismatch_between_intext_and_references_is_error(self):
        result = validate_intext_citation_excerpts(
            ["พบการอ้างอิง (กวินนาฏ พลอยกระจ่าง และคณะ, 2564) ในเนื้อหา"],
            references_text=(
                "กวินนาฏ พลอยกระจ่าง, ศศิเทพ ปิติพรเทพิน, และ บุญเสถียร บุญสูง. "
                "(2563). การพัฒนาทักษะการแก้ปัญหาอย่างสร้างสรรค์."
            ),
        )

        self.assertEqual(result["summary"]["issues_found"], 1)
        issue = result["issues"][0]
        self.assertEqual(issue["severity"], "ERROR")
        self.assertIn("possible_year_mismatch", issue["issues"])
        self.assertIn("2564", issue["excerpt"])
        self.assertIn("2563", issue["explanation"])

    def test_orphan_parenthetical_fragment_still_detects_year_mismatch(self):
        result = validate_intext_citation_excerpts(
            ["ภุชงค์ประเวศ, 2563; กวินนาฏ พลอยกระจ่าง และคณะ, 2564) แต่ยังไม่พบการศึกษา"],
            references_text=(
                "กวินนาฏ พลอยกระจ่าง, ศศิเทพ ปิติพรเทพิน, และ บุญเสถียร บุญสูง. "
                "(2563). การพัฒนาทักษะการแก้ปัญหาอย่างสร้างสรรค์.\n"
                "จักรกฤต ภุชงค์ประเวศ. (2563). ผลของการจัดการเรียนการสอน."
            ),
        )

        self.assertEqual(result["summary"]["issues_found"], 1)
        issue = result["issues"][0]
        self.assertIn("possible_year_mismatch", issue["issues"])
        self.assertIn("2564", issue["explanation"])
        self.assertIn("2563", issue["explanation"])

    def test_matching_buddhist_year_is_valid(self):
        result = validate_intext_citation_excerpts(
            ["พบการอ้างอิง (กวินนาฏ พลอยกระจ่าง และคณะ, 2563) ในเนื้อหา"],
            references_text=(
                "กวินนาฏ พลอยกระจ่าง, ศศิเทพ ปิติพรเทพิน, และ บุญเสถียร บุญสูง. "
                "(2563). การพัฒนาทักษะการแก้ปัญหาอย่างสร้างสรรค์."
            ),
        )

        self.assertEqual(result["summary"]["issues_found"], 0)
        self.assertEqual(result["issues"], [])

    def test_common_author_forms_match_references(self):
        references_text = "\n".join(
            [
                "Idin, Ş. (2020). New trends in science education.",
                "Buck Institute for Education. (2022). Project based teaching.",
                "Jiang, C., & Pang, Y. (2023). Enhancing design thinking.",
                "Sagoro, E. M., & Aghni, R. I. (2024). The influence of scaffolding.",
                "Boyles, M. (2022). What is creative problem-solving?",
            ]
        )
        result = validate_intext_citation_excerpts(
            [
                "(Idin, 2020)",
                "(Buck Institute for Education, 2022; Boyles, 2022)",
                "Jiang and Pang (2023) showed improvement.",
                "Sagoro and Aghni (2024) ระบุว่า",
            ],
            references_text=references_text,
        )

        self.assertEqual(result["issues"], [])

    def test_unmatched_citation_is_warning_not_error(self):
        result = validate_intext_citation_excerpts(
            ["พบการอ้างอิง (Unknown, 2020) ในเนื้อหา"],
            references_text="Known, A. (2020). A title.",
        )

        self.assertEqual(result["summary"]["issues_found"], 1)
        self.assertEqual(result["issues"][0]["severity"], "WARNING")
        self.assertIn("possible_unmatched_citation", result["issues"][0]["issues"])

    def test_uncited_reference_is_warning_after_successful_matching(self):
        result = validate_intext_citation_excerpts(
            ["พบการอ้างอิง (Known, 2020) ในเนื้อหา"],
            references_text="\n".join(
                [
                    "Known, A. (2020). A title.",
                    "Unused, B. (2021). Another title.",
                ]
            ),
        )

        uncited = [issue for issue in result["issues"] if "listed_but_not_cited" in issue["issues"]]
        self.assertEqual(len(uncited), 1)
        self.assertEqual(uncited[0]["severity"], "WARNING")
        self.assertEqual(uncited[0]["reference_number"], 2)

    def test_uncited_reference_uses_body_evidence_for_narrative_et_al(self):
        result = validate_intext_citation_excerpts(
            ["Jiang and Pang (2023) กล่าวไว้ ต่อด้วย Jia et al."],
            references_text="\n".join(
                [
                    "Jiang, C., & Pang, Y. (2023). Enhancing design thinking.",
                    "Jia, L., Jalaludin, N., & Rasul, S. (2023). Design thinking in PBL.",
                    "Willemsen, R. H., de Vink, I. C., Kroesbergen, E. H., & Lazonder, A. W. (2024). Creative problem-solving.",
                    "Metwaly, S., Fernández-Castilla, B., Kyndt, E., & Van den Noortgate, W. (2020). Testing conditions.",
                    "Paek, S. H., Abdulla Alabbasi, A. M., Acar, S., & Runco, M. A. (2021). Time and creativity.",
                    "Treffinger, D. J., Edwin, C. S., & Scott, G. I. (2008). Creative problem solving.",
                ]
            ),
            body_text=(
                "Jiang and Pang (2023) กล่าวไว้ ต่อด้วย Jia et al. (2023), "
                "Willemsen et al. (2024), Metwaly et al. (2020), "
                "Paek et al. (2021), และ Treffinger et al. (2008)"
            ),
        )

        uncited_refs = {issue.get("reference_number") for issue in result["issues"] if "listed_but_not_cited" in issue["issues"]}
        self.assertFalse({2, 3, 4, 5, 6} & uncited_refs)


if __name__ == "__main__":
    unittest.main()
