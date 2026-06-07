<img width="300" height="115" alt="image" src="https://github.com/user-attachments/assets/dde9353f-a203-46db-b615-582abf616a0d" />

# kruroo_apa_checker

ระบบช่วยตรวจรายการอ้างอิงและการอ้างอิงในเนื้อหาตาม APA 7 สำหรับงานบรรณาธิการเบื้องต้น

สถานะปัจจุบัน: ใช้เป็น pilot report / editorial screening ได้ แต่ยังไม่ควรใช้แทนการตรวจทานขั้นสุดท้ายของมนุษย์

## ระบบตรวจอะไรได้บ้าง

- ตรวจรูปแบบรายการอ้างอิงที่เสี่ยงต่ำ เช่น DOI ซ้ำ prefix, ช่วงหน้า hyphen เป็น en dash, จุดเกินหลังเครื่องหมายคำถาม
- ตรวจรูปแบบ Word บางส่วน เช่น volume ควรเป็นตัวเอียง และ issue ไม่ควรเป็นตัวเอียง
- ตรวจ metadata จาก DOI โดยใช้ Crossref exact DOI lookup
- ตรวจความขัดแย้งบางชนิด เช่น ผู้แต่งหรือชื่อเรื่องไม่ตรงกับ metadata ของ DOI
- ตรวจ citation กับ References เช่น ปีใน citation ไม่ตรงกับ References และรายการอ้างอิงที่ยังไม่พบ citation
- สร้างรายงาน `.docx` สำหรับผู้เขียนด้วยภาษาที่อ่านง่าย

ระบบจะไม่แก้ข้อมูลสำคัญให้อัตโนมัติ เช่น ผู้แต่ง ปี ชื่อเรื่อง ชื่อวารสาร แหล่งพิมพ์ หรือ DOI suffix หากไม่มีหลักฐานแน่นพอ

## แหล่งข้อมูลภายนอกที่ใช้

- Crossref: ใช้ยืนยัน metadata จาก DOI โดยตรง
- OpenAlex: ใช้หา possible match จากชื่อเรื่องเฉพาะกรณีไม่มี DOI
- OpenAI API: ใช้กับ Streamlit app และการเกลาภาษารายงาน ไม่ใช้เป็นแหล่งยืนยันข้อมูลบรรณานุกรม
- LlamaCloud: ใช้เฉพาะกรณีอัปโหลด PDF

## ความต้องการของระบบ

- Python 3.11 หรือ 3.12
- Git
- Internet connection สำหรับติดตั้ง dependency และตรวจ metadata จาก Crossref/OpenAlex
- OpenAI API key สำหรับใช้งานผ่าน Streamlit app

แนะนำให้ใช้ไฟล์ `.docx` เป็นหลัก เพราะตรวจตำแหน่งและรูปแบบตัวเอียงได้ดีกว่า PDF

## ติดตั้งครั้งแรก: เตรียม Python และ Git

โปรเจกต์นี้ไม่ได้ติดตั้ง Python หรือ Git ให้อัตโนมัติ ผู้ใช้ต้องติดตั้ง 2 อย่างนี้ในเครื่องก่อน แล้วจึงค่อย `git clone` โปรเจกต์

### Windows

1. ติดตั้ง Python 3.11 หรือ 3.12 จาก <https://www.python.org/downloads/>
2. ตอนติดตั้ง Python ให้ติ๊ก `Add python.exe to PATH`
3. ติดตั้ง Git จาก <https://git-scm.com/download/win>
4. เปิด PowerShell แล้วตรวจว่าใช้งานได้:

```powershell
py --version
git --version
```

ถ้าเห็นเลข version ทั้งสองคำสั่ง แปลว่าพร้อมติดตั้งโปรเจกต์

### macOS

1. ติดตั้ง Python 3.11 หรือ 3.12 จาก <https://www.python.org/downloads/macos/>
2. ติดตั้ง Git หากเครื่องยังไม่มี

ตรวจว่าใช้งานได้:

```bash
python3 --version
git --version
```

ถ้า macOS แจ้งให้ติดตั้ง Xcode Command Line Tools ตอนรัน `git --version` ให้กดติดตั้งตามที่ระบบแจ้ง แล้วรันคำสั่งเช็กอีกครั้ง

### หมายเหตุ

- Python/Git เป็นโปรแกรมส่วนกลางของเครื่อง ไม่ได้อยู่ในโฟลเดอร์โปรเจกต์
- เมื่อลบ `kruroo_apa_checker` จะลบเฉพาะระบบ APA checker และ dependency ใน `.venv`
- การลบโฟลเดอร์โปรเจกต์จะไม่ลบ Python หรือ Git ออกจากเครื่อง

## ติดตั้งบน macOS

```bash
git clone https://github.com/datakruroo/kruroo_apa_checker.git
cd kruroo_apa_checker

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
python scripts/check_install.py
```

จากนั้นเปิดไฟล์ `.env` แล้วใส่ค่าอย่างน้อย:

```env
OPENAI_API_KEY=your_openai_api_key
```

ถ้าต้องการตรวจ PDF ให้ใส่เพิ่ม:

```env
LLAMA_CLOUD_API_KEY=your_llama_cloud_key
```

## ติดตั้งบน Windows PowerShell

```powershell
git clone https://github.com/datakruroo/kruroo_apa_checker.git
cd kruroo_apa_checker

py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env
python scripts/check_install.py
```

จากนั้นเปิดไฟล์ `.env` แล้วใส่ค่าอย่างน้อย:

```env
OPENAI_API_KEY=your_openai_api_key
```

ถ้า PowerShell ไม่ยอม activate virtual environment ให้รัน:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

หรือใช้ Command Prompt แทน:

```cmd
.venv\Scripts\activate.bat
```

## เปิดใช้งานแบบ Web UI

macOS / Windows:

```bash
streamlit run app.py
```

จากนั้นเปิด browser ที่:

```text
http://localhost:8501
```

ผู้ใช้สามารถอัปโหลด `.docx` หรือ `.pdf` แล้วดาวน์โหลดรายงาน `.docx` ได้จากหน้าเว็บ

## ใช้งานผ่าน command line

เหมาะสำหรับ batch run หรือทดสอบ fixture

macOS:

```bash
python scripts/run_apa_pipeline.py --manuscript "/path/to/paper.docx" --output "outputs/report.docx"
```

Windows PowerShell:

```powershell
python scripts/run_apa_pipeline.py --manuscript "C:\Users\Name\Downloads\paper.docx" --output "outputs\report.docx"
```

ถ้า path มีช่องว่างหรือภาษาไทย ให้ใส่เครื่องหมาย quote รอบ path เสมอ

## รันทดสอบ

ตรวจการติดตั้งเบื้องต้น:

```bash
python scripts/check_install.py
```

รัน automated tests:

```bash
python -m unittest
```

หมายเหตุ: regression tests ที่ต้องใช้ manuscript จริงจะถูก skip หากไม่มีไฟล์ใน `tests/fixtures/`

## การตั้งค่า

ค่าหลักอยู่ใน `.env`

```env
OPENAI_API_KEY=
LLAMA_CLOUD_API_KEY=
BRAVE_SEARCH_API_KEY=
OPENAI_MODEL=gpt-5.4-mini
REPORT_WRITER_MODEL=gpt-5.1
CHECKLIST_PATH=checklists/apa_chula_2568.md
OUTPUT_DIR=outputs
```

อย่า commit ไฟล์ `.env` ขึ้น GitHub

## ข้อควรระวังเรื่องข้อมูลผู้เขียน

- อย่า commit ไฟล์บทความจริงของผู้เขียน
- อย่า commit รายงานผลตรวจจริง
- โฟลเดอร์ `outputs/` ถูก ignore ไว้แล้ว
- ถ้าใช้งานกับบทความจริงจำนวนมาก ควรใช้เครื่องหรือ server ที่ควบคุมสิทธิ์การเข้าถึงได้

## ข้อจำกัดปัจจุบัน

- รายงานเป็นผลตรวจเบื้องต้น ไม่ใช่ผลตรวจ APA ขั้นสุดท้าย
- Metadata จาก Crossref/OpenAlex อาจไม่ครบหรือผิดได้ จึงต้องให้มนุษย์ตรวจเมื่อเป็นข้อมูลสำคัญ
- PDF parsing ขึ้นกับคุณภาพไฟล์และ LlamaCloud
- DOCX ที่มี run/style ซับซ้อนมากอาจต้องสุ่มตรวจด้วยตา
- ระบบไม่ควร auto-fix ผู้แต่ง ปี ชื่อเรื่อง ชื่อวารสาร หรือ DOI suffix

## โครงสร้างไฟล์หลัก

```text
app.py                         Streamlit UI
scripts/run_apa_pipeline.py    CLI runner
src/apa_format_linter.py       ตรวจรูปแบบ APA แบบ rule-based
src/bibliographic_verifier.py  ยืนยัน DOI และหา possible metadata match
src/metadata_comparator.py     เทียบ reference กับ metadata จาก DOI
src/citation_checker.py        ตรวจ in-text citations กับ References
src/report_generator.py        สร้างรายงาน DOCX
tests/                         automated tests
checklists/                    APA checklist
```
