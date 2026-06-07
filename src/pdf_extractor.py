"""
pdf_extractor.py
ดึงข้อความจาก PDF โดยใช้ LlamaParse → Markdown (รักษา italic/bold formatting)
"""

import re
from pathlib import Path


# หัวข้อที่บ่งบอกว่าเริ่มส่วนรายการอ้างอิง
REFERENCE_HEADERS = [
    r"รายการอ้างอิง",
    r"เอกสารอ้างอิง",
    r"บรรณานุกรม",
    r"References",
    r"REFERENCES",
    r"Bibliography",
    r"BIBLIOGRAPHY",
]

# Pattern สำหรับตรวจจับ in-text citation
INTEXT_PATTERN = re.compile(
    r"""
    (?:
        # รูปแบบท้ายข้อความ: (Author, Year) หรือ (สกุล, ปี)
        \(
            [^)]{1,200}   # ข้อความในวงเล็บ (จำกัด 200 ตัวอักษร)
            (?:19|20|25)\d{2} # ปี ค.ศ. หรือ ปี พ.ศ.
            [^)]{0,20}
        \)
        |
        # รูปแบบหน้าข้อความ: Author (Year)
        [A-Zก-ฮ][^\s(]{1,50}\s+(?:et\s+al\.|และคณะ)?\s*\((?:19|20|25)\d{2}\)
    )
    """,
    re.VERBOSE,
)


def _parse_pdf_to_markdown(pdf_path: str) -> str:
    """แปลง PDF เป็น Markdown โดยใช้ LlamaParse (รักษา italic formatting)"""
    import html
    from llama_parse import LlamaParse
    import config

    llama_key = config.get_llama_key()
    if not llama_key:
        raise ValueError("ไม่พบ LLAMA_CLOUD_API_KEY กรุณาตั้งค่าใน .env")

    parser = LlamaParse(
        api_key=llama_key,
        result_type="markdown",
        verbose=False,
        language="en",          # รองรับทั้ง English และ Thai
        skip_diagonal_text=True,  # ข้าม watermark/diagonal text
    )

    documents = parser.load_data(pdf_path)

    # join ด้วย \n เดี่ยว (ไม่ใช่ \n\n) เพื่อป้องกัน reference ที่ข้ามหน้าถูกตัดเป็นสองย่อหน้า
    raw = "\n".join(doc.text for doc in documents)

    # LlamaParse อาจ escape HTML entities เช่น & → &amp;, – → &ndash;
    # unescape คืนค่ากลับให้ถูกต้องก่อนส่งต่อ
    unescaped = html.unescape(raw)

    # กรอง running header/footer ที่ซ้ำทุกหน้า
    footer_pattern = re.compile(
        r"ISSN\s+\d[\d\-]+.*?(?=\n|$)|"          # ISSN line
        r"Journal of Education Studies.*?(?=\n|$)|"  # English journal footer
        r"วารสารครุศาสตร์.*?(?=\n|$)",              # Thai journal header
        re.IGNORECASE,
    )
    return footer_pattern.sub("", unescaped)


def find_references_start(text: str) -> int:
    """
    หาตำแหน่งที่เริ่มส่วนรายการอ้างอิง คืน -1 ถ้าไม่พบ

    ทำงานโดย strip Markdown markers ออกจากแต่ละบรรทัดก่อน compare
    รองรับ: plain text, **bold**, *italic*, ## heading, และ combinations ทุกแบบ
    """
    header_set = {h.lower() for h in REFERENCE_HEADERS}
    lines = text.split("\n")
    pos = 0

    for line in lines:
        # strip Markdown formatting markers (* # _ ~ `) แล้ว trim whitespace
        clean = re.sub(r"[\*#_~`]+", "", line).strip()
        if clean.lower() in header_set:
            return pos
        pos += len(line) + 1  # +1 สำหรับ \n

    return -1


def split_document(pdf_path: str) -> dict:
    """
    แปลง PDF เป็น Markdown และแยก body กับ references section

    Returns:
        dict: {
            "body": str,           # Markdown ส่วนเนื้อหา
            "references": str,     # Markdown ส่วนรายการอ้างอิง
            "full_text": str,      # Markdown ทั้งหมด
            "ref_found": bool      # พบส่วนอ้างอิงหรือไม่
        }
    """
    full_text = _parse_pdf_to_markdown(pdf_path)
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


def extract_intext_citations(body_text: str) -> list[str]:
    """
    ดึงประโยคที่มี in-text citation จาก body text (Markdown)
    คืนเป็น list ของ excerpt ที่มีการอ้างอิง
    """
    # ลบ Markdown heading markers ออกก่อน split (# ## ###)
    clean_text = re.sub(r"^#{1,6}\s+", "", body_text, flags=re.MULTILINE)

    excerpts = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", clean_text)
    for sent in sentences:
        sent = sent.strip()
        if INTEXT_PATTERN.search(sent) and len(sent) > 10:
            excerpts.append(sent)
    return excerpts


def _filter_ref_lines(lines: list[str]) -> list[str]:
    """กรอง lines ที่ไม่ใช่รายการอ้างอิงออก"""
    skip_exact = {"ภาษาไทย", "ภาษาอังกฤษ", "thai", "english", "references", "bibliography",
                  "รายการอ้างอิง", "เอกสารอ้างอิง", "บรรณานุกรม"}
    result = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 20:
            continue
        if re.match(r"^#{1,6}\s+", line) or line.startswith("---"):
            continue
        if re.sub(r"[\*#_~`]+", "", line).strip().lower() in skip_exact:
            continue
        line = re.sub(r"^\s*[-*]\s+", "", line)
        result.append(line)
    return result


def _looks_like_reference_start(line: str) -> bool:
    """
    ตรวจว่าบรรทัดนี้น่าจะเป็นจุดเริ่ม reference ใหม่หรือไม่

    รองรับทั้ง ค.ศ. และ พ.ศ. โดยตั้งใจดูเฉพาะช่วงต้นบรรทัด เพื่อไม่ให้
    ปีที่อยู่ในชื่อบทความ/URL ตอนกลางรายการทำให้ split ผิด
    """
    clean = re.sub(r"[\*#_~`]+", "", line).strip()
    if len(clean) < 12:
        return False
    if re.match(r"^(ภาษาไทย|ภาษาอังกฤษ|thai|english|references|bibliography)$", clean, re.IGNORECASE):
        return False
    return bool(re.search(r"^.{1,220}?\((?:19|20|25)\d{2}[a-z]?(?:,\s*[^)]{1,40})?\)\.", clean))


def _split_wrapped_references(lines: list[str]) -> list[str]:
    refs: list[str] = []
    current: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if re.sub(r"[\*#_~`]+", "", line).strip().lower() in {
            "ภาษาไทย",
            "ภาษาอังกฤษ",
            "thai",
            "english",
            "references",
            "bibliography",
            "รายการอ้างอิง",
            "เอกสารอ้างอิง",
            "บรรณานุกรม",
        }:
            continue

        if _looks_like_reference_start(line) and current:
            refs.append(" ".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        refs.append(" ".join(current).strip())

    return [ref for ref in refs if len(ref) >= 20]


def parse_individual_references(references_text: str) -> list[str]:
    """
    แยกรายการอ้างอิงแต่ละรายการออกจากกัน
    รองรับทั้ง double-newline (LlamaParse) และ single-newline (docx)
    """
    lines = references_text.split("\n")
    wrapped_refs = _split_wrapped_references(lines)
    if len(wrapped_refs) >= 2:
        return wrapped_refs

    # ลอง double-newline split ก่อน (LlamaParse output)
    paragraphs = re.split(r"\n{2,}", references_text)
    candidates = _filter_ref_lines(paragraphs)
    if len(candidates) > 2 and not any("\n" in candidate for candidate in candidates):
        return candidates

    # Fallback: single-newline split (docx output — แต่ละ paragraph = 1 บรรทัด)
    return _filter_ref_lines(lines)
