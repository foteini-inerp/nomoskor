import os
import time
import tempfile
import shutil
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup
import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions

# =============================================================================
# ⚙️ ΡΥΘΜΙΣΕΙΣ & API KEY
# =============================================================================

# Βάλε το κλειδί σου εδώ
GEMINI_API_KEY = "TO_API_KEY_SOY_EDO"

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
# 🛠️ HELPER FUNCTIONS
# =============================================================================

def safe_get(url, params=None):
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response
    except Exception as e:
        return None

def download_pdf(url, folder, prefix="doc"):
    try:
        if url.startswith("/"):
            url = "https://www.hellenicparliament.gr" + url
        res = safe_get(url)
        if res:
            filename = url.split("/")[-1].split("?")[0]
            if not filename.endswith(".pdf"): filename += ".pdf"
            
            # Αφαιρούμε επικίνδυνους χαρακτήρες από το όνομα
            filename = "".join([c for c in filename if c.isalnum() or c in (' ', '.', '_')]).strip()
            
            save_path = os.path.join(folder, f"{prefix}_{filename}")
            with open(save_path, "wb") as f:
                f.write(res.content)
            return save_path
    except Exception:
        pass
    return None

# =============================================================================
# 1️⃣ API ΒΟΥΛΗΣ
# =============================================================================

def search_parliament_api(query):
    """Αναζήτηση στο API της Βουλής."""
    api_url = "https://www.hellenicparliament.gr/api.ashx"
    params = {"q": "laws", "freetext": query, "pageSize": 5}
    
    res = safe_get(api_url, params)
    if res:
        try:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                law = data[0]
                return {
                    "id": law.get("LawId") or law.get("id"),
                    "title": law.get("Title") or law.get("title"),
                    "url": law.get("Url") # Ενδεχομένως να επιστρέφει URL
                }
        except:
            pass
    return None

# =============================================================================
# 2️⃣ OPENGOV SCAN
# =============================================================================

def search_opengov(law_title):
    """Google Search για Opengov."""
    query = f"site:opengov.gr {law_title} διαβούλευση"
    google_url = f"https://www.google.com/search?q={quote(query)}"
    
    res = safe_get(google_url)
    if not res: return None, "Google Block (429)"

    soup = BeautifulSoup(res.text, "html.parser")
    found_link = None
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "opengov.gr" in href and "google" not in href:
            found_link = href
            break
        if "/url?q=" in href and "opengov.gr" in href:
            found_link = href.split("/url?q=")[1].split("&")[0]
            break
            
    if found_link:
        og_res = safe_get(found_link)
        if og_res:
            og_soup = BeautifulSoup(og_res.content, "html.parser")
            for tag in og_soup(["script", "style", "nav", "footer"]): tag.decompose()
            text = og_soup.get_text(separator=" ", strip=True)[:25000]
            return found_link, text
            
    return None, ""

# =============================================================================
# 3️⃣ PARLIAMENT SCRAPING
# =============================================================================

def scrape_parliament_page(url, temp_dir):
    """Scrapes PDFs from Parliament page."""
    res = safe_get(url)
    if not res: return []
        
    soup = BeautifulSoup(res.content, "html.parser")
    pdf_files = []
    
    keywords = {
        "αιτιολογική": "Aitiologiki", "σχέδιο νόμου": "Sxedio_Nomou",
        "ψηφισθέν": "Psifisthen", "συνεπειών": "Analysi_Synepeion",
        "γλκ": "Ekthesi_GLK", "ειδική": "Eidiki_Ekthesi"
    }
    
    found_types = []
    for link in soup.find_all("a", href=True):
        href = link['href']
        text = link.get_text().lower()
        
        if ".pdf" in href or "UserFiles" in href:
            for key, fname in keywords.items():
                if key in text and key not in found_types:
                    path = download_pdf(href, temp_dir, fname)
                    if path:
                        pdf_files.append(path)
                        found_types.append(key)
                    break
    return pdf_files

# =============================================================================
# 🧠 GEMINI ANALYSIS
# =============================================================================

def analyze_with_gemini(files, opengov_text, law_title):
    uploaded_files = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, file_path in enumerate(files):
        status_text.text(f"📤 Ανέβασμα: {os.path.basename(file_path)}")
        try:
            # ΕΔΩ ΗΤΑΝ ΤΟ ΛΑΘΟΣ ΠΡΙΝ - ΤΩΡΑ ΔΙΟΡΘΩΘΗΚΕ
            uf = genai.upload_file(file_path, mime_type="application/pdf")
            uploaded_files.append(uf)
        except Exception as e:
            st.error(f"Σφάλμα Upload για {file_path}: {e}")
        
        progress_bar.progress((i + 1) / len(files))

    if not uploaded_files:
        return "❌ Απέτυχε το ανέβασμα όλων των αρχείων στο AI."

    status_text.text("⏳ Το AI επεξεργάζεται τα έγγραφα (OCR)...")
    
    # Αναμονή για processing
    while True:
        try:
            states = [genai.get_file(uf.name).state.name for uf in uploaded_files]
            if all(s == "ACTIVE" for s in states):
                break
            if any(s == "FAILED" for s in states):
                st.error("Κάποιο αρχείο απέτυχε στην επεξεργασία Google AI.")
                break
            time.sleep(2)
        except Exception as e:
            st.warning(f"Καθυστέρηση στον έλεγχο κατάστασης: {e}")
            time.sleep(2)
    
    status_text.text("🤖 Ο Ελεγκτής συντάσσει το πόρισμα...")
    model = genai.GenerativeModel(model_name="gemini-1.5-pro", system_instruction=SYSTEM_INSTRUCTIONS)
    
    prompt = f"""
    ΑΝΤΙΚΕΙΜΕΝΟ ΕΛΕΓΧΟΥ: {law_title}
    
    ΔΕΔΟΜΕΝΑ ΔΙΑΒΟΥΛΕΥΣΗΣ (OPENGOV):
    {opengov_text}
    
    ΕΝΤΟΛΗ:
    Διάβασε τα επισυναπτόμενα αρχεία. Συνδύασέ τα με τα δεδομένα της διαβούλευσης.
    Βγάλε το Πόρισμα Ελέγχου βάσει του Δεκαλόγου και του Εγχειριδίου.
    """
    
    try:
        response = model.generate_content(
            uploaded_files + [prompt],
            request_options={"timeout": 600}
        )
        return response.text
    except Exception as e:
        return f"Σφάλμα AI κατά τη σύνταξη: {e}"

# =============================================================================
# 🖥️ MAIN UI
# =============================================================================

def main():
    st.title("🏛️ AI Legislative Auditor (Τριπλή Σάρωση)")
    st.markdown("---")

    col1, col2 = st.columns([3, 1])
    with col1:
        law_query = st.text_input("🔍 Αριθμός Νόμου ή Τίτλος (π.χ. 4940/2022):")
        manual_url = st.text_input("🔗 (Προαιρετικό) Χειροκίνητο Link Βουλής:")
    with col2:
        st.write("##")
        start_btn = st.button("🚀 Έναρξη Ελέγχου", type="primary")

    if start_btn and (law_query or manual_url):
        temp_dir = tempfile.mkdtemp()
        try:
            # 1. API Check
            law_data = None
            if not manual_url:
                with st.spinner("1️⃣ Αναζήτηση στο API Βουλής..."):
                    law_data = search_parliament_api(law_query)
            
            law_title = law_data.get("title", law_query) if law_data else law_query
            final_url = manual_url
            if law_data and law_data.get("id") and not final_url:
                final_url = f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id={law_data['id']}"
            
            # 2. OpenGov Check
            og_link, og_text = None, ""
            with st.spinner("2️⃣ Αναζήτηση Διαβούλευσης (OpenGov)..."):
                og_link, og_text = search_opengov(law_title)
            
            # 3. Scraping
            pdfs = []
            if final_url:
                with st.spinner("3️⃣ Λήψη Εγγράφων από Βουλή..."):
                    pdfs = scrape_parliament_page(final_url, temp_dir)
            
            # Checklist UI
            st.markdown("### ✅ Αποτελέσματα Σάρωσης:")
            c1, c2, c3 = st.columns(3)
            c1.metric("Link Βουλής", "✅" if final_url else "❌")
            c2.metric("OpenGov", "✅" if og_link else "❌")
            c3.metric("Αρχεία PDF", len(pdfs))
            
            if pdfs:
                st.divider()
                st.subheader("🤖 Πόρισμα Ελέγχου")
                report = analyze_with_gemini(pdfs, og_text, law_title)
                st.markdown(report)
                st.download_button("💾 Κατέβασμα Πορίσματος", report, file_name="audit_report.txt")
            else:
                st.error("❌ Δεν βρέθηκαν αρχεία PDF. Ελέγξτε τα κριτήρια αναζήτησης.")

        finally:
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
