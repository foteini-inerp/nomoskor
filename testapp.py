import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from io import BytesIO
import json
import re
import tempfile
import time

# --- 1. ΡΥΘΜΙΣΕΙΣ ---
st.set_page_config(page_title="Legislative Auditor AI (Official Manuals)", page_icon=":balance_scale:", layout="wide")

st.markdown("""
<style>
    .score-card { background-color: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #2e7d32; }
    .big-score { font-size: 48px; font-weight: bold; color: #2e7d32; }
    .stButton>button { width: 100%; background-color: #1565C0; color: white; border-radius: 5px; }
    .manual-badge { background-color: #e0f7fa; color: #006064; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #006064;}
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Legislative Auditor AI")
st.caption("V23: Εκπαιδευμένο με το Εγχειρίδιο Νομοπαρασκευαστικής Μεθοδολογίας")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("Ρυθμίσεις")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ API Key loaded!")
    else:
        api_key = st.text_input("Google Gemini API Key", type="password")
    
    if api_key: 
        genai.configure(api_key=api_key)

# --- 3. FUNCTIONS ---

def get_law_from_api(lawnum):
    url = "https://www.hellenicparliament.gr/api.ashx"
    params = {"q": "laws", "lawnum": lawnum, "format": "json"}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get('TotalRecords', 0) > 0:
            return data['Data'][0]
    except: pass
    return None

def find_opengov_smart(law_title):
    # Αφαίρεση θορύβου για καλύτερη αναζήτηση
    stopwords = ["Κύρωση", "Ενσωμάτωση", "Ρυθμίσεις", "Διατάξεις", "του", "την", "και", "για", "με"]
    words = law_title.split()
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    search_query = " ".join(keywords[:6])
    query = f"site:opengov.gr {search_query}"
    
    try:
        for url in search(query, num_results=2):
            if "opengov.gr" in url: return url
    except: pass
    return None

def scrape_opengov(url):
    if not url: return ""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        return re.sub(r'\s+', ' ', soup.get_text()).strip()[:20000]
    except: return ""

def ocr_scanned_pdf(file_bytes):
    """OCR για εικόνες/σκαναρισμένα PDF μέσω Gemini Vision"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
            
        uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
        time.sleep(2) # Αναμονή επεξεργασίας
        
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(
            [uploaded_file, "Extract all text from this document verbatim."],
            request_options={"timeout": 600}
        )
        return response.text
    except Exception as e:
        return ""

def process_pdf_smart(url, ftype):
    """Έξυπνος διακόπτης Text vs OCR"""
    if not url: return "", "N/A"
    try:
        if not url.startswith("http"): url = "https://www.hellenicparliament.gr" + url
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        file_bytes = res.content
        
        # 1. Πρώτα δοκιμή Text extraction
        text_content = ""
        with BytesIO(file_bytes) as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text_content += page.extract_text() or ""
        
        clean_txt = re.sub(r'\s+', ' ', text_content).strip()
        
        # 2. Αν βρήκαμε κείμενο > 200 chars, επιστρέφουμε αυτό
        if len(clean_txt) > 200:
            return clean_txt, "TEXT"
        else:
            # 3. Αλλιώς OCR
            ocr_txt = ocr_scanned_pdf(file_bytes)
            return ocr_txt, "OCR"
            
    except Exception as e:
        return "", "ERR"

def run_auditor_certified(law_text, reports_text, amendments_text, opengov_text, metadata):
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # --- ΓΝΩΣΙΑΚΗ ΒΑΣΗ (Από τα Εγχειρίδια που ανεβάσατε) ---
        knowledge_base = """
        ΒΑΣΙΚΕΣ ΑΡΧΕΣ ΑΠΟ ΤΟ ΕΓΧΕΙΡΙΔΙΟ ΝΟΜΟΠΑΡΑΣΚΕΥΑΣΤΙΚΗΣ ΜΕΘΟΔΟΛΟΓΙΑΣ & ΟΔΗΓΟ ΑΣΥΡ:
        1. Η Ανάλυση Συνεπειών Ρύθμισης (ΑΣΥΡ) περιέχει υποχρεωτικά:
           - Ενότητα Δ: Έκθεση Γενικών Συνεπειών (Οφέλη/Κόστος).
           - Ενότητα Ε: Έκθεση Διαβούλευσης (Πρέπει να αναφέρει σχόλια & ενσωμάτωση).
           - Ενότητα ΣΤ: Έκθεση Νομιμότητας.
        2. "Επιχρύσωση" (Gold-plating): Η προσθήκη κανονιστικών βαρών πέραν των απαιτούμενων από την ΕΕ κατά την ενσωμάτωση οδηγιών.
        3. Διαβούλευση: Ελάχιστη διάρκεια 2 εβδομάδες (14 ημέρες). Αν είναι λιγότερο, απαιτείται ειδική αιτιολόγηση.
        4. Τροπολογίες: Πρέπει να είναι συναφείς με το κύριο αντικείμενο. Εκπρόθεσμες θεωρούνται αυτές που κατατίθενται λίγο πριν την ψήφιση χωρίς επαρκή χρόνο μελέτης.
        """

        prompt = f"""
        Ενεργείς ως Πιστοποιημένος Νομικός Ελεγκτής (Certified Auditor).
        Κρίνεις με βάση τον "Δεκάλογο Καλής Νομοθέτησης" και τα Επίσημα Εγχειρίδια της Κυβέρνησης.
        
        --- ΕΠΙΣΗΜΕΣ ΟΔΗΓΙΕΣ (CONTEXT) ---
        {knowledge_base}
        
        --- ΔΕΔΟΜΕΝΑ ΠΡΟΣ ΕΛΕΓΧΟ ---
        METADATA: {metadata}
        OPENGOV (Web): {opengov_text[:15000]}
        
        [ΚΕΙΜΕΝΑ ΝΟΜΟΥ]
        {law_text[:50000]}
        
        [ΕΚΘΕΣΕΙΣ - ΨΑΞΕ ΕΔΩ ΓΙΑ ΤΗΝ 'ΕΝΟΤΗΤΑ Ε' ΚΑΙ 'ΕΝΟΤΗΤΑ Δ']
        {reports_text[:80000]}
        
        [ΤΡΟΠΟΛΟΓΙΕΣ]
        {amendments_text[:20000]}
        
        --- Ο ΔΕΚΑΛΟΓΟΣ (ΚΡΙΤΗΡΙΑ) ---
        Βαθμολόγησε (1=ΝΑΙ/Θετικό, 0.5=ΜΕΡΙΚΩΣ, 0=ΟΧΙ/Αρνητικό).
        Για κάθε κριτήριο, δώσε: "score_val" και "reason" (Αιτιολογία βασισμένη στα κείμενα).

        1. ΠΡΟ-ΚΟΙΝΟΒΟΥΛΕΥΤΙΚΗ ΔΙΑΒΟΥΛΕΥΣΗ (>14 ημέρες);
           - Ψάξε ημερομηνίες στο OpenGov ή στην "Ενότητα Ε" της ΑΣΥΡ.
        2. ΕΚΘΕΣΗ ΔΙΑΒΟΥΛΕΥΣΗΣ (Ποιότητα);
           - Υπάρχει στην ΑΣΥΡ (Ενότητα Ε); Παρουσιάζει σχόλια και αιτιολόγηση απόρριψης;
        3. ΧΡΟΝΟΣ ΑΚΡΟΑΣΗΣ ΦΟΡΕΩΝ;
           - Υπήρχε χρόνος στη Βουλή;
        4. ΤΡΟΠΟΛΟΓΙΕΣ (Συνάφεια/Χρόνος);
           - Είναι άσχετες (φωτογραφικές) ή εκπρόθεσμες; (Αν ναι = 0).
        5. ΕΠΙΧΡΥΣΩΣΗ (Gold-plating);
           - Υπάρχει αδικαιολόγητη επέκταση κοινοτικών οδηγιών; (Δες Ενότητα ΣΤ ΑΣΥΡ).
        6. ΝΗΣΙΩΤΙΚΟΤΗΤΑ;
           - Ειδική μνεία/ρήτρα;
        7. ΑΝΑΛΥΣΗ ΚΟΣΤΟΥΣ (ΓΛΚ);
           - Υπάρχει έκθεση ΓΛΚ με συγκεκριμένα νούμερα (όχι αόριστη);
        8. ΑΠΛΟΥΣΤΕΥΣΗ;
           - Ρητή μείωση βαρών/διαδικασιών;
        9. ΕΞΟΥΣΙΟΔΟΤΗΣΕΙΣ;
           - Είναι περιορισμένες και ειδικές;
        10. ΠΟΙΟΤΗΤΑ ΓΛΩΣΣΑΣ;
            - Σαφής, κατανοητή, χωρίς νομικισμούς;

        OUTPUT JSON ONLY: {{ "criteria": [...], "summary": "..." }}
        """
        
        response = model.generate_content(prompt)
        txt = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(txt.strip())
    except Exception as e: return {"error": str(e)}

# --- 4. UI ---

st.subheader("🔍 Πλήρης Έλεγχος (Certified)")

col1, col2 = st.columns([1, 1])
with col1:
    l_input = st.text_input("Αριθμός Νόμου", placeholder="π.χ. 4940")
with col2:
    l_link = st.text_input("Link Βουλής (Προαιρετικό)", placeholder="https://...")

start = st.button("🚀 Έναρξη Ανάλυσης", type="primary")

if start and l_input:
    if not api_key: st.error("Missing Key"); st.stop()
    
    status = st.status("⚙️ Εκκίνηση...", expanded=True)
    clean_num = l_input.split("/")[0].strip()
    
    # A. API
    status.write("🏛️ Ανάκτηση από API...")
    api_data = get_law_from_api(clean_num)
    if not api_data:
        status.update(label="❌ Δεν βρέθηκε ο νόμος.", state="error"); st.stop()
        
    title = api_data.get('Title', '')
    st.success(f"**{title}**")
    
    # B. OpenGov
    status.write("🌍 Αναζήτηση OpenGov...")
    og_url = find_opengov_smart(title)
    og_text = scrape_opengov(og_url) if og_url else ""
    if og_url: st.info(f"🔗 OpenGov: {og_url}")

    # C. Files
    status.write("📥 Ανάγνωση Αρχείων (Smart OCR)...")
    files = api_data.get('LawPhotocopy', [])
    
    txt_law = ""
    txt_reports = ""
    txt_amendments = ""
    processed_log = []
    
    prog = st.progress(0)
    for i, f in enumerate(files):
        url = f.get('File')
        ftype = str(f.get('FileType', '')).lower()
        
        if url:
            text, mode = process_pdf_smart(url, ftype)
            processed_log.append(f"{ftype[:40]}... -> {mode}")
            
            if text:
                if "νόμου" in ftype or "ψηφισθέν" in ftype:
                    txt_law += text
                elif "τροπολογία" in ftype:
                    txt_amendments += f"\n--- ΤΡΟΠΟΛΟΓΙΑ ---\n" + text
                else:
                    txt_reports += f"\n--- ΕΓΓΡΑΦΟ ({ftype}) ---\n" + text
        
        prog.progress((i + 1) / len(files))

    with st.expander("Λεπτομέρειες Επεξεργασίας"):
        for p in processed_log: st.text(p)

    # D. Audit
    status.write("🧠 Αξιολόγηση με Πρότυπα Εγχειριδίου...")
    meta = json.dumps(api_data, ensure_ascii=False)
    
    res = run_auditor_certified(txt_law, txt_reports, txt_amendments, og_text, meta)
    
    if "error" in res:
        status.update(label="❌ AI Error", state="error"); st.error(res['error']); st.stop()
        
    status.update(label="✅ Ολοκληρώθηκε!", state="complete", expanded=False)
    
    # --- RESULTS ---
    score = sum([c.get('score_val', 0) * 10 for c in res.get('criteria', [])])
    
    c1, c2 = st.columns([1,2])
    # ΔΙΟΡΘΩΣΗ: Ασφαλής εγγραφή HTML
    score_html = f"""<div class="score-card"><h3>Βαθμολογία</h3><div class="big-score">{int(score)}/100</div></div>"""
    with c1: st.markdown(score_html, unsafe_allow_html=True)
    with c2: st.info(res.get('summary'))
    
    st.divider()
    
    for c in res.get('criteria', []):
        val = c.get('score_val', 0)
        icon = "✅" if val == 1 else ("⚠️" if val == 0.5 else "❌")
        
        # Ενδειξη αν το AI βρήκε στοιχεία από τα εγχειρίδια (π.χ. αναφορά σε Ενότητα Ε)
        extra_info = ""
        if "Ενότητα" in c.get('reason', ''): 
            extra_info = " <span class='manual-badge'>ΑΣΥΡ Checked</span>"
            
        with st.expander(f"{icon} {c.get('title')} ({int(val*10)}/10)"):
            st.markdown(f"**Αιτιολογία:** {c.get('reason')}", unsafe_allow_html=True)
            if extra_info: st.markdown(extra_info, unsafe_allow_html=True)