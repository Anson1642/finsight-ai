import streamlit as st
import sqlite3
import json
import pandas as pd
import re  # 
from google import genai

# ==========================================
# 1. CONFIGURATION & SECURITY
# ==========================================
# [SECURITY NOTICE] 
# Please paste your API key below before running.
MY_API_KEY = "AIzaSyBOWAqxkAKxBBNkUy2-Fck_PkTqZlL6gIQ"

DB_NAME = "finance.db"

# ==========================================
# 2. DATABASE FUNCTIONS
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_transaction(amount, category, description):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (amount, category, description) VALUES (?, ?, ?)", 
              (amount, category, description))
    conn.commit()
    conn.close()

def get_all_transactions_df():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    return df

def clear_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM transactions")
    conn.commit()
    conn.close()

# ==========================================
# 3. AI LOGIC ENGINE (RAG & Intent Routing)
# ==========================================
def process_user_input(user_text, df):
    if MY_API_KEY == "PASTE_YOUR_API_KEY_HERE":
        st.error("⚠️ Please insert your Google API Key in the code first!")
        return None

    client = genai.Client(api_key=MY_API_KEY)
    history_text = df.to_string(index=False) if not df.empty else "No transactions logged yet."
    
    prompt = f"""
    You are 'FinSight', a professional AI Finance Assistant.
    
    User's Transaction History:
    {history_text}
    
    User Input: "{user_text}"
    
    Task: Determine if the user is logging a NEW expense OR asking a QUESTION.
    OUTPUT ABSOLUTELY NOTHING EXCEPT A VALID JSON OBJECT.
    
    Format 1 (Logging expense):
    {{
        "intent": "log",
        "amount": <number>,
        "category": "<One word, e.g., Food, Transport>",
        "description": "<short description>"
    }}
    
    Format 2 (Answering question / Chatting):
    {{
        "intent": "chat",
        "chat_reply": "<Provide a conversational answer based on the history.>"
    }}
    """
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        text = response.text
        
        # --- 超強防護機制：強制抓取 { } 裡面的內容 ---
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            clean_json_string = match.group(0)
            return json.loads(clean_json_string)
        else:
            print("Regex failed to find JSON in AI response.")
            return None
            
    except Exception as e:
        error_msg = str(e)
        if "503" in error_msg or "UNAVAILABLE" in error_msg:
            st.toast("⚠️ Google Server is busy. Please try again in a few seconds.", icon="⏳")
        else:
            print(f"AI Processing Error: {e}")
        return None

# ==========================================
# 4. STREAMLIT UI (FRONTEND)
# ==========================================
def main():
    st.set_page_config(page_title="FinSight AI", page_icon="💰", layout="wide")
    init_db()
    df = get_all_transactions_df()

    # --- SIDEBAR: Analytics & Settings ---
    with st.sidebar:
        st.title("📊 Dashboard")
        
        if not df.empty:
            st.subheader("Spending by Category")
            category_sums = df.groupby('category')['amount'].sum()
            st.bar_chart(category_sums)
            
            st.success(f"**Total Transactions:** {len(df)}")
            
            st.divider()
            st.subheader("📥 Export Data")
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download as CSV",
                data=csv_data,
                file_name='my_financial_data.csv',
                mime='text/csv'
            )
        else:
            st.info("No data yet. Log some transactions in the chat!")

        st.divider()
        st.subheader("⚙️ Settings")
        if st.button("🗑️ Clear All Data"):
            clear_database()
            st.session_state.messages = [] 
            st.rerun() 

    # --- MAIN SCREEN: Chat Interface ---
    st.title("💰 FinSight AI Assistant")
    st.caption("Log expenses naturally or ask questions about your financial habits.")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I can log your expenses or analyze your spending. Try saying: *'Spent $20 on lunch'* or *'How much did I spend today?'*"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_text := st.chat_input("Type your expense or ask a question..."):
        st.chat_message("user").markdown(user_text)
        st.session_state.messages.append({"role": "user", "content": user_text})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = process_user_input(user_text, df)
                
                if result:
                    intent = result.get("intent")
                    
                    if intent == "log" and result.get("amount") is not None:
                        category = result.get("category", "Uncategorized") 
                        insert_transaction(result["amount"], category, result["description"])
                        reply = f"✅ **Logged successfully!** \n\n**Amount:** ${result['amount']} \n**Category:** {category} \n**Detail:** {result['description']}"
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        st.rerun() 
                    
                    elif intent == "chat" and result.get("chat_reply"):
                        reply = f"🤖 **AI Advice:**\n\n{result['chat_reply']}"
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    
                    else:
                        reply = "❌ Sorry, I couldn't understand that. Please provide an amount if logging an expense."
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                else:
                    reply = "🤔 Hmm, the AI server is busy or didn't understand. Please try asking again!"
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()