"""
TripMate AI - Travel Service
Destination search, filtering, and travel utility functions.
"""

import pandas as pd
from data_loader import load_destinations


def search_destinations(query: str = "", travel_type: str = "All", max_budget: int = 0) -> pd.DataFrame:
    """
    Filter destinations by search query, travel type, and budget.
    Returns a filtered DataFrame.
    """
    df = load_destinations()
    if df.empty:
        return df

    if query:
        q = query.strip().lower()
        mask = (
            df["destination"].str.lower().str.contains(q, na=False) |
            df["state"].str.lower().str.contains(q, na=False) |
            df["description"].str.lower().str.contains(q, na=False) |
            df["travel_type"].str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    if travel_type and travel_type != "All":
        df = df[df["travel_type"].str.lower().str.contains(travel_type.lower(), na=False)]

    if max_budget and max_budget > 0:
        df = df[df["budget_min"] <= max_budget]

    return df.reset_index(drop=True)


def get_destination_by_name(name: str) -> dict:
    """
    Return a single destination row as a dict.
    Returns an empty dict if not found.
    """
    df = load_destinations()
    if df.empty:
        return {}
    row = df[df["destination"].str.lower() == name.strip().lower()]
    if not row.empty:
        return row.iloc[0].to_dict()
    return {}


def get_trips_under_budget(budget: int) -> pd.DataFrame:
    """Return destinations whose budget_min is <= the given budget."""
    df = load_destinations()
    if df.empty:
        return df
    return df[df["budget_min"] <= budget].sort_values("budget_min").reset_index(drop=True)


def get_all_travel_types() -> list:
    """Return unique travel types from destinations data."""
    df = load_destinations()
    if df.empty:
        return ["All"]
    types = df["travel_type"].dropna().unique().tolist()
    return ["All"] + sorted(types)


def get_travel_duration_options() -> list:
    return ["Any", "1 day", "2 days", "3+ days", "Weekend (2 days)"]
