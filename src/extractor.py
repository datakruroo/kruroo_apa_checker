"""
extractor.py
Router — เลือกใช้ docx_extractor หรือ pdf_extractor ตาม file extension
ทุก module ภายนอก import จากไฟล์นี้ไฟล์เดียว ไม่ต้องรู้จัก extractor ข้างใน
"""

from pathlib import Path

from .pdf_extractor import extract_intext_citations, parse_individual_references


def split_document(file_path: str) -> dict:
    """
    แปลงไฟล์ (PDF หรือ Word) เป็น Markdown แล้วแยก body กับ references

    - .docx → docx_extractor (italic จาก run.italic โดยตรง, ไม่ต้อง LlamaParse)
    - .pdf  → pdf_extractor  (LlamaParse → Markdown)

    Returns: {"body", "references", "full_text", "ref_found"}
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".docx":
        from .docx_extractor import split_document as _split
    else:
        from .pdf_extractor import split_document as _split

    return _split(file_path)
