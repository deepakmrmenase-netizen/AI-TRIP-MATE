"""
TripMate AI - Configuration Module
Central configuration for the application.
"""

import os

# Load .env for local development (safe no-op if file is absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── App Info ────────────────────────────────────────────────────────────────
APP_NAME = "TripMate AI"
APP_TAGLINE = "Plan Smarter. Travel More. Spend Less."
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "An AI-powered travel planning platform created to help students "
    "discover destinations, build personalized itineraries and manage "
    "their travel budgets."
)

# ─── API Keys ─────────────────────────────────────────────────────────────────
# Priority: Streamlit Secrets (Cloud) → environment variable (.env / system)
def _get_secret(key: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets first, then os.environ."""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)

GEMINI_API_KEY = _get_secret("AI_API_KEY") or _get_secret("GEMINI_API_KEY")
MAP_API_KEY    = _get_secret("MAP_API_KEY")

# ─── Demo / Fallback ──────────────────────────────────────────────────────────
DEMO_MODE = not bool(GEMINI_API_KEY)

# ─── Currency ─────────────────────────────────────────────────────────────────
CURRENCY_SYMBOL = "₹"
CURRENCY_CODE = "INR"

# ─── Budget Presets ───────────────────────────────────────────────────────────
BUDGET_PRESETS = [1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000]

BUDGET_CATEGORIES = [
    "Transportation",
    "Accommodation",
    "Food",
    "Activities",
    "Miscellaneous",
]

# Default budget split (%)
DEFAULT_BUDGET_SPLIT = {
    "Transportation": 30,
    "Accommodation": 30,
    "Food": 25,
    "Activities": 10,
    "Miscellaneous": 5,
}

# ─── Travel Interests ─────────────────────────────────────────────────────────
TRAVEL_INTERESTS = [
    "🌄 Nature",
    "🏛️ History",
    "🏖️ Beaches",
    "🏔️ Mountains",
    "📸 Photography",
    "🍴 Food",
    "🛍️ Shopping",
    "🎢 Adventure",
    "🛕 Spiritual",
    "🎨 Culture",
    "🎶 Entertainment",
]

# ─── Transportation Options ───────────────────────────────────────────────────
TRANSPORT_OPTIONS = ["🚌 Bus", "🚆 Train", "✈️ Flight", "🚕 Cab", "🚇 Metro", "🚶 Walking", "🚲 Bike"]

# ─── Accommodation Options ────────────────────────────────────────────────────
ACCOMMODATION_OPTIONS = [
    "🏨 Budget Hotel",
    "🛏️ Hostel",
    "🏠 Homestay",
    "🏡 Guest House",
    "🎓 Student Accommodation",
]

# ─── Food Preferences ─────────────────────────────────────────────────────────
FOOD_OPTIONS = [
    "🥗 Vegetarian",
    "🍗 Non-Vegetarian",
    "🌱 Vegan",
    "🍛 Local Food",
    "🥘 Street Food",
    "💰 Budget Food",
]

# ─── Popular Destinations ─────────────────────────────────────────────────────
POPULAR_DESTINATIONS = [
    "Mysuru", "Bengaluru", "Chikkamagaluru", "Coorg",
    "Hampi", "Udupi", "Mangaluru", "Goa", "Ooty", "Hyderabad",
]
