# faq_updater.py

import os
import requests
import shutil
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from apscheduler.schedulers.blocking import BlockingScheduler

API_URL = "http://43.230.201.118:6504/metadata.json"
PDF_PATH = "files/oppiWallet_FAQ_updated.pdf"
INDEX_DIR = "faq_vector_index"
LAST_TIMESTAMP_FILE = "files/last_update.txt"
LOG_FILE = "files/faq_updater.log"

embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def log(message: str):
    """Append message with timestamp to log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)  # optional: also print to console

def fetch_new_faqs():
    """Fetch FAQ data from API"""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching API: {e}")
        return []

def get_last_timestamp():
    """Read last processed timestamp from file"""
    if not os.path.exists(LAST_TIMESTAMP_FILE):
        return None
    with open(LAST_TIMESTAMP_FILE, "r") as f:
        return f.read().strip() or None

def set_last_timestamp(ts: str):
    """Update last processed timestamp file"""
    with open(LAST_TIMESTAMP_FILE, "w") as f:
        f.write(ts)

def append_to_pdf(data, pdf_path=PDF_PATH):
    """Append Q&A to PDF in proper format"""
    text_content = ""
    for item in data:
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()
        if q and a:
            text_content += f"Q: {q}\nA: {a}\n\n"

    if not text_content:
        log("⚠️ No new Q&A to append.")
        return False
    
    log(f"✅ Appended {len(data)} new FAQs to {pdf_path}")

    # Write new Q&A to a temporary PDF
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    y = height - 50
    for line in text_content.splitlines():
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(50, y, line)
        y -= 20
    c.save()

    packet.seek(0)
    new_pdf = PdfReader(packet)
    output = PdfWriter()

    # Keep existing pages if PDF exists
    if os.path.exists(pdf_path):
        existing_pdf = PdfReader(open(pdf_path, "rb"))
        for page in existing_pdf.pages:
            output.add_page(page)

    # Add new pages
    for page in new_pdf.pages:
        output.add_page(page)

    with open(pdf_path, "wb") as f:
        output.write(f)

    print(f"✅ Appended {len(data)} new FAQs to {pdf_path}")
    return True

def rebuild_faiss(pdf_path=PDF_PATH):
    """Rebuild FAISS index from updated PDF"""
    from langchain_community.document_loaders import PyPDFLoader

    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)

    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    vectorstore = FAISS.from_documents(chunks, embedding=embedding_model)
    vectorstore.save_local(INDEX_DIR)

    print("✅ FAISS index rebuilt successfully.")

def run_updater():
    print(f"\n⏳ Running FAQ updater at {datetime.now()}")

    faqs = fetch_new_faqs()
    if not faqs:
        log("✅ No new FAQ updates since last check.")
        return
    
    last_ts = get_last_timestamp()
    new_faqs = []

    for item in faqs:
        log(f"    Q: {item.get('question','')}")
        ts = item.get("timestamp")
        if not ts:
            continue
        if (not last_ts) or (ts > last_ts):
            new_faqs.append(item)

    if not new_faqs:
        print("✅ No new FAQ updates since last check.")
        return

    # Append to PDF
    updated = append_to_pdf(new_faqs)
    if updated:
        rebuild_faiss()
        # update last timestamp with latest
        max_ts = max(f["timestamp"] for f in new_faqs if "timestamp" in f)
        set_last_timestamp(max_ts)
        log(f"🕒 Updated last timestamp to {max_ts}")

if __name__ == "__main__":
    # Scheduler: run every 1 hour
    scheduler = BlockingScheduler()
    scheduler.add_job(run_updater, "interval", hours=1)
    print("🚀 FAQ updater started, checking every 1 hour...")
    run_updater()  # run once at startup
    scheduler.start()
