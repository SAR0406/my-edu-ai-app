import streamlit as st
import streamlit_authenticator as stauth
from pathlib import Path
import pickle
from langdetect import detect
import random
import datetime
import openai

# ============ USER AUTH SETUP ===============
users_db = {"admin": {"name": "Admin", "password": stauth.Hasher(["admin123"]).generate()[0]}}
CREDENTIALS_FILE = "users.pkl"

# Save credentials
def save_users(users):
    with open(CREDENTIALS_FILE, "wb") as f:
        pickle.dump(users, f)

# Load credentials
def load_users():
    if Path(CREDENTIALS_FILE).exists():
        with open(CREDENTIALS_FILE, "rb") as f:
            return pickle.load(f)
    return users_db

users_db = load_users()

# ============ UI ================
st.set_page_config(page_title="My Edu AI App", layout="centered", page_icon="🤖")
st.title("📘 My Edu AI Assistant")
st.markdown("👩‍🏫 Chat | 🧠 Learn | 🎓 Quiz | 🌐 Multilingual")

# ============ LOGIN SYSTEM ================
authenticator = stauth.Authenticate(
    credentials={"usernames": {u: {"name": d["name"], "password": d["password"]} for u, d in users_db.items()}},
    cookie_name="eduai",
    key="abc",
    cookie_expiry_days=7
)

name, auth_status, username = authenticator.login("Login", "main")

if auth_status is False:
    st.error("❌ Incorrect username or password")
elif auth_status is None:
    st.warning("👤 Please enter your credentials")

# ============ SIGNUP ====================
with st.expander("📌 New user? Sign up here"):
    new_user = st.text_input("New username")
    new_pass = st.text_input("New password", type="password")
    if st.button("Create Account"):
        if new_user in users_db:
            st.error("🚫 Username already exists.")
        else:
            users_db[new_user] = {"name": new_user, "password": stauth.Hasher([new_pass]).generate()[0]}
            save_users(users_db)
            st.success("✅ Account created. Please log in!")

# ============ MAIN APP ====================
if auth_status:
    st.success(f"Welcome, {name}!")

    persona = st.selectbox("🧠 Choose Persona", ["Fun", "Teacher", "Translator"])
    lang = st.selectbox("🌍 Language", ["English", "Hindi"])
    st.markdown("---")

    chat_input = st.text_input("💬 Ask me anything...", key="chat_input")
    chat_area = st.empty()

    if chat_input:
        st.session_state.chat_history = st.session_state.get("chat_history", []) + [(chat_input, persona)]

        # Simulated AI reply
        response = f"[{persona} Persona says]: " + chat_input[::-1]  # Replace with real API call
        chat_area.markdown(f"**You:** {chat_input}")
        chat_area.markdown("**AI:** ")

        # Simulate typing
        response_container = st.empty()
        for i in range(len(response)):
            response_container.markdown("**AI:** " + response[:i+1])
            st.sleep(0.02)

        if st.button("💾 Save Chat"):
            with open("chat_history.txt", "a") as f:
                f.write(f"{datetime.datetime.now()}\n{chat_input}\n{response}\n\n")
            st.success("Chat saved!")

    # ============ QUIZ GENERATOR ===============
    st.markdown("---")
    st.header("🧪 Quiz Generator")
    subject = st.selectbox("📘 Subject", ["Math", "Science", "English"])
    grade = st.selectbox("🎓 Class", [str(i) for i in range(1, 13)])
    chapter = st.text_input("📖 Chapter")

    if st.button("🎯 Generate Quiz"):
        st.subheader(f"Quiz: {subject} - Class {grade} - {chapter}")
        for i in range(1, 6):
            q = f"Q{i}. What is {random.randint(1,10)} + {random.randint(1,10)}?"
            st.markdown(f"{q}\n- A) {random.randint(10,20)}\n- B) {random.randint(5,15)}\n- C) {random.randint(1,10)}")

    authenticator.logout("🚪 Logout", "sidebar")
