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
from google.api_core import exceptions

# =============================================================================
# ⚙️ ΡΥΘΜΙΣΕΙΣ & API KEY
# =============================================================================

# Βάλε το κλειδί σου εδώ
GEMINI_API_KEY = "AIzaSyB4gLIzWq51OKAdG37vIhLL8X0Z4uNd9UU"

st.set_page_config(page_title="AI Legislative Auditor", page_icon="⚖️", layout="wide")

if not GEMINI_API_KEY:
    st.error("⚠️ Λείπει το GEMINI_API_KEY.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# =============================================================================
# 📜 ΤΟ ΑΥΣΤΗΡΟ SYSTEM PROMPT (ΠΛΗΡΕΣ)
# =============================================================================
SYSTEM_INSTRUCTIONS = """
Ενεργείς ως ο Ανώτατος Ελεγκτής Ποιότητας Νομοθεσίας (Supreme Legislative Auditor).
Έχεις στη διάθεσή σου τα πλήρη κείμενα του νομοσχεδίου και στοιχεία διαβούλευσης.

Η αποστολή σου είναι να διενεργήσεις έναν ΕΛΕΓΧΟ ΒΑΘΟΥΣ (DEEP AUDIT) βασισμένο σε 3 πυλώνες.

--- ΠΥΛΩΝΑΣ Α: Ο ΔΕΚΑΛΟΓΟΣ ΤΗΣ ΚΑΛΗΣ ΝΟΜΟΘΕΤΗΣΗΣ ---
Απάντησε ΑΥΣΤΗΡΑ με [ΝΑΙ/ΟΧΙ/ΜΕΡΙΚΩΣ] και ΤΕΚΜΗΡΙΩΣΗ για κάθε σημείο:

1. Έγινε προ-κοινοβουλευτική διαβούλευση; 
   - 1.1. Αν ναι, διήρκεσε ΠΕΡΙΣΣΟΤΕΡΟ ή ΛΙΓΟΤΕΡΟ από 14 ημέρες; (Χρησιμοποίησε τις ημερομηνίες που σου δίνονται από το Opengov).
   - 1.2. Παρουσιάστηκαν τα ευρήματα σε ξεχωριστή έκθεση που συνόδευε το νομοσχέδιο; (Ελήφθησαν υπόψη τα σχόλια;)

2. Ο μέσος χρόνος που δόθηκε στην ακρόαση φορέων υπερβαίνει τα 5 λεπτά; (Αναζήτησε ενδείξεις στα κείμενα).

3. Συγκρίνοντας το αρχικό σχέδιο με το τελικό, υπάρχουν διατάξεις που εμφανίστηκαν ως (πολυ-)τροπολογίες; (Ψάξε για "Λοιπές/Επείγουσες διατάξεις" στο τέλος του νόμου που είναι άσχετες με τον τίτλο).

4. Υπάρχει «επιχρύσωση» (gold-plating); (Προσθήκη εθνικών βαρών σε διεθνείς κανόνες).

5. Υπάρχουν ειδικές διατάξεις που αφορούν τους ορεινούς όγκους και τα νησιά; (Ρήτρα Νησιωτικότητας - Έλεγξε την Έκθεση Συνεπειών).

6. Υπάρχει τεκμηριωμένη ανάλυση κόστους-ωφέλειας; (Υπάρχουν ΠΟΣΟΤΙΚΑ στοιχεία για το ΟΦΕΛΟΣ ή μόνο αόριστες περιγραφές; Το κόστος συνήθως υπάρχει στην έκθεση ΓΛΚ).

7. Υπάρχουν διατάξεις που απλουστεύουν/καταργούν διοικητικές επιβαρύνσεις; (Ή μήπως προσθέτουν γραφειοκρατία;).

8. Υπάρχουν εξουσιοδοτήσεις για την έκδοση Υπουργικών Αποφάσεων για θέματα του κυρίως αντικειμένου; (Το φαινόμενο της "Λευκής Επιταγής" - Μέτρα τες).

9. Αναφέρονται ειδικότεροι μηχανισμοί εφαρμογής; (Χρονοδιαγράμματα, πλατφόρμες).

10. Υπάρχουν δυσκολίες στην κατανόηση του νόμου; (Συντακτικά λάθη, αοριστίες).

--- ΠΥΛΩΝΑΣ Β: ΕΛΕΓΧΟΣ ΣΥΜΒΑΤΟΤΗΤΑΣ ΜΕ ΤΟ "ΕΓΧΕΙΡΙΔΙΟ 2020" ---
Έλεγξε την "Ανάλυση Συνεπειών Ρύθμισης" (ΑΣΡ) και την Αιτιολογική Έκθεση:
* **Αρχή της Αναγκαιότητας:** Τεκμηριώνεται πειστικά γιατί χρειάζεται νέος νόμος;
* **Πίνακας Τροποποιούμενων Διατάξεων:** Υπάρχει σαφής πίνακας παλαιού vs νέου δικαίου;
* **Διοικητικό Βάρος:** Υπολογίζεται το κόστος σε ανθρωποώρες για τους πολίτες/υπαλλήλους;

--- ΠΥΛΩΝΑΣ Γ: ΓΛΩΣΣΙΚΟΣ ΕΛΕΓΧΟΣ & ΚΡΙΤΙΚΗ (LINGUISTIC AUDIT) ---
* **Ξύλινη Γλώσσα:** Εντόπισε όρους όπως "εξορθολογισμός", "βέλτιστη πρακτική", "καινοτομία" αν χρησιμοποιούνται χωρίς συγκεκριμένο νομικό ορισμό.
* **Αοριστία:** Εντόπισε φράσεις όπως "κατά την κρίση του οργάνου", "εντός ευλόγου χρόνου".
* **Πολυνομία:** Εντόπισε αλυσίδες παραπομπών (π.χ. "άρθρο Χ του ν.Α όπως τροποποιήθηκε με το ν.Β...").

--- ΤΕΛΙΚΟ ΠΟΡΙΣΜΑ (SCORECARD) ---
Δώσε βαθμολογία (0-10) και τα 3 σοβαρότερα "Κόκκινα Σημεία" (Red Flags).
"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

# =============================================================================
# 🛠️ HELPER FUNCTIONS (API & HYBRID DOWNLOAD)
# =============================================================================

def get_law_data_from_api(query):
    """Ψάχνει στο API της Βουλής και επιστρέφει όλο το JSON αντικείμενο."""
    url = "https://www.hellenicparliament.gr/api.ashx"
    # Αν είναι αριθμός (π.χ. 4940) ψάχνει με lawnum, αλλιώς με freetext
    params = {"q": "laws", "format": "json"}
    
    if query.isdigit():
        params["lawnum"] = query
    else:
        params["freetext"] = query
        
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        # Έλεγχος αν βρέθηκαν εγγραφές
        if data.get('TotalRecords', 0) > 0:
            return data['Data'][0] # Επιστρέφει τον πρώτο νόμο που βρήκε
    except Exception as e:
        st.error(f"API Error: {e}")
    return None

def process_pdf_hybrid(url, file_type):
    """
    Κατεβάζει το PDF.
    1. Προσπαθεί να εξάγει κείμενο (Text) με pypdf.
    2. Αν το κείμενο είναι λίγο (<500 chars), το θεωρεί εικόνα και το ανεβάζει στο Gemini για OCR.
    """
    if not url: return "", None, False
    
    try:
        # Διόρθωση URL
        if not url.startswith("http"): 
            url = "https://www.hellenicparliament.gr" + url
            
        st.write(f"⬇️ Λήψη: {file_type}...")
        res = requests.get(url, headers=HEADERS, timeout=60)
        res.raise_for_status()
        
        # Προσπάθεια εξαγωγής κειμένου
        text_content = ""
        try:
            with BytesIO(res.content) as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text() or ""
        except:
            pass # Αν αποτύχει το pypdf, συνεχίζουμε με OCR
            
        clean_txt = re.sub(r'\s+', ' ', text_content).strip()
        
        # Λογική απόφασης: Κείμενο ή Εικόνα;
        if len(clean_txt) > 500:
            return clean_txt, None, False # Είναι Text PDF
            
        # Fallback σε OCR (Gemini Vision)
        st.caption(f"⚠️ Το αρχείο '{file_type}' φαίνεται σκαναρισμένο. Ενεργοποίηση OCR...")
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(res.content)
            tmp_path = tmp.name
            
        uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
        return "", uploaded_file, True # Είναι Image PDF
        
    except Exception as e:
        st.warning(f"Σφάλμα κατά την επεξεργασία του {file_type}: {e}")
        return "", None, False

def find_opengov_smart(law_title):
    """Ψάχνει στο Google για τη διαβούλευση (Opengov)."""
    # Αφαιρούμε κοινές λέξεις για καλύτερη αναζήτηση
    stopwords = ["Κύρωση", "Ενσωμάτωση", "Ρυθμίσεις", "Διατάξεις", "του", "την", "και", "για", "με"]
    words = law_title.split()
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    search_query = " ".join(keywords[:6])
    
    query = f"site:opengov.gr {search_query} διαβούλευση"
    # ΧΡΗΣΗ urllib.parse.quote (ΔΙΟΡΘΩΘΗΚΕ)
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if "opengov.gr" in href and "google" not in href:
                    return href
                if "/url?q=" in href and "opengov.gr" in href:
                    return href.split("/url?q=")[1].split("&")[0]
    except:
        pass
    return None

def scrape_opengov(url):
    """Κατεβάζει το κείμενο από το Opengov."""
    if not url: return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        # Καθαρισμός
        for s in soup(["script", "style", "nav", "footer"]): s.decompose()
        return re.sub(r'\s+', ' ', soup.get_text()).strip()[:20000]
    except: 
        return ""

# =============================================================================
# 🧠 AI ANALYSIS
# =============================================================================

def run_auditor(law_text, uploaded_files, opengov_text, metadata):
    # Ετοιμασία Prompt με context
    intro_text = f"""
    ΤΑΥΤΟΤΗΤΑ ΝΟΜΟΥ:
    {metadata}

    ΚΕΙΜΕΝΟ ΑΠΟ OPENGOV (ΔΙΑΒΟΥΛΕΥΣΗ):
    {opengov_text}

    ΚΕΙΜΕΝΟ ΑΠΟ PDF (που διαβάστηκαν ως Text):
    {law_text[:50000]}
    """
    
    parts = [intro_text]
    
    # Προσθήκη αρχείων για OCR
    if uploaded_files:
        parts.append("\n--- ΑΚΟΛΟΥΘΟΥΝ ΣΚΑΝΑΡΙΣΜΕΝΑ ΕΓΓΡΑΦΑ ΓΙΑ ΕΛΕΓΧΟ ---\n")
        for f in uploaded_files:
            parts.append(f)
            
    parts.append(SYSTEM_INSTRUCTIONS) # Το αυστηρό ερωτηματολόγιο
    
    try:
        # ΧΡΗΣΗ ΤΟΥ GEMINI 2.0 FLASH (ΔΙΟΡΘΩΘΗΚΕ)
        model = genai.GenerativeModel('models/gemini-2.0-flash') 
        
        # Έλεγχος ετοιμότητας αρχείων
        if uploaded_files:
            st.info("⏳ Αναμονή για επεξεργασία αρχείων από Google...")
            while True:
                states = [genai.get_file(uf.name).state.name for uf in uploaded_files]
                if all(s == "ACTIVE" for s in states): break
                if any(s == "FAILED" for s in states): st.error("Αποτυχία OCR"); return "Error"
                time.sleep(2)
        
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"Σφάλμα AI: {e}"

# =============================================================================
# 🖥️ MAIN UI
# =============================================================================

def main():
    st.title("🏛️ AI Legislative Auditor (Hybrid Engine)")
    st.caption("API Βουλής + Hybrid OCR + Full Checks + Gemini 2.0 Flash")
    
    query = st.text_input("🔍 Αριθμός Νόμου (π.χ. 4940) ή Λέξεις Κλειδιά:")
    
    if st.button("Έναρξη Ελέγχου", type="primary") and query:
        
        # 1. API SEARCH & METADATA
        with st.spinner("1️⃣ Αναζήτηση στο API της Βουλής..."):
            api_data = get_law_data_from_api(query)
            
        if not api_data:
            st.error("❌ Δεν βρέθηκε ο νόμος στο API.")
            return
            
        title = api_data.get('Title', 'Άγνωστος Τίτλος')
        st.success(f"✅ Βρέθηκε: {title}")
        
        # 2. OPENGOV SEARCH
        og_url = find_opengov_smart(title)
        og_text = ""
        if og_url:
            st.info(f"🌍 Opengov Link: {og_url}")
            og_text = scrape_opengov(og_url)
        else:
            st.warning("⚠️ Δεν βρέθηκε αυτόματα η διαβούλευση.")

        # 3. DOWNLOAD FILES (Hybrid Method)
        # Το API της Βουλής επιστρέφει λίστα 'LawPhotocopy' με τα URLs
        files_list = api_data.get('LawPhotocopy', [])
        st.write(f"📂 Βρέθηκαν {len(files_list)} αρχεία στο API.")
        
        text_content = ""
        ocr_files = []
        
        progress = st.progress(0)
        
        for i, f in enumerate(files_list):
            url = f.get('File')
            ftype = f.get('FileType', 'Unknown')
            
            if url:
                # ΕΔΩ ΕΙΝΑΙ Η ΜΑΓΕΙΑ: Κατεβάζει και αποφασίζει (Text vs Image)
                txt, file_obj, is_ocr = process_pdf_hybrid(url, ftype)
                
                if is_ocr:
                    ocr_files.append(file_obj)
                elif txt:
                    text_content += f"\n--- ΑΡΧΕΙΟ: {ftype} ---\n{txt}\n"
            
            progress.progress((i + 1) / len(files_list))
            
        st.success(f"Επεξεργασία ολοκληρώθηκε: {len(ocr_files)} αρχεία για OCR, {len(text_content)} χαρακτήρες κειμένου.")
        
        # 4. AUDIT
        st.divider()
        with st.spinner("🤖 Ο Ελεγκτής εξετάζει τα δεδομένα..."):
            audit_report = run_auditor(text_content, ocr_files, og_text, json.dumps(api_data, ensure_ascii=False))
            st.markdown(audit_report)
            st.download_button("💾 Κατέβασμα Πορίσματος", audit_report, file_name="audit.md")

if __name__ == "__main__":
    main()
