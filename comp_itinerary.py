"""
TripMate AI - Itinerary Component
Renders a complete AI-generated trip itinerary with beautiful cards.
"""

import streamlit as st
from util_helpers import format_inr


PERIOD_META = {
    "morning":   ("🌅", "Morning",   "#eff6ff", "#bfdbfe", "#1d4ed8"),
    "afternoon": ("☀️", "Afternoon", "#fff7ed", "#fed7aa", "#c2410c"),
    "evening":   ("🌇", "Evening",   "#faf5ff", "#e9d5ff", "#7c3aed"),
    "night":     ("🌙", "Night",     "#f8fafc", "#e2e8f0", "#334155"),
}


def _field_row(label: str, value, icon: str = ""):
    if value is None or str(value).strip() == "":
        return ""
    return f"""
<div style="display:flex; gap:8px; margin-bottom:4px; font-size:0.875rem;">
  <span style="color:#64748b; min-width:130px; font-weight:500;">{icon} {label}</span>
  <span style="color:#1e293b;">{value}</span>
</div>"""


def render_trip_summary(trip_data: dict):
    """Render the trip summary banner."""
    summary = trip_data.get("trip_summary", {})
    is_demo = trip_data.get("_demo_mode", False)

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0ea5e9,#3b82f6,#6366f1);
            border-radius:20px; padding:28px 32px; color:white; margin-bottom:24px;
            box-shadow:0 8px 32px rgba(59,130,246,0.3);">
  <div style="font-size:1.8rem; font-weight:800; margin-bottom:4px;">
    ✈️ {summary.get('destination','Destination')} Trip Plan
  </div>
  <div style="opacity:0.85; font-size:0.95rem; margin-bottom:20px;">
    📍 {summary.get('origin','Origin')} → {summary.get('destination','Destination')} &nbsp;|&nbsp;
    📅 {summary.get('duration','N/A')} &nbsp;|&nbsp;
    👥 {summary.get('travelers',1)} Traveler{'s' if summary.get('travelers',1)>1 else ''}
  </div>
  <div style="display:flex; gap:20px; flex-wrap:wrap;">
    <div style="background:rgba(255,255,255,0.18); border-radius:12px; padding:12px 20px; text-align:center;">
      <div style="font-size:1.4rem; font-weight:700;">{format_inr(summary.get('total_budget',0))}</div>
      <div style="font-size:0.75rem; opacity:0.85;">Total Budget</div>
    </div>
    <div style="background:rgba(255,255,255,0.18); border-radius:12px; padding:12px 20px; text-align:center;">
      <div style="font-size:1.4rem; font-weight:700;">{format_inr(summary.get('estimated_cost',0))}</div>
      <div style="font-size:0.75rem; opacity:0.85;">Estimated Cost</div>
    </div>
    <div style="background:rgba(255,255,255,0.18); border-radius:12px; padding:12px 20px; text-align:center;">
      <div style="font-size:1.4rem; font-weight:700;">{format_inr(summary.get('savings',0))}</div>
      <div style="font-size:0.75rem; opacity:0.85;">Estimated Savings</div>
    </div>
    <div style="background:rgba(255,255,255,0.18); border-radius:12px; padding:12px 20px; text-align:center;">
      <div style="font-size:1.4rem; font-weight:700;">{summary.get('travel_style','Budget')}</div>
      <div style="font-size:0.75rem; opacity:0.85;">Travel Style</div>
    </div>
  </div>
  {"<div style='margin-top:14px; background:rgba(0,0,0,0.2); border-radius:8px; padding:6px 14px; font-size:0.8rem; display:inline-block;'>🤖 Demo Mode – Add AI API key for personalised plans</div>" if is_demo else ""}
</div>
""", unsafe_allow_html=True)


def render_period_card(period: str, data: dict):
    """Render a single time-of-day card (morning/afternoon/evening/night)."""
    if not data:
        return
    emoji, label, bg, border, accent = PERIOD_META.get(period, ("•", period.title(), "#f8fafc", "#e2e8f0", "#334155"))

    cost = data.get("cost", 0)

    # Build field rows
    skip_keys = {"cost"}
    rows_html = ""
    field_icons = {
        "place": "📍",
        "activity": "🎯",
        "transport": "🚌",
        "duration": "⏱️",
        "lunch": "🍽️",
        "accommodation": "🏨",
        "dinner": "🍴",
    }
    for key, value in data.items():
        if key in skip_keys:
            continue
        icon = field_icons.get(key, "•")
        label_text = key.replace("_", " ").title()
        rows_html += _field_row(label_text, value, icon)

    st.markdown(f"""
<div style="background:{bg}; border:1px solid {border}; border-radius:14px; padding:16px 18px; margin-bottom:12px;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <div style="font-size:1rem; font-weight:700; color:{accent};">{emoji} {label}</div>
    <div style="font-size:0.82rem; font-weight:600; color:{accent}; background:rgba(255,255,255,0.7);
                border-radius:8px; padding:3px 10px;">Est. {format_inr(cost)}</div>
  </div>
  {rows_html}
</div>
""", unsafe_allow_html=True)


def render_day_plan(day: dict, day_number: int):
    """Render a complete day plan inside an expander."""
    with st.expander(f"📅  Day {day_number}", expanded=(day_number == 1)):
        for period in ["morning", "afternoon", "evening", "night"]:
            period_data = day.get(period)
            if period_data and isinstance(period_data, dict):
                render_period_card(period, period_data)


def render_full_itinerary(trip_data: dict):
    """
    Render the full AI-generated itinerary.
    """
    # Trip summary banner
    render_trip_summary(trip_data)

    # Day-by-day plan
    st.markdown('<div class="tm-section-header">📅 Day-by-Day Itinerary</div>', unsafe_allow_html=True)
    days = trip_data.get("days", [])
    if not days:
        st.info("No day-by-day plan available. Try generating a new trip.")
        return
    for i, day in enumerate(days, 1):
        render_day_plan(day, i)

    # Money saving tips
    tips = trip_data.get("money_saving_tips", trip_data.get("tips", []))
    if tips:
        st.markdown('<div class="tm-section-header">💡 AI Money-Saving Tips</div>', unsafe_allow_html=True)
        tips_html = "".join(f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #f1f5f9;"><span style="color:#16a34a;font-weight:700;">✓</span><span style="color:#374151;font-size:0.9rem;">{t}</span></div>' for t in tips)
        potential = trip_data.get("trip_summary", {}).get("savings", 0)
        st.markdown(f"""
<div class="tm-card tm-card-green">
  {tips_html}
  {"<div style='margin-top:12px;background:#16a34a;color:white;border-radius:10px;padding:10px 16px;font-weight:600;'>💰 Potential Savings: " + format_inr(potential) + " by following these tips</div>" if potential else ""}
</div>
""", unsafe_allow_html=True)

    # Safety tips
    safety_tips = trip_data.get("safety_tips", [])
    if safety_tips:
        st.markdown('<div class="tm-section-header">🛡️ Student Travel Safety</div>', unsafe_allow_html=True)
        safety_html = "".join(f'<div style="display:flex;gap:10px;padding:7px 0;"><span>🛡️</span><span style="color:#374151;font-size:0.88rem;">{t}</span></div>' for t in safety_tips)
        st.markdown(f'<div class="tm-card">{safety_html}</div>', unsafe_allow_html=True)

    st.info("⚠️ All costs shown are estimates only. Verify current prices, schedules, and availability before booking.")
