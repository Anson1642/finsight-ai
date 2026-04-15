import streamlit as st
import sqlite3
import json
import pandas as pd
import hashlib
import re
from google import genai
from datetime import datetime

# ==========================================
# 1. CONFIG & DB
# ==========================================
MY_API_KEY = "AIzaSyBOWAqxkAKxBBNkUy2-Fck_PkTqZlL6gIQ"
DB_NAME = "finance.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 amount REAL, category TEXT, description TEXT, 
                 currency TEXT, username TEXT)''')
    conn.commit(); conn.close()

def insert_transaction(amt, cat, desc, cur, user):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (amount, category, description, currency, username) VALUES (?, ?, ?, ?, ?)", 
              (amt, cat, desc, cur, user))
    conn.commit(); conn.close()

def get_user_transactions(username):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM transactions WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

# ==========================================
# 2. ADVANCED AI LOGIC (Currency & Recurring)
# ==========================================
def process_user_input(user_text, df):
    client = genai.Client(api_key=MY_API_KEY)
    # 傳入歷史記錄，讓 AI 偵測循環訂閱
    history = df.tail(10).to_string() 
    prompt = f"""
    Analyze text: "{user_text}". 
    History: {history}.
    Task: 
    1. Extract JSON: {{"intent": "log", "amount": <num>, "category": "<std_cat>", "description": "<text>", "currency": "HKD/USD/etc"}}
    2. Check for Recurring: Based on history, does this description appear frequently? If so, flag 'is_recurring': True.
    3. If Chat: {{"intent": "chat", "chat_reply": "<answer>"}}
    Output ONLY JSON.
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# ==========================================
# 3. ANALYTICS & PREDICTION
# ==========================================
def get_financial_prediction(df):
    if len(df) < 3: return "Log more data to get predictions!"
    avg_daily = df['amount'].sum() / 30 # 簡化預測模型
    return f"Based on your habits, you are spending ${avg_daily:.2f} per day. To save more, try to reduce Entertainment category."

# ==========================================
# 4. MAIN UI
# ==========================================
def main():
    st.set_page_config(page_title="FinSight Pro", layout="wide")
    init_db()
    
 
    username = "DemoUser" 
    df = get_user_transactions(username)
    
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Analysis", "🔮 AI Insights"])

    with tab1:
        st.header("Log Expenses")
        if prompt := st.chat_input("Spent 500 HKD on Food..."):
            res = process_user_input(prompt, df)
            if res and res.get("intent") == "log":
                insert_transaction(res['amount'], res['category'], res['description'], res.get('currency', 'HKD'), username)
                # 偵測循環訂閱
                if res.get('is_recurring'): st.warning("🔔 Recurring expense detected!")
                st.rerun()

    with tab2:
        st.header("Spending Analytics")
        if not df.empty:
            st.bar_chart(df.groupby('category')['amount'].sum())
            st.download_button("Download CSV", df.to_csv().encode('utf-8'), "data.csv")

    with tab3:
        st.header("AI Future Predictions")
        st.info(get_financial_prediction(df))
        if st.button("Generate Strategy"):
            st.write("AI is analyzing your 30-day spending trend...")
            # 這裡可以呼叫 AI 針對 df 生成一份 PDF 或報告文字

if __name__ == "__main__":
    main()
