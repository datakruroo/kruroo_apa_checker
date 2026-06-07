"""
crossref_verifier.py
ค้นหาข้อมูลบรรณานุกรมจริงจากฐานข้อมูลภายนอก เพื่อใช้เปรียบเทียบกับรายการอ้างอิงในเอกสาร

ลำดับการค้นหา:
  1. CrossRef  — lookup ตรงจาก DOI (แม่นยำ 100%)
  2. OpenAlex  — ค้นจากชื่อบทความ (ครอบคลุมกว้าง, ฟรี, ไม่ต้อง key)
  3. Brave Search — web search fallback (ครอบคลุม TCI / Thai journals, ต้อง key)
"""

import re
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional


# ===== ดึง DOI จาก reference text =====

def _extract_doi(text: str) -> Optional[str]:
    """ดึง DOI จากข้อความ รองรับ https://doi.org/... และ doi:..."""
    m = re.search(
        r"(?:https?://doi\.org/|doi:\s*)(10\.\d{4,}/\S+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).rstrip(".,;)")
    return None


def _extract_title_rough(text: str) -> str:
    """
    ดึงชื่อบทความโดยประมาณจาก APA reference
    pattern: (YEAR). Title. Source → ดึง Title
    """
    # หลัง (ปี).
    m = re.search(r"\(\d{4}[a-z]?\)\.\s+\*?([^*\n]{10,150})(?:[.*]?\s+[A-Z*฀-๿]|$)", text)
    if m:
        title = m.group(1).strip().rstrip(".")
        return title[:120]
    # fallback: ใช้ 80 ตัวอักษรแรก
    return text[:80]


def _http_get(url: str, headers: dict = None, timeout: int = 10) -> Optional[dict]:
    """HTTP GET → dict หรือ None ถ้า error"""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ===== Source 1: CrossRef =====

def _lookup_crossref_doi(doi: str) -> Optional[dict]:
    """Lookup ตรงจาก DOI ผ่าน CrossRef API"""
    encoded = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded}"
    data = _http_get(url, headers={"User-Agent": "APA-Checker/1.0 (mailto:admin@example.com)"})
    if not data or data.get("status") != "ok":
        return None
    return _normalize_crossref(data["message"])


def _search_crossref_title(title: str) -> Optional[dict]:
    """ค้นหาใน CrossRef ด้วยชื่อบทความ"""
    q = urllib.parse.quote(title)
    url = (
        f"https://api.crossref.org/works?query.title={q}&rows=1"
    )
    data = _http_get(url, headers={"User-Agent": "APA-Checker/1.0 (mailto:admin@example.com)"})
    if not data or not data.get("message", {}).get("items"):
        return None
    item = data["message"]["items"][0]
    # ตรวจ relevance score — CrossRef ใช้ score > 80 ถือว่าน่าเชื่อถือ
    if item.get("score", 0) < 60:
        return None
    return _normalize_crossref(item)


def _normalize_crossref(item: dict) -> dict:
    """แปลง CrossRef response เป็น format มาตรฐาน"""
    authors = []
    for a in item.get("author", []):
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            authors.append(f"{family}, {given[:1]}." if given else family)

    editors = []
    for e in item.get("editor", []):
        family = e.get("family", "")
        given = e.get("given", "")
        if family:
            editors.append(f"{given[:1]}. {family}" if given else family)

    year = None
    for date_field in ("published", "published-print", "published-online", "issued", "created"):
        pub = item.get(date_field, {})
        if pub.get("date-parts"):
            year = pub["date-parts"][0][0]
            break

    titles = item.get("title", [])
    container = item.get("container-title", [])

    return {
        "title": titles[0] if titles else "",
        "authors": authors,
        "year": year,
        "doi": item.get("DOI", ""),
        "type": item.get("type", ""),          # journal-article, book-chapter, book, report, ...
        "journal": container[0] if container else "",
        "volume": str(item.get("volume", "")),
        "issue": str(item.get("issue", "")),
        "pages": item.get("page", ""),
        "publisher": item.get("publisher", ""),
        "editors": editors,
    }


# ===== Source 2: OpenAlex =====

def _search_openalex(title: str) -> Optional[dict]:
    """ค้นหาใน OpenAlex ด้วยชื่อบทความ"""
    q = urllib.parse.quote(title)
    url = (
        f"https://api.openalex.org/works?search={q}&per-page=1"
        "&select=title,authorships,publication_year,doi,primary_location,biblio,type"
    )
    data = _http_get(url, headers={"User-Agent": "APA-Checker/1.0"})
    if not data or not data.get("results"):
        return None

    item = data["results"][0]

    authors = []
    for a in item.get("authorships", []):
        name = a.get("author", {}).get("display_name", "")
        if name:
            parts = name.split()
            if len(parts) >= 2:
                authors.append(f"{parts[-1]}, {parts[0][0]}.")
            else:
                authors.append(name)

    loc = item.get("primary_location", {}) or {}
    source = loc.get("source", {}) or {}
    biblio = item.get("biblio", {}) or {}

    doi_raw = item.get("doi", "") or ""
    doi = doi_raw.replace("https://doi.org/", "")

    return {
        "title": item.get("title", ""),
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": doi,
        "type": item.get("type", ""),
        "journal": source.get("display_name", ""),
        "volume": str(biblio.get("volume", "") or ""),
        "issue": str(biblio.get("issue", "") or ""),
        "pages": f"{biblio.get('first_page','')}–{biblio.get('last_page','')}".strip("–"),
        "publisher": "",
        "editors": [],
    }


# ===== Source 3: Brave Search =====

def _search_brave(query: str, api_key: str) -> list[dict]:
    """Web search ผ่าน Brave Search API — คืน list ของ {title, url, description}"""
    q = urllib.parse.quote(query)
    url = f"https://api.search.brave.com/res/v1/web/search?q={q}&count=3"
    data = _http_get(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    if not data:
        return []

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        })
    return results


# ===== Main entry point =====

def verify_reference(ref_text: str, brave_key: str = "") -> dict:
    """
    ค้นหาข้อมูลบรรณานุกรมจริงสำหรับ reference หนึ่งรายการ

    Returns:
        {
            "found": bool,
            "source": "CrossRef" | "OpenAlex" | "Brave" | None,
            "data": dict,         # structured bibliographic data (CrossRef/OpenAlex)
            "snippets": list,     # web search snippets (Brave only)
        }
    """
    # --- Source 1: CrossRef via DOI ---
    doi = _extract_doi(ref_text)
    if doi:
        data = _lookup_crossref_doi(doi)
        if data:
            return {"found": True, "source": "CrossRef", "data": data, "snippets": []}

    # --- Source 2: OpenAlex title search ---
    title = _extract_title_rough(ref_text)
    if title:
        data = _search_openalex(title)
        if data and data.get("title"):
            return {"found": True, "source": "OpenAlex", "data": data, "snippets": []}

        # CrossRef title search (fallback จาก OpenAlex)
        data = _search_crossref_title(title)
        if data and data.get("title"):
            return {"found": True, "source": "CrossRef (title)", "data": data, "snippets": []}

    # --- Source 3: Brave web search ---
    if brave_key and title:
        search_query = f'"{title}" site:scholar.google.com OR site:tci-thaijo.org OR doi.org'
        snippets = _search_brave(search_query, brave_key)
        if snippets:
            return {"found": True, "source": "Brave", "data": {}, "snippets": snippets}

    return {"found": False, "source": None, "data": {}, "snippets": []}


def format_verification_context(ref_text: str, verification: dict) -> str:
    """
    แปลง verification result เป็นข้อความ context สำหรับใส่ใน LLM prompt
    """
    if not verification["found"]:
        return f"ต้นฉบับ: {ref_text}\n[ไม่พบในฐานข้อมูล — ตรวจเฉพาะรูปแบบ APA]"

    source = verification["source"]

    # Brave search → ส่ง snippets
    if source == "Brave":
        snippets_text = "\n".join(
            f"  - {s['title']}: {s['description'][:150]}"
            for s in verification["snippets"][:3]
        )
        return (
            f"ต้นฉบับ: {ref_text}\n"
            f"[ผลค้นหาจากเว็บ ({source})]:\n{snippets_text}"
        )

    # CrossRef / OpenAlex → structured data
    d = verification["data"]
    authors_str = "; ".join(d.get("authors", [])[:5])
    if len(d.get("authors", [])) > 5:
        authors_str += " et al."

    lines = [f"ต้นฉบับ: {ref_text}", f"[ข้อมูลจริงจาก {source}]:"]
    if d.get("title"):
        lines.append(f"  ชื่อบทความ/เรื่อง: {d['title']}")
    if authors_str:
        lines.append(f"  ผู้แต่ง: {authors_str}")
    if d.get("year"):
        lines.append(f"  ปีพิมพ์: {d['year']}")
    if d.get("type"):
        lines.append(f"  ประเภท: {d['type']}")
    if d.get("journal"):
        lines.append(f"  วารสาร/หนังสือ: {d['journal']}")
    if d.get("editors"):
        lines.append(f"  บรรณาธิการ: {', '.join(d['editors'])}")
    if d.get("volume"):
        lines.append(f"  เล่มที่/ฉบับที่: {d['volume']}" + (f"({d['issue']})" if d.get("issue") else ""))
    if d.get("pages"):
        lines.append(f"  หน้า: {d['pages']}")
    if d.get("doi"):
        lines.append(f"  DOI: https://doi.org/{d['doi']}")
    if d.get("publisher"):
        lines.append(f"  สำนักพิมพ์: {d['publisher']}")

    return "\n".join(lines)
