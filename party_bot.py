import streamlit as st
import sqlite3
from openai import OpenAI
from datetime import datetime

# ---------------- CONFIG ---------------- #

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Party Assistant", page_icon="🎉")

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("party_memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest TEXT,
    role TEXT,
    message TEXT,
    timestamp TEXT
)
""")
conn.commit()

# ---------------- UTILITIES ---------------- #

def save_message(guest, role, message):
    cursor.execute(
        "INSERT INTO conversations (guest, role, message, timestamp) VALUES (?, ?, ?, ?)",
        (guest, role, message, datetime.now().isoformat())
    )
    conn.commit()

def get_guest_messages():
    cursor.execute("SELECT guest, message FROM conversations WHERE role='user'")
    return cursor.fetchall()

def snack_calculator(guest_count):
    base = max(1, int(guest_count))
    return {
        "chips_packets": 3 * base,
        "sweet_snacks": 1 * base,
        "random_munchies": 2 * base
    }

# ---------------- SIDEBAR ---------------- #

mode = st.sidebar.radio("Mode", ["Guest Chat", "Host Dashboard"])

# ---------------- SYSTEM PROMPT ---------------- #

BASE_SYSTEM_PROMPT = """
You are a cool, socially smooth, lightly witty AI party assistant.

PERSONALITY:
- Relaxed, effortless tone
- Dry humor, subtle confidence
- Friendly but never overeager
- Never creepy or intense

INTERACTION PRINCIPLE:
The guest should feel like they are casually chatting with a clever human.

CONVERSATION STYLE:
- Short natural messages
- No survey feel
- No repeated questions
- No stacked interrogation

OBJECTIVE:
Casually understand preferences through conversation.

Topics to gradually understand:
- Arrival timing
- Coming from office or not
- Hard stop constraints
- Activities
- Dinner preference
- Snack preferences

PARTY CONTEXT:
Night gathering in Besant Nagar, Chennai.

RULES:
- Never ask about dancing
- Never sound like a questionnaire
- Never repeat questions
"""

# ---------------- GUEST CHAT ---------------- #

if mode == "Guest Chat":

    st.title("🎉 Welcome to theprabhs house party!")

    guest_name = st.text_input("Enter your name")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}]

    if "chat_started" not in st.session_state:
        st.session_state.chat_started = False

    if "known_info" not in st.session_state:
        st.session_state.known_info = {
            "arrival_time": False,
            "office_status": False,
            "hard_stop": False,
            "activities": False,
            "dinner": False,
            "snacks": False
        }

    # Render history
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    user_input = st.chat_input("Say something…")

    if user_input and guest_name:

        st.session_state.chat_started = True

        text = user_input.lower()

        if any(word in text for word in ["come", "reach", "arrive", "by", "around"]):
            st.session_state.known_info["arrival_time"] = True

        if "office" in text:
            st.session_state.known_info["office_status"] = True

        if any(word in text for word in ["leave", "hard stop", "have to go"]):
            st.session_state.known_info["hard_stop"] = True

        if any(word in text for word in ["playstation", "ps", "game", "walk", "beach", "run"]):
            st.session_state.known_info["activities"] = True

        if any(word in text for word in ["dinner", "eat", "food", "biryani", "pizza"]):
            st.session_state.known_info["dinner"] = True

        if any(word in text for word in ["snack", "chips", "nachos"]):
            st.session_state.known_info["snacks"] = True

        knowledge_state = st.session_state.known_info

        dynamic_system_prompt = BASE_SYSTEM_PROMPT + f"""

KNOWN INFORMATION (DO NOT RE-ASK):

Arrival time known: {knowledge_state['arrival_time']}
Coming from office known: {knowledge_state['office_status']}
Hard stop known: {knowledge_state['hard_stop']}
Activities known: {knowledge_state['activities']}
Dinner known: {knowledge_state['dinner']}
Snacks known: {knowledge_state['snacks']}

RULE:
Never ask for information already marked as known.
"""

        st.session_state.messages.append({"role": "user", "content": user_input})
        save_message(guest_name, "user", user_input)

        messages_for_api = [{"role": "system", "content": dynamic_system_prompt}] + st.session_state.messages[1:]

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages_for_api
        )

        reply = response.choices[0].message.content

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_message(guest_name, "assistant", reply)

        with st.chat_message("assistant"):
            st.write(reply)

    if not st.session_state.chat_started:
        st.chat_message("assistant").write(
            "Hey 👋 Quick curiosity — when are you planning to show up tonight?"
        )

# ---------------- HOST DASHBOARD ---------------- #

elif mode == "Host Dashboard":

    st.title("🎛 Host Control Center")

    data = get_guest_messages()

    if not data:
        st.info("No guest data yet 😄")
    else:
        guests = {}
        for guest, message in data:
            guests.setdefault(guest, []).append(message)

        st.subheader("🧠 Recent Guest Signals")

        for guest, messages in guests.items():
            st.write(f"**{guest}**")
            st.write(" • " + "\n • ".join(messages[-5:]))

    st.subheader("🍟 Snack Calculator")

    guest_count = st.number_input("Expected guests", min_value=1, value=3)

    if st.button("Calculate Snacks"):
        snacks = snack_calculator(guest_count)

        st.write("Recommended snack buffer:")
        st.write(f"✅ Chips packets: {snacks['chips_packets']}")
        st.write(f"✅ Sweet snacks: {snacks['sweet_snacks']}")
        st.write(f"✅ Random munchies: {snacks['random_munchies']}")

    if st.button("Generate Plan"):
        cursor.execute("SELECT message FROM conversations WHERE role='user'")
        all_inputs = "\n".join([row[0] for row in cursor.fetchall()])

        planner_prompt = f"""
        Generate a concise party strategy.

        Guest inputs:
        {all_inputs}
        """

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": planner_prompt}]
        )

        st.write(response.choices[0].message.content)


