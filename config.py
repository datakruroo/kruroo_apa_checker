"""
config.py
โหลด configuration จาก .env file และ environment variables
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# โหลด .env จากโฟลเดอร์เดียวกับไฟล์นี้
_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / ".env", override=True)  # .env ต้อง override system env


def get_openai_key() -> str:
    """คืน OpenAI API key จาก environment"""
    key = os.getenv("OPENAI_API_KEY", "")
    return key.strip()


def get_openrouter_key() -> str:
    """คืน OpenRouter API key จาก environment"""
    key = os.getenv("OPENROUTER_API_KEY", "")
    return key.strip()


def get_llm_provider() -> str:
    """คืน LLM provider ที่ใช้: openai หรือ openrouter"""
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    return provider if provider in {"openai", "openrouter"} else "openai"


def get_llm_key() -> str:
    """คืน API key ของ provider ที่เลือก"""
    if get_llm_provider() == "openrouter":
        return get_openrouter_key()
    return get_openai_key()


def get_openrouter_base_url() -> str:
    """คืน OpenRouter base URL แบบ OpenAI-compatible"""
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()


def create_llm_client() -> OpenAI:
    """สร้าง OpenAI-compatible client ตาม provider ที่ตั้งไว้"""
    provider = get_llm_provider()
    key = get_llm_key()
    if provider == "openrouter":
        return OpenAI(
            api_key=key,
            base_url=get_openrouter_base_url(),
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://github.com/datakruroo/kruroo_apa_checker"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "kruroo_apa_checker"),
            },
        )
    return OpenAI(api_key=key)


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
    if get_llm_provider() == "openrouter":
        return (
            os.getenv("OPENROUTER_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
            or "openai/gpt-5.1"
        )
    return os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def get_report_writer_model() -> str:
    """คืน model สำหรับเกลาภาษารายงานผู้วิจัย"""
    if get_llm_provider() == "openrouter":
        return (
            os.getenv("OPENROUTER_REPORT_WRITER_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "").strip()
            or "openai/gpt-5.1"
        )
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
