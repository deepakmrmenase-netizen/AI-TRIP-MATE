"""
TripMate AI - AI Service
Handles all communication with the Generative AI API (Google Gemini).
Falls back gracefully to demo mode when no API key is present.
"""

import json
import sys
import os

# Try importing Google Generative AI (new SDK first, fallback to old).
try:
    from google import genai as _genai_new
    GENAI_AVAILABLE = True
    GENAI_SDK = "new"
except ImportError:
    try:
        import google.generativeai as _genai_old
        GENAI_AVAILABLE = True
        GENAI_SDK = "old"
    except ImportError:
        GENAI_AVAILABLE = False
        GENAI_SDK = None

from app_config import GEMINI_API_KEY, DEMO_MODE
from util_helpers import safe_json_parse
from data_loader import load_sample_trips


# ─── Gemini Client Initialisation ─────────────────────────────────────────────

_client = None   # new SDK client
_model  = None   # old SDK model

def _get_model():
    """Return a callable that accepts a prompt string and returns text."""
    global _client, _model
    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        return None

    if GENAI_SDK == "new":
        if _client is not None:
            return _client
        try:
            _client = _genai_new.Client(api_key=GEMINI_API_KEY)
            return _client
        except Exception:
            return None
    else:  # old SDK
        if _model is not None:
            return _model
        try:
            _genai_old.configure(api_key=GEMINI_API_KEY)
            _model = _genai_old.GenerativeModel("gemini-1.5-flash")
            return _model
        except Exception:
            return None


# ─── Core AI Call ─────────────────────────────────────────────────────────────

_GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
LAST_AI_ERROR = [""]          # short reason shown to the user when AI could not be used


def _ai_ready() -> bool:
    return bool(GEMINI_API_KEY) and not DEMO_MODE


_MODEL_CACHE = {"list": None, "bad": set()}


def _usable_models() -> list:
    """Ask Google which models THIS key can use (model names change over time), best 'flash' first."""
    import requests
    if _MODEL_CACHE["list"]:
        return [m for m in _MODEL_CACHE["list"] if m not in _MODEL_CACHE["bad"]]
    found = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         headers={"x-goog-api-key": GEMINI_API_KEY}, params={"pageSize": 200}, timeout=20)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    found.append(m["name"].split("/")[-1])
    except Exception:
        pass

    def rank(name: str):
        n = name.lower()
        if any(x in n for x in ("embed", "image", "tts", "audio", "live", "vision", "robotics", "computer", "thinking", "learnlm", "gemma", "aqa")):
            return 99
        score = 50
        if "flash" in n:
            score = 10
        if "lite" in n:
            score += 5
        if "preview" in n or "exp" in n:
            score += 8
        if n.startswith("gemini-2.5"):
            score -= 4
        elif n.startswith("gemini-3"):
            score -= 3
        elif n.startswith("gemini-2.0"):
            score -= 1
        if n.endswith("-latest"):
            score -= 2
        return score

    found = sorted((m for m in set(found) if rank(m) < 99), key=lambda m: (rank(m), m))
    fallback = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-lite-latest"]
    order = (found[:6] or []) + [m for m in fallback if m not in found]
    if found:
        _MODEL_CACHE["list"] = order
    return order


def _gen_config(model: str, expect_json: bool, fast: bool) -> dict:
    cfg = {"temperature": 0.4 if not expect_json else 0.7, "maxOutputTokens": 1100 if fast else 8192}
    if expect_json:
        cfg["responseMimeType"] = "application/json"
    if fast and "2.5" in model:
        cfg["thinkingConfig"] = {"thinkingBudget": 0}          # answer straight away instead of "thinking" first
    return cfg


def _rest_generate(prompt: str, expect_json: bool = False) -> str:
    """Call Gemini through its public web API. Needs only `requests` and the API key (no extra install)."""
    import requests
    problems = []
    for model in _usable_models()[:6]:
        for with_config in (True, False):
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            if with_config:
                body["generationConfig"] = _gen_config(model, expect_json, fast=not expect_json)
            elif expect_json:
                body["generationConfig"] = {"responseMimeType": "application/json"}
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                    json=body, timeout=45)
            except Exception as exc:
                problems.append(f"{model}: network error ({type(exc).__name__})")
                break
            if r.status_code == 200:
                try:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    problems.append(f"{model}: empty answer")
                    break
            try:
                msg = r.json().get("error", {}).get("message", "")
            except Exception:
                msg = ""
            if r.status_code == 400 and with_config and "api key" not in msg.lower():
                continue                                   # model did not like the extra settings: retry plain
            problems.append(f"{model}: HTTP {r.status_code} {msg[:90]}")
            if r.status_code == 404:
                _MODEL_CACHE["bad"].add(model)
            if r.status_code in (400, 401, 403) and "not found" not in msg.lower() and "not supported" not in msg.lower():
                raise RuntimeError(" | ".join(problems[:3]))
            break
    raise RuntimeError(" | ".join(problems[:3]) or "no Gemini model available for this key")


def _rest_stream(prompt: str):
    """Yield the answer piece by piece (so the user sees words appearing at once instead of waiting)."""
    import requests, json as _json
    problems = []
    for model in _usable_models()[:4]:
        for with_config in (True, False):
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            if with_config:
                body["generationConfig"] = _gen_config(model, False, fast=True)
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse",
                    headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                    json=body, timeout=45, stream=True)
            except Exception as exc:
                problems.append(f"{model}: network error ({type(exc).__name__})")
                break
            if r.status_code != 200:
                try:
                    msg = r.json().get("error", {}).get("message", "")
                except Exception:
                    msg = ""
                if r.status_code == 400 and with_config and "api key" not in msg.lower():
                    continue
                problems.append(f"{model}: HTTP {r.status_code} {msg[:90]}")
                if r.status_code == 404:
                    _MODEL_CACHE["bad"].add(model)
                if r.status_code in (400, 401, 403) and "not found" not in msg.lower() and "not supported" not in msg.lower():
                    raise RuntimeError(" | ".join(problems[:3]))
                break
            got = False
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    parts = _json.loads(line[5:].strip())["candidates"][0]["content"]["parts"]
                    piece = "".join(p.get("text", "") for p in parts)
                except Exception:
                    continue
                if piece:
                    got = True
                    yield piece
            if got:
                return
            problems.append(f"{model}: empty answer")
            break
    raise RuntimeError(" | ".join(problems[:3]) or "no Gemini model available for this key")


def call_ai(prompt: str, expect_json: bool = False) -> str:
    """
    Call the Gemini API with the given prompt.
    Uses the official SDK when installed, otherwise the plain web API (works on Streamlit Cloud as is).
    Returns the raw text response or raises an exception.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("AI model not available.")
    return _rest_generate(prompt, expect_json)


# ─── Trip Generation ──────────────────────────────────────────────────────────

TRIP_SYSTEM_PROMPT = """You are an expert student travel planner specialising in affordable travel in India.
Your task is to create realistic, practical, and budget-friendly travel plans for college students.
IMPORTANT RULES:
- Prioritise student budgets and value for money.
- Never invent exact real-time prices or live availability – clearly mark all prices as estimates.
- Optimise travel time and minimise unnecessary transportation.
- Consider the user's interests, accommodation, food, and transport preferences.
- Recommend free or low-cost attractions wherever possible.
- Suggest student discounts, hostel stays, and local eateries.
- Output ONLY valid JSON with no extra text, markdown fences, or commentary.
"""

def build_trip_prompt(trip_params: dict) -> str:
    p = trip_params
    duration = p.get("duration", 2)
    days_json = ",\n".join([
        f'''    {{
      "day": {d},
      "morning": {{"place": "", "activity": "", "transport": "", "cost": 0, "duration": ""}},
      "afternoon": {{"place": "", "activity": "", "lunch": "", "transport": "", "cost": 0, "duration": ""}},
      "evening": {{"place": "", "activity": "", "transport": "", "cost": 0, "duration": ""}},
      "night": {{"accommodation": "", "dinner": "", "cost": 0}}
    }}''' for d in range(1, duration + 1)
    ])
    return f"""{TRIP_SYSTEM_PROMPT}

Generate a complete travel plan for the following request and return ONLY a JSON object matching this exact schema:

{{
  "trip_summary": {{
    "destination": "{p.get('destination')}",
    "origin": "{p.get('origin')}",
    "duration": "{duration} Days",
    "travelers": {p.get('travelers', 1)},
    "total_budget": {p.get('budget', 3000)},
    "estimated_cost": 0,
    "savings": 0,
    "travel_style": ""
  }},
  "days": [
{days_json}
  ],
  "budget_breakdown": {{
    "Transportation": 0,
    "Accommodation": 0,
    "Food": 0,
    "Activities": 0,
    "Miscellaneous": 0
  }},
  "money_saving_tips": [],
  "safety_tips": []
}}

Trip Parameters:
- Origin: {p.get('origin')}
- Destination: {p.get('destination')}
- Start Date: {p.get('start_date')}
- End Date: {p.get('end_date')}
- Duration: {duration} days
- Number of Travelers: {p.get('travelers', 1)}
- Total Budget: ₹{p.get('budget', 3000)}
- Daily Budget: ₹{p.get('daily_budget', p.get('budget', 3000) // max(duration, 1))}
- Interests: {', '.join(p.get('interests', ['General']))}
- Transport Preference: {p.get('transport', 'Bus')}
- Accommodation Preference: {p.get('accommodation', 'Budget Hotel')}
- Food Preference: {p.get('food', 'Vegetarian')}
- Travel Style: {p.get('travel_style', 'Budget')}

Fill every field with realistic, student-friendly recommendations.
Ensure estimated_cost <= total_budget.
All monetary values should be in Indian Rupees (integers).
"""


def generate_trip_plan(trip_params: dict) -> dict:
    """
    Generate a complete trip plan.
    Returns a dict with trip data (either from AI or demo fallback).
    """
    if not _ai_ready():
        return _demo_trip(trip_params)

    try:
        LAST_AI_ERROR[0] = ""
        prompt = build_trip_prompt(trip_params)
        raw = call_ai(prompt, expect_json=True)
        parsed = safe_json_parse(raw)
        if parsed and isinstance(parsed, dict) and "trip_summary" in parsed:
            # Patch savings
            ts = parsed["trip_summary"]
            if ts.get("estimated_cost", 0) == 0:
                estimated = sum(parsed.get("budget_breakdown", {}).values())
                ts["estimated_cost"] = estimated
            ts["savings"] = max(0, ts.get("total_budget", 0) - ts.get("estimated_cost", 0))
            return parsed
        LAST_AI_ERROR[0] = "AI answer was not valid plan JSON"
        return _demo_trip(trip_params)
    except Exception as exc:
        LAST_AI_ERROR[0] = str(exc)[:200]
        return _demo_trip(trip_params)


def _nearby_spots_geo(destination: str, radius_km: float = 45.0, want: int = 12) -> list:
    """Real places around the destination from TripMate's own lists: [(name, note, straight_km, lat, lon)]."""
    try:
        from svc_map_service import lookup_coordinates, haversine_km
        from data_loader import load_india_places, load_route_stops
    except Exception:
        return []
    c = lookup_coordinates(destination)
    if not c:
        return []
    spots, seen = [], set()
    try:
        for _, r in load_india_places().iterrows():
            if str(r["category"]) == "Luxury Stay" or int(r["budget_min"]) >= 8000:
                continue
            km = haversine_km(c, (float(r["latitude"]), float(r["longitude"])))
            if km <= radius_km:
                hl = [h.strip() for h in str(r["highlight"]).split(",") if h.strip()]
                for h in (hl or [str(r["place"])]):
                    if h[:1].islower() or len(h) < 5:      # skip generic words like "forests"
                        continue
                    spots.append((h, f"Visit {h} ({r['category'].lower()})", km, float(r["latitude"]), float(r["longitude"])))
    except Exception:
        pass
    try:
        for _, r in load_route_stops().iterrows():
            km = haversine_km(c, (float(r["latitude"]), float(r["longitude"])))
            if km <= radius_km:
                kind = str(r["kind"]).split(" ", 1)[-1]
                spots.append((str(r["name"]), f"Visit {r['name']} - {kind.lower()}", km, float(r["latitude"]), float(r["longitude"])))
    except Exception:
        pass
    spots.sort(key=lambda s: s[2])
    out = []
    for name, note, km, la, lo in spots:
        key = name.lower()
        core = key.split(" (")[0].strip()
        if core in ("sunset point", "viewpoint") or any(
                core in o[0].lower() or o[0].lower().split(" (")[0] in key for o in out):
            continue
        out.append((name, note, km, la, lo))
    return out[:want]


def _nearby_spots(destination: str, radius_km: float = 45.0, want: int = 12) -> list:
    """Real places around the destination: [(name, note, km_away)]."""
    return [(n, note, km) for n, note, km, _, _ in _nearby_spots_geo(destination, radius_km, want)]


def _demo_trip(trip_params: dict) -> dict:
    """Demo plan built for the REAL destination from TripMate's own place lists (no AI needed)."""
    sample_data = load_sample_trips()
    template = sample_data.get("demo_itinerary_template", {})

    duration = trip_params.get("duration", 2)
    budget = trip_params.get("budget", 4000)
    travelers = trip_params.get("travelers", 1)
    destination = trip_params.get("destination", "Mysuru")
    origin = trip_params.get("origin", "Bengaluru")
    scale = budget / 4000.0
    pretty = str(destination).strip().title() if str(destination).strip().islower() else str(destination).strip()

    spots = _nearby_spots(destination)
    stay = f"Budget guesthouse in {pretty}"
    days = []
    for d in range(1, duration + 1):
        pick = lambda i: spots[(d - 1) * 3 + i] if (d - 1) * 3 + i < len(spots) else None
        slots = {}
        for i, (slot, trans, mins) in enumerate((("morning", "Walk / local auto", "2 hours"),
                                                 ("afternoon", "Local bus / auto", "2 hours"),
                                                 ("evening", "Walk / shared auto", "1.5 hours"))):
            s = pick(i)
            if s:
                name, note, km = s
                place, activity = name, note + (f" - about {km:.0f} km from {pretty}" if km > 3 else "")
            elif i == 0:
                place, activity = f"{pretty} - main sights", f"Explore the main sights and temples of {pretty}"
            elif i == 1:
                place, activity = f"{pretty} local market", "Local market walk and lunch"
            else:
                place, activity = f"{pretty} viewpoint / river side", "Relax, sunset and photography"
            slots[slot] = {"place": place, "activity": activity, "transport": trans,
                           "cost": int((200 if i == 0 else 120 if i == 1 else 60) * scale), "duration": mins}
        slots["afternoon"]["lunch"] = "Local meals / darshini (₹60-120)"
        days.append({"day": d, **slots,
                     "night": {"accommodation": stay, "dinner": "Local restaurant / street food",
                               "cost": int(450 * scale)}})

    b_split = {
        "Transportation": int(budget * 0.28),
        "Accommodation": int(budget * 0.28),
        "Food": int(budget * 0.24),
        "Activities": int(budget * 0.12),
        "Miscellaneous": int(budget * 0.08),
    }
    estimated_cost = sum(b_split.values())

    return {
        "trip_summary": {
            "destination": destination,
            "origin": origin,
            "duration": f"{duration} Day{'s' if duration > 1 else ''}",
            "travelers": travelers,
            "total_budget": budget,
            "estimated_cost": estimated_cost,
            "savings": max(0, budget - estimated_cost),
            "travel_style": trip_params.get("travel_style", "Budget"),
        },
        "days": days,
        "budget_breakdown": b_split,
        "money_saving_tips": template.get("money_saving_tips", [
            "Use KSRTC buses for the cheapest inter-city travel.",
            "Stay in hostels or guesthouses to save on accommodation.",
            "Eat at local darshini restaurants – great food at ₹30-80/meal.",
            "Carry a student ID for entry discounts at monuments.",
            "Travel in groups to split cab/auto costs.",
            "Visit free attractions: parks, viewpoints, beaches, markets.",
        ]),
        "safety_tips": [
            "Keep copies of your student ID and government ID separately.",
            "Share your itinerary with a family member or friend.",
            "Avoid isolated places after 10 PM.",
            "Keep emergency numbers saved: Police 100, Ambulance 108.",
            "Note: All prices are estimates. Verify before booking.",
        ],
        "_demo_mode": True,
        "_ai_error": LAST_AI_ERROR[0] if GEMINI_API_KEY else "",
    }


# ─── Chat Assistant ────────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are TripMate AI, a travel assistant for Indian college students (budget travel in India).
How to answer:
- Answer the exact question asked, in 3-8 short lines or a short list. No long introductions, no repeating the question.
- Use simple English, Indian context (KSRTC/state buses, IRCTC trains, darshini hotels, dharamshalas, UPI, Rs prices).
- If VERIFIED MAP FACTS are given, use their numbers exactly (distances, drive times, place names). Never invent or change them.
- Never invent exact prices, timings, phone numbers, ratings or opening hours. Give a realistic range and say "approx., please verify".
- If you are not sure a place exists or you do not know, say so plainly and suggest checking Google Maps. Do not guess.
- If the question is unclear (for example "near places" with no place), ask ONE short question to clarify.
- For safety topics (night travel, trekking, rivers, forests) add one short safety tip.
"""

DEMO_RESPONSES = {
    "mysuru": "Mysuru (Mysore) is a fantastic 2-day trip! 🏛️\n\n**Day 1:** Mysore Palace (₹70 entry), Devaraja Market, Chamundi Hills sunset\n**Day 2:** Brindavan Gardens, Mysore Zoo (₹80), Jaganmohan Art Gallery\n\n**Budget estimate (per person):** ₹1,500-2,000\n**Travel:** KSRTC bus from Bengaluru – ₹150-200 each way\n**Stay:** Budget hostels near Palace – ₹300-500/night\n\n💡 Carry your college ID for potential student discounts!",
    "budget": "Here are top trips under ₹3,000 (per person) from Karnataka:\n\n1. 🏛️ **Mysuru** – ₹1,500-2,000 | 2 days\n2. 🏔️ **Chikkamagaluru** – ₹2,000-2,500 | 2 days\n3. 🌊 **Udupi/Malpe Beach** – ₹1,800-2,200 | 2 days\n4. 🏰 **Hampi** – ₹2,000-2,500 | 2 days\n\n💡 Travel mid-week and book KSRTC buses in advance for the best prices!",
    "save": "💰 **Top money-saving tips for student travel:**\n\n1. **KSRTC buses** – cheapest way to travel in Karnataka\n2. **Hostels & guesthouses** – save 60% vs hotels\n3. **Darshini restaurants** – full meals at ₹50-80\n4. **Group travel** – split auto/cab costs\n5. **Student ID** – discounts at museums, monuments, some buses\n6. **Off-season travel** – 30-50% cheaper accommodation\n7. **Free attractions** – parks, viewpoints, beaches, temples\n8. **Pack snacks** – avoid tourist-area overpriced food",
    "pack": "🎒 **Student Travel Packing Checklist:**\n\n**Documents:** College ID, Aadhar/government ID, tickets, accommodation confirmation\n**Tech:** Phone + charger, power bank, earphones\n**Health:** Medicines, hand sanitiser, ORS packets, basic first aid\n**Clothing:** Comfortable walking shoes, light clothes, rain jacket/umbrella\n**Essentials:** Water bottle, cash + UPI app, small backpack\n**Safety:** Emergency contact list, hotel/hostel address note\n\n💡 Keep digital copies of all documents in Google Drive!",
    "photography": "📸 **Best photography spots in Karnataka for students:**\n\n1. **Hampi** – Ancient ruins, golden hour on Matanga Hill\n2. **Chikkamagaluru** – Misty coffee plantations at sunrise\n3. **Coorg** – Abbey Falls, rolling green hills\n4. **Mysuru** – Palace illumination (Tue/Sat/Sun evenings)\n5. **Udupi** – St. Mary's Island rock formations\n\n💡 Golden hour (6-8 AM & 5-7 PM) gives the best natural lighting!",
    "accommodation": "🏠 **Budget accommodation options for students:**\n\n1. **Hostels** – ₹200-400/night | Meet fellow travelers\n2. **Budget guesthouses** – ₹300-600/night | More privacy\n3. **Homestays** – ₹400-700/night | Authentic local experience\n4. **Dharamshalas** (near temples) – ₹0-150/night | Very basic\n5. **College alumni networks** – Sometimes free stays!\n\n💡 Book through MakeMyTrip or Booking.com for verified reviews. Always check ratings before booking.",
    "cheap": "🚌 **Cheapest ways to travel as a student:**\n\n1. **KSRTC/State buses** – ₹50-300 for most routes in Karnataka\n2. **Train (Sleeper class)** – ₹100-400 for longer distances\n3. **Shared autos** – ₹10-20/km in smaller towns\n4. **Rented bicycles** – ₹100-150/day at tourist spots like Hampi\n5. **City metro/local buses** – ₹10-30 in Bengaluru/Hyderabad\n\n💡 Always book train tickets 2-4 weeks in advance on IRCTC!",
    "default": "Hi! I'm TripMate AI 🤖✈️\n\nI can help you with:\n- **Destination suggestions** – 'What can I visit in Mysuru?'\n- **Budget planning** – 'Suggest a trip under ₹3,000'\n- **Money-saving tips** – 'How can I save money?'\n- **Packing advice** – 'What should I pack?'\n- **Photography spots** – 'Best places for photography'\n- **Accommodation tips** – 'Suggest budget accommodation'\n- **Cheap travel** – 'How do I travel cheaply?'\n\nWhat would you like to know? 😊",
}


_STOP_WORDS = {"the", "a", "an", "my", "your", "this", "that", "india", "trip", "budget", "me", "us", "it", "there",
               "here", "weekend", "day", "days", "friends", "college", "students", "student", "winter", "summer"}

_NAME_INDEX = {}


def _name_index():
    """name -> (display, (lat, lon), exact) from our own lists. exact=False for sights listed under a bigger place."""
    if _NAME_INDEX:
        return _NAME_INDEX
    import re
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()
    try:
        from data_loader import load_india_places, load_route_stops
        for r in load_india_places().itertuples():
            c = (float(r.latitude), float(r.longitude))
            for n in [str(r.place), str(r.place).split(" (")[0]] + [a for a in str(r.aliases).split(",") if a.strip()]:
                _NAME_INDEX[clean(n)] = (str(r.place).split(" (")[0], c, True)
        for r in load_route_stops().itertuples():
            c = (float(r.latitude), float(r.longitude))
            for n in (str(r.name), str(r.name).split(" (")[0]):
                _NAME_INDEX.setdefault(clean(n), (str(r.name).split(" (")[0], c, True))
        for r in load_india_places().itertuples():                  # sights listed under a bigger place
            c = (float(r.latitude), float(r.longitude))
            for h in str(r.highlight).split(","):
                if clean(h) and clean(h) not in _NAME_INDEX:
                    _NAME_INDEX[clean(h)] = (h.strip(), c, False)
    except Exception:
        pass
    return _NAME_INDEX


def _resolve_place(text: str):
    """(display name, (lat, lon), approx?) for a typed place - our lists, live map search, spelling-tolerant."""
    import re, difflib
    text = re.sub(r"\b(the|distance|between|route|how|far|is|from|to|km|time|please|temple of)\b", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9 .'-]+", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) < 3:
        return None
    key = text.lower()
    idx = _name_index()
    hit = idx.get(key)
    if hit and hit[2]:
        return hit[0], hit[1], False
    try:
        from svc_map_service import lookup_coordinates
        c = lookup_coordinates(text)
    except Exception:
        c = None
    if c:
        return text.title(), c, False
    if hit:
        return hit[0], hit[1], True
    close = difflib.get_close_matches(key, list(idx.keys()), n=1, cutoff=0.72)
    if close:
        d, c, exact = idx[close[0]]
        return d, c, not exact
    return None


def _extract_pair(msg: str):
    import re
    m = msg.strip().rstrip("?.! ")
    pats = [
        (r"how\s+far\s+(?:is\s+)?(.+?)\s+from\s+(.+)", True),
        (r"distance\s+(?:between\s+)?(.+?)\s+(?:to|and)\s+(.+)", False),
        (r"(?:route|way|drive|travel|go)\s+from\s+(.+?)\s+to\s+(.+)", False),
        (r"from\s+(.+?)\s+to\s+(.+)", False),
        (r"(.+?)\s+to\s+(.+?)\s+(?:distance|route|km|kms|how far|time|cost)\b.*", False),
        (r"(.+?)\s+to\s+(.+?)\s*$", False),
    ]
    for p, swap in pats:
        mm = re.search(p, m, re.I)
        if mm:
            a, b = mm.group(1), mm.group(2)
            b = re.sub(r"\s+(distance|route|km|kms|by .*|how .*|what .*|cost.*|time.*)$", "", b, flags=re.I)
            return (b, a) if swap else (a, b)
    return None


def _fmt_time(mins: float) -> str:
    h, mn = divmod(int(round(mins)), 60)
    return f"{h}h {mn:02d}m" if h else f"{mn} min"


def _distance_answer(msg: str):
    pair = _extract_pair(msg)
    if not pair:
        return None
    a, b = _resolve_place(pair[0]), _resolve_place(pair[1])
    if not a or not b:
        missing = pair[0] if not a else pair[1]
        return (f"I couldn't find **{missing.strip()}** on the map. Check the spelling or add the area, "
                f"for example *Kudlu Falls, Karnataka*.")
    from svc_map_service import get_route, estimate_travel_options, google_maps_link
    r = get_route(a[1], b[1])
    km, mins = r["distance_km"], r["duration_min"]
    opts = estimate_travel_options(km, mins, road_available=not r.get("no_road", False))
    src = {"google": "Google Maps", "osm": "OpenStreetMap road routing"}.get(r.get("source"), "estimate (routing service busy)")
    lines = [f"🚗 **{a[0]} → {b[0]}**\n",
             f"- **Road distance:** {km:,.1f} km" if r.get("is_road") else f"- **Distance (approx):** {km:,.0f} km",
             f"- **Drive time:** about {_fmt_time(mins)} (with typical traffic)" if r.get("is_road") else f"- **Time (approx):** {_fmt_time(mins)}"]
    if r.get("via"):
        lines.append(f"- **Main road:** {r['via']}")
    lines.append("\n**Approximate cost (one way):**")
    for o in opts:
        extra = " (whole vehicle, split between people)" if o.get("seats") else " per person"
        lines.append(f"- {o['icon']} {o['mode']}: ₹{o['low']:,}-{o['high']:,}{extra}, about {_fmt_time(o['hours'] * 60)}")
    if a[2] or b[2]:
        lines.append("\n⚠️ One of these is listed as part of a bigger place, so its exact point may be a few km off.")
    lines.append(f"\nSource: {src}. [Open in Google Maps]({google_maps_link(a[1], b[1])}) for live traffic, or use **Trip Map** for the full route and famous places on the way.")
    return "\n".join(lines)


def _find_place_in_message(msg: str):
    """Return ('dataset', row_dict) | ('state', name) | ('online', (name, (lat, lon))) | None."""
    import re
    low = " " + re.sub(r"[^a-z0-9 ]+", " ", msg.lower()) + " "
    try:
        from data_loader import load_india_places
        df = load_india_places()
    except Exception:
        return None
    best = None
    for _, r in df.iterrows():
        names = [str(r["place"]).lower().split(" (")[0]] + [a.strip().lower() for a in str(r.get("aliases", "")).split(",") if a.strip()]
        for n in names:
            n2 = re.sub(r"[^a-z0-9 ]+", " ", n).strip()
            if len(n2) >= 4 and f" {n2} " in low and (best is None or len(n2) > best[0]):
                best = (len(n2), r.to_dict())
    if best:
        return "dataset", best[1]
    for s in sorted(set(df["state"]), key=len, reverse=True):
        if f" {s.lower()} " in low:
            return "state", s
    m = re.search(r"\b(?:in|to|at|near|around|visit|about|of|from)\s+([A-Za-z][A-Za-z .'-]{2,28}?)(?=\s+(?:for|from|with|please|trip|visit|in|and|how|what|is|are)\b|[?.!,]|$)", msg)
    for cand in ([m.group(1).strip()] if m else []):
        words = [w for w in cand.split() if w.lower() not in _STOP_WORDS]
        if not words:
            continue
        r = _resolve_place(" ".join(words))
        if r:
            return "online", (r[0], r[1])
    return None


def _place_answer(msg: str):
    """Real answer about a place or state from TripMate's data + live map data (road distances). None if no place found."""
    found = _find_place_in_message(msg)
    if not found:
        return None
    kind, val = found
    try:
        from data_loader import load_india_places
        df = load_india_places()
    except Exception:
        return None

    if kind == "state":
        sub = df[(df["state"] == val) & (df["category"] != "Luxury Stay")].sort_values("budget_min").head(8)
        lines = [f"- **{r.place}** - {r.category}, ₹{int(r.budget_min):,}-{int(r.budget_max):,} per person ({r.highlight.split(',')[0].strip()})"
                 for r in sub.itertuples()]
        return (f"🗺️ **Places to visit in {val}** (cheapest first):\n\n" + "\n".join(lines) +
                "\n\n💡 Open **Explore Destinations** to filter by budget and type, or ask me about any of these places.")

    if kind == "dataset":
        r = val
        name, center = str(r["place"]), (float(r["latitude"]), float(r["longitude"]))
        head = (f"📍 **{name}, {r['state']}** - {r['category']}\n\n"
                f"**Known for:** {r['highlight']}\n\n**Estimated cost:** ₹{int(r['budget_min']):,}-{int(r['budget_max']):,} per person (2-3 days)")
    else:
        name, center = val
        head = f"📍 **{name}**"

    from svc_map_service import road_distances, haversine_km, find_places_near, lookup_coordinates, get_route
    parts = [head]
    try:
        spots = _nearby_spots_geo(name, radius_km=45.0, want=12)
        if spots:
            rd = road_distances(center, [(la, lo) for _, _, _, la, lo in spots])
            rows = []
            for i, (n, _, skm, la, lo) in enumerate(spots):
                if rd and rd[i][0] is not None and rd[i][0] < 2:
                    rows.append((0.0, f"{i + 1}. {n} - in {name} itself"))
                elif rd and rd[i][0] is not None:
                    rows.append((rd[i][0], f"{i + 1}. {n} - about {rd[i][0]:.0f} km by road, {_fmt_time(rd[i][1])}"))
                else:
                    rows.append((skm * 1.35, f"{i + 1}. {n} - about {skm * 1.35:.0f} km by road (approx.)"))
            rows.sort(key=lambda x: x[0])
            parts.append(f"**{len(rows)} places to visit around {name}** (road distance from {name}):\n" +
                         "\n".join(f"{j}. {txt.split('. ', 1)[1]}" for j, (_, txt) in enumerate(rows, 1)))
            if not rd:
                parts[-1] += "\n_Road-routing service is busy, so distances are estimates._"
    except Exception:
        pass
    try:
        near = find_places_near(center, radius_km=15.0, limit=10)
        if near:
            rd2 = road_distances(center, [(p["lat"], p["lon"]) for p in near])
            lines = []
            for i, p in enumerate(near):
                d = f"{rd2[i][0]:.1f} km by road" if rd2 and rd2[i][0] is not None else f"{p['km_away'] * 1.35:.1f} km (approx.)"
                lines.append(f"- {p['name']} ({p['kind'].split(' ', 1)[1].lower()}) - {d}")
            parts.append("**🛕 Temples and local sights nearby (live map data):**\n" + "\n".join(lines))
    except Exception:
        pass
    try:
        r = get_route(lookup_coordinates("Bengaluru"), center)
        if r.get("is_road") and r["distance_km"] > 5:
            parts.append(f"**From Bengaluru:** {r['distance_km']:,.0f} km by road, about {_fmt_time(r['duration_min'])} drive. "
                         f"Open **Trip Map** for the route, famous places on the way and fares.")
    except Exception:
        pass
    parts.append("💡 Ask me for the distance between any two places, for example *Kudlu Falls to Horanadu*, or open **AI Trip Planner** for a day-by-day plan.")
    return "\n\n".join(parts)


def _facts_for(message: str):
    """Map-based answer for place / distance questions (used directly in demo mode, as verified facts with real AI)."""
    low = message.lower()
    try:
        if any(k in low for k in (" to ", "distance", "how far", "route from", "between")):
            ans = _distance_answer(message)
            if ans:
                return ans
        return _place_answer(message)
    except Exception:
        return None


_SERVICE_WORDS = [
    ("food", ("breakfast", "lunch", "dinner", "food", "eat", "restaurant", "cafe", "tiffin", "meal", "snack", "hungry", "veg")),
    ("medical", ("hospital", "doctor", "clinic", "medical", "pharmacy", "medicine")),
    ("fuel", ("petrol", "diesel", "fuel", "gas station", "pump")),
    ("atm", ("atm", "bank", "cash")),
    ("stay", ("hotel", "stay", "lodge", "room", "hostel", "accommodation", "guesthouse", "homestay", "resort")),
]


def _service_answer(msg: str, history=None):
    """'best hotel for breakfast in Sringeri', 'hospital near Hampi' ... answered from live map listings."""
    low = " " + msg.lower() + " "
    import re
    kind = next((k for k, words in _SERVICE_WORDS
                 if any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)), None)
    if not kind:
        return None
    found = _find_place_in_message(msg)
    if found and found[0] == "state":
        found = None
    if not found:
        found = _context_place(history)
    if not found:
        return ("📍 **Which place?** Tell me the town, for example *best breakfast in Sringeri* or *hospital near Hampi*, "
                "and I'll list what the map has around it.")
    name, center = (found[1]["place"], (float(found[1]["latitude"]), float(found[1]["longitude"]))) if found[0] == "dataset" \
        else (found[1][0], found[1][1])
    name = str(name).split(" (")[0]
    from svc_map_service import find_services_near, road_distances
    items = find_services_near(center, kind, radius_km=6.0, limit=8)
    label = {"food": "places to eat", "stay": "hotels and stays", "medical": "hospitals and medical shops",
             "fuel": "fuel stations", "atm": "ATMs and banks"}[kind]
    meal = next((w for w in ("breakfast", "lunch", "dinner") if w in low), "")
    q = f"{meal + ' ' if meal else ''}{'restaurants' if kind == 'food' else label} near {name}".replace(" ", "+")
    gmaps = f"https://www.google.com/maps/search/{q}"
    if not items:
        return (f"I couldn't load {label} around **{name}** right now (the map service is busy or has no listing). "
                f"[Search on Google Maps]({gmaps}) for ratings and photos.")
    rd = road_distances(center, [(p["lat"], p["lon"]) for p in items])
    lines = []
    for i, p in enumerate(items):
        d = f"{rd[i][0]:.1f} km by road" if rd and rd[i][0] is not None else f"~{p['km_away'] * 1.3:.1f} km"
        lines.append(f"{i + 1}. **{p['name']}** - {d}" + (f" ({p['info']})" if p["info"] else ""))
    intro = f"{'🍽️' if kind == 'food' else '📍'} **{label.capitalize()} near {name}** (from the live map)"
    if kind == "food":
        tip = ("\n\n💡 Local tip: in Karnataka towns, breakfast is usually idli, vada, dosa, upma or khara bath at small darshini "
               "hotels, which open early (about 6:30-7:30 AM) and cost about ₹40-100. " if meal in ("breakfast", "") else "\n\n")
        if "sringeri" in name.lower():
            tip += ("The Sharada Peetham temple complex is known for serving free meals to pilgrims, so check timings at the temple office. ")
    else:
        tip = "\n\n"
    return (intro + "\n\n" + "\n".join(lines) + tip +
            f"\n\n⚠️ The map has no ratings or reviews, so I can't say which is the *best*. "
            f"[See ratings and photos on Google Maps]({gmaps}) before choosing.")


def _context_place(history):
    """Last place the user talked about (chat history, then the destination typed in the planner)."""
    for m in reversed(history or []):
        if m.get("role") == "user":
            f = _find_place_in_message(str(m.get("content", "")))
            if f and f[0] in ("dataset", "online"):
                return f
    try:
        import streamlit as _st
        d = _st.session_state.get("planner_destination")
        if d:
            r = _resolve_place(str(d))
            if r:
                return "online", (r[0], r[1])
    except Exception:
        pass
    return None


def _suggestions_answer(msg: str = "") -> str:
    """Destination ideas from TripMate's all-India list, grouped by budget."""
    try:
        from data_loader import load_india_places
        df = load_india_places()
        df = df[df["category"] != "Luxury Stay"]
        low = msg.lower()
        for cat in sorted(df["category"].unique()):
            if cat.split(" & ")[0].lower() in low:
                df = df[df["category"] == cat]
                break
        else:
            for kw, cat in (("temple", "Spiritual"), ("pilgrim", "Spiritual"), ("beach", "Beach & Islands"),
                            ("hill", "Nature & Hills"), ("nature", "Nature & Hills"), ("wild", "Wildlife & Adventure"),
                            ("palace", "Heritage & Royal"), ("heritage", "Heritage & Royal"), ("city", "City & Culture")):
                if kw in low:
                    df = df[df["category"] == cat]
                    break
        lines = []
        for tier, label in (("Cheap", "💚 Cheap (under ₹2,500)"), ("Mid-range", "💙 Mid-range (₹2,500-7,999)"), ("Royal / Luxury", "💜 Royal / Luxury (₹8,000+)")):
            pool = df[df["tier"] == tier].sort_values(["budget_min", "place"])
            sub = pool.groupby("category", sort=False).head(1).head(4)          # a mix of types, not 4 of the same
            if len(sub) < 4:
                sub = pool.head(4)
            if len(sub):
                lines.append(f"**{label}**\n" + "\n".join(
                    f"- **{r.place}** ({r.state}) - {r.highlight.split(',')[0].strip()}, ₹{int(r.budget_min):,}-{int(r.budget_max):,}" for r in sub.itertuples()))
        if lines:
            return ("✨ **Destination ideas for you:**\n\n" + "\n\n".join(lines) +
                    "\n\n💬 Tell me your **budget**, **days** and what you like (beach, temples, hills, wildlife...) "
                    "and I'll narrow it down. Or ask about any of these, for example *tell me about Gokarna*.")
    except Exception:
        pass
    return DEMO_RESPONSES["budget"]


def get_demo_response(user_message: str, history: list = None) -> str:
    """Answer without an AI key: real place/distance facts from maps, destination ideas, tips and follow-up questions."""
    msg = user_message.lower().strip()
    generic = any(k in msg for k in ["pack", "packing", "save money", "money tip", "photography", "hostel"])
    if not any(k in msg for k in ("pack", "packing", "save money", "money tip", "photography")):
        try:
            svc = _service_answer(user_message, history)
        except Exception:
            svc = None
        if svc:
            return svc
    if not generic:
        answer = _facts_for(user_message)
        if answer:
            return answer

        nearby_words = ("near", "nearby", "around", "close to", "places to visit", "things to do", "what to see", "tourist", "visit")
        suggest_words = ("suggest", "recommend", "where to go", "where should", "destination", "ideas", "idea", "which place", "best place", "plan")
        if any(k in msg for k in nearby_words):
            ctx = _context_place(history)
            if ctx:
                name = ctx[1]["place"] if ctx[0] == "dataset" else ctx[1][0]
                ans = _place_answer(f"tell me about {name}")
                if ans:
                    return f"(Showing places around **{name}**. Tell me another place name to change it.)\n\n" + ans
            return ("📍 **Near which place?** Tell me a town or landmark, for example *places near Sringeri* or "
                    "*what to see in Gokarna*, and I'll list the temples and sights around it with real road distances.")
        if any(k in msg for k in suggest_words) and not any(k in msg for k in ("under", "₹", "budget", "cheap")):
            return _suggestions_answer(msg)

    if any(k in msg for k in ["₹", "budget", "cheap trip", "under", "affordable", "3000", "2000", "5000"]):
        return _suggestions_answer(msg)
    if any(k in msg for k in ["save money", "saving", "money tip", "cut cost", "reduce"]):
        return DEMO_RESPONSES["save"]
    if any(k in msg for k in ["pack", "packing", "carry", "bring", "checklist"]):
        return DEMO_RESPONSES["pack"]
    if any(k in msg for k in ["photo", "photography", "camera", "picture", "scenic"]):
        return DEMO_RESPONSES["photography"]
    if any(k in msg for k in ["accommodation", "hostel", "hotel", "stay", "room", "guesthouse"]):
        return DEMO_RESPONSES["accommodation"]
    if any(k in msg for k in ["travel cheap", "cheapest", "bus", "train", "transport", "how to travel"]):
        return DEMO_RESPONSES["cheap"]

    # a short message may just be a place name ("Kigga", "Hampi")
    if len(msg.split()) <= 4:
        r = _resolve_place(user_message)
        if r:
            ans = _place_answer(f"tell me about {r[0]}")
            if ans:
                return ans
    return ("🤔 I didn't fully get that. I can answer questions like:\n\n"
            "- *places near Sringeri* or *what to see in Hampi*\n"
            "- *Kudlu Falls to Horanadu distance* (road km, time and cost)\n"
            "- *suggest a beach trip* or *trips under ₹3,000*\n"
            "- *how to save money*, *what to pack*, *budget stay*\n\n"
            "Type a place name and I'll tell you what is around it.")


_FACT_HINTS = ("near", "nearby", "around", "distance", "how far", " km", "route", " to ", "visit", "places", "see in", "things to do",
               "how many", "hotel", "stay", "lodge", "hostel", "food", "eat", "breakfast", "lunch", "dinner", "restaurant", "cafe",
               "hospital", "pharmacy", "atm", "petrol", "bank", "temple", "falls", "beach")


def _facts_with_limit(message: str, seconds: float = 5.0):
    """Map facts, but never make the user wait more than a few seconds for them."""
    low = " " + message.lower() + " "
    if not any(h in low for h in _FACT_HINTS):
        return None                                   # general question (tips, packing...): no map look-up needed
    import concurrent.futures as cf
    ex = cf.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_facts_for, message)
    try:
        return fut.result(timeout=seconds)
    except Exception:
        return None
    finally:
        ex.shutdown(wait=False)


def _chat_prompt(user_message: str, history: list = None) -> str:
    context = CHAT_SYSTEM_PROMPT + "\n"
    if history:
        for msg in history[-8:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {str(msg['content'])[:700]}\n"
    facts = _facts_with_limit(user_message)
    if facts:
        context += ("\nVERIFIED MAP FACTS for this question (real road distances, drive times and nearby places from OpenStreetMap; "
                    "use them exactly and put them in your own short words):\n" + facts + "\n\n")
    return context + f"User: {user_message}\nAssistant:"


def chat_with_ai(user_message: str, history: list = None) -> str:
    """One full answer (no streaming). Falls back to the built-in answer, saying why."""
    if not _ai_ready():
        return get_demo_response(user_message, history)
    try:
        answer = call_ai(_chat_prompt(user_message, history))
        LAST_AI_ERROR[0] = ""
        return answer
    except Exception as exc:
        LAST_AI_ERROR[0] = str(exc)[:160]
        return (f"⚠️ *The AI service could not be reached ({LAST_AI_ERROR[0]}), so this is TripMate's built-in answer.*\n\n"
                + get_demo_response(user_message, history))


def chat_stream(user_message: str, history: list = None):
    """Same as chat_with_ai, but yields the answer in pieces so it appears word by word."""
    if not _ai_ready():
        yield get_demo_response(user_message, history)
        return
    started = False
    try:
        for piece in _rest_stream(_chat_prompt(user_message, history)):
            started = True
            yield piece
        LAST_AI_ERROR[0] = ""
    except Exception as exc:
        LAST_AI_ERROR[0] = str(exc)[:160]
        if started:
            return                                   # keep what the AI already said
        yield (f"⚠️ *The AI service could not be reached ({LAST_AI_ERROR[0]}), so this is TripMate's built-in answer.*\n\n"
               + get_demo_response(user_message, history))


# ─── Budget Optimisation AI ───────────────────────────────────────────────────

def get_budget_optimization_tips(trip_params: dict, budget_breakdown: dict) -> list:
    """
    Ask AI for budget optimisation tips. Returns a list of tip strings.
    """
    if not _ai_ready():
        return [
            f"Use KSRTC buses instead of private taxis – save approximately ₹{int(budget_breakdown.get('Transportation', 0) * 0.3):,}.",
            f"Choose hostels over budget hotels – save approximately ₹{int(budget_breakdown.get('Accommodation', 0) * 0.35):,}.",
            "Eat at local darshini restaurants and street food stalls instead of tourist restaurants.",
            "Visit free attractions: public parks, beaches, viewpoints, and religious sites.",
            "Travel mid-week – accommodation is 20-30% cheaper than weekends.",
            "Carry a student ID card – many monuments and museums offer student discounts.",
            "Book KSRTC/train tickets in advance for the best prices.",
        ]
    try:
        total = sum(budget_breakdown.values())
        prompt = f"""You are a student travel budget advisor.
The student is planning a trip to {trip_params.get('destination')} with a budget of ₹{trip_params.get('budget', 3000)}.
Current estimated breakdown: {json.dumps(budget_breakdown)}.
Total estimated cost: ₹{total}.
Budget: ₹{trip_params.get('budget', 3000)}.

Provide exactly 6 specific, actionable money-saving tips as a JSON array of strings.
Each tip should mention approximate savings in ₹.
Return ONLY the JSON array."""
        raw = call_ai(prompt, expect_json=True)
        parsed = safe_json_parse(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
        return _default_budget_tips(budget_breakdown)
    except Exception:
        return _default_budget_tips(budget_breakdown)


def _default_budget_tips(budget_breakdown: dict) -> list:
    return [
        f"Use public transportation instead of private taxis – save up to ₹{int(budget_breakdown.get('Transportation', 500) * 0.3):,}.",
        f"Choose hostels or guesthouses over hotels – save up to ₹{int(budget_breakdown.get('Accommodation', 500) * 0.4):,}.",
        "Eat at local darshini restaurants and street food stalls instead of tourist restaurants.",
        "Visit free attractions: public parks, beaches, viewpoints, and religious sites.",
        "Travel mid-week – accommodation is 20–30% cheaper than weekends.",
        "Book KSRTC or train tickets in advance online for the best prices.",
    ]
