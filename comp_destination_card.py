"""
TripMate AI - Destination Card Component
Renders beautiful destination cards for the Explore page.
"""

import streamlit as st
from util_helpers import format_inr, truncate


def render_destination_card(dest: dict, show_plan_button: bool = True, key_prefix: str = ""):
    """
    Render a single destination card.
    dest: row dict from destinations DataFrame.
    """
    name = str(dest.get("destination", "Unknown"))
    state = str(dest.get("state", ""))
    description = str(dest.get("description", ""))
    budget_min = int(dest.get("budget_min", 0))
    budget_max = int(dest.get("budget_max", 0))
    duration = int(dest.get("duration_days", 2))
    best_time = str(dest.get("best_time", ""))
    travel_type = str(dest.get("travel_type", ""))
    popular_places = str(dest.get("popular_places", ""))
    student_tip = str(dest.get("student_tip", ""))

    # Build popular places badges
    places_list = [p.strip() for p in popular_places.split(",") if p.strip()][:5]
    badges_html = " ".join(
        f'<span class="tm-badge">{p}</span>' for p in places_list
    )

    # Travel type badge colour
    tt_lower = travel_type.lower()
    if "nature" in tt_lower or "adventure" in tt_lower:
        type_badge = f'<span class="tm-badge tm-badge-green">{travel_type}</span>'
    elif "beach" in tt_lower:
        type_badge = f'<span class="tm-badge tm-badge-orange">{travel_type}</span>'
    else:
        type_badge = f'<span class="tm-badge">{travel_type}</span>'

    st.markdown(f"""
<div class="tm-card" style="border-left:4px solid #3b82f6;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div>
      <div style="font-size:1.25rem; font-weight:700; color:#1e293b;">🌍 {name}</div>
      <div style="color:#64748b; font-size:0.85rem; margin-top:2px;">📍 {state}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:1.1rem; font-weight:700; color:#2563eb;">{format_inr(budget_min)} – {format_inr(budget_max)}</div>
      <div style="font-size:0.78rem; color:#64748b;">per person (est.)</div>
    </div>
  </div>

  <p style="color:#475569; font-size:0.88rem; margin:10px 0 12px 0; line-height:1.6;">{truncate(description, 160)}</p>

  <div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:10px; font-size:0.82rem; color:#64748b;">
    <span>⏱️ {duration} day{'s' if duration>1 else ''}</span>
    <span>🌤️ Best: {best_time}</span>
    {f'<span>{type_badge}</span>' if travel_type else ''}
  </div>

  <div style="margin-bottom:10px;">{badges_html}</div>

  <div style="background:#f0fdf4; border-radius:10px; padding:10px 14px; font-size:0.82rem; color:#15803d;">
    💡 <strong>Student Tip:</strong> {student_tip}
  </div>
</div>
""", unsafe_allow_html=True)

    if show_plan_button:
        if st.button(f"✈️ Plan Trip to {name}", key=f"{key_prefix}plan_{name}", use_container_width=True):
            # Pre-fill the planner with this destination
            st.session_state["planner_destination"] = name
            st.session_state.current_page = "AI Trip Planner"
            st.rerun()


def render_destination_grid(destinations_df, key_prefix: str = ""):
    """
    Render destinations in a 2-column card grid.
    """
    if destinations_df.empty:
        st.info("No destinations found matching your filters.")
        return

    rows = destinations_df.to_dict("records")
    # 2-column layout
    cols = st.columns(2)
    for i, dest in enumerate(rows):
        with cols[i % 2]:
            render_destination_card(dest, show_plan_button=True, key_prefix=f"{key_prefix}{i}_")


def render_budget_table(destinations_df, budget: int):
    """
    Render a clean table of destinations within the given budget.
    """
    if destinations_df.empty:
        st.info(f"No destinations found within {format_inr(budget)} budget.")
        return

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#eff6ff,#dbeafe); border-radius:14px; padding:16px 20px; margin-bottom:16px;">
  <div style="font-size:1.1rem; font-weight:700; color:#1d4ed8;">
    🌍 Weekend Trips Under {format_inr(budget)}
  </div>
  <div style="font-size:0.85rem; color:#3b82f6; margin-top:2px;">
    {len(destinations_df)} destinations found within your budget
  </div>
</div>
""", unsafe_allow_html=True)

    # Table header
    header_html = """
<div style="display:grid; grid-template-columns:1.5fr 0.8fr 0.8fr 0.8fr 0.8fr 0.8fr; gap:8px;
     background:#1e293b; color:white; border-radius:10px 10px 0 0; padding:10px 14px;
     font-size:0.8rem; font-weight:700; letter-spacing:0.5px;">
  <div>DESTINATION</div>
  <div>TRAVEL</div>
  <div>STAY</div>
  <div>FOOD</div>
  <div>ACTIVITIES</div>
  <div>TOTAL (EST.)</div>
</div>"""

    rows_html = ""
    for i, row in destinations_df.iterrows():
        bmin = int(row.get("budget_min", 0))
        travel = int(bmin * 0.30)
        stay = int(bmin * 0.30)
        food = int(bmin * 0.25)
        activities = int(bmin * 0.15)
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        rows_html += f"""
<div style="display:grid; grid-template-columns:1.5fr 0.8fr 0.8fr 0.8fr 0.8fr 0.8fr; gap:8px;
     background:{bg}; padding:10px 14px; font-size:0.83rem;
     border-bottom:1px solid #f1f5f9;">
  <div style="font-weight:600; color:#1e293b;">{row.get('destination','')} <span style="color:#64748b;font-weight:400;font-size:0.75rem;">{row.get('state','')}</span></div>
  <div style="color:#374151;">₹{travel:,}</div>
  <div style="color:#374151;">₹{stay:,}</div>
  <div style="color:#374151;">₹{food:,}</div>
  <div style="color:#374151;">₹{activities:,}</div>
  <div style="font-weight:700; color:#2563eb;">₹{bmin:,}</div>
</div>"""

    st.markdown(
        f'<div style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">{header_html}{rows_html}'
        f'<div style="background:#f8fafc; padding:8px 14px; font-size:0.75rem; color:#64748b; border-top:1px solid #e5e7eb;">* All prices are estimates only.</div></div>',
        unsafe_allow_html=True,
    )
