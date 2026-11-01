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


# Budget tiers (based on the minimum per-person trip cost, in rupees)
CHEAP_BELOW = 2500
ROYAL_FROM = 8000
TIERS = ["Cheap", "Mid-range", "Royal / Luxury"]


def budget_tier(budget_min) -> str:
    try:
        v = float(budget_min)
    except (TypeError, ValueError):
        return "Mid-range"
    if v < CHEAP_BELOW:
        return "Cheap"
    if v < ROYAL_FROM:
        return "Mid-range"
    return "Royal / Luxury"


@st.cache_data
def load_india_places() -> pd.DataFrame:
    """All-India places, from cheap student trips to royal / luxury stays."""
    path = os.path.join(BASE_DIR, "data_india_places.csv")
    cols = ["place", "state", "category", "budget_min", "budget_max",
            "highlight", "latitude", "longitude", "aliases", "tier"]
    try:
        df = pd.read_csv(path)
        df["aliases"] = df["aliases"].fillna("")
        df["tier"] = df["budget_min"].apply(budget_tier)
        return df
    except Exception:
        return pd.DataFrame(columns=cols)
