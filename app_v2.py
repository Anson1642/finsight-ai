import streamlit as st
import sqlite3, json, pandas as pd, hashlib, re, io
from google import genai
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas # 需安裝: pip install reportlab

# --- DATABASE & SECURITY ---
MY_API_KEY = "AIzaSyBOWAqxkAKxBBNkUy2-Fck_PkTqZlL6gIQ"
DB_NAME = "finance.db"

def make_hashes(pwd): return hashlib.sha256(str.encode(pwd)).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, sec_q TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, category TEXT, description TEXT, username TEXT, date DATE)''')
    conn.commit(); conn.close()

# --- PDF GENERATOR ---
def generate_pdf(df, username):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, f"Financial Report for {username}")
    p.drawString(100, 780, f"Generated on: {datetime.now().strftime('%Y-%m-%d')}")
    y = 750
    for _, row in df.iterrows():
        p.drawString(100, y, f"{row['category']}: ${row['amount']} - {row['description']}")
        y -= 20
    p.showPage(); p.save()
    return buffer.getvalue()

# --- AI ENGINE ---
def process_user_input(user_text, df):
    client = genai.Client(api_key=MY_API_KEY)
    history = df.tail(15).to_string() 
    prompt = f"""You are FinSight. Analyze history: {history}. Input: "{user_text}".
    Rules: 
    1. If logging: Return {{"intent": "log", "amount": <num>, "category": "<Food/Transport/Housing/Entertainment/Others>", "description": "<text>"}}
    2. If prediction/advice: Return {{"intent": "chat", "chat_reply": "<answer>"}}
    Output ONLY JSON."""
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# --- UI (Simplified for brevity) ---
def main():
    st.set_page_config(page_title="FinSight Pro", layout="wide")
    init_db()
    
    # 這裡省略登入邏輯，請保留你之前的登入碼
    username = "DemoUser" # 假設已登入
    df = get_user_transactions(username)

    st.sidebar.title("📊 Control Panel")
    budget = st.sidebar.slider("Set Monthly Budget ($)", 100, 5000, 1000)
    
    # Tabs
    t1, t2, t3 = st.tabs(["💬 Chat", "📈 Charts", "📄 Reports"])
    
    with t1:
        if prompt := st.chat_input("Log expense..."):
            res = process_user_input(prompt, df)
            if res and res.get("intent") == "log":
                # 加入時間日期
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("INSERT INTO transactions (amount, category, description, username, date) VALUES (?,?,?,?,?)",
                          (res['amount'], res['category'], res['description'], username, datetime.now().strftime('%Y-%m-%d')))
                conn.commit(); conn.close()
                st.rerun()

    with t2:
        if not df.empty:
            st.bar_chart(df.groupby('category')['amount'].sum())
            # 預算比對
            total = df['amount'].sum()
            st.progress(min(total/budget, 1.0), text=f"Budget Usage: {total}/{budget}")
            
    with t3:
        if not df.empty:
            st.download_button("Export PDF Report", generate_pdf(df, username), "report.pdf", "application/pdf")

if __name__ == "__main__":
    main()
