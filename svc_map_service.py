"""
TripMate AI - Map Service
Builds interactive Folium maps for trip visualisation.
Falls back gracefully when folium or streamlit-folium is unavailable.
"""

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

from data_loader import load_destinations


# ─── Coordinate Lookup ────────────────────────────────────────────────────────

def get_coordinates(location_name: str):
    """
    Return (lat, lon) for a location name from the static destinations dataset.
    Falls back to Bengaluru coordinates if not found.
    """
    df = load_destinations()
    if not df.empty:
        row = df[df["destination"].str.lower() == location_name.strip().lower()]
        if not row.empty:
            return float(row.iloc[0]["latitude"]), float(row.iloc[0]["longitude"])
    # Fallback: major Indian cities
    fallback = {
        "bengaluru": (12.9716, 77.5946),
        "bangalore": (12.9716, 77.5946),
        "mysuru": (12.2958, 76.6394),
        "mysore": (12.2958, 76.6394),
        "coorg": (12.3375, 75.8069),
        "hampi": (15.3350, 76.4600),
        "goa": (15.2993, 74.1240),
        "ooty": (11.4102, 76.6950),
        "hyderabad": (17.3850, 78.4867),
        "chikkamagaluru": (13.3161, 75.7720),
        "udupi": (13.3409, 74.7421),
        "mangaluru": (12.9141, 74.8560),
        "mumbai": (19.0760, 72.8777),
        "delhi": (28.6139, 77.2090),
        "chennai": (13.0827, 80.2707),
        "kolkata": (22.5726, 88.3639),
        "pune": (18.5204, 73.8567),
    }
    key = location_name.strip().lower()
    return fallback.get(key, (12.9716, 77.5946))  # default: Bengaluru


# ─── Map Builder ──────────────────────────────────────────────────────────────

def build_trip_map(origin: str, destination: str, attractions: list = None):
    """
    Build a Folium map showing origin, destination, and optional attractions.
    Returns (folium.Map, bool) – the map object and whether folium was available.
    attractions: list of dicts with keys: name, lat, lon, description, cost, duration
    """
    if not FOLIUM_AVAILABLE:
        return None, False

    origin_coords = get_coordinates(origin)
    dest_coords = get_coordinates(destination)

    # Centre the map between origin and destination
    centre_lat = (origin_coords[0] + dest_coords[0]) / 2
    centre_lon = (origin_coords[1] + dest_coords[1]) / 2

    m = folium.Map(
        location=[centre_lat, centre_lon],
        zoom_start=7,
        tiles="OpenStreetMap",
    )

    # Origin marker (blue)
    folium.Marker(
        location=origin_coords,
        popup=folium.Popup(
            f"<b>📍 Start: {origin}</b><br>Your starting point",
            max_width=200,
        ),
        tooltip=f"📍 {origin} (Start)",
        icon=folium.Icon(color="blue", icon="home", prefix="fa"),
    ).add_to(m)

    # Destination marker (red)
    folium.Marker(
        location=dest_coords,
        popup=folium.Popup(
            f"<b>🎯 Destination: {destination}</b><br>Your main destination",
            max_width=200,
        ),
        tooltip=f"🎯 {destination} (Destination)",
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
    ).add_to(m)

    # Draw a dashed line between origin and destination
    folium.PolyLine(
        locations=[origin_coords, dest_coords],
        color="#3b82d4",
        weight=2.5,
        opacity=0.7,
        dash_array="8 4",
    ).add_to(m)

    # Attraction markers (green)
    if attractions:
        for attr in attractions:
            try:
                lat = float(attr.get("lat", dest_coords[0]))
                lon = float(attr.get("lon", dest_coords[1]))
                name = attr.get("name", "Attraction")
                desc = attr.get("description", "")
                cost = attr.get("cost", "")
                duration = attr.get("duration", "")

                popup_html = f"<b>📌 {name}</b>"
                if desc:
                    popup_html += f"<br>{desc}"
                if cost:
                    popup_html += f"<br>💰 Est. cost: ₹{cost}"
                if duration:
                    popup_html += f"<br>⏱️ Duration: {duration}"

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8,
                    color="#22c55e",
                    fill=True,
                    fill_color="#22c55e",
                    fill_opacity=0.7,
                    popup=folium.Popup(popup_html, max_width=220),
                    tooltip=f"📌 {name}",
                ).add_to(m)
            except Exception:
                continue

    return m, True


def build_destinations_map(destinations_df):
    """
    Build a Folium map showing all destinations from the DataFrame.
    """
    if not FOLIUM_AVAILABLE:
        return None, False

    # Centre on India
    m = folium.Map(location=[15.0, 78.0], zoom_start=5, tiles="OpenStreetMap")

    for _, row in destinations_df.iterrows():
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            name = str(row["destination"])
            state = str(row.get("state", ""))
            budget_min = int(row.get("budget_min", 0))
            budget_max = int(row.get("budget_max", 0))
            tip = str(row.get("student_tip", ""))

            popup_html = (
                f"<b>🌍 {name}</b><br>"
                f"📍 {state}<br>"
                f"💰 ₹{budget_min:,} – ₹{budget_max:,}<br>"
                f"💡 {tip[:80]}..."
            )

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"🌍 {name} | ₹{budget_min:,}+",
                icon=folium.Icon(color="green", icon="map-marker", prefix="fa"),
            ).add_to(m)
        except Exception:
            continue

    return m, True


def render_map(folium_map, height: int = 400):
    """
    Render a Folium map using streamlit-folium.
    Returns the map output dict or None.
    """
    if not FOLIUM_AVAILABLE or folium_map is None:
        return None
    try:
        return st_folium(folium_map, height=height, width=None, returned_objects=[])
    except Exception:
        return None
