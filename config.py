"""
config.py
โหลด configuration จาก .env file และ environment variables
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# โหลด .env จากโฟลเดอร์เดียวกับไฟล์นี้
_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / ".env", override=True)  # .env ต้อง override system env


def get_openai_key() -> str:
    """คืน OpenAI API key จาก environment"""
    key = os.getenv("OPENAI_API_KEY", "")
    return key.strip()


def get_llama_key() -> str:
    """คืน LlamaCloud API key สำหรับ LlamaParse"""
    key = os.getenv("LLAMA_CLOUD_API_KEY", "")
    return key.strip()


def get_brave_key() -> str:
    """คืน Brave Search API key สำหรับ web search fallback (ไม่บังคับ)"""
    key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    return key.strip()


def get_model() -> str:
    """คืน model ที่ใช้ (default: gpt-5.4-mini)"""
    return os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def get_report_writer_model() -> str:
    """คืน model สำหรับเกลาภาษารายงานผู้วิจัย"""
    return os.getenv("REPORT_WRITER_MODEL", "gpt-5.1")


def get_checklist_path() -> Path:
    """คืน path ของ checklist file ที่ใช้งาน"""
    custom = os.getenv("CHECKLIST_PATH", "")
    if custom and Path(custom).exists():
        return Path(custom)
    # default: checklist ที่มากับโปรแกรม
    return _BASE_DIR / "checklists" / "apa_chula_2568.md"


def get_output_dir() -> Path:
    """คืน directory สำหรับบันทึก output"""
    output = os.getenv("OUTPUT_DIR", str(_BASE_DIR / "outputs"))
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    return path
