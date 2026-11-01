"""
TripMate AI - Map Service
Builds an interactive, *useful* trip map:
  - real road route (OSRM) with distance + driving time, falling back to a straight line
  - travel-cost estimates (bus / train / cab / bike) from the distance
  - itinerary stops pinned on the map, colour-coded by day
  - any city can be searched (OpenStreetMap Nominatim), not only the built-in ones

Every network call is optional: if it fails the app still shows a map.
"""

import math
import time

import requests
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

from data_loader import load_destinations, load_india_places

_HEADERS = {"User-Agent": "TripMateAI-StudentProject/1.0 (streamlit app)"}
_TIMEOUT = 8

# One colour per day (cycles if the trip is longer than 6 days)
DAY_COLORS = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#dc2626", "#0891b2"]

_FALLBACK_CITIES = {
    "bengaluru": (12.9716, 77.5946), "bangalore": (12.9716, 77.5946),
    "mysuru": (12.2958, 76.6394), "mysore": (12.2958, 76.6394),
    "coorg": (12.3375, 75.8069), "hampi": (15.3350, 76.4600),
    "goa": (15.2993, 74.1240), "ooty": (11.4102, 76.6950),
    "hyderabad": (17.3850, 78.4867), "chikkamagaluru": (13.3161, 75.7720),
    "udupi": (13.3409, 74.7421), "mangaluru": (12.9141, 74.8560),
    "mumbai": (19.0760, 72.8777), "delhi": (28.6139, 77.2090),
    "chennai": (13.0827, 80.2707), "kolkata": (22.5726, 88.3639),
    "pune": (18.5204, 73.8567),
    # Malnad / coastal Karnataka
    "sringeri": (13.4167, 75.2500), "agumbe": (13.5089, 75.0905),
    "horanadu": (13.2470, 75.3570), "kalasa": (13.2330, 75.3550),
    "kudremukh": (13.2150, 75.2500), "dharmasthala": (12.9500, 75.3800),
    "shivamogga": (13.9299, 75.5681), "shimoga": (13.9299, 75.5681),
    "hassan": (13.0033, 76.1004), "belur": (13.1651, 75.8655),
    "halebidu": (13.2130, 76.0080), "jog falls": (14.2293, 74.8125),
    "gokarna": (14.5479, 74.3188), "murudeshwar": (14.0940, 74.4850),
    "hubballi": (15.3647, 75.1240), "belagavi": (15.8497, 74.4977),
    "kollur": (13.8630, 74.8140), "sakleshpur": (12.9440, 75.7840),
}


# ─── Distance maths ───────────────────────────────────────────────────────────

def haversine_km(a, b) -> float:
    """Straight-line distance in km between two (lat, lon) points."""
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


# ─── Geocoding ────────────────────────────────────────────────────────────────

def _try_nominatim(query, india_first):
    attempts = [{"countrycodes": "in"}, {}] if india_first else [{}]
    answered = False
    for extra in attempts:
        try:
            resp = requests.get("https://nominatim.openstreetmap.org/search",
                                params={"q": query, "format": "json", "limit": 1, **extra},
                                headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code == 200:
                answered = True
                data = resp.json()
                if data:
                    return True, (float(data[0]["lat"]), float(data[0]["lon"]))
        except Exception:
            pass
    return answered, None


def _try_photon(query):
    try:
        resp = requests.get("https://photon.komoot.io/api/",
                            params={"q": query, "limit": 1}, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            feats = resp.json().get("features", [])
            if feats:
                lon, lat = feats[0]["geometry"]["coordinates"]
                return True, (float(lat), float(lon))
            return True, None
    except Exception:
        pass
    return False, None


def _try_open_meteo(query):
    try:
        resp = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                            params={"name": query.split(",")[0].strip(), "count": 1, "language": "en"},
                            headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            res = resp.json().get("results", [])
            if res:
                return True, (float(res[0]["latitude"]), float(res[0]["longitude"]))
            return True, None
    except Exception:
        pass
    return False, None


@st.cache_data(ttl=86400, show_spinner=False)
def _nominatim_cached(query: str, india_first: bool = True):
    """
    Find a place by trying up to three free geocoders in turn (OpenStreetMap Nominatim,
    Photon, Open-Meteo). Returns (lat, lon), or None if none of them knows the place.
    Raises if NO service could be reached at all, so a temporary outage is not cached.
    """
    any_answered = False
    for attempt in (lambda: _try_nominatim(query, india_first),
                    lambda: _try_photon(query),
                    lambda: _try_open_meteo(query)):
        answered, coords = attempt()
        any_answered = any_answered or answered
        if coords:
            return coords
    if not any_answered:
        raise RuntimeError("geocoding services unavailable")
    return None


def _nominatim(query: str, india_first: bool = True):
    try:
        return _nominatim_cached(query, india_first)
    except Exception:
        return None


def lookup_coordinates(name: str):
    """
    Find (lat, lon) for any place name.
    Order: built-in dataset -> built-in city list -> OpenStreetMap search.
    Returns (lat, lon) or None when the place can't be found.
    """
    key = (name or "").strip().lower()
    if not key:
        return None
    df = load_destinations()
    if not df.empty:
        row = df[df["destination"].str.lower() == key]
        if not row.empty:
            return float(row.iloc[0]["latitude"]), float(row.iloc[0]["longitude"])
    hit = _india_index().get(key)
    if hit:
        return hit
    if key in _FALLBACK_CITIES:
        return _FALLBACK_CITIES[key]
    return _nominatim(name.strip())


def get_coordinates(location_name: str):
    """Backward-compatible helper: always returns a coordinate (Bengaluru if unknown)."""
    return lookup_coordinates(location_name) or (12.9716, 77.5946)


# ─── All-India places: lookup + suggestions ───────────────────────────────────

TIER_COLORS = {"Cheap": "green", "Mid-range": "blue", "Royal / Luxury": "purple"}
TIER_HEX = {"Cheap": "#16a34a", "Mid-range": "#2563eb", "Royal / Luxury": "#7e22ce"}
CATEGORY_ICONS = {
    "Heritage & Royal": "university", "Nature & Hills": "tree", "Beach & Islands": "umbrella",
    "Spiritual": "bell", "City & Culture": "building", "Wildlife & Adventure": "paw",
    "Luxury Stay": "diamond",
}


def _india_index() -> dict:
    """name / alias (lower-case) -> (lat, lon) for every place in the all-India list."""
    idx = {}
    try:
        df = load_india_places()
        for _, r in df.iterrows():
            pt = (float(r["latitude"]), float(r["longitude"]))
            idx[str(r["place"]).strip().lower()] = pt
            for a in str(r["aliases"]).split(";"):
                if a.strip():
                    idx.setdefault(a.strip().lower(), pt)
    except Exception:
        pass
    return idx


def _dataset_matches(query: str, limit: int) -> list:
    q = query.strip().lower()
    out = []
    try:
        df = load_india_places()
    except Exception:
        return out
    scored = []
    for _, r in df.iterrows():
        names = [str(r["place"]).lower()] + [a.strip().lower() for a in str(r["aliases"]).split(";") if a.strip()]
        if any(n == q for n in names):
            score = 0
        elif any(n.startswith(q) for n in names):
            score = 1
        elif any(q in n for n in names):
            score = 2
        else:
            continue
        scored.append((score, str(r["place"]), r))
    scored.sort(key=lambda x: (x[0], x[1]))
    for _, name, r in scored[:limit]:
        out.append({"label": f"{name}, {r['state']}  ·  {r['tier']}", "name": name,
                    "lat": float(r["latitude"]), "lon": float(r["longitude"])})
    return out


def _label_from_parts(*parts) -> str:
    seen, clean = set(), []
    for p in parts:
        p = (p or "").strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            clean.append(p)
    return ", ".join(clean)


@st.cache_data(ttl=86400, show_spinner=False)
def _online_suggestions_cached(query: str):
    """Places in India matching the text (landmarks, towns, temples...). Raises if all services are down."""
    results, answered = [], False
    try:
        resp = requests.get("https://photon.komoot.io/api/",
                            params={"q": query, "limit": 12, "lat": 22.5, "lon": 79.0},
                            headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            answered = True
            for ft in resp.json().get("features", []):
                p = ft.get("properties", {})
                if p.get("countrycode", "").upper() != "IN" or not p.get("name"):
                    continue
                lon, lat = ft["geometry"]["coordinates"]
                label = _label_from_parts(p.get("name"), p.get("city") or p.get("district") or p.get("county"), p.get("state"))
                results.append({"label": label, "name": p["name"], "lat": float(lat), "lon": float(lon)})
    except Exception:
        pass
    if not results:
        try:
            resp = requests.get("https://nominatim.openstreetmap.org/search",
                                params={"q": query, "format": "json", "limit": 6,
                                        "countrycodes": "in", "addressdetails": 1},
                                headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code == 200:
                answered = True
                for it in resp.json():
                    addr = it.get("address", {})
                    name = it.get("name") or it.get("display_name", "").split(",")[0]
                    area = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
                    results.append({"label": _label_from_parts(name, area, addr.get("state")), "name": name,
                                    "lat": float(it["lat"]), "lon": float(it["lon"])})
        except Exception:
            pass
    if not answered:
        raise RuntimeError("place search unavailable")
    return results


def suggest_places(query: str, limit: int = 6) -> list:
    """
    'Did you mean...' list for a typed place: the built-in all-India list first,
    then any famous place / landmark / town in India from OpenStreetMap.
    Each item: label, name, lat, lon.
    """
    query = (query or "").strip()
    if len(query) < 2:
        return []
    out = _dataset_matches(query, 4)
    if len(query) >= 3:
        try:
            online = _online_suggestions_cached(query)
        except Exception:
            online = []
        have = {o["name"].lower() for o in out}
        for o in online:
            if o["name"].lower() not in have and len(out) < limit:
                out.append(o)
                have.add(o["name"].lower())
    return out[:limit]


# ─── Routing ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _osrm_route_cached(o_lat, o_lon, d_lat, d_lon):
    """Road route from OSRM. Raises on any failure so errors are NOT cached."""
    url = (f"https://router.project-osrm.org/route/v1/driving/"
           f"{o_lon},{o_lat};{d_lon},{d_lat}")
    resp = requests.get(url, params={"overview": "full", "geometries": "geojson"},
                        headers=_HEADERS, timeout=_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError("routing service unavailable")
    route = resp.json()["routes"][0]
    path = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    return {"path": path,
            "distance_km": route["distance"] / 1000.0,
            "duration_min": route["duration"] / 60.0}


def _osrm_route(o_lat, o_lon, d_lat, d_lon):
    try:
        return dict(_osrm_route_cached(o_lat, o_lon, d_lat, d_lon))
    except Exception:
        return None


def get_route(origin_coords, dest_coords) -> dict:
    """
    Road route between two points.
    Always returns a dict: path, distance_km, duration_min, is_road (bool).
    If the routing service is unavailable it falls back to a straight line
    (distance x 1.25 to approximate roads) so the app never breaks.
    """
    road = _osrm_route(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1])
    if road:
        road["is_road"] = True
        return road
    straight = haversine_km(origin_coords, dest_coords)
    est_km = straight * 1.25
    return {"path": [origin_coords, dest_coords], "distance_km": est_km,
            "duration_min": est_km / 50.0 * 60.0, "is_road": False}


def estimate_travel_options(distance_km: float, road_minutes: float) -> list:
    """
    Rough student-budget estimates for each way of travelling. All values are
    approximate (typical Indian fares) and shown to the user as estimates.
    Returns a list of dicts: mode, icon, low, high, hours, note.
    """
    d = max(distance_km, 1.0)
    options = [
        {"mode": "Bus (ordinary/express)", "icon": "🚌", "low": d * 1.0, "high": d * 1.8,
         "hours": d / 45.0, "note": "Cheapest on most routes"},
        {"mode": "Train (sleeper/2S)", "icon": "🚆", "low": max(60, d * 0.4), "high": max(120, d * 0.75),
         "hours": d / 55.0 + 0.3, "note": "Book on IRCTC in advance"},
        {"mode": "Shared cab / group", "icon": "🚕", "low": d * 9.0, "high": d * 14.0,
         "hours": road_minutes / 60.0, "note": "Total for the cab - split among friends"},
        {"mode": "Bike (fuel only)", "icon": "🏍️", "low": d * 2.0, "high": d * 3.0,
         "hours": road_minutes / 60.0 * 1.1, "note": "Per bike, one way"},
    ]
    for o in options:
        o["low"], o["high"] = int(round(o["low"], -1)), int(round(o["high"], -1))
    if distance_km > 600:
        options.append({"mode": "Flight", "icon": "✈️", "low": 2500, "high": 6000,
                        "hours": 1.5 + distance_km / 700.0, "note": "Book early for the best fares"})
    return options


def format_hours(hours: float) -> str:
    total_min = int(round(hours * 60))
    h, m = divmod(total_min, 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


# ─── Famous places along the route ────────────────────────────────────────────

_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# (tag key, tag value) -> label shown to the user
_KIND_LABELS = {
    ("tourism", "attraction"): "🎯 Attraction", ("tourism", "viewpoint"): "🌄 Viewpoint",
    ("tourism", "museum"): "🏛️ Museum", ("tourism", "zoo"): "🦁 Zoo",
    ("tourism", "theme_park"): "🎢 Theme park",
    ("historic", "castle"): "🏰 Fort / Castle", ("historic", "fort"): "🏰 Fort / Castle",
    ("historic", "palace"): "🏰 Palace", ("historic", "monument"): "🗿 Monument",
    ("historic", "ruins"): "🏛️ Ruins", ("historic", "temple"): "🛕 Heritage temple",
    ("natural", "waterfall"): "💦 Waterfall", ("natural", "peak"): "⛰️ Peak",
    ("natural", "beach"): "🏖️ Beach", ("natural", "hot_spring"): "♨️ Hot spring",
    ("amenity", "place_of_worship"): "🛕 Temple / Shrine",
}


def _simplify_path(path, max_points=40):
    if len(path) <= max_points:
        return list(path)
    step = (len(path) - 1) / (max_points - 1)
    return [path[int(round(i * step))] for i in range(max_points)]


def _classify(tags: dict) -> str:
    for key in ("tourism", "historic", "natural", "amenity"):
        label = _KIND_LABELS.get((key, tags.get(key)))
        if label:
            return label
    return "📌 Place"


@st.cache_data(ttl=86400, show_spinner=False)
def _overpass_places_cached(coords_key: tuple, radius_m: int):
    """Query OpenStreetMap (Overpass) for well-known places within radius of the route line."""
    flat = ",".join(f"{lat:.4f},{lon:.4f}" for lat, lon in coords_key)
    around = f"(around:{radius_m},{flat})"
    query = (
        "[out:json][timeout:25];("
        f'nwr["name"]["wikidata"]["tourism"~"^(attraction|viewpoint|museum|zoo|theme_park)$"]{around};'
        f'nwr["name"]["wikidata"]["historic"~"^(castle|fort|palace|monument|ruins|temple)$"]{around};'
        f'nwr["name"]["wikidata"]["natural"~"^(waterfall|peak|beach|hot_spring)$"]{around};'
        f'nwr["name"]["wikidata"]["amenity"="place_of_worship"]{around};'
        ");out center 200;"
    )
    for url in _OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, headers=_HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("elements", [])
        except Exception:
            continue
    raise RuntimeError("places service unavailable")   # not cached


def _overpass_places(coords_key: tuple, radius_m: int):
    try:
        return _overpass_places_cached(coords_key, radius_m)
    except Exception:
        return None


def find_places_along_route(path, radius_km: float = 6.0, limit: int = 15) -> list:
    """
    Well-known places (waterfalls, forts, temples, viewpoints, museums...) close to the
    route. Only places with a Wikipedia/Wikidata entry are kept, so the list stays
    "famous" instead of listing every small shrine.
    Returns a list ordered from start to end: name, kind, lat, lon, km_from_start, off_route_km.
    Returns [] if the service is unavailable.
    """
    if not path or len(path) < 2:
        return []
    elements = _overpass_places(tuple(_simplify_path(path)), int(radius_km * 1000))
    if not elements:
        return []

    # cumulative distance along the route
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + haversine_km(path[i - 1], path[i]))

    places, seen = [], set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not name or lat is None or lon is None or name.lower() in seen:
            continue
        seen.add(name.lower())
        # nearest route vertex -> position along the route
        best_i, best_d = 0, float("inf")
        for i, p in enumerate(path):
            d = haversine_km(p, (lat, lon))
            if d < best_d:
                best_i, best_d = i, d
        if best_d > radius_km * 1.5:
            continue
        places.append({
            "name": name, "kind": _classify(tags), "lat": lat, "lon": lon,
            "km_from_start": cum[best_i], "off_route_km": best_d,
            "wiki": 1 if "wikipedia" in tags else 0,
        })

    # keep the most notable (has a Wikipedia page, then closest to the road), then order by trip direction
    places.sort(key=lambda p: (-p["wiki"], p["off_route_km"]))
    places = places[:limit]
    places.sort(key=lambda p: p["km_from_start"])
    return places


# ─── Itinerary stops ──────────────────────────────────────────────────────────

_PERIOD_LABEL = {"morning": "🌅 Morning", "afternoon": "☀️ Afternoon", "evening": "🌇 Evening"}


def extract_stops(trip: dict, destination: str, dest_coords, max_stops: int = 12) -> list:
    """
    Turn a generated trip plan into map stops by looking each place up on
    OpenStreetMap (near the destination only, so wrong matches are dropped).
    Returns: list of dicts: day, period, name, activity, cost, lat, lon.
    """
    stops = []
    seen = set()
    for day in trip.get("days", []):
        d_num = day.get("day", len(stops) + 1)
        for period in ("morning", "afternoon", "evening"):
            p = day.get(period)
            if not isinstance(p, dict):
                continue
            name = str(p.get("place", "")).strip()
            if not name or name.lower() in seen or len(stops) >= max_stops:
                continue
            seen.add(name.lower())
            coords = _nominatim_with_delay(f"{name}, {destination}")
            if not coords:
                continue
            if haversine_km(coords, dest_coords) > 80:      # ignore far-away wrong matches
                continue
            stops.append({"day": d_num, "period": period, "name": name,
                          "activity": p.get("activity", ""), "cost": p.get("cost", 0),
                          "lat": coords[0], "lon": coords[1]})
    return stops


_SEEN_QUERIES = set()


def _nominatim_with_delay(query: str):
    """Nominatim asks for max 1 request/second; pause only for lookups not made before."""
    if query not in _SEEN_QUERIES:
        time.sleep(1.05)
        _SEEN_QUERIES.add(query)
    return _nominatim(query, False)


# ─── Map Builder ──────────────────────────────────────────────────────────────

def _numbered_icon(number, color):
    return folium.DivIcon(
        icon_size=(30, 30), icon_anchor=(15, 15),
        html=(f'<div style="background:{color};color:#fff;width:28px;height:28px;border-radius:50%;'
              f'border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.4);display:flex;'
              f'align-items:center;justify-content:center;font:700 13px sans-serif;">{number}</div>'),
    )


def build_trip_map(origin: str, destination: str, stops: list = None, route: dict = None,
                   origin_coords=None, dest_coords=None, places: list = None):
    """
    Build the Folium map. Returns (folium.Map, True) or (None, False).
    stops  : list from extract_stops()
    places : list from find_places_along_route() (famous places on the way)
    route  : dict from get_route()
    """
    if not FOLIUM_AVAILABLE:
        return None, False

    origin_coords = origin_coords or get_coordinates(origin)
    dest_coords = dest_coords or get_coordinates(destination)

    m = folium.Map(location=dest_coords, zoom_start=8, tiles="OpenStreetMap")

    # Route line
    if route:
        folium.PolyLine(
            route["path"], color="#2563eb", weight=5, opacity=0.85,
            dash_array=None if route.get("is_road") else "8 6",
            tooltip=f"{route['distance_km']:.0f} km - about {format_hours(route['duration_min'] / 60)} by road",
        ).add_to(m)

    # Start and destination
    folium.Marker(
        origin_coords,
        popup=folium.Popup(f"<b>Start: {origin}</b>", max_width=200),
        tooltip=f"Start: {origin}",
        icon=folium.Icon(color="blue", icon="home", prefix="fa"),
    ).add_to(m)
    folium.Marker(
        dest_coords,
        popup=folium.Popup(f"<b>Destination: {destination}</b>", max_width=200),
        tooltip=f"Destination: {destination}",
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
    ).add_to(m)

    # Itinerary stops, numbered and coloured per day
    points = [origin_coords, dest_coords]
    for i, s in enumerate(stops or [], 1):
        color = DAY_COLORS[(int(s["day"]) - 1) % len(DAY_COLORS)]
        html = (f"<b>{i}. {s['name']}</b><br>Day {s['day']} - {_PERIOD_LABEL.get(s['period'], s['period'])}"
                f"<br>{s['activity']}<br>Est. cost: Rs.{s['cost']}")
        folium.Marker(
            [s["lat"], s["lon"]],
            icon=_numbered_icon(i, color),
            popup=folium.Popup(html, max_width=260),
            tooltip=f"Day {s['day']}: {s['name']}",
        ).add_to(m)
        points.append((s["lat"], s["lon"]))

    # Famous places along the way (orange)
    for pl in places or []:
        html = (f"<b>{pl['name']}</b><br>{pl['kind']}<br>"
                f"~{pl['km_from_start']:.0f} km from {origin}<br>{pl['off_route_km']:.1f} km off the route")
        folium.Marker(
            [pl["lat"], pl["lon"]],
            icon=folium.Icon(color="orange", icon="camera", prefix="fa"),
            popup=folium.Popup(html, max_width=240),
            tooltip=f"{pl['name']} ({pl['kind']})",
        ).add_to(m)
        points.append((pl["lat"], pl["lon"]))

    # Zoom so everything is visible
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))
    return m, True


def build_destinations_map(destinations_df):
    """Map of every destination in the dataset."""
    if not FOLIUM_AVAILABLE:
        return None, False

    m = folium.Map(location=[15.0, 78.0], zoom_start=5, tiles="OpenStreetMap")
    for _, row in destinations_df.iterrows():
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
            name = str(row["destination"])
            state = str(row.get("state", ""))
            budget_min = int(row.get("budget_min", 0))
            budget_max = int(row.get("budget_max", 0))
            tip = str(row.get("student_tip", ""))
            popup_html = (f"<b>{name}</b><br>{state}<br>Rs.{budget_min:,} - Rs.{budget_max:,}"
                          f"<br>{tip[:80]}...")
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{name} | from Rs.{budget_min:,}",
                icon=folium.Icon(color="green", icon="map-marker", prefix="fa"),
            ).add_to(m)
        except Exception:
            continue
    return m, True


def render_map(folium_map, height: int = 400):
    """Render a Folium map with streamlit-folium."""
    if not FOLIUM_AVAILABLE or folium_map is None:
        return None
    try:
        return st_folium(folium_map, height=height, width=None, returned_objects=[])
    except Exception:
        return None


def build_india_map(places_df):
    """
    One map of all India: green = cheap, blue = mid-range, purple = royal / luxury.
    The marker icon shows the type (palace, hills, beach, temple...).
    """
    if not FOLIUM_AVAILABLE:
        return None, False

    m = folium.Map(location=[22.5, 79.0], zoom_start=5, tiles="OpenStreetMap")
    try:
        from folium.plugins import MarkerCluster
        layer = MarkerCluster(disable_clustering_at_zoom=8).add_to(m)
    except Exception:
        layer = m

    for _, r in places_df.iterrows():
        try:
            tier = str(r["tier"])
            html = (f"<b>{r['place']}</b><br>{r['state']} · {r['category']}<br>"
                    f"<b>Rs.{int(r['budget_min']):,} - Rs.{int(r['budget_max']):,}</b> per person ({tier})<br>"
                    f"{r['highlight']}")
            folium.Marker(
                [float(r["latitude"]), float(r["longitude"])],
                popup=folium.Popup(html, max_width=280),
                tooltip=f"{r['place']} - {tier}",
                icon=folium.Icon(color=TIER_COLORS.get(tier, "blue"),
                                 icon=CATEGORY_ICONS.get(str(r["category"]), "map-marker"), prefix="fa"),
            ).add_to(layer)
        except Exception:
            continue
    return m, True
