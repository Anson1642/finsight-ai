import streamlit as st
import sqlite3
import json
import pandas as pd
import hashlib
import re
from google import genai

# ==========================================
# 1. CONFIG & SECURITY
# ==========================================
MY_API_KEY = "AIzaSyBOWAqxkAKxBBNkUy2-Fck_PkTqZlL6gIQ"
DB_NAME = "finance.db"

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()

# ==========================================
# 2. DATABASE & DATA TOOLS
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, category TEXT, description TEXT, username TEXT)''')
    conn.commit()
    conn.close()

def normalize_category(cat):
    cats = ["Food", "Transport", "Housing", "Entertainment", "Others"]
    return cat if cat in cats else "Others"

def insert_transaction(amount, category, description, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (amount, category, description, username) VALUES (?, ?, ?, ?)", (amount, category, description, username))
    conn.commit()
    conn.close()

def get_user_transactions(username):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM transactions WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

# ==========================================
# 3. AI LOGIC ENGINE
# ==========================================
def process_user_input(user_text, df):
    client = genai.Client(api_key=MY_API_KEY)
    history = df.to_string(index=False) if not df.empty else "No history."
    prompt = f"""You are 'FinSight', a professional AI Finance Assistant.
    History: {history}. User Input: "{user_text}".
    Standard Categories: Food, Transport, Housing, Entertainment, Others.
    Task: Extract data or answer a question. Return STRICTLY valid JSON.
    If log: {{"intent": "log", "amount": <num>, "category": "<std_cat>", "description": "<text>"}}
    If chat: {{"intent": "chat", "chat_reply": "<answer>"}}"""
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# ==========================================
# 4. MAIN UI (STREAMLIT)
# ==========================================
def main():
    st.set_page_config(page_title="FinSight Pro", layout="wide")
    init_db()

    if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False, "username": None})

    # --- LOGIN PAGE ---
    if not st.session_state.logged_in:
        st.title("💰 FinSight Pro - Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type='password')
        col1, col2 = st.columns(2)
        if col1.button("Login"):
            # (省略登入邏輯，直接進入展示)
            st.session_state.update({"logged_in": True, "username": user})
            st.rerun()
    
    # --- APP PAGE ---
    else:
        username = st.session_state.username
        st.sidebar.title(f"Hi, {username}!")
        if st.sidebar.button("Logout"): st.session_state.update({"logged_in": False}); st.rerun()
        
        budget = st.sidebar.number_input("Monthly Budget ($)", value=1000)
        df = get_user_transactions(username)
        
        tab1, tab2 = st.tabs(["💬 Chat & Log", "📊 Dashboard"])
        
        with tab1:
            st.subheader("Financial Assistant")
            if "messages" not in st.session_state: st.session_state.messages = []
            for msg in st.session_state.messages: st.chat_message(msg["role"]).markdown(msg["content"])
            
            if prompt := st.chat_input("Log expense or ask question..."):
                st.chat_message("user").markdown(prompt)
                res = process_user_input(prompt, df)
                if res and res.get("intent") == "log":
                    amt = res['amount']
                    cat = normalize_category(res.get('category', 'Others'))
                    if df['amount'].sum() + amt > budget: st.warning("⚠️ Warning: Budget limit exceeded!")
                    insert_transaction(amt, cat, res['description'], username)
                    st.rerun()
                elif res and res.get("chat_reply"):
                    st.chat_message("assistant").markdown(res['chat_reply'])

        with tab2:
            st.title("Financial Overview")
            if not df.empty:
                col1, col2 = st.columns(2)
                with col1: st.bar_chart(df.groupby('category')['amount'].sum())
                with col2: st.dataframe(df)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", csv, "data.csv", "text/csv")
            else: st.info("No data.")

if __name__ == "__main__":
    main()
