"""
run_app.py
Entry point สำหรับ PyInstaller — เปิด Streamlit app ใน browser อัตโนมัติ
"""

import sys
import os
import subprocess
import webbrowser
import time
from pathlib import Path


def main():
    # กำหนด port
    port = 8501

    # path ของ app.py (รองรับทั้ง dev และ PyInstaller bundle)
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent

    app_path = base_dir / "app.py"

    # รัน streamlit
    cmd = [
        sys.executable if not getattr(sys, "frozen", False) else "streamlit",
        "run" if not getattr(sys, "frozen", False) else "run",
        str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]

    # ถ้า frozen ใช้ streamlit ที่ bundle มา
    if getattr(sys, "frozen", False):
        streamlit_bin = base_dir / "streamlit"
        cmd = [str(streamlit_bin), "run", str(app_path),
               "--server.port", str(port),
               "--server.headless", "true",
               "--browser.gatherUsageStats", "false"]

    proc = subprocess.Popen(cmd, cwd=str(base_dir))

    # รอให้ server พร้อม แล้วเปิด browser
    time.sleep(3)
    webbrowser.open(f"http://localhost:{port}")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
