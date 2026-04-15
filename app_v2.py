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

# ==========================================
# 2. DATABASE FUNCTIONS
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, category TEXT, description TEXT, username TEXT)''')
    
    c.execute("PRAGMA table_info(transactions)")
    if 'username' not in [info[1] for info in c.fetchall()]:
        c.execute("ALTER TABLE transactions ADD COLUMN username TEXT")
    
    conn.commit()
    conn.close()

def insert_transaction(amount, category, description, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (amount, category, description, username) VALUES (?, ?, ?, ?)", 
              (amount, category, description, username))
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
    history = df.tail(10).to_string()
    prompt = f"""You are a professional AI Finance Assistant.
    History: {history}. User Input: "{user_text}".
    Return STRICTLY valid JSON.
    If log: {{"intent": "log", "amount": <num>, "category": "<Food/Transport/Housing/Entertainment/Others>", "description": "<text>"}}
    If chat: {{"intent": "chat", "chat_reply": "<answer>"}}
    No markdown."""
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# ==========================================
# 4. MAIN UI
# ==========================================
def main():
    st.set_page_config(page_title="FinSight Pro", layout="wide")
    init_db()
    
    # 登入邏輯保留
    if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})
    
    if not st.session_state.logged_in:
        st.title("💰 FinSight AI - Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type='password')
        if st.button("Enter"):
            st.session_state.update({"logged_in": True, "username": user})
            st.rerun()
    else:
        username = st.session_state.username
        st.sidebar.title(f"Hi, {username}!")
        if st.sidebar.button("Logout"): st.session_state.update({"logged_in": False}); st.rerun()
        
        df = get_user_transactions(username)
        budget = st.sidebar.slider("Monthly Budget ($)", 100, 5000, 1000)
        
        tab1, tab2 = st.tabs(["💬 Chat", "📊 Analysis"])
        
        with tab1:
            if "messages" not in st.session_state: st.session_state.messages = []
            for msg in st.session_state.messages: st.chat_message(msg["role"]).markdown(msg["content"])
            
            if prompt := st.chat_input("Log expense or ask..."):
                st.chat_message("user").markdown(prompt)
                res = process_user_input(prompt, df)
                if res and res.get("intent") == "log":
                    if df['amount'].sum() + res['amount'] > budget: st.warning("⚠️ Budget limit exceeded!")
                    insert_transaction(res['amount'], res['category'], res['description'], username)
                    st.rerun()
                elif res and res.get("chat_reply"):
                    st.chat_message("assistant").markdown(res['chat_reply'])
                    st.session_state.messages.append({"role": "assistant", "content": res['chat_reply']})

        with tab2:
            if not df.empty:
                st.bar_chart(df.groupby('category')['amount'].sum())
                st.download_button("Export CSV", df.to_csv().encode('utf-8'), "data.csv")

if __name__ == "__main__":
    main()
