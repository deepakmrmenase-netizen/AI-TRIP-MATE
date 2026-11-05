"""
TripMate AI - Chatbot Component
AI Travel Assistant chat interface.
"""

import streamlit as st
from svc_ai_service import chat_with_ai, call_ai
from app_config import DEMO_MODE


SUGGESTED_QUESTIONS = [
    "What can I visit in Mysuru in 2 days?",
    "Suggest a trip under ₹3,000",
    "How can I save money while travelling?",
    "What should I pack for a weekend trip?",
    "Which places are good for photography?",
    "Suggest budget accommodation options",
    "How do I travel cheaply by train?",
    "Best places to eat local food cheaply",
]


def _init_chat_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm **TripMate AI** 🤖✈️ – your personal student travel assistant!\n\n"
                    "I can help you plan affordable trips, suggest destinations, give packing tips, "
                    "and answer any travel question. Try one of the suggested questions below, "
                    "or just type your own!\n\n"
                    "*(Demo mode active – add your Gemini API key for fully personalised responses)*"
                    if DEMO_MODE else
                    "Hi! I'm **TripMate AI** 🤖✈️ – your personal student travel assistant!\n\n"
                    "I can help you plan affordable trips, suggest destinations, give packing tips, "
                    "and answer any travel question. What would you like to know?"
                ),
            }
        ]


def render_chatbot_page():
    """Render the full AI Travel Assistant page."""
    _init_chat_state()

    # Header
    st.markdown("""
<div style="background:linear-gradient(135deg,#0f172a,#1e293b); border-radius:20px; padding:24px 28px;
     color:white; margin-bottom:24px; display:flex; align-items:center; gap:16px;">
  <div style="font-size:2.5rem;">🤖</div>
  <div>
    <div style="font-size:1.4rem; font-weight:800;">TripMate AI Assistant</div>
    <div style="font-size:0.85rem; opacity:0.75; margin-top:2px;">
      Your intelligent student travel advisor • Available 24/7
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Which brain is answering? (so it is never a mystery)
    if DEMO_MODE:
        st.markdown(
            '<div style="background:#fef9c3;border:1px solid #fde047;border-radius:10px;padding:10px 14px;margin-bottom:14px;'
            'font-size:0.88rem;color:#713f12;">🟡 <b>Built-in mode</b> - answers come from TripMate\'s own place data and live maps '
            '(real road distances, nearby temples, food, stays). For a free-talking AI, add <code>GEMINI_API_KEY</code> '
            'in <b>Manage app → Settings → Secrets</b>.</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="background:#dcfce7;border:1px solid #86efac;border-radius:10px;padding:10px 14px;margin-bottom:6px;'
            'font-size:0.88rem;color:#14532d;">🟢 <b>Gemini AI connected</b> - answers use your API key plus live map facts.</div>',
            unsafe_allow_html=True)
        if st.button("🔧 Test my AI connection", key="ai_test_btn"):
            with st.spinner("Testing..."):
                try:
                    reply = call_ai("Reply with exactly: OK")
                    st.success(f"AI works. Reply: {reply.strip()[:60]}")
                except Exception as exc:
                    st.error(f"AI is NOT working: {str(exc)[:220]}")
                    st.caption("Common reasons: wrong or expired key, key not allowed for Gemini, free quota finished. "
                               "Create a new key at aistudio.google.com and paste it in Secrets as GEMINI_API_KEY = \"your-key\".")

    if DEMO_MODE:
        st.markdown("""
<div class="tm-demo-banner">
  🤖 <strong>Demo AI Mode Active</strong> – Showing pre-built responses.
  Add your Gemini API key in <code>.env</code> for live AI responses.
</div>
""", unsafe_allow_html=True)

    # Chat history display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "🧑‍🎓"):
                st.markdown(msg["content"])

    # Suggested questions (shown when history is short)
    if len(st.session_state.chat_history) <= 2:
        st.markdown('<div style="font-size:0.85rem;font-weight:600;color:#64748b;margin:12px 0 8px 0;">💡 Try asking:</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED_QUESTIONS[:6]):
            with cols[i % 2]:
                if st.button(q, key=f"suggested_{i}", use_container_width=True):
                    _handle_message(q)
                    st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask me anything about travel... 🌍"):
        _handle_message(prompt)
        st.rerun()

    # Clear chat button
    if len(st.session_state.chat_history) > 1:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                _init_chat_state()
                st.rerun()


def _handle_message(user_message: str):
    """Add user message, get AI response, update history."""
    st.session_state.chat_history.append({"role": "user", "content": user_message})
    with st.spinner("🤖 Thinking..."):
        try:
            response = chat_with_ai(user_message, st.session_state.chat_history[:-1])
        except Exception:
            response = "Sorry, I encountered an error. Please try again."
    st.session_state.chat_history.append({"role": "assistant", "content": response})
