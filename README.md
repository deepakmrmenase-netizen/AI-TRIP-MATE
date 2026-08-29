# ✈️ TripMate AI

> **Plan Smarter. Travel More. Spend Less.**

An AI-powered travel planning platform designed specifically for college students. TripMate AI helps you discover student-friendly destinations, generate personalized day-by-day itineraries using Generative AI, manage your budget, and plan your trip — all in one beautiful Streamlit application.

---

## 🎯 Problem Statement

College students struggle to plan affordable trips due to:
- Lack of budget awareness and planning tools
- No personalized destination recommendations
- Difficulty creating structured day-by-day itineraries
- Inability to visualise budget breakdowns

## 💡 Proposed Solution

TripMate AI combines **Generative AI**, **Python**, and **Streamlit** to provide:
- AI-generated itineraries based on budget, interests, and preferences
- Interactive budget dashboards and Plotly charts
- Student-specific money-saving tips
- Interactive Folium maps with attraction pins
- An AI chatbot for travel questions

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 AI Trip Planner | Enter your trip details → AI generates a complete day-by-day itinerary |
| 💰 Budget Analysis | Donut chart, bar charts, per-person and per-day cost breakdowns |
| 🗺️ Interactive Maps | Folium-powered maps with route visualization |
| 💬 AI Chatbot | Ask travel questions, get tips, budget suggestions |
| 🌍 Explore Destinations | Browse and filter student-friendly destinations |
| ❤️ Saved Trips | Save, view, download, and manage trip plans |
| 📋 Checklist | Interactive packing checklist with progress tracking |
| 💰 Budget Planner | Standalone trip cost calculator |
| 🔄 Demo Mode | Fully functional without any API keys |

---

## 🛠️ Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.8+ | Core language |
| Streamlit | ≥1.28 | Web UI framework |
| Google Gemini AI | ≥0.3 | Generative AI for itineraries |
| Pandas | ≥1.5 | Destination data handling |
| Plotly | ≥5.15 | Interactive budget charts |
| Folium | ≥0.14 | Interactive maps |
| streamlit-folium | ≥0.15 | Folium → Streamlit integration |
| python-dotenv | ≥1.0 | Secure API key loading |

---

## 📁 Project Structure

```
TripMate_AI/
│
├── app.py                    ← Main entry point
├── data_loader.py            ← Cached data loading helpers
├── requirements.txt
├── README.md
├── .env.example              ← Copy to .env and add your API keys
│
├── config/
│   └── config.py             ← Central configuration & constants
│
├── services/
│   ├── ai_service.py         ← Gemini AI integration + fallback
│   ├── travel_service.py     ← Destination search & filtering
│   ├── map_service.py        ← Folium map building
│   └── budget_service.py     ← Budget calculations & Plotly charts
│
├── components/
│   ├── navbar.py             ← Sidebar navigation & global CSS
│   ├── itinerary.py          ← Trip itinerary rendering
│   ├── budget.py             ← Budget dashboard component
│   ├── destination_card.py   ← Destination card UI
│   └── chatbot.py            ← AI chat interface
│
├── data/
│   ├── destinations.csv      ← 10 student-friendly destinations
│   └── sample_trips.json     ← Sample trip templates
│
├── utils/
│   ├── validators.py         ← Input validation
│   └── helpers.py            ← Formatting & utility functions
│
└── assets/
    └── images/               ← (For future image assets)
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone / Download the Project

```bash
# If using git:
git clone <your-repo-url>
cd TripMate_AI

# Or simply navigate to the project folder:
cd TripMate_AI
```

### Step 2: Create a Virtual Environment (Recommended)

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```cmd
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

```cmd
copy .env.example .env
```

Open `.env` and add your API keys:

```env
AI_API_KEY=your_gemini_api_key_here
MAP_API_KEY=your_map_api_key_here
```

> ⚠️ **Never share or commit your `.env` file.**

### Step 5: Run the Application

```cmd
streamlit run app.py
```

The app will open automatically at **http://localhost:8501**

---

## 🔑 API Key Setup

### Google Gemini AI Key (Free Tier Available)

1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key
5. Add it to your `.env` file:
   ```
   AI_API_KEY=your_key_here
   ```

> **Note:** The Gemini free tier provides generous usage limits, more than enough for student use.

---

## 🤖 Demo Mode (No API Key Needed)

TripMate AI works **fully without any API key** in Demo Mode:

- **AI Trip Planner** → Generates a realistic sample itinerary based on pre-built templates
- **AI Chatbot** → Returns pre-written helpful responses for common travel questions
- **Budget Planner** → Fully functional (no AI needed)
- **Explore Destinations** → Fully functional with CSV data
- **Maps** → Fully functional with Folium
- **Checklist** → Fully functional

When Demo Mode is active, you'll see a **yellow banner** in the app. Add your Gemini API key to enable fully personalised AI-powered responses.

---

## 📱 Application Pages

| Page | Description |
|---|---|
| 🏠 Home | Hero section, feature cards, popular destinations quick-launch |
| 🧭 AI Trip Planner | Main feature – complete trip generation with form input |
| 🌍 Explore Destinations | Browse destinations with filters; Trips Under Budget feature |
| 💰 Budget Planner | Manual trip cost calculator with Plotly visualisation |
| 🗺️ Trip Map | Interactive Folium map for any origin → destination |
| 💬 AI Travel Assistant | Chatbot with suggested questions and chat history |
| ❤️ Saved Trips | View/download/delete saved trips (session-based storage) |
| 📋 Travel Checklist | Pre-trip checklist with progress bar and custom items |
| ℹ️ About | Project info, technology stack, and key benefits |

---

## 🔮 Future Enhancements

- [ ] Real-time hotel and bus ticket price integration (via APIs)
- [ ] User authentication and cloud-based trip saving
- [ ] Trip sharing via unique links
- [ ] Multi-language support (Hindi, Kannada)
- [ ] AI-generated packing lists based on destination and season
- [ ] Google Maps embed integration
- [ ] WhatsApp itinerary sharing
- [ ] Community reviews and ratings for destinations

---

## ⚠️ Disclaimer

All travel costs, prices, and time estimates shown in TripMate AI are **estimates only**. They are generated for educational and planning purposes. Always verify current prices, schedules, and availability directly with transportation providers, hotels, and official tourism websites before booking. TripMate AI is not responsible for any discrepancies between estimated and actual costs.

---

## 📄 License

This project is created for educational purposes as part of a BCA Final Year Project.

---

*Made with ❤️ for students | TripMate AI v1.0 | Built with Python & Streamlit*
