"""
docx_extractor.py
แปลง Word document (.docx) เป็น Markdown โดยอ่าน italic/bold โดยตรงจาก run properties
ให้ข้อมูล formatting ที่แม่นยำ 100% โดยไม่ต้องพึ่ง LlamaParse
"""

from docx import Document
from docx.oxml.ns import qn

# import shared utilities จาก pdf_extractor
from .pdf_extractor import (
    find_references_start,
    extract_intext_citations,
    parse_individual_references,
)


def _run_text_and_italic(run_element) -> tuple[str, bool]:
    text = "".join(node.text or "" for node in run_element.iter(qn("w:t")))
    rpr = run_element.find(qn("w:rPr"))
    is_italic = rpr is not None and rpr.find(qn("w:i")) is not None
    return text, is_italic


def _para_to_markdown(para) -> str:
    """
    แปลง paragraph เป็น Markdown โดย:
    1. สนใจเฉพาะ italic (bold ไม่เกี่ยวกับ APA)
    2. Merge adjacent runs ที่มี italic status เดียวกันก่อน wrap
       → ป้องกัน *text1 **text2* ที่ LLM เข้าใจผิดว่าเป็นตัวอักษรจริง
    """
    groups: list[tuple[bool, str]] = []

    def add_text(text: str, is_italic: bool) -> None:
        if not text:
            return
        if groups and groups[-1][0] == is_italic:
            groups[-1] = (is_italic, groups[-1][1] + text)
        else:
            groups.append((is_italic, text))

    # เดิน XML children เพื่อรวม text ใน hyperlink ด้วย; python-docx para.runs
    # ไม่คืน runs ที่อยู่ใต้ w:hyperlink ทำให้ DOI/URL หายได้
    for child in para._p:
        if child.tag == qn("w:r"):
            text, is_italic = _run_text_and_italic(child)
            add_text(text, is_italic)
        elif child.tag == qn("w:hyperlink"):
            for run_element in child.iter(qn("w:r")):
                text, is_italic = _run_text_and_italic(run_element)
                add_text(text, is_italic)

    parts = []
    for is_italic, text in groups:
        parts.append(f"*{text}*" if is_italic else text)

    return "".join(parts)


def _parse_docx_to_markdown(docx_path: str) -> str:
    """
    แปลง Word document เป็น Markdown
    แต่ละ paragraph → หนึ่งบรรทัด, italic spans → *text* (ไม่มี ** เด็ดขาด)
    """
    doc = Document(docx_path)
    lines = []

    for para in doc.paragraphs:
        if not para.text.strip():
            lines.append("")
            continue

        line = _para_to_markdown(para)
        if not line:
            line = para.text  # fallback กรณีไม่มี runs

        lines.append(line)

    return "\n".join(lines)


def split_document(docx_path: str) -> dict:
    """
    แปลง Word document เป็น Markdown แล้วแยก body กับ references section

    Returns:
        dict: {
            "body": str,       # Markdown ส่วนเนื้อหา (มี *italic*)
            "references": str, # Markdown ส่วนรายการอ้างอิง (มี *italic*)
            "full_text": str,
            "ref_found": bool
        }
    """
    full_text = _parse_docx_to_markdown(docx_path)
    ref_start = find_references_start(full_text)

    if ref_start == -1:
        return {
            "body": full_text,
            "references": "",
            "full_text": full_text,
            "ref_found": False,
        }

    return {
        "body": full_text[:ref_start].strip(),
        "references": full_text[ref_start:].strip(),
        "full_text": full_text,
        "ref_found": True,
    }
