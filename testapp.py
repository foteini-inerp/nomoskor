import os
import time
import tempfile
import shutil
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from pypdf import PdfReader
import streamlit as st
import google.generativeai as genai

# =============================================================================
# ⚙️ ΡΥΘΜΙΣΕΙΣ
# =============================================================================

# Βάλε το κλειδί σου εδώ
GEMINI_API_KEY = "AIzaSyDj0m9d1hs3eWaHUWhHeLhsmlfKYt4hgz4"

st.set_page_config(page_title="AI Legislative Auditor", page_icon="⚖️", layout="wide")

if not GEMINI_API_KEY:
    st.error("⚠️ Λείπει το GEMINI_API_KEY.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# =============================================================================
# 📜 ΤΟ ΑΥΣΤΗΡΟ SYSTEM PROMPT (ΟΛΟΚΛΗΡΟ)
# =============================================================================
SYSTEM_INSTRUCTIONS = """
Ενεργείς ως ο Ανώτατος Ελεγκτής Ποιότητας Νομοθεσίας (Supreme Legislative Auditor).
Έχεις στη διάθεσή σου τα πλήρη κείμενα του νομοσχεδίου (Σχέδιο, Τροπολογίες, Εκθέσεις) και στοιχεία διαβούλευσης.

Η αποστολή σου είναι να διενεργήσεις έναν ΕΛΕΓΧΟ ΒΑΘΟΥΣ (DEEP AUDIT) βασισμένο σε 3 πυλώνες.

--- ΠΥΛΩΝΑΣ Α: Ο ΔΕΚΑΛΟΓΟΣ ΤΗΣ ΚΑΛΗΣ ΝΟΜΟΘΕΤΗΣΗΣ ---
Απάντησε ΑΥΣΤΗΡΑ με [ΝΑΙ/ΟΧΙ/ΜΕΡΙΚΩΣ] και ΤΕΚΜΗΡΙΩΣΗ για κάθε σημείο:

1. Έγινε προ-κοινοβουλευτική διαβούλευση; 
   - 1.1. Αν ναι, διήρκεσε ΠΕΡΙΣΣΟΤΕΡΟ ή ΛΙΓΟΤΕΡΟ από 14 ημέρες; (Χρησιμοποίησε τις ημερομηνίες που σου δίνονται από το Opengov ή την ΑΣΡ).
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

# =============================================================================
# 🛠️ ΛΕΙΤΟΥΡΓΙΕΣ ΑΝΑΖΗΤΗΣΗΣ (ΔΙΟΡΘΩΜΕΝΕΣ ΓΙΑ ΑΚΡΙΒΕΙΑ)
# =============================================================================

def get_law_data_strict(query):
    """
    Ψάχνει στο API. Αν ο χρήστης έδωσε αριθμό (π.χ. 4940), φιλτράρει τα αποτελέσματα
    για να βρει ΑΚΡΙΒΩΣ αυτόν τον νόμο, αποφεύγοντας άσχετα ή παλιά αποτελέσματα.
    """
    url = "https://www.hellenicparliament.gr/api.ashx"
    params = {"q": "laws", "format": "json"}
    
    # Καθαρισμός input (π.χ. αν έδωσε "4940/2022" κρατάμε το "4940")
    clean_query = query.strip()
    if "/" in clean_query:
        clean_query = clean_query.split("/")[0]

    if clean_query.isdigit():
        params["lawnum"] = clean_query
    else:
        params["freetext"] = clean_query

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        data = r.json()
        
        if data.get('TotalRecords', 0) > 0:
            items = data['Data']
            selected_law = items[0] # Default: το πρώτο

            # ΑΥΣΤΗΡΟΣ ΕΛΕΓΧΟΣ: Αν ψάχνουμε αριθμό, βεβαιωνόμαστε ότι ταιριάζει
            if clean_query.isdigit():
                for item in items:
                    if str(item.get('LawNum')) == clean_query:
                        selected_law = item
                        break
            
            # Συλλογή αρχείων
            all_files = []
            
            # 1. LawPhotocopy
            if selected_law.get("LawPhotocopy"):
                for f in selected_law["LawPhotocopy"]:
                    all_files.append({"url": f.get("File"), "type": f.get("FileType", "Έγγραφο"), "desc": ""})
            
            # 2. Amendments (Τροπολογίες)
            if selected_law.get("Amendments"):
                for am in selected_law["Amendments"]:
                    desc = am.get("Description", "").replace('\r\n', ' ')
                    all_files.append({"url": am.get("File"), "type": "ΤΡΟΠΟΛΟΓΙΑ", "desc": desc})
            
            # 3. VotedLaws
            if selected_law.get("VotedLaws"):
                for v in selected_law["VotedLaws"]:
                    all_files.append({"url": v.get("File"), "type": "ΨΗΦΙΣΘΕΙΣ ΝΟΜΟΣ", "desc": "Τελικό Κείμενο"})

            # 4. RecommReport
            if selected_law.get("RecommReport"):
                for r in selected_law["RecommReport"]:
                    all_files.append({"url": r.get("File"), "type": "ΕΚΘΕΣΗ ΕΠΙΤΡΟΠΗΣ", "desc": ""})

            return {
                "title": selected_law.get("Title"),
                "law_num": selected_law.get("LawNum"),
                "files": all_files
            }

    except Exception as e:
        st.error(f"API Error: {e}")
        return None
    return None

def find_opengov_smart(law_title):
    stopwords = ["Κύρωση", "Ενσωμάτωση", "Ρυθμίσεις", "Διατάξεις", "του", "την", "και", "για", "με", "τον"]
    words = law_title.split()
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    search_query = " ".join(keywords[:6])
    
    query = f"site:opengov.gr {search_query} διαβούλευση"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if "opengov.gr" in href and "google" not in href:
                return href
            if "/url?q=" in href and "opengov.gr" in href:
                return href.split("/url?q=")[1].split("&")[0]
    except: pass
    return None

def scrape_opengov(url):
    if not url: return "", []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        for s in soup(["script", "style", "nav", "footer"]): s.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text()).strip()
        dates = re.findall(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b", text)
        return text[:20000], dates
    except: return "", []

def process_pdf_hybrid(url, file_type):
    if not url: return "", None, False
    try:
        if not url.startswith("http"): url = "https://www.hellenicparliament.gr" + url
        res = requests.get(url, headers=HEADERS, timeout=60)
        
        text_content = ""
        try:
            with BytesIO(res.content) as f:
                reader = PdfReader(f)
                for page in reader.pages: text_content += page.extract_text() or ""
        except: pass
            
        clean_txt = re.sub(r'\s+', ' ', text_content).strip()
        if len(clean_txt) > 500: return clean_txt, None, False 
            
        # OCR
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(res.content)
            tmp_path = tmp.name
        uf = genai.upload_file(tmp_path, mime_type="application/pdf")
        return "", uf, True 
    except Exception as e:
        return "", None, False

# =============================================================================
# 🧠 AI ENGINE
# =============================================================================

def run_auditor(context_text, uploaded_files, opengov_text, dates, metadata):
    parts = [f"""
    ΤΑΥΤΟΤΗΤΑ ΝΟΜΟΥ: {metadata}
    
    ΣΤΟΙΧΕΙΑ ΔΙΑΒΟΥΛΕΥΣΗΣ (OPENGOV):
    - Κείμενο: {opengov_text}
    - Εντοπισμένες Ημερομηνίες: {dates}
    
    ΠΕΡΙΕΧΟΜΕΝΟ ΑΡΧΕΙΩΝ (TEXT):
    {context_text[:70000]}
    """]
    
    if uploaded_files:
        parts.append("\n--- OCR FILES ---\n")
        for f in uploaded_files: parts.append(f)
        
    parts.append(SYSTEM_INSTRUCTIONS)
    
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        if uploaded_files:
            st.info("⏳ Αναμονή OCR...")
            while True:
                states = [genai.get_file(uf.name).state.name for uf in uploaded_files]
                if all(s == "ACTIVE" for s in states): break
                if any(s == "FAILED" for s in states): return "Error: OCR Failed"
                time.sleep(2)
        
        response = model.generate_content(parts)
        return response.text
    except Exception as e: return f"AI Error: {e}"

# =============================================================================
# 🖥️ MAIN UI
# =============================================================================

def main():
    st.title("🏛️ AI Legislative Auditor (Full & Strict)")
    
    query = st.text_input("🔍 Αριθμός Νόμου (π.χ. 4940) ή Λέξεις Κλειδιά:")
    
    if st.button("Έναρξη", type="primary") and query:
        
        with st.spinner("1️⃣ Ανάκτηση φακέλου από Βουλή..."):
            law_data = get_law_data_strict(query)
            
        if not law_data:
            st.error("❌ Δεν βρέθηκε ο νόμος (ή το API κόλλησε).")
            return
            
        title = law_data['title']
        law_num = law_data.get('law_num', 'N/A')
        files = law_data['files']
        
        st.success(f"✅ Βρέθηκε: Νόμος {law_num} - {title[:80]}...")
        st.write(f"📂 Εντοπίστηκαν **{len(files)} έγγραφα**.")
        
        # Opengov
        og_url = find_opengov_smart(title)
        og_text = ""
        og_dates = []
        if og_url:
            st.info(f"🌍 Opengov: {og_url}")
            og_text, og_dates = scrape_opengov(og_url)
            if og_dates: st.write(f"📅 Dates: {', '.join(og_dates[:4])}")
        
        # Process Files
        full_text_context = ""
        ocr_files = []
        progress = st.progress(0)
        
        for i, f in enumerate(files):
            url = f['url']
            ftype = f['type']
            desc = f['desc']
            
            txt, fobj, is_ocr = process_pdf_hybrid(url, ftype)
            
            header = f"\n--- {ftype} ---\nΠεριγραφή: {desc}\n"
            
            if is_ocr:
                ocr_files.append(fobj)
                full_text_context += f"{header}[IMAGE FOR OCR]\n"
            elif txt:
                full_text_context += f"{header}{txt[:15000]}\n"
                
            progress.progress((i + 1) / len(files))
            
        st.divider()
        with st.spinner("🤖 Ο Ελεγκτής εξετάζει (Δεκάλογος & Εγχειρίδιο)..."):
            rep = run_auditor(full_text_context, ocr_files, og_text, og_dates, title)
            st.markdown(rep)
            st.download_button("Download Report", rep, file_name="audit_report.txt")

if __name__ == "__main__":
    main()
