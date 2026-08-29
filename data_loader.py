"""
TripMate AI - Data Loader
Centralised helper to load static data files (destinations CSV, sample trips JSON).
Cached with Streamlit's cache_data for performance.
"""

import json
import os
import pandas as pd
import streamlit as st


# os.path.abspath ensures this works on Streamlit Cloud where __file__ may be relative
# Data files live flat, next to this script (no subfolder) to survive GitHub uploads intact.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_data
def load_destinations() -> pd.DataFrame:
    """Load destinations from CSV and return as a DataFrame."""
    path = os.path.join(BASE_DIR, "data_destinations.csv")
    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        # Return minimal fallback DataFrame
        return pd.DataFrame(columns=[
            "destination", "state", "description", "budget_min", "budget_max",
            "duration_days", "best_time", "travel_type", "popular_places",
            "student_tip", "latitude", "longitude",
        ])


@st.cache_data
def load_sample_trips() -> dict:
    """Load sample trips from JSON file."""
    path = os.path.join(BASE_DIR, "data_sample_trips.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sample_trips": [], "demo_itinerary_template": {}}
