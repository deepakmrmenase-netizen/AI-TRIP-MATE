"""
TripMate AI - Helper Utilities
Common formatting and utility functions used across the app.
"""

from datetime import date, datetime
import json
import re


# ─── Currency Formatting ──────────────────────────────────────────────────────

def format_inr(amount: float) -> str:
    """Format a number as Indian Rupees, e.g. ₹1,500."""
    try:
        return f"₹{int(amount):,}"
    except (TypeError, ValueError):
        return "₹0"


def format_inr_float(amount: float, decimals: int = 0) -> str:
    """Format float as INR with optional decimals."""
    try:
        if decimals == 0:
            return f"₹{int(round(amount)):,}"
        return f"₹{amount:,.{decimals}f}"
    except (TypeError, ValueError):
        return "₹0"


# ─── Date Helpers ─────────────────────────────────────────────────────────────

def calculate_duration(start_date, end_date) -> int:
    """Return number of trip days (inclusive)."""
    try:
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        return max(1, (end_date - start_date).days + 1)
    except Exception:
        return 1


def format_date_range(start_date, end_date) -> str:
    """Return a human-readable date range string."""
    try:
        fmt = "%d %b %Y"
        return f"{start_date.strftime(fmt)} – {end_date.strftime(fmt)}"
    except Exception:
        return "Date not set"


# ─── Text Helpers ─────────────────────────────────────────────────────────────

def truncate(text: str, max_chars: int = 120) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= max_chars else text[:max_chars - 3] + "..."


def clean_interests(interests: list) -> list:
    """Strip emoji prefixes from interest labels."""
    cleaned = []
    for item in interests:
        # Remove leading emoji + space if present
        parts = item.split(" ", 1)
        if len(parts) == 2:
            cleaned.append(parts[1])
        else:
            cleaned.append(item)
    return cleaned


def list_to_natural(items: list) -> str:
    """Convert a list to a natural language string: a, b and c."""
    if not items:
        return ""
    items = [str(i) for i in items]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ─── JSON Helpers ─────────────────────────────────────────────────────────────

def safe_json_parse(text: str):
    """
    Attempt to extract and parse JSON from an AI response string.
    Returns the parsed object or None on failure.
    """
    if not text:
        return None
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to extract a JSON block from markdown fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try to find the first { ... } block
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ─── Download Helpers ─────────────────────────────────────────────────────────

def generate_trip_text(trip_data: dict) -> str:
    """
    Convert a trip dictionary into a clean, readable plain-text itinerary
    suitable for download.
    """
    lines = []
    sep = "=" * 60

    lines.append(sep)
    lines.append("         ✈️  TripMate AI – Travel Itinerary")
    lines.append("         Plan Smarter. Travel More. Spend Less.")
    lines.append(sep)
    lines.append("")

    summary = trip_data.get("trip_summary", {})
    lines.append("TRIP SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Destination   : {summary.get('destination', 'N/A')}")
    lines.append(f"From          : {summary.get('origin', 'N/A')}")
    lines.append(f"Duration      : {summary.get('duration', 'N/A')}")
    lines.append(f"Travelers     : {summary.get('travelers', 'N/A')}")
    lines.append(f"Total Budget  : {format_inr(summary.get('total_budget', 0))}")
    lines.append(f"Est. Cost     : {format_inr(summary.get('estimated_cost', 0))}")
    lines.append(f"Travel Style  : {summary.get('travel_style', 'N/A')}")
    lines.append("")

    days = trip_data.get("days", [])
    for i, day in enumerate(days, 1):
        lines.append(sep)
        lines.append(f"DAY {i}")
        lines.append("-" * 40)
        for period, emoji in [("morning", "🌅"), ("afternoon", "☀️"), ("evening", "🌇"), ("night", "🌙")]:
            period_data = day.get(period, {})
            if period_data:
                lines.append(f"\n{emoji} {period.upper()}")
                for k, v in period_data.items():
                    if k not in ("cost",):
                        lines.append(f"  {k.replace('_', ' ').title()}: {v}")
                cost = period_data.get("cost")
                if cost is not None:
                    lines.append(f"  Estimated Cost: {format_inr(cost)}")
        lines.append("")

    breakdown = trip_data.get("budget_breakdown", {})
    if breakdown:
        lines.append(sep)
        lines.append("BUDGET BREAKDOWN (Estimated)")
        lines.append("-" * 40)
        for cat, amt in breakdown.items():
            lines.append(f"  {cat:<20}: {format_inr(amt)}")
        total = sum(breakdown.values())
        lines.append(f"  {'TOTAL':<20}: {format_inr(total)}")
        lines.append("")

    tips = trip_data.get("money_saving_tips", trip_data.get("tips", []))
    if tips:
        lines.append(sep)
        lines.append("💡 MONEY-SAVING TIPS")
        lines.append("-" * 40)
        for tip in tips:
            lines.append(f"  • {tip}")
        lines.append("")

    lines.append(sep)
    lines.append("🛡️ STUDENT TRAVEL SAFETY TIPS")
    lines.append("-" * 40)
    safety = [
        "Keep copies of your student ID and government ID separately.",
        "Share your travel itinerary with a family member or friend.",
        "Avoid isolated places after 10 PM.",
        "Keep emergency contacts saved: Police 100, Ambulance 108.",
        "Verify accommodation before booking.",
        "Keep your phone charged; carry a power bank.",
        "Note: All costs shown are estimates. Verify current prices before travel.",
    ]
    for tip in safety:
        lines.append(f"  • {tip}")
    lines.append("")
    lines.append(sep)
    lines.append("Generated by TripMate AI | All prices are estimates only.")
    lines.append(sep)

    return "\n".join(lines)
