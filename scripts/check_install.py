"""
Small cross-platform installation check.

Run after installing dependencies:
    python scripts/check_install.py
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys


REQUIRED_MODULES = [
    "docx",
    "dotenv",
    "openai",
    "streamlit",
]

OPTIONAL_MODULES = [
    ("llama_parse", "Required only for PDF uploads."),
]


def _check_module(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        print(f"FAIL {module_name}: {exc}")
        return False
    print(f"OK   {module_name}")
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    print(f"Project: {root}")
    print(f"Python:  {sys.version.split()[0]}")
    print()

    ok = True
    for module_name in REQUIRED_MODULES:
        ok = _check_module(module_name) and ok

    print()
    for module_name, note in OPTIONAL_MODULES:
        if not _check_module(module_name):
            print(f"      {note}")

    env_path = root / ".env"
    example_path = root / ".env.example"
    print()
    if env_path.exists():
        print("OK   .env exists")
    elif example_path.exists():
        print("WARN .env is missing. Copy .env.example to .env before using the Streamlit app.")
    else:
        print("FAIL .env.example is missing")
        ok = False

    checklist = root / "checklists" / "apa_chula_2568.md"
    if checklist.exists():
        print("OK   checklist exists")
    else:
        print("FAIL checklist is missing")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
