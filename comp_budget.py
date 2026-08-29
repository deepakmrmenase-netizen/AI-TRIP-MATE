"""
TripMate AI - Budget Component
Budget analysis dashboard with Plotly charts and metrics.
"""

import streamlit as st
from svc_budget_service import (
    calculate_budget,
    make_donut_chart,
    make_daily_bar_chart,
    make_category_bar_chart,
)
from util_helpers import format_inr


def render_budget_metrics(total_budget: float, total_cost: float, travelers: int = 1, duration: int = 1):
    """Render budget metric cards in a 4-column layout."""
    metrics = calculate_budget(total_budget, {"_dummy": total_cost}, travelers, duration)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Total Budget", format_inr(total_budget))
    with col2:
        delta = format_inr(metrics["remaining"])
        st.metric("📊 Estimated Cost", format_inr(total_cost), delta=f"{delta} remaining")
    with col3:
        st.metric("👤 Per Person", format_inr(metrics["per_person"]))
    with col4:
        st.metric("📅 Per Day", format_inr(metrics["per_day"]))


def render_budget_progress(total_budget: float, total_cost: float):
    """Render a budget usage progress bar."""
    pct = min(1.0, total_cost / max(total_budget, 1))
    color = "#16a34a" if pct < 0.8 else ("#f59e0b" if pct < 1.0 else "#ef4444")
    label = "✅ Within Budget" if pct < 0.9 else ("⚠️ Near Budget Limit" if pct < 1.0 else "🚨 Over Budget!")

    st.markdown(f"""
<div style="background:#f8fafc; border:1px solid #e5e7eb; border-radius:14px; padding:16px 20px; margin:12px 0;">
  <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
    <span style="font-weight:600; color:#374151;">Budget Usage</span>
    <span style="font-weight:700; color:{color};">{label}</span>
  </div>
  <div style="background:#e5e7eb; border-radius:99px; height:12px; overflow:hidden;">
    <div style="background:{color}; width:{pct*100:.1f}%; height:100%; border-radius:99px; transition:width 0.5s;"></div>
  </div>
  <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:0.8rem; color:#64748b;">
    <span>{format_inr(total_cost)} used</span>
    <span>{pct*100:.1f}%</span>
    <span>{format_inr(total_budget)} total</span>
  </div>
</div>
""", unsafe_allow_html=True)


def render_budget_dashboard(trip_data: dict):
    """
    Render the complete budget analysis dashboard for a generated trip.
    """
    summary = trip_data.get("trip_summary", {})
    breakdown = trip_data.get("budget_breakdown", {})
    days = trip_data.get("days", [])

    total_budget = summary.get("total_budget", 0)
    total_cost = summary.get("estimated_cost", sum(breakdown.values()) if breakdown else 0)
    travelers = summary.get("travelers", 1)
    duration = len(days) if days else 1

    st.markdown('<div class="tm-section-header">💰 Budget Analysis</div>', unsafe_allow_html=True)

    # Metrics row
    render_budget_metrics(total_budget, total_cost, travelers, duration)
    st.markdown("<br>", unsafe_allow_html=True)
    render_budget_progress(total_budget, total_cost)

    # Charts
    tab1, tab2, tab3 = st.tabs(["🍩 Breakdown", "📊 Daily Spend", "📈 Budget vs Estimate"])

    with tab1:
        if breakdown:
            fig = make_donut_chart(breakdown, "Budget Breakdown by Category")
            st.plotly_chart(fig, use_container_width=True)
            # Table
            st.markdown("**Estimated Breakdown**")
            rows = "".join(
                f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f1f5f9;">'
                f'<span style="color:#374151;">{cat}</span>'
                f'<span style="font-weight:600;color:#1e293b;">{format_inr(amt)}</span></div>'
                for cat, amt in breakdown.items()
            )
            rows += (
                f'<div style="display:flex;justify-content:space-between;padding:9px 0;margin-top:4px;">'
                f'<span style="font-weight:700;color:#1e293b;">Total (Estimated)</span>'
                f'<span style="font-weight:700;color:#2563eb;">{format_inr(total_cost)}</span></div>'
            )
            st.markdown(f'<div class="tm-card">{rows}</div>', unsafe_allow_html=True)
        else:
            st.info("No breakdown data available.")

    with tab2:
        if days:
            fig2 = make_daily_bar_chart(days)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Generate a trip plan to see daily spending.")

    with tab3:
        if breakdown:
            fig3 = make_category_bar_chart(breakdown, total_budget)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No budget data available.")
