import unittest

from src.pdf_extractor import parse_individual_references


class ReferenceSplittingTests(unittest.TestCase):
    def test_wrapped_thai_and_english_references_are_split_by_author_year_start(self):
        references_text = """
รายการอ้างอิง
ภาษาไทย
กวินนาฏ พลอยกระจ่าง, ศศิเทพ ปิติพรเทพิน, และ บุญเสถียร บุญสูง. (2563). การพัฒนาทักษะการ
แก้ปัญหาอย่างสร้างสรรค์ของนักเรียนชั้นมัธยมศึกษาปีที่ 4 เรื่องเซลล์และการทำงานของเซลล์.
https://doi.org/10.14457/KU.res.2020.200
จักรกฤต ภุชงค์ประเวศ. (2563). ผลของการจัดการเรียนการสอนโครงงานวิทยาศาสตร์โดยใช้กระบวนการ
ออกแบบเชิงวิศวกรรม ที่มีต่อความสามารถในการแก้ปัญหาเชิงสร้างสรรค์.
https://doi.org/10.14457/CU.the.2020.100
ภาษาอังกฤษ
Boyles, M. (2022). What is creative problem-solving? Harvard Business School Online.
https://online.hbs.edu/blog/post/what-is-creative-problem-solving
Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84-92.
"""

        refs = parse_individual_references(references_text)

        self.assertEqual(len(refs), 4)
        self.assertTrue(refs[0].startswith("กวินนาฏ"))
        self.assertIn("แก้ปัญหาอย่างสร้างสรรค์", refs[0])
        self.assertTrue(refs[1].startswith("จักรกฤต"))
        self.assertTrue(refs[2].startswith("Boyles"))
        self.assertTrue(refs[3].startswith("Brown"))
        self.assertFalse(any("ภาษาไทย" in ref or "ภาษาอังกฤษ" in ref for ref in refs))

    def test_single_newline_reference_section_does_not_merge_all_references(self):
        references_text = "\n".join(
            [
                "References",
                "Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84-92.",
                "Dorst, K. (2011). The core of design thinking and its application. Design Studies,",
                "32(6), 521-532. https://doi.org/10.1016/j.destud.2011.07.006",
                "OECD. (2023). The uses of process data in large-scale educational assessments.",
                "OECD Publishing. https://doi.org/10.1787/5d9009ff-en",
            ]
        )

        refs = parse_individual_references(references_text)

        self.assertEqual(len(refs), 3)
        self.assertTrue(refs[0].startswith("Brown"))
        self.assertTrue(refs[1].startswith("Dorst"))
        self.assertIn("32(6), 521-532", refs[1])
        self.assertTrue(refs[2].startswith("OECD"))
        self.assertNotIn("OECD. (2023)", refs[1])

    def test_blank_line_separated_references_still_work(self):
        references_text = """
References

Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84-92.

Dorst, K. (2011). The core of design thinking and its application. Design Studies, 32(6), 521-532.
"""

        refs = parse_individual_references(references_text)

        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0], "Brown, T. (2008). Design thinking. Harvard Business Review, 86(6), 84-92.")
        self.assertTrue(refs[1].startswith("Dorst, K. (2011)."))

    def test_reference_start_allows_year_with_month_inside_parentheses(self):
        references_text = "\n".join(
            [
                "Idin, Ş. (2020). New trends in science education within the 21st century skills perspective.",
                "Jäder, J. (2019, February). Task design with a focus on conceptual and creative challenges.",
                "Lusiana, R., & Andari, T. (2020). Brain based learning to improve students’ higher order thinking skills.",
                "Maknuunah, L., Kuswandi, D., & Soepriyanto, Y. (2021, January). Project-based learning integrated with design thinking.",
            ]
        )

        refs = parse_individual_references(references_text)

        self.assertEqual(len(refs), 4)
        self.assertTrue(refs[0].startswith("Idin"))
        self.assertTrue(refs[1].startswith("Jäder"))
        self.assertTrue(refs[2].startswith("Lusiana"))
        self.assertTrue(refs[3].startswith("Maknuunah"))


if __name__ == "__main__":
    unittest.main()
