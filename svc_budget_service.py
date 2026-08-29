"""
TripMate AI - Budget Service
Budget calculation, formatting, and Plotly chart generation.
"""

import plotly.graph_objects as go
import plotly.express as px
from app_config import CURRENCY_SYMBOL, DEFAULT_BUDGET_SPLIT
from util_helpers import format_inr


# ─── Budget Calculation ───────────────────────────────────────────────────────

def calculate_budget(total_budget: float, breakdown: dict = None, travelers: int = 1, duration: int = 1) -> dict:
    """
    Calculate budget metrics.
    Returns a dict with total_cost, per_person, per_day, remaining, pct_used.
    """
    if breakdown:
        total_cost = sum(breakdown.values())
    else:
        total_cost = total_budget * 0.85  # 85% of budget as default estimate

    remaining = max(0, total_budget - total_cost)
    per_person = total_cost / max(travelers, 1)
    per_day = total_cost / max(duration, 1)
    pct_used = min(100, (total_cost / max(total_budget, 1)) * 100)

    return {
        "total_budget": total_budget,
        "total_cost": total_cost,
        "remaining": remaining,
        "per_person": per_person,
        "per_day": per_day,
        "pct_used": pct_used,
    }


def apply_budget_split(total_budget: float, split: dict = None) -> dict:
    """
    Split total_budget according to percentage split dict.
    Defaults to DEFAULT_BUDGET_SPLIT if split is None.
    """
    split = split or DEFAULT_BUDGET_SPLIT
    breakdown = {}
    for cat, pct in split.items():
        breakdown[cat] = round(total_budget * pct / 100)
    return breakdown


# ─── Plotly Charts ────────────────────────────────────────────────────────────

_CHART_COLORS = ["#3b82d4", "#22c55e", "#f59e0b", "#8b5cf6", "#ef4444"]

def make_donut_chart(breakdown: dict, title: str = "Budget Breakdown") -> go.Figure:
    """Create a Plotly donut chart for the budget breakdown."""
    labels = list(breakdown.keys())
    values = [max(0, v) for v in breakdown.values()]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.52,
        marker=dict(colors=_CHART_COLORS, line=dict(color="#ffffff", width=2)),
        textfont=dict(size=13),
        hovertemplate="<b>%{label}</b><br>₹%{value:,}<br>%{percent}<extra></extra>",
    )])

    total = sum(values)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#1f2328"), x=0.5),
        annotations=[dict(
            text=f"<b>{format_inr(total)}</b>",
            x=0.5, y=0.5, font_size=17,
            showarrow=False, font=dict(color="#1f2328"),
        )],
        legend=dict(orientation="v", x=1.0, y=0.5),
        margin=dict(t=60, b=20, l=20, r=20),
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def make_daily_bar_chart(days: list) -> go.Figure:
    """
    Create a Plotly bar chart showing estimated cost per day.
    days: list of day dicts from the trip plan.
    """
    day_labels = []
    day_costs = []

    for day in days:
        d_num = day.get("day", len(day_labels) + 1)
        day_labels.append(f"Day {d_num}")
        total = 0
        for period in ["morning", "afternoon", "evening", "night"]:
            period_data = day.get(period, {})
            total += period_data.get("cost", 0) if isinstance(period_data, dict) else 0
        day_costs.append(total)

    fig = go.Figure(data=[go.Bar(
        x=day_labels,
        y=day_costs,
        marker_color=_CHART_COLORS[0],
        marker_line_color="#ffffff",
        marker_line_width=1.5,
        hovertemplate="<b>%{x}</b><br>Est. cost: ₹%{y:,}<extra></extra>",
    )])
    fig.update_layout(
        title=dict(text="Estimated Daily Spending", font=dict(size=16, color="#1f2328"), x=0.5),
        xaxis=dict(title="", tickfont=dict(size=12)),
        yaxis=dict(title="Est. Cost (₹)", tickfont=dict(size=12), tickprefix="₹"),
        margin=dict(t=60, b=40, l=60, r=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def make_category_bar_chart(breakdown: dict, budget: float) -> go.Figure:
    """Bar chart comparing budget allocation vs actual estimate per category."""
    cats = list(breakdown.keys())
    estimates = [max(0, v) for v in breakdown.values()]
    budget_alloc = [budget * DEFAULT_BUDGET_SPLIT.get(c, 10) / 100 for c in cats]

    fig = go.Figure(data=[
        go.Bar(
            name="Budget Allocated",
            x=cats,
            y=budget_alloc,
            marker_color="#cbd5e1",
            hovertemplate="<b>%{x}</b><br>Budget: ₹%{y:,}<extra></extra>",
        ),
        go.Bar(
            name="Estimated Spend",
            x=cats,
            y=estimates,
            marker_color=_CHART_COLORS[0],
            hovertemplate="<b>%{x}</b><br>Est. Spend: ₹%{y:,}<extra></extra>",
        ),
    ])
    fig.update_layout(
        barmode="group",
        title=dict(text="Budget Allocated vs Estimated Spend", font=dict(size=16, color="#1f2328"), x=0.5),
        xaxis=dict(title="", tickfont=dict(size=12)),
        yaxis=dict(title="Amount (₹)", tickfont=dict(size=12), tickprefix="₹"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(t=80, b=40, l=60, r=20),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
