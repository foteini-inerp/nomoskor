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
st.set_page_config(page_title="Legislative Auditor AI (Fail-safe)", page_icon=":balance_scale:", layout="wide")

st.markdown("""
<style>
    .score-card { background-color: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #2e7d32; }
    .big-score { font-size: 48px; font-weight: bold; color: #2e7d32; }
    .stButton>button { width: 100%; background-color: #1565C0; color: white; border-radius: 5px; }
    .manual-badge { background-color: #e0f7fa; color: #006064; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #006064;}
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Legislative Auditor AI")
st.caption("V24: Με σύστημα ασφαλείας (Αυτόματη χρήση Link αν αποτύχει το API)")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("Ρυθμίσεις")
    api_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ API Key loaded!")
    except: pass

    if not api_key:
        api_key = st.text_input("Google Gemini API Key", type="password")
    
    if api_key: 
        genai.configure(api_key=api_key)

# --- 3. FUNCTIONS ---

def get_law_from_api(lawnum):
    """Ανάκτηση από το επίσημο API."""
    url = "https://www.hellenicparliament.gr/api.ashx"
    params = {"q": "laws", "lawnum": lawnum, "format": "json"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get('TotalRecords', 0) > 0:
            return data['Data'][0]
    except: pass
    return None

def scrape_law_from_url(url):
    """
    FALLBACK: Αν αποτύχει το API, μπαίνει στη σελίδα και βρίσκει τα PDF χειροκίνητα.
    Δημιουργεί ένα ψεύτικο αντικείμενο δεδομένων που μοιάζει με του API.
    """
    if not url: return None
    print(f"Scraping Manual URL: {url}")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Προσπάθεια εύρεσης τίτλου
        title = "Χειροκίνητη Ανάκτηση Νόμου"
        h1 = soup.find("h1")
        if h1: title = h1.get_text().strip()
        
        # Εύρεση PDF Links
        files_list = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            txt = a.get_text().strip()
            
            if ".pdf" in href:
                # Καθαρισμός URL
                if not href.startswith("http"):
                    href = "https://www.hellenicparliament.gr" + href
                
                # Προσπάθεια μαντεψιάς τύπου αρχείου από το κείμενο του link ή το filename
                ftype = "Αρχείο Νόμου/Έκθεσης"
                if "αιτιολογική" in txt.lower(): ftype = "Αιτιολογική Έκθεση"
                elif "συνεπειών" in txt.lower(): ftype = "Ανάλυση Συνεπειών (ΑΣΥΡ)"
                elif "τροπολογία" in txt.lower(): ftype = "Τροπολογία"
                elif "νόμος" in txt.lower() or "ψηφισθέν" in txt.lower(): ftype = "Κείμενο Νόμου"
                
                files_list.append({
                    "File": href,
                    "FileType": ftype
                })
        
        if files_list:
            return {
                "Title": title,
                "LawPhotocopy": files_list,
                "DateInserted": "Άγνωστο (Scraped)",
                "DateVoted": "Άγνωστο (Scraped)"
            }
            
    except Exception as e:
        print(f"Scraping Error: {e}")
        return None
    return None

def find_opengov_smart(law_title):
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
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name  
        uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
        time.sleep(2)
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content([uploaded_file, "Extract text verbatim."], request_options={"timeout": 600})
        return response.text
    except: return ""

def process_pdf_smart(url, ftype):
    if not url: return "", "N/A"
    try:
        if not url.startswith("http"): url = "https://www.hellenicparliament.gr" + url
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        file_bytes = res.content
        text_content = ""
        with BytesIO(file_bytes) as f:
            reader = PdfReader(f)
            for page in reader.pages: text_content += page.extract_text() or ""
        clean_txt = re.sub(r'\s+', ' ', text_content).strip()
        
        if len(clean_txt) > 200: return clean_txt, "TEXT"
        else:
            ocr = ocr_scanned_pdf(file_bytes)
            return ocr, "OCR"
    except: return "", "ERR"

def run_auditor_certified(law_text, reports_text, amendments_text, opengov_text, metadata):
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        knowledge_base = """
        ΒΑΣΙΚΕΣ ΑΡΧΕΣ ΑΠΟ ΤΟ ΕΓΧΕΙΡΙΔΙΟ ΝΟΜΟΠΑΡΑΣΚΕΥΑΣΤΙΚΗΣ ΜΕΘΟΔΟΛΟΓΙΑΣ & ΟΔΗΓΟ ΑΣΥΡ:
        1. Η Ανάλυση Συνεπειών Ρύθμισης (ΑΣΥΡ) περιέχει υποχρεωτικά: Ενότητα Δ (Γενικές Συνέπειες), Ενότητα Ε (Διαβούλευση), Ενότητα ΣΤ (Νομιμότητα).
        2. "Επιχρύσωση" (Gold-plating): Προσθήκη βαρών πέραν των απαιτούμενων από την ΕΕ.
        3. Διαβούλευση: Ελάχιστη διάρκεια 14 ημέρες.
        """
        prompt = f"""
        Ενεργείς ως Πιστοποιημένος Νομικός Ελεγκτής (Certified Auditor).
        Κρίνεις με βάση τον "Δεκάλογο Καλής Νομοθέτησης".
        
        CONTEXT: {knowledge_base}
        METADATA: {metadata}
        OPENGOV: {opengov_text[:15000]}
        ΝΟΜΟΣ: {law_text[:50000]}
        ΕΚΘΕΣΕΙΣ: {reports_text[:80000]}
        ΤΡΟΠΟΛΟΓΙΕΣ: {amendments_text[:20000]}
        
        ΚΡΙΤΗΡΙΑ (1=ΝΑΙ, 0.5=ΜΕΡΙΚΩΣ, 0=ΟΧΙ). Δώσε score_val και reason.
        1. ΠΡΟ-ΚΟΙΝΟΒΟΥΛΕΥΤΙΚΗ ΔΙΑΒΟΥΛΕΥΣΗ (>14 ημέρες); (Ψάξε ημερομηνίες στο OpenGov ή στην ΑΣΥΡ).
        2. ΕΚΘΕΣΗ ΔΙΑΒΟΥΛΕΥΣΗΣ (Ποιότητα); (Υπάρχει στην ΑΣΥΡ Ενότητα Ε;).
        3. ΧΡΟΝΟΣ ΑΚΡΟΑΣΗΣ ΦΟΡΕΩΝ;
        4. ΤΡΟΠΟΛΟΓΙΕΣ (Συνάφεια/Χρόνος);
        5. ΕΠΙΧΡΥΣΩΣΗ (Gold-plating);
        6. ΝΗΣΙΩΤΙΚΟΤΗΤΑ;
        7. ΑΝΑΛΥΣΗ ΚΟΣΤΟΥΣ (ΓΛΚ);
        8. ΑΠΛΟΥΣΤΕΥΣΗ;
        9. ΕΞΟΥΣΙΟΔΟΤΗΣΕΙΣ;
        10. ΠΟΙΟΤΗΤΑ ΓΛΩΣΣΑΣ;

        OUTPUT JSON ONLY: {{ "criteria": [...], "summary": "..." }}
        """
        response = model.generate_content(prompt)
        txt = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(txt.strip())
    except Exception as e: return {"error": str(e)}

# --- 4. UI ---
st.subheader("🔍 Πλήρης Έλεγχος (Fail-Safe)")
col1, col2 = st.columns([1, 1])
with col1: l_input = st.text_input("1. Αριθμός Νόμου (π.χ. 4940)", value="")
with col2: l_link = st.text_input("2. Link Βουλής (Αν δεν το βρίσκει το API)", placeholder="https://www.hellenicparliament.gr/...")
start = st.button("🚀 Έναρξη Ανάλυσης", type="primary")

if start:
    if not api_key: st.error("Missing Key"); st.stop()
    status = st.status("⚙️ Εκκίνηση...", expanded=True)
    
    # --- 1. ΑΝΑΚΤΗΣΗ ΔΕΔΟΜΕΝΩΝ (API ή SCRAPING) ---
    law_data = None
    
    # Προσπάθεια Α: API
    if l_input:
        status.write("🏛️ Δοκιμή μέσω API...")
        clean_num = l_input.split("/")[0].strip()
        law_data = get_law_from_api(clean_num)
    
    # Προσπάθεια Β: Scraping (Αν απέτυχε το API)
    if not law_data:
        if l_link:
            status.write("⚠️ Το API απέτυχε. Δοκιμή ανάγνωσης από το Link (Scraping)...")
            law_data = scrape_law_from_url(l_link)
        else:
            status.update(label="❌ Ο Νόμος δεν βρέθηκε.", state="error")
            st.error("Το API δεν βρήκε τον νόμο. Παρακαλώ επικολλήστε το Link από το hellenicparliament.gr στο πεδίο 2.")
            st.stop()
            
    if not law_data:
        st.error("Αποτυχία ανάκτησης δεδομένων.")
        st.stop()

    title = law_data.get('Title', 'Άγνωστος Τίτλος')
    st.success(f"**Βρέθηκε:** {title}")
    
    # --- 2. OPENGOV ---
    status.write("🌍 Αναζήτηση OpenGov...")
    og_url = find_opengov_smart(title)
    og_text = scrape_opengov(og_url) if og_url else ""
    if og_url: st.info(f"🔗 OpenGov: {og_url}")

    # --- 3. FILES ---
    status.write("📥 Ανάγνωση Αρχείων...")
    files = law_data.get('LawPhotocopy', [])
    if not files: 
        st.warning("Δεν βρέθηκαν PDF.")
        st.stop()
        
    txt_law, txt_reports, txt_amendments = "", "", ""
    prog = st.progress(0)
    
    for i, f in enumerate(files):
        url = f.get('File')
        ftype = str(f.get('FileType', '')).lower()
        if url:
            text, mode = process_pdf_smart(url, ftype)
            if text:
                if "νόμου" in ftype or "ψηφισθέν" in ftype: txt_law += text
                elif "τροπολογία" in ftype: txt_amendments += f"\n--- ΤΡΟΠΟΛΟΓΙΑ ---\n" + text
                else: txt_reports += f"\n--- ΕΓΓΡΑΦΟ ({ftype}) ---\n" + text
        prog.progress((i + 1) / len(files))

    # --- 4. AUDIT ---
    status.write("🧠 Αξιολόγηση...")
    meta = json.dumps(law_data, ensure_ascii=False)
    res = run_auditor_certified(txt_law, txt_reports, txt_amendments, og_text, meta)
    
    if "error" in res:
        status.update(label="❌ AI Error", state="error"); st.error(res['error']); st.stop()
        
    status.update(label="✅ Ολοκληρώθηκε!", state="complete", expanded=False)
    
    # --- RESULTS ---
    score = sum([c.get('score_val', 0) * 10 for c in res.get('criteria', [])])
    c1, c2 = st.columns([1,2])
    score_html = f"""<div class="score-card"><h3>Βαθμολογία</h3><div class="big-score">{int(score)}/100</div></div>"""
    with c1: st.markdown(score_html, unsafe_allow_html=True)
    with c2: st.info(res.get('summary'))
    st.divider()
    
    for c in res.get('criteria', []):
        val = c.get('score_val', 0)
        icon = "✅" if val == 1 else ("⚠️" if val == 0.5 else "❌")
        extra = " <span class='manual-badge'>ΑΣΥΡ Checked</span>" if "Ενότητα" in c.get('reason', '') else ""
        with st.expander(f"{icon} {c.get('title')} ({int(val*10)}/10)"):
            st.markdown(f"**Αιτιολογία:** {c.get('reason')}" + extra, unsafe_allow_html=True)