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

_GEMINI_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
LAST_AI_ERROR = [""]          # short reason shown to the user when AI could not be used


def _ai_ready() -> bool:
    return bool(GEMINI_API_KEY) and not DEMO_MODE


def _rest_generate(prompt: str, expect_json: bool = False) -> str:
    """Call Gemini through its public web API. Needs only `requests` and the API key (no extra install)."""
    import requests
    last = "unknown error"
    for model in _GEMINI_MODELS:
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        if expect_json:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=body, timeout=45)
        except Exception as exc:
            last = f"network error ({type(exc).__name__})"
            continue
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                last = "empty answer from Gemini"
                continue
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            msg = ""
        last = f"{model}: HTTP {r.status_code} {msg[:120]}"
        if r.status_code in (400, 401, 403):      # bad / blocked key: other models will fail too
            break
    raise RuntimeError(last)


def call_ai(prompt: str, expect_json: bool = False) -> str:
    """
    Call the Gemini API with the given prompt.
    Uses the official SDK when installed, otherwise the plain web API (works on Streamlit Cloud as is).
    Returns the raw text response or raises an exception.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("AI model not available.")
    handle = _get_model()
    if handle is not None:
        try:
            if GENAI_SDK == "new":
                return handle.models.generate_content(model="gemini-2.0-flash", contents=prompt).text
            return handle.generate_content(prompt).text
        except Exception:
            pass                                   # fall through to the web API
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


def _nearby_spots(destination: str, radius_km: float = 45.0, want: int = 12) -> list:
    """Real places around the destination from TripMate's own lists: [(name, note, km_away)]."""
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
                    spots.append((h, f"Visit {h} ({r['category'].lower()})", km))
    except Exception:
        pass
    try:
        for _, r in load_route_stops().iterrows():
            km = haversine_km(c, (float(r["latitude"]), float(r["longitude"])))
            if km <= radius_km:
                kind = str(r["kind"]).split(" ", 1)[-1]
                spots.append((str(r["name"]), f"Visit {r['name']} - {kind.lower()}", km))
    except Exception:
        pass
    spots.sort(key=lambda s: s[2])
    out = []
    for name, note, km in spots:
        key = name.lower()
        core = key.split(" (")[0].strip()
        if core in ("sunset point", "viewpoint") or any(
                core in o.lower() or o.lower().split(" (")[0] in key for o, _, _ in out):
            continue
        out.append((name, note, km))
    return out[:want]


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

CHAT_SYSTEM_PROMPT = """You are TripMate AI Assistant – a friendly, knowledgeable student travel advisor for India.
You help students plan affordable trips, suggest destinations, give packing tips, and answer travel questions.
Be concise, helpful, and student-budget-focused.
All price estimates are approximate and should be verified before travel.
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


def get_demo_response(user_message: str) -> str:
    """Return a canned demo response based on keywords in the user message."""
    msg = user_message.lower()
    if any(k in msg for k in ["mysuru", "mysore"]):
        return DEMO_RESPONSES["mysuru"]
    if any(k in msg for k in ["₹", "budget", "cheap trip", "under", "affordable", "3000", "2000", "5000"]):
        return DEMO_RESPONSES["budget"]
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
    return DEMO_RESPONSES["default"]


def chat_with_ai(user_message: str, history: list = None) -> str:
    """
    Send a message to the AI chatbot.
    Returns AI response string.
    Falls back to demo responses if API is unavailable.
    """
    if not _ai_ready():
        return get_demo_response(user_message)

    try:
        # Build conversation context
        context = CHAT_SYSTEM_PROMPT + "\n\n"
        if history:
            for msg in history[-6:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                context += f"{role}: {msg['content']}\n"
        context += f"User: {user_message}\nAssistant:"

        return call_ai(context)
    except Exception:
        return get_demo_response(user_message)


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
