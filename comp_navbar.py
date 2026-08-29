"""
TripMate AI - Navbar / Sidebar
Sidebar navigation and global CSS injection.
"""

import streamlit as st
from app_config import APP_NAME, APP_TAGLINE, DEMO_MODE


PAGES = [
    ("🏠", "Home"),
    ("🧭", "AI Trip Planner"),
    ("🌍", "Explore Destinations"),
    ("💰", "Budget Planner"),
    ("🗺️", "Trip Map"),
    ("💬", "AI Travel Assistant"),
    ("❤️", "Saved Trips"),
    ("📋", "Travel Checklist"),
    ("ℹ️", "About"),
]


def inject_global_css():
    st.markdown("""
<style>
/* ── Google Font ──────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif !important;
}

/* ── Hide default Streamlit chrome ───────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── App background ──────────────────────────────────── */
.stApp {
    background: linear-gradient(160deg, #f0f7ff 0%, #ffffff 60%, #f0fdf4 100%);
}

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* ── Cards ───────────────────────────────────────────── */
.tm-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    transition: box-shadow 0.2s;
    margin-bottom: 16px;
}
.tm-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.11);
}
.tm-card-blue {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border-color: #bfdbfe;
}
.tm-card-green {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border-color: #bbf7d0;
}
.tm-card-orange {
    background: linear-gradient(135deg, #fff7ed 0%, #fed7aa 100%);
    border-color: #fdba74;
}
.tm-card-purple {
    background: linear-gradient(135deg, #faf5ff 0%, #e9d5ff 100%);
    border-color: #d8b4fe;
}

/* ── Hero Section ─────────────────────────────────────── */
.tm-hero {
    background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 50%, #6366f1 100%);
    border-radius: 24px;
    padding: 48px 40px;
    text-align: center;
    color: white;
    margin-bottom: 32px;
    box-shadow: 0 8px 40px rgba(59,130,246,0.3);
}
.tm-hero h1 {
    font-size: 2.6rem;
    font-weight: 800;
    margin: 0 0 12px 0;
    text-shadow: 0 2px 8px rgba(0,0,0,0.2);
    color: white !important;
}
.tm-hero p {
    font-size: 1.15rem;
    opacity: 0.92;
    margin: 0 0 28px 0;
    color: white !important;
}

/* ── Buttons ──────────────────────────────────────────── */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
    border: none !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(59,130,246,0.35) !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
    color: white !important;
    padding: 0.6rem 2rem !important;
    font-size: 1rem !important;
}

/* ── Section Headers ─────────────────────────────────── */
.tm-section-header {
    font-size: 1.35rem;
    font-weight: 700;
    color: #1e293b;
    margin: 24px 0 16px 0;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
}

/* ── Metric Override ─────────────────────────────────── */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 14px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #1e293b !important;
    font-weight: 700 !important;
    font-size: 1.5rem !important;
}

/* ── Chat messages ───────────────────────────────────── */
[data-testid="chat-message-container"] {
    border-radius: 16px;
    padding: 4px;
}

/* ── Tabs ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    color: #475569;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #3b82f6;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #3b82f6 !important;
}

/* ── Info / warning boxes ────────────────────────────── */
.stAlert {
    border-radius: 12px !important;
}

/* ── Expander ────────────────────────────────────────── */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: #1e293b !important;
}

/* ── Destination card badge ──────────────────────────── */
.tm-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 600;
    background: #dbeafe;
    color: #1d4ed8;
    margin: 2px 2px;
}
.tm-badge-green {
    background: #dcfce7;
    color: #15803d;
}
.tm-badge-orange {
    background: #fed7aa;
    color: #c2410c;
}

/* ── Progress bars ───────────────────────────────────── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #3b82f6, #6366f1);
    border-radius: 99px;
}

/* ── Input fields ────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 10px !important;
}

/* ── Demo mode banner ────────────────────────────────── */
.tm-demo-banner {
    background: linear-gradient(90deg, #fef3c7, #fde68a);
    border: 1px solid #fbbf24;
    border-radius: 12px;
    padding: 10px 18px;
    font-size: 0.88rem;
    color: #92400e;
    font-weight: 500;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


def render_sidebar() -> str:
    """
    Render the sidebar navigation.
    Returns the name of the currently selected page.
    """
    inject_global_css()

    # Initialise session state for page if not set
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"

    with st.sidebar:
        # ── Branding ───────────────────────────────────────────────────────
        st.markdown("""
<div style="text-align:center; padding: 20px 0 10px 0;">
  <div style="font-size:2.8rem; margin-bottom:4px;">✈️</div>
  <div style="font-size:1.35rem; font-weight:800; color:#f8fafc; letter-spacing:-0.5px;">TripMate AI</div>
  <div style="font-size:0.72rem; color:#94a3b8; margin-top:3px; font-style:italic;">Plan Smarter. Travel More. Spend Less.</div>
</div>
<hr style="border:none; border-top:1px solid #334155; margin:8px 0 16px 0;">
""", unsafe_allow_html=True)

        # ── Demo mode indicator ────────────────────────────────────────────
        if DEMO_MODE:
            st.markdown("""
<div style="background:#1e3a5f; border:1px solid #2563eb; border-radius:8px; padding:8px 12px;
     font-size:0.75rem; color:#93c5fd; text-align:center; margin-bottom:12px;">
  🤖 Demo AI Mode Active
</div>
""", unsafe_allow_html=True)

        # ── Navigation ─────────────────────────────────────────────────────
        st.markdown('<div style="font-size:0.72rem; font-weight:700; color:#64748b; letter-spacing:1px; padding:0 4px; margin-bottom:8px;">NAVIGATION</div>', unsafe_allow_html=True)

        for icon, page_name in PAGES:
            is_active = st.session_state.current_page == page_name
            btn_style = (
                "background:linear-gradient(90deg,#2563eb,#4f46e5); color:#fff; border-radius:10px;"
                if is_active
                else "background:transparent; color:#cbd5e1; border-radius:10px;"
            )
            if st.button(
                f"{icon}  {page_name}",
                key=f"nav_{page_name}",
                use_container_width=True,
            ):
                st.session_state.current_page = page_name
                st.rerun()

        # ── Bottom section ─────────────────────────────────────────────────
        st.markdown("""
<hr style="border:none; border-top:1px solid #334155; margin:16px 0 12px 0;">
<div style="text-align:center; font-size:0.72rem; color:#475569;">
  Made with ❤️ for Students<br>
  <span style="color:#2563eb;">TripMate AI v1.0</span>
</div>
""", unsafe_allow_html=True)

    return st.session_state.current_page
