"""
app.py
Streamlit UI สำหรับระบบตรวจสอบการอ้างอิง APA
"""

import tempfile
from pathlib import Path

import streamlit as st

import config
from src.extractor import split_document
from src.apa_checker import load_checklist, run_full_check
from src.report_generator import generate_report

# ===== Page config =====
st.set_page_config(
    page_title="APA Citation Checker",
    page_icon="📋",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ===== CSS =====
st.markdown(
    """
    <style>
    .stApp { max-width: 800px; margin: auto; }
    .result-box { background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 8px 0; }
    .error-text { color: #e94f37; font-weight: bold; }
    .ok-text { color: #069a2e; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== Header =====
st.title("📋 APA Citation Checker")
st.caption("ระบบตรวจสอบการอ้างอิงตาม APA 7th Edition (จุฬาฯ 2568)")
st.divider()

# ===== ตรวจสอบ API keys =====
llm_provider = config.get_llm_provider()
llm_key = config.get_llm_key()
llama_key = config.get_llama_key()
brave_key = config.get_brave_key()

if not llm_key:
    st.error(
        "⚠️ ไม่พบ API Key สำหรับโมเดลภาษา กรุณาให้ Admin ตั้งค่าไฟล์ .env "
        + ("โดยเพิ่ม OPENROUTER_API_KEY=... หรือเปลี่ยน LLM_PROVIDER=openai" if llm_provider == "openrouter" else "โดยเพิ่ม OPENAI_API_KEY=...")
    )
    st.stop()

if not llama_key:
    st.warning(
        "⚠️ ไม่พบ LLAMA_CLOUD_API_KEY — รองรับเฉพาะไฟล์ .docx เท่านั้น "
        "ถ้าต้องการอัปโหลด PDF ให้ Admin เพิ่ม LLAMA_CLOUD_API_KEY ใน .env "
        "(สมัครฟรีได้ที่ https://cloud.llamaindex.ai)"
    )

client = config.create_llm_client()
checklist_path = config.get_checklist_path()
model = config.get_model()
report_writer_model = config.get_report_writer_model()

# ===== Upload section =====
st.subheader("1. อัปโหลดบทความ")
accepted_types = ["docx"] if not llama_key else ["docx", "pdf"]
uploaded_file = st.file_uploader(
    "เลือกไฟล์บทความที่ต้องการตรวจสอบ (.docx หรือ .pdf)",
    type=accepted_types,
    help="แนะนำ .docx เพื่อความแม่นยำสูงสุด (italic detection 100%) | .pdf ต้องการ LLAMA_CLOUD_API_KEY",
)

# ===== Options =====
with st.expander("⚙️ ตั้งค่าเพิ่มเติม (สำหรับผู้พัฒนา)", expanded=False):
    st.text_input("LLM Provider", value=llm_provider, disabled=True)
    show_model = st.text_input("Checker Model", value=model, disabled=True)
    st.text_input("Report Writer Model", value=report_writer_model, disabled=True)
    show_checklist = st.text_area(
        "เนื้อหา Checklist ที่ใช้",
        value=checklist_path.read_text(encoding="utf-8") if checklist_path.exists() else "ไม่พบ checklist",
        height=200,
        disabled=True,
        help="แก้ไขได้โดยแก้ไฟล์ checklists/apa_chula_2568.md แล้วรีสตาร์ทโปรแกรม",
    )

st.divider()

# ===== Check button =====
st.subheader("2. ตรวจสอบ")
run_btn = st.button(
    "🔍 เริ่มตรวจสอบ",
    type="primary",
    disabled=uploaded_file is None,
    use_container_width=True,
)

if run_btn and uploaded_file:
    # บันทึก PDF ชั่วคราว
    file_suffix = ".docx" if uploaded_file.name.lower().endswith(".docx") else ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_pdf_path = tmp.name

    try:
        is_pdf = uploaded_file.name.lower().endswith(".pdf")

        # ตรวจสอบ LlamaCloud key ก่อน process PDF
        if is_pdf and not llama_key:
            st.error("⚠️ ไม่สามารถประมวล PDF ได้ เนื่องจากไม่พบ LLAMA_CLOUD_API_KEY กรุณาให้ Admin ตั้งค่าใน .env")
            st.stop()

        # ===== Progress =====
        init_msg = "กำลังส่ง PDF ไปยัง LlamaParse..." if is_pdf else "กำลังอ่านไฟล์ Word..."
        progress = st.progress(0, text=init_msg)

        # Step 1: extract (LlamaParse → Markdown)
        sections = split_document(tmp_pdf_path)
        progress.progress(25, text="แปลง PDF เป็น Markdown เสร็จแล้ว กำลังแยกส่วนอ้างอิง...")

        if not sections["ref_found"]:
            st.warning(
                "⚠️ ไม่พบส่วน 'รายการอ้างอิง' ในไฟล์ PDF นี้ "
                "กรุณาตรวจสอบว่า PDF มีข้อความ (ไม่ใช่ภาพสแกน) "
                "และมีหัวข้อ 'รายการอ้างอิง' หรือ 'References'"
            )

        # Step 2: load checklist
        checklist = load_checklist(str(checklist_path))
        progress.progress(35, text="โหลด checklist แล้ว กำลังส่งข้อมูลไปตรวจสอบ...")

        # Step 3: check references
        from src.apa_checker import check_references, check_intext_citations
        from src.extractor import extract_intext_citations

        results = {"ref_found": sections["ref_found"]}

        if sections.get("references"):
            progress.progress(40, text="กำลังค้นหาข้อมูลจากฐานข้อมูล + ตรวจสอบรายการอ้างอิง...")
            results["ref_check"] = check_references(client, sections["references"], checklist, model, brave_key=brave_key)
            progress.progress(70, text="ตรวจสอบรายการอ้างอิงเสร็จแล้ว...")

        if sections.get("body"):
            progress.progress(75, text="กำลังตรวจสอบการอ้างอิงในเนื้อหา (In-Text)...")
            excerpts = extract_intext_citations(sections["body"])[:80]
            results["intext_check"] = check_intext_citations(
                client,
                excerpts,
                checklist,
                model,
                references_text=sections.get("references", ""),
                body_text=sections.get("body", ""),
            )
            progress.progress(90, text="สร้างรายงาน...")

        # Step 4: generate report
        output_dir = config.get_output_dir()
        output_filename = f"APA_Report_{Path(uploaded_file.name).stem}.docx"
        output_path = str(output_dir / output_filename)

        generate_report(
            results=results,
            article_filename=uploaded_file.name,
            output_path=output_path,
            report_writer_client=client,
            report_writer_model=report_writer_model,
        )
        progress.progress(100, text="เสร็จสิ้น!")

        # ===== แสดงสรุปผล =====
        st.divider()
        st.subheader("3. ผลการตรวจสอบ")

        ref_check = results.get("ref_check", {})
        intext_check = results.get("intext_check", {})

        col1, col2 = st.columns(2)
        with col1:
            ref_summary = ref_check.get("summary", {})
            st.metric(
                "รายการอ้างอิง (References)",
                f"{ref_summary.get('total_references', 0)} รายการ",
                delta=f"ต้องตรวจ {ref_summary.get('unsafe_generated_outputs', 0)} | ควรตรวจสอบ {ref_summary.get('possible_matches_requiring_review', 0)}",
                delta_color="off",
            )
        with col2:
            intext_summary = intext_check.get("summary", {})
            st.metric(
                "การอ้างอิงในเนื้อหา (In-Text)",
                f"{intext_summary.get('total_checked', 0)} ประโยค",
                delta=f"ต้องตรวจ {intext_summary.get('issues_found', 0)} ประโยค",
                delta_color="inverse",
            )

        if ref_check:
            st.caption(
                "References: "
                f"ตรวจยืนยันแล้วไม่ต้องแก้ {ref_summary.get('verified_no_change_needed', 0)} | "
                f"มีจุดที่แก้ได้เลย {ref_summary.get('verified_with_low_risk_formatting_fix', 0)} | "
                f"ข้อความที่อ่านจากไฟล์อาจมีปัญหา {ref_summary.get('parser_warnings', 0)} | "
                f"ยังยืนยันจากแหล่งภายนอกไม่ได้ {ref_summary.get('unverified_references', 0)}"
            )

        # แสดงประเภทปัญหา
        issue_types = (
            ref_check.get("summary", {}).get("issue_types", [])
            + intext_check.get("summary", {}).get("issue_types", [])
        )
        if issue_types:
            st.info("**ประเภทปัญหาที่พบ:** " + " | ".join(set(issue_types)))

        # Download button
        st.divider()
        st.subheader("4. ดาวน์โหลดรายงาน")
        with open(output_path, "rb") as f:
            st.download_button(
                label="⬇️ ดาวน์โหลด รายงานผลการตรวจสอบ (.docx)",
                data=f.read(),
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
            )

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")
        raise
    finally:
        Path(tmp_pdf_path).unlink(missing_ok=True)

elif uploaded_file is None:
    st.info("กรุณาอัปโหลดไฟล์บทความเพื่อเริ่มตรวจสอบ")
