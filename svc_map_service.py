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

from data_loader import load_destinations, load_india_places, load_route_stops

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

# OSRM gives free-flow driving time. Real Indian roads (traffic, ghats, towns) are slower,
# so the time we show is OSRM x this factor. (Google's time already includes traffic.)
TRAFFIC_FACTOR = 1.3

_OSRM_URLS = [
    "https://router.project-osrm.org/route/v1/driving",
    "https://routing.openstreetmap.de/routed-car/route/v1/driving",
]


# ---- turn-by-turn text -------------------------------------------------------

def _step_text(step: dict) -> str:
    man = step.get("maneuver", {}) or {}
    typ, mod = man.get("type", ""), man.get("modifier", "")
    name, ref = step.get("name") or "", step.get("ref") or ""
    road = f"{ref} ({name})" if ref and name and ref not in name else (name or ref)
    on = f" on {road}" if road else ""
    onto = f" onto {road}" if road else ""
    if typ == "depart":
        return f"Head {mod or 'ahead'}{on}"
    if typ == "arrive":
        return "Arrive at your destination"
    if typ in ("roundabout", "rotary", "roundabout turn"):
        ex = man.get("exit")
        return f"At the roundabout take exit {ex}{onto}" if ex else f"Go through the roundabout{onto}"
    if typ in ("turn", "end of road"):
        if mod == "straight":
            return f"Continue straight{on}"
        return f"Turn {mod}{onto}".replace("  ", " ")
    if typ == "fork":
        return f"Keep {mod or 'ahead'} at the fork{onto}"
    if typ == "off ramp":
        return f"Take the exit{onto}"
    if typ == "on ramp":
        return f"Take the ramp{onto}"
    if typ == "merge":
        return f"Merge{onto}"
    return f"Continue{on}"


def _summarize_steps(steps: list, max_steps: int = 80) -> list:
    """Readable directions: [{'text': 'Turn left onto NH 275', 'km': 12.3}, ...]."""
    out = []
    for i, st_ in enumerate(steps):
        km = float(st_.get("distance", 0)) / 1000.0
        typ = (st_.get("maneuver", {}) or {}).get("type", "")
        if km < 0.3 and typ not in ("depart", "arrive") and i not in (0, len(steps) - 1):
            continue
        out.append({"text": _step_text(st_), "km": km})
    return out[:max_steps]


def _via_road(steps: list) -> str:
    """Name of the road the route follows for the most kilometres."""
    by_road = {}
    for st_ in steps:
        r = st_.get("ref") or st_.get("name") or ""
        if r:
            by_road[r] = by_road.get(r, 0.0) + float(st_.get("distance", 0))
    return max(by_road, key=by_road.get) if by_road else ""


def _parse_osrm_routes(data: dict) -> list:
    out = []
    for r in data.get("routes", []):
        steps = [s for leg in r.get("legs", []) for s in leg.get("steps", [])]
        out.append({
            "path": [(lat, lon) for lon, lat in r["geometry"]["coordinates"]],
            "distance_km": r["distance"] / 1000.0,
            "duration_min": r["duration"] / 60.0,
            "steps": _summarize_steps(steps),
            "via": _via_road(steps),
        })
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def _osrm_route_cached(o_lat, o_lon, d_lat, d_lon):
    """
    Road routes (best + alternatives) from OSRM, trying two public servers.
    Raises when no server answered, so failures are NOT cached.
    """
    for base in _OSRM_URLS:
        try:
            resp = requests.get(f"{base}/{o_lon},{o_lat};{d_lon},{d_lat}",
                                params={"overview": "full", "geometries": "geojson",
                                        "alternatives": "true", "steps": "true"},
                                headers=_HEADERS, timeout=_TIMEOUT + 4)
            try:
                data = resp.json()
            except Exception:
                continue
            if data.get("code") == "NoRoute":
                return {"no_route": True}
            if resp.status_code == 200 and data.get("routes"):
                return {"routes": _parse_osrm_routes(data)}
        except Exception:
            continue
    raise RuntimeError("routing service unavailable")


def _osrm_route(o_lat, o_lon, d_lat, d_lon):
    try:
        return dict(_osrm_route_cached(o_lat, o_lon, d_lat, d_lon))
    except Exception:
        return None


# ---- optional: real Google Maps data (needs a Google Maps Platform API key) ---

def _google_key() -> str:
    try:
        v = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if v:
            return str(v)
    except Exception:
        pass
    import os
    return os.getenv("GOOGLE_MAPS_API_KEY", "")


def _decode_polyline(encoded: str) -> list:
    """Decode a Google encoded polyline into [(lat, lon), ...]."""
    pts, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lat:
                lat += delta
            else:
                lng += delta
        pts.append((lat / 1e5, lng / 1e5))
    return pts


@st.cache_data(ttl=3600, show_spinner=False)
def _google_route_cached(o_lat, o_lon, d_lat, d_lon, key: str):
    """Google Routes API (traffic-aware). Raises on any failure so it is NOT cached."""
    body = {
        "origin": {"location": {"latLng": {"latitude": o_lat, "longitude": o_lon}}},
        "destination": {"location": {"latLng": {"latitude": d_lat, "longitude": d_lon}}},
        "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": True, "units": "METRIC", "languageCode": "en-IN",
    }
    resp = requests.post(
        "https://routes.googleapis.com/directions/v2:computeRoutes", json=body, timeout=_TIMEOUT + 4,
        headers={"X-Goog-Api-Key": key, "Content-Type": "application/json",
                 "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.description"})
    if resp.status_code != 200:
        raise RuntimeError("google routes unavailable")
    routes = resp.json().get("routes", [])
    if not routes:
        raise RuntimeError("google found no route")
    out = []
    for r in routes:
        out.append({
            "path": _decode_polyline(r["polyline"]["encodedPolyline"]),
            "distance_km": r["distanceMeters"] / 1000.0,
            "duration_min": float(str(r["duration"]).rstrip("s")) / 60.0,
            "steps": [], "via": r.get("description", ""),
        })
    return out


def _google_route(o, d):
    key = _google_key()
    if not key:
        return None
    try:
        return list(_google_route_cached(o[0], o[1], d[0], d[1], key))
    except Exception:
        return None


def google_maps_link(o, d) -> str:
    """Link that opens this exact trip in Google Maps (works for everyone, no key needed)."""
    return (f"https://www.google.com/maps/dir/?api=1&origin={o[0]:.5f},{o[1]:.5f}"
            f"&destination={d[0]:.5f},{d[1]:.5f}&travelmode=driving")


# ---- main entry --------------------------------------------------------------


@st.cache_data(ttl=86400, show_spinner=False)
def _osrm_table_cached(src: tuple, dests: tuple):
    """Road distance + time from ONE start to MANY places in a single call. Raises on failure (not cached)."""
    pts = [src] + list(dests)
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in pts)
    for base in _OSRM_URLS:
        try:
            resp = requests.get(f"{base.replace('/route/', '/table/')}/{coords}",
                                params={"sources": "0", "annotations": "distance,duration"},
                                headers=_HEADERS, timeout=_TIMEOUT + 4)
            js = resp.json()
            if resp.status_code == 200 and js.get("code") == "Ok":
                return [(d, t) for d, t in zip(js["distances"][0][1:], js["durations"][0][1:])]
        except Exception:
            continue
    raise RuntimeError("table service unavailable")


def road_distances(origin, dests: list):
    """
    Real road [(km, minutes), ...] from origin to each place (OpenStreetMap routing), minutes include
    typical traffic. Returns None when the service is unreachable.
    """
    if not dests:
        return []
    try:
        res = _osrm_table_cached((round(origin[0], 5), round(origin[1], 5)),
                                 tuple((round(a, 5), round(b, 5)) for a, b in dests))
    except Exception:
        return None
    out = []
    for d, t in res:
        out.append((None, None) if d is None or t is None else (d / 1000.0, t / 60.0 * TRAFFIC_FACTOR))
    return out


def _label(r: dict) -> str:
    via = f"via {r['via']} - " if r.get("via") else ""
    return f"{via}{r['distance_km']:,.0f} km - {format_hours(r['duration_min'] / 60)}"


def get_route(origin_coords, dest_coords) -> dict:
    """
    Route between two points. Always returns a dict with:
      path, distance_km, duration_min, steps, via   (the best route)
      all        : list of every route found (best first) - alternatives like Google Maps
      source     : "google" | "osm" | "estimate"
      is_road    : real road route?      no_road: no road link exists (islands / overseas)
    Time from OpenStreetMap includes typical traffic (x1.3). Google's time already does.
    If routing services are unreachable: straight-line x 1.25 as an estimate.
    """
    straight = haversine_km(origin_coords, dest_coords)

    routes, source = _google_route(origin_coords, dest_coords), "google"
    if not routes:
        osrm = _osrm_route(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1])
        if osrm and (osrm.get("no_route") or osrm["routes"][0]["distance_km"] > straight * 2.5 + 80):
            return {"path": [origin_coords, dest_coords], "distance_km": straight, "steps": [], "via": "",
                    "duration_min": straight / 700.0 * 60.0 + 120.0, "is_road": False, "no_road": True,
                    "source": "estimate", "all": []}
        if osrm:
            routes, source = osrm["routes"], "osm"
            for r in routes:
                r["duration_min"] *= TRAFFIC_FACTOR
    if routes:
        best = dict(routes[0])
        best.update({"is_road": True, "no_road": False, "source": source, "all": routes})
        return best

    est_km = straight * 1.25
    return {"path": [origin_coords, dest_coords], "distance_km": est_km, "steps": [], "via": "",
            "duration_min": est_km / 40.0 * 60.0, "is_road": False, "no_road": False,
            "source": "estimate", "all": []}


def estimate_travel_options(distance_km: float, road_minutes: float, road_available: bool = True) -> list:
    """
    Rough cost / time for each way of travelling (typical Indian prices).
    Always estimates. Items with "seats" are per VEHICLE (cab, car, bike): use per_person_costs().
    Returns a list of dicts: mode, icon, low, high, hours, note, seats (optional).
    """
    d = max(distance_km, 1.0)
    flight = {"mode": "Flight", "icon": "✈️", "low": 2500, "high": 7000,
              "hours": 1.5 + d / 700.0, "note": "Book early for the best fares"}
    if not road_available:
        return [flight]          # islands / overseas: no bus, train or cab
    options = [
        {"mode": "Bus (ordinary/express)", "icon": "🚌", "low": d * 1.0, "high": d * 1.8,
         "hours": d / 45.0, "note": "Cheapest on most routes"},
        {"mode": "Train (2S / sleeper)", "icon": "🚆", "low": max(50, d * 0.4), "high": max(100, d * 1.1),
         "hours": d / 55.0 + 0.3, "note": "Book on IRCTC in advance"},
        {"mode": "Cab (one way)", "icon": "🚕", "low": d * 12.0, "high": d * 18.0, "seats": 4,
         "hours": road_minutes / 60.0, "note": "Split by up to 4 people. Tolls extra"},
        {"mode": "Own car (fuel)", "icon": "🚗", "low": d * 6.0, "high": d * 8.0, "seats": 4,
         "hours": road_minutes / 60.0, "note": "Petrol only. Tolls extra"},
        {"mode": "Bike (fuel only)", "icon": "🏍️", "low": d * 2.0, "high": d * 3.0, "seats": 2,
         "hours": road_minutes / 60.0 * 1.1, "note": "2 riders per bike"},
    ]
    for o in options:
        o["low"], o["high"] = int(round(o["low"], -1)), int(round(o["high"], -1))
    if distance_km > 600:
        options.append(flight)
    return options


def per_person_costs(options: list, travelers: int) -> list:
    """
    Add per-person numbers: pp_low / pp_high, plus total_low / total_high for vehicles.
    Vehicles are shared: 5 people in cars of 4 seats need 2 cars.
    """
    travelers = max(1, int(travelers))
    out = []
    for o in options:
        o = dict(o)
        if o.get("seats"):
            vehicles = -(-travelers // o["seats"])           # ceiling division
            o["total_low"], o["total_high"] = o["low"] * vehicles, o["high"] * vehicles
            o["vehicles"] = vehicles
            o["pp_low"] = int(round(o["total_low"] / travelers, -1))
            o["pp_high"] = int(round(o["total_high"] / travelers, -1))
        else:
            o["pp_low"], o["pp_high"] = o["low"], o["high"]
        out.append(o)
    return out


def format_hours(hours: float) -> str:
    total_min = int(round(hours * 60))
    h, m = divmod(total_min, 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


# ─── Famous places along the route ────────────────────────────────────────────

_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
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

_CATEGORY_KIND = {
    "Heritage & Royal": "🏰 Heritage", "Nature & Hills": "⛰️ Nature", "Beach & Islands": "🏖️ Beach",
    "Spiritual": "🛕 Spiritual", "City & Culture": "🏙️ City", "Wildlife & Adventure": "🐅 Wildlife",
    "Luxury Stay": "💎 Luxury stay",
}


def _simplify_path(path, max_points=40):
    if len(path) <= max_points:
        return list(path)
    step = (len(path) - 1) / (max_points - 1)
    return [path[int(round(i * step))] for i in range(max_points)]


def _densify(path, step_km=5.0):
    """Add points along long straight segments so 'distance to route' is accurate."""
    out = [path[0]]
    for a, b in zip(path, path[1:]):
        n = int(haversine_km(a, b) // step_km)
        for k in range(1, n + 1):
            f = k / (n + 1)
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
        out.append(b)
    return out


def _classify(tags: dict) -> str:
    for key in ("tourism", "historic", "natural", "amenity"):
        label = _KIND_LABELS.get((key, tags.get(key)))
        if label:
            return label
    return "📌 Place"


@st.cache_data(ttl=21600, show_spinner=False)
def _overpass_places_cached(coords_key: tuple, radius_m: int, strict: bool):
    """
    Query OpenStreetMap (Overpass) for places near the route line.
    strict=True  -> only places that have a Wikidata entry (famous ones)
    strict=False -> any named attraction / fort / waterfall (wider net)
    Raises if no server gave a usable answer (so failures and timeouts are NOT cached).
    """
    flat = ",".join(f"{lat:.4f},{lon:.4f}" for lat, lon in coords_key)
    around = f"(around:{radius_m},{flat})"
    if strict:
        body = (
            f'nwr["name"]["wikidata"]["tourism"~"^(attraction|viewpoint|museum|zoo|theme_park)$"]{around};'
            f'nwr["name"]["wikidata"]["historic"~"^(castle|fort|palace|monument|ruins|temple)$"]{around};'
            f'nwr["name"]["wikidata"]["natural"~"^(waterfall|peak|beach|hot_spring)$"]{around};'
            f'nwr["name"]["wikidata"]["amenity"="place_of_worship"]{around};'
        )
    else:
        body = (
            f'nwr["name"]["tourism"~"^(attraction|viewpoint|museum|zoo|theme_park)$"]{around};'
            f'nwr["name"]["historic"~"^(castle|fort|palace|monument|ruins)$"]{around};'
            f'nwr["name"]["natural"="waterfall"]{around};'
        )
    query = f"[out:json][timeout:10];({body});out center 120;"
    deadline = time.monotonic() + 14          # never make the user wait much longer than this
    for url in _OVERPASS_URLS:
        if time.monotonic() > deadline:
            break
        try:
            resp = requests.post(url, data={"data": query}, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            js = resp.json()
            remark = str(js.get("remark", "")).lower()
            if "error" in remark or "timed out" in remark or "out of memory" in remark:
                continue                       # server gave up: try the next one, don't cache
            return js.get("elements", [])
        except Exception:
            continue
    raise RuntimeError("places service unavailable")


_OVERPASS_DOWN_UNTIL = [0.0]     # after a failure, skip the slow online look-up for a few minutes


def _overpass_places(coords_key: tuple, radius_m: int, strict: bool = True):
    if time.monotonic() < _OVERPASS_DOWN_UNTIL[0]:
        return None
    try:
        return _overpass_places_cached(coords_key, radius_m, strict)
    except Exception:
        _OVERPASS_DOWN_UNTIL[0] = time.monotonic() + 180
        return None


def _along(path, cum, point):
    """(km from start along the route, distance off the route in km) for a point."""
    best_i, best_d = 0, float("inf")
    for i, p in enumerate(path):
        d = haversine_km(p, point)
        if d < best_d:
            best_i, best_d = i, d
    return cum[best_i], best_d


def _builtin_places_near_route(path, cum, radius_km: float, skip_near_ends_km: float = 8.0) -> list:
    """Places from TripMate's own all-India list that lie close to the route (works offline)."""
    out = []
    try:
        df = load_india_places()
    except Exception:
        return out
    if df.empty:
        return out
    start, end = path[0], path[-1]
    # coarse bounding box first (cheap), then exact distance
    lat_pad = radius_km / 111.0 + 0.1
    lons = [p[1] for p in path]; lats = [p[0] for p in path]
    lo_lat, hi_lat = min(lats) - lat_pad, max(lats) + lat_pad
    lo_lon, hi_lon = min(lons) - lat_pad * 1.2, max(lons) + lat_pad * 1.2
    for _, r in df.iterrows():
        lat, lon = float(r["latitude"]), float(r["longitude"])
        if not (lo_lat <= lat <= hi_lat and lo_lon <= lon <= hi_lon):
            continue
        if haversine_km((lat, lon), start) < skip_near_ends_km or haversine_km((lat, lon), end) < skip_near_ends_km:
            continue
        km, off = _along(path, cum, (lat, lon))
        if off <= radius_km:
            out.append({"name": str(r["place"]), "kind": _CATEGORY_KIND.get(str(r["category"]), "📌 Place"),
                        "lat": lat, "lon": lon, "km_from_start": km, "off_route_km": off, "score": 2})
    # curated well-known road-trip stops (towns, forts, temples, falls, dams ...)
    try:
        stops = load_route_stops()
        for _, r in stops.iterrows():
            lat, lon = float(r["latitude"]), float(r["longitude"])
            if not (lo_lat <= lat <= hi_lat and lo_lon <= lon <= hi_lon):
                continue
            if haversine_km((lat, lon), start) < skip_near_ends_km or haversine_km((lat, lon), end) < skip_near_ends_km:
                continue
            km, off = _along(path, cum, (lat, lon))
            if off <= min(radius_km, 12.0):
                out.append({"name": str(r["name"]), "kind": str(r["kind"]), "lat": lat, "lon": lon,
                            "km_from_start": km, "off_route_km": off, "score": 3})
    except Exception:
        pass
    return out


def find_places_along_route(path, radius_km: float = 6.0, limit: int = 18, online: bool = True) -> list:
    """
    Famous places close to the route, ordered from start to end.
    Sources: OpenStreetMap (famous = has a Wikidata/Wikipedia entry; widened if few are found)
    plus TripMate's own all-India list (within ~20 km, works even if the online service is down).
    Each item: name, kind, lat, lon, km_from_start, off_route_km.
    """
    if not path or len(path) < 2:
        return []
    path = _densify(list(path)) if len(path) < 200 else list(path)

    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + haversine_km(path[i - 1], path[i]))

    key = tuple(_simplify_path(path, 30))
    radius_m = int(radius_km * 1000)
    elements = []
    if online:
        elements = _overpass_places(key, radius_m, True) or []
        if len(elements) < 4:                               # too few famous ones -> cast a wider net
            elements = elements + (_overpass_places(key, radius_m, False) or [])

    places = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not name or lat is None or lon is None:
            continue
        km, off = _along(path, cum, (lat, lon))
        if off > radius_km * 1.5:
            continue
        score = 2 if "wikipedia" in tags else (1 if "wikidata" in tags else 0)
        places.append({"name": name, "kind": _classify(tags), "lat": lat, "lon": lon,
                       "km_from_start": km, "off_route_km": off, "score": score})

    places += _builtin_places_near_route(path, cum, radius_km=20.0)

    # drop duplicates (same name, or within 1.5 km of one already kept), best first
    places.sort(key=lambda p: (-p["score"], p["off_route_km"]))
    kept, names = [], set()
    for p in places:
        if p["name"].lower() in names:
            continue
        if any(haversine_km((p["lat"], p["lon"]), (k["lat"], k["lon"])) < 1.5 for k in kept):
            continue
        names.add(p["name"].lower())
        kept.append(p)
    kept = kept[:limit]
    kept.sort(key=lambda p: p["km_from_start"])
    return kept


# ─── Temples & local sights around a place ──────────────────────────────────

_RELIGION_KIND = {"hindu": "🛕 Temple", "jain": "🛕 Jain basadi", "buddhist": "🛕 Buddhist shrine",
                  "muslim": "🕌 Mosque / Dargah", "christian": "⛪ Church", "sikh": "🛕 Gurudwara"}


@st.cache_data(ttl=21600, show_spinner=False)
def _nearby_cached(lat: float, lon: float, radius_m: int):
    """Named temples / sights within radius of a point from OpenStreetMap. Raises on failure (not cached)."""
    a = f"(around:{radius_m},{lat:.5f},{lon:.5f})"
    body = (
        f'nwr["name"]["amenity"="place_of_worship"]{a};'
        f'nwr["name"]["tourism"~"^(attraction|viewpoint|museum|zoo)$"]{a};'
        f'nwr["name"]["historic"~"^(castle|fort|palace|monument|ruins|temple)$"]{a};'
        f'nwr["name"]["natural"~"^(waterfall|peak|hot_spring)$"]{a};'
    )
    query = f"[out:json][timeout:10];({body});out center 200;"
    deadline = time.monotonic() + 14
    for url in _OVERPASS_URLS:
        if time.monotonic() > deadline:
            break
        try:
            resp = requests.post(url, data={"data": query}, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            js = resp.json()
            remark = str(js.get("remark", "")).lower()
            if "error" in remark or "timed out" in remark or "out of memory" in remark:
                continue
            return js.get("elements", [])
        except Exception:
            continue
    raise RuntimeError("places service unavailable")


def find_places_near(center, radius_km: float = 15.0, limit: int = 15) -> list:
    """
    Temples and local sights around a place (e.g. Kigga Rishyashringeshwara near Sringeri).
    Live from OpenStreetMap. Returns [] if the service is busy. Each item: name, kind, lat, lon, km_away.
    """
    if not center or time.monotonic() < _OVERPASS_DOWN_UNTIL[0]:
        return []
    try:
        els = _nearby_cached(round(center[0], 4), round(center[1], 4), int(radius_km * 1000))
    except Exception:
        _OVERPASS_DOWN_UNTIL[0] = time.monotonic() + 180
        return []
    out, seen = [], []
    for el in els:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not name or lat is None or lon is None:
            continue
        if tags.get("amenity") == "place_of_worship":
            kind = _RELIGION_KIND.get(str(tags.get("religion", "")).lower(), "🛕 Place of worship")
        else:
            kind = _classify(tags)
        km = haversine_km(center, (lat, lon))
        n = name.lower()
        score = (3 if "wikipedia" in tags else 2 if "wikidata" in tags else 0)
        score += 1 if any(w in n for w in ("temple", "mandir", "devasthana", "matha", "mutt", "eshwara", "eshwar", "falls", "peak", "parvata")) else 0
        score += 1 if tags.get("name:en") or all(ord(c) < 128 for c in name) else 0   # readable name
        out.append({"name": name, "kind": kind, "lat": lat, "lon": lon, "km_away": km, "score": score})
    out.sort(key=lambda p: (-p["score"], p["km_away"]))
    kept = []
    for p in out:
        if any(p["name"].lower() == k["name"].lower() or haversine_km((p["lat"], p["lon"]), (k["lat"], k["lon"])) < 0.15 for k in kept):
            continue
        kept.append(p)
    kept = kept[:limit]
    kept.sort(key=lambda p: p["km_away"])
    return kept


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


def _add_map_extras(m):
    """Satellite / street layers, layer switcher and a fullscreen button (all free map tiles)."""
    try:
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri", name="Satellite", control=True).add_to(m)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri", name="Streets (Esri)", control=True).add_to(m)
        folium.LayerControl(collapsed=True, position="topright").add_to(m)
    except Exception:
        pass
    try:
        from folium.plugins import Fullscreen
        Fullscreen(position="topleft").add_to(m)
    except Exception:
        pass


def build_trip_map(origin: str, destination: str, stops: list = None, route: dict = None,
                   origin_coords=None, dest_coords=None, places: list = None, nearby: list = None):
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

    # Alternative routes (grey), like Google Maps
    for alt in ((route or {}).get("all") or [])[1:3]:
        if route and alt.get("path") is not route.get("path"):
            folium.PolyLine(alt["path"], color="#94a3b8", weight=5, opacity=0.8,
                            tooltip=f"Alternative: {alt['distance_km']:.0f} km").add_to(m)

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

    # Temples & local sights around the destination (purple)
    for pl in nearby or []:
        folium.Marker(
            [pl["lat"], pl["lon"]],
            icon=folium.Icon(color="purple", icon="star", prefix="fa"),
            popup=folium.Popup(f"<b>{pl['name']}</b><br>{pl['kind']}<br>{pl['km_away']:.1f} km from {destination}", max_width=240),
            tooltip=f"{pl['name']} ({pl['kind']})",
        ).add_to(m)
        points.append((pl["lat"], pl["lon"]))

    if route and route.get("path"):
        points += _simplify_path(route["path"], 25)

    _add_map_extras(m)
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
    _add_map_extras(m)
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
