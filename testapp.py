import os
import time
import tempfile
import shutil
import re
import json
import urllib.parse
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from pypdf import PdfReader
import streamlit as st
import google.generativeai as genai

# =============================================================================
# ⚙️ ΡΥΘΜΙΣΕΙΣ & API KEY
# =============================================================================

GEMINI_API_KEY = "TO_API_KEY_SOY_EDO"  # Βάλε το δικό σου

st.set_page_config(page_title="AI Legislative Auditor", page_icon="⚖️", layout="wide")

if not GEMINI_API_KEY:
    st.error("⚠️ Λείπει το GEMINI_API_KEY.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# =============================================================================
# 📜 SYSTEM PROMPT
# =============================================================================
SYSTEM_INSTRUCTIONS = """
... ΒΑΛΕ ΕΔΩ ΟΛΟ ΤΟ PROMPT ΠΟΥ ΕΧΕΙΣ ...
"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/"
}

# =============================================================================
# 🛠️ API ΒΟΥΛΗΣ
# =============================================================================

def get_law_data_from_api(query: str):
    """Ψάχνει στο API της Βουλής και επιστρέφει το πρώτο αποτέλεσμα (dict) ή None."""
    url = "https://www.hellenicparliament.gr/api.ashx"
    params = {"q": "laws", "format": "json"}
    if query.isdigit():
        params["lawnum"] = query
    else:
        params["freetext"] = query

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            st.error(f"API HTTP {r.status_code}: {r.text[:200]}")
            return None

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            st.error(f"API δεν επέστρεψε έγκυρο JSON: {e}")
            st.text(r.text[:500])
            return None

        if isinstance(data, dict) and data.get("TotalRecords", 0) > 0:
            items = data.get("Data") or data.get("data") or []
            if items:
                return items[0]

        st.warning("Το API γύρισε άδειο αποτέλεσμα.")
        return None

    except Exception as e:
        st.error(f"API Error: {e}")
        return None

# =============================================================================
# 🧾 HYBRID PDF (TEXT + OCR)
# =============================================================================

def process_pdf_hybrid(url, file_type):
    """
    Κατεβάζει το PDF.
    1. Προσπαθεί να εξάγει κείμενο με pypdf.
    2. Αν το κείμενο είναι λίγο (<500 chars), το θεωρεί σκαναρισμένο και το ανεβάζει στο Gemini (OCR).
    """
    if not url:
        return "", None, False

    try:
        if not url.startswith("http"):
            url = "https://www.hellenicparliament.gr" + url

        st.write(f"⬇️ Λήψη: {file_type}...")
        res = requests.get(url, headers=HEADERS, timeout=60)
        res.raise_for_status()

        text_content = ""
        try:
            with BytesIO(res.content) as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text() or ""
        except Exception:
            pass

        clean_txt = re.sub(r"\s+", " ", text_content).strip()

        if len(clean_txt) > 500:
            return clean_txt, None, False  # Text PDF

        # Fallback σε OCR (Gemini)
        st.caption(f"⚠️ Το αρχείο '{file_type}' φαίνεται σκαναρισμένο. Ενεργοποίηση OCR...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(res.content)
            tmp_path = tmp.name

        uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
        return "", uploaded_file, True

    except Exception as e:
        st.warning(f"Σφάλμα κατά την επεξεργασία του {file_type}: {e}")
        return "", None, False

# =============================================================================
# 🌐 OPENGOV
# =============================================================================

def find_opengov_smart(law_title):
    """Ψάχνει στο Google για διαβούλευση στο Opengov."""
    stopwords = ["Κύρωση", "Ενσωμάτωση", "Ρυθμίσεις", "Διατάξεις", "του", "την", "και", "για", "με"]
    words = law_title.split()
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    search_query = " ".join(keywords[:6])

    query = f"site:opengov.gr {search_query} διαβούλευση"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "opengov.gr" in href and "google" not in href:
                    return href
                if "/url?q=" in href and "opengov.gr" in href:
                    return href.split("/url?q=")[1].split("&")[0]
    except Exception:
        pass

    return None

def scrape_opengov(url):
    """Κατεβάζει και καθαρίζει κείμενο από σελίδα διαβούλευσης Opengov."""
    if not url:
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        return re.sub(r"\s+", " ", soup.get_text()).strip()[:20000]
    except Exception:
        return ""

# =============================================================================
