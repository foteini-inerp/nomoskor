import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import requests
from io import BytesIO
import pandas as pd
import altair as alt
import json

# --- 1. ΡΥΘΜΙΣΕΙΣ ---
st.set_page_config(page_title="Legislative Auditor AI", page_icon=":balance_scale:", layout="wide")

WEIGHTS = {
    "1": 15, "2": 5, "3": 10, "4": 10, "5": 5,
    "6": 15, "7": 10, "8": 10, "9": 10, "10": 10
}

st.markdown("""
<style>
    .score-card { background-color: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #2e7d32; }
    .big-score { font-size: 48px; font-weight: bold; color: #2e7d32; }
    .stButton>button { width: 100%; background-color: #1565C0; color: white; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Legislative Auditor AI")
st.caption("Έκδοση συμβατή με Gemini 2.0 Flash")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("Ρυθμίσεις")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key loaded!")
    else:
        api_key = st.text_input("Google Gemini API Key", type="password")
    
    if api_key: 
        genai.configure(api_key=api_key)

# --- 3. FUNCTIONS ---

def get_law_data(lawnum):
    """Κλήση στο API της Βουλής"""
    base_url = "https://www.hellenicparliament.gr/api.ashx"
    params = { "q": "laws", "lawnum": lawnum, "format": "json" }
    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get('TotalRecords', 0) > 0:
            return result['Data'][0]
        else:
            return None
    except Exception as e:
        st.error(f"Σφάλμα API: {e}")
        return None

def download_pdf_text(url):
    """Κατέβασμα PDF"""
    if not url: return ""
    try:
        if not url.startswith("http"): url = "https://www.hellenicparliament.gr" + url
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        with BytesIO(res.content) as f:
            reader = PdfReader(f)
            text = ""
            for i, page in enumerate(reader.pages):
                if i > 50: break  # περιορισμός σε 50 σελίδες για μεγάλους νόμους
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"PDF Error: {e}")
        return ""

def run_ai_audit(law_text, reports_text, metadata_str):
    """
    Χρήση του Gemini 2.0 Flash που υπάρχει στη λίστα.
    """
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        prompt = f"""
Ενεργείς ως Ελεγκτής Νομοθεσίας.

ΣΤΟΙΧΕΙΑ: {metadata_str}

ΚΕΙΜΕΝΑ ΝΟΜΟΥ: {law_text[:35000]}
ΕΚΘΕΣΕΙΣ: {reports_text[:30000]}

ΚΡΙΤΗΡΙΑ (1=ΝΑΙ, 0.5=Μερικώς, 0=ΟΧΙ):
1. Διαβούλευση
2. Χρόνος Ακρόασης
3. Νομοθετική Διαδικασία
4. Gold-plating
5. Νησιωτικότητα
6. Ανάλυση Κόστους
7. Απλούστευση
8. Εξουσιοδοτήσεις
9. Μηχανισμοί Εφαρμογής
10. Σαφήνεια Γλώσσας

OUTPUT JSON ONLY:
{{
    "criteria": [
        {{"id": "1", "title": "Διαβούλευση", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "2", "title": "Χρόνος Ακρόασης", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "3", "title": "Νομοθετική Διαδικασία", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "4", "title": "Gold-plating", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "5", "title": "Νησιωτικότητα", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "6", "title": "Ανάλυση Κόστους", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "7", "title": "Απλούστευση", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "8", "title": "Εξουσιοδοτήσεις", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "9", "title": "Μηχανισμοί Εφαρμογής", "score_text": "...", "score_val": 1.0, "reason": "..."}},
        {{"id": "10", "title": "Σαφήνεια Γλώσσας", "score_text": "...", "score_val": 1.0, "reason": "..."}}
    ],
    "summary": "..."
}}
"""
        response = model.generate_content(prompt)
        txt = response.text.strip()
        if txt.startswith("```json"): txt = txt[7:]
        if txt.startswith("```"): txt = txt[3:]
        if txt.endswith("```"): txt = txt[:-3]
        return json.loads(txt.strip())
    except Exception as e:
        # fallback
        try:
             model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
             response = model.generate_content(prompt)
             txt = response.text.strip().replace("```json","").replace("```","")
             return json.loads(txt.strip())
        except Exception as e2:
             return {"error": f"Primary error: {str(e)} | Backup error: {str(e2)}"}

# --- 4. UI ---

st.subheader("🔍 Αναζήτηση Νόμου")
col1, col2 = st.columns([3, 1])

with col1:
    law_input = st.text_input("Αριθμός ή Τίτλος Νόμου", placeholder="π.χ. 4940 ή Τίτλος νόμου")

with col2:
    st.write("") 
    st.write("")
    start_btn = st.button("🚀 Εκκίνηση", type="primary")

if start_btn and law_input:
    if not api_key: st.error("⚠️ Λείπει το API Key!"); st.stop()
    
    clean_num = law_input.split("/")[0].strip()
    status = st.status("📡 Σύνδεση με Βουλή...", expanded=True)
    
    # 1. API
    law_data = get_law_data(clean_num)
    if not law_data:
        status.update(label="❌ Δεν βρέθηκε ο νόμος.", state="error"); st.stop()
        
    title = law_data.get('Title', '')
    st.success(f"**Βρέθηκε:** {title}")
    
    # 2. PDF Files
    status.write("📥 Λήψη και ανάγνωση όλων των PDF...")
    files_list = law_data.get('LawPhotocopy', [])
    full_law_text = ""
    full_reports_text = ""
    count_files = 0
    
    for f in files_list:
        f_url = f.get('File')
        f_type = f.get('FileType', '')
        if f_url:
            content = download_pdf_text(f_url)
            if content:
                count_files += 1
                # Όλα τα αρχεία μπαίνουν σε reports αν δεν είναι ο κύριος νόμος
                if "Νόμου" in f_type or "Ψηφισθέν" in f_type: 
                    full_law_text += content + "\n"
                else:
                    full_reports_text += f"\n--- {f_type} ---\n" + content

    if count_files == 0:
        status.update(label="⚠️ Δεν βρέθηκαν PDF.", state="error"); st.stop()
        
    status.write(f"✅ Διαβάστηκαν {count_files} αρχεία.")
    
    # 3. AI Analysis
    status.write("🤖 AI Grading (Gemini 2.0 Flash)...")
    meta = json.dumps(law_data, ensure_ascii=False)
    res = run_ai_audit(full_law_text, full_reports_text, meta)
    
    if "error" in res:
        status.update(label="❌ Σφάλμα AI", state="error")
        st.error(res['error'])
        st.stop()
        
    status.update(label="✅ Ολοκληρώθηκε!", state="complete", expanded=False)
    
    # 4. RESULTS
    score = 0
    for c in res.get('criteria', []):
        score += c.get('score_val', 0) * WEIGHTS.get(str(c.get('id')), 0)
        
    st.divider()
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"""<div class="score-card"><h3>Βαθμολογία</h3><div class="big-score">{int(score)}/100</div></div>""", unsafe_allow_html=True)
    with c2:
        st.info(res.get('summary', ''))
        
    # Chart
    data = [{"Κριτήριο": c['title'], "Πόντοι": c['score_val']*WEIGHTS.get(str(c['id']),0)} for c in res.get('criteria', [])]
    st.altair_chart(alt.Chart(pd.DataFrame(data)).mark_bar().encode(
        x='Πόντοι', y=alt.Y('Κριτήριο', sort=None), color=alt.value("#2e7d32")), use_container_width=True)
    
    for c in res.get('criteria', []):
        with st.expander(f"{'✅' if c['score_val']==1 else '❌'} {c['title']}"):
            st.write(c['reason'])
