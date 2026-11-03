"""
TripMate AI - Data Loader
Centralised helper to load static data files (destinations CSV, sample trips JSON).
Cached with Streamlit's cache_data for performance.
"""

import io
import json
import os
import pandas as pd
import streamlit as st


# os.path.abspath ensures this works on Streamlit Cloud where __file__ may be relative
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_data
def load_destinations() -> pd.DataFrame:
    """Load destinations from CSV and return as a DataFrame."""
    path = os.path.join(BASE_DIR, "data_destinations.csv")
    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        # Return minimal fallback DataFrame
        return pd.DataFrame(columns=[
            "destination", "state", "description", "budget_min", "budget_max",
            "duration_days", "best_time", "travel_type", "popular_places",
            "student_tip", "latitude", "longitude",
        ])


@st.cache_data
def load_sample_trips() -> dict:
    """Load sample trips from JSON file."""
    path = os.path.join(BASE_DIR, "data_sample_trips.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sample_trips": [], "demo_itinerary_template": {}}


# Budget tiers (based on the minimum per-person trip cost, in rupees)
CHEAP_BELOW = 2500
ROYAL_FROM = 8000
TIERS = ["Cheap", "Mid-range", "Royal / Luxury"]


def budget_tier(budget_min) -> str:
    try:
        v = float(budget_min)
    except (TypeError, ValueError):
        return "Mid-range"
    if v < CHEAP_BELOW:
        return "Cheap"
    if v < ROYAL_FROM:
        return "Mid-range"
    return "Royal / Luxury"


# The all-India place list lives INSIDE this file (nothing extra to upload).
# columns: place, state, category, budget_min, budget_max (Rs per person, 2-3 day trip), highlight, latitude, longitude, aliases
_INDIA_PLACES_CSV = """place,state,category,budget_min,budget_max,highlight,latitude,longitude,aliases
Mysuru,Karnataka,Heritage & Royal,1500,4000,"Mysore Palace, Chamundi Hills, Brindavan Gardens",12.2958,76.6394,Mysore
Mysore Palace,Karnataka,Heritage & Royal,1500,4000,"Grand Wadiyar palace, lit up on Sundays",12.3052,76.6552,Amba Vilas Palace
Bengaluru,Karnataka,City & Culture,2000,6000,"Lalbagh, Cubbon Park, cafes, Nandi Hills",12.9716,77.5946,Bangalore
Hampi,Karnataka,Heritage & Royal,2000,4500,"Vijayanagara ruins, Virupaksha Temple, boulders",15.335,76.46,
Chikkamagaluru,Karnataka,Nature & Hills,2500,5000,"Mullayanagiri, coffee estates, Hebbe Falls",13.3161,75.772,Chikmagalur
Sringeri,Karnataka,Spiritual,1200,3000,"Sharada Peetham, Tunga river, forests",13.4167,75.25,Sringeri Sharadamba Temple
Agumbe,Karnataka,Nature & Hills,1500,3500,"Sunset point, rainforest, Kudlu Falls",13.5089,75.0905,
Udupi,Karnataka,Spiritual,1800,3500,"Krishna Matha, Malpe Beach, St Mary's Island",13.3409,74.7421,
Mangaluru,Karnataka,Beach & Islands,2000,4500,"Panambur Beach, seafood, Kudroli Temple",12.9141,74.856,Mangalore
Gokarna,Karnataka,Beach & Islands,2000,4500,"Om Beach, Kudle Beach, Mahabaleshwar Temple",14.5479,74.3188,
Badami,Karnataka,Heritage & Royal,1500,3500,"Chalukya cave temples, Agastya Lake",15.9149,75.676,
Belur,Karnataka,Heritage & Royal,1500,3500,Chennakeshava Temple and Halebidu (Hoysala art),13.1651,75.8655,Halebidu
Jog Falls,Karnataka,Nature & Hills,1800,4000,One of India's highest plunge waterfalls,14.2293,74.8125,
Coorg,Karnataka,Nature & Hills,3000,7000,"Abbey Falls, Raja's Seat, coffee plantations",12.4244,75.7382,Madikeri;Kodagu
Dharmasthala,Karnataka,Spiritual,1200,3000,"Manjunatha Temple, Bahubali statue",12.95,75.38,
Kudremukh,Karnataka,Nature & Hills,2000,4500,"Trek, Lakya Dam, Kudremukh National Park",13.215,75.25,
Munnar,Kerala,Nature & Hills,3000,7000,"Tea gardens, Eravikulam, Mattupetty Dam",10.0889,77.0595,
Alleppey,Kerala,Nature & Hills,3500,9000,"Backwaters, houseboats, Vembanad Lake",9.4981,76.3388,Alappuzha
Kochi,Kerala,City & Culture,2500,6000,"Fort Kochi, Chinese fishing nets, Mattancherry",9.9312,76.2673,Cochin;Ernakulam
Varkala,Kerala,Beach & Islands,2500,5500,"Cliff beach, Janardhana Temple",8.7379,76.7163,
Thekkady,Kerala,Wildlife & Adventure,3000,7000,"Periyar Wildlife Sanctuary, spice plantations",9.6,77.1667,Periyar
Wayanad,Kerala,Wildlife & Adventure,3000,7000,"Edakkal Caves, Banasura Dam, waterfalls",11.6854,76.132,
Kovalam,Kerala,Beach & Islands,3000,7500,"Lighthouse Beach, Ayurveda",8.4004,76.9787,
Thiruvananthapuram,Kerala,City & Culture,2000,5000,"Padmanabhaswamy Temple, Napier Museum",8.5241,76.9366,Trivandrum
Kumarakom,Kerala,Luxury Stay,12000,30000,Luxury lakeside resorts and private houseboats,9.6177,76.43,
Ooty,Tamil Nadu,Nature & Hills,2500,6000,"Botanical Gardens, toy train, Doddabetta",11.4102,76.695,Udhagamandalam
Kodaikanal,Tamil Nadu,Nature & Hills,2500,6000,"Coaker's Walk, Pillar Rocks, lake",10.2381,77.4892,
Madurai,Tamil Nadu,Spiritual,1500,3500,Meenakshi Amman Temple,9.9252,78.1198,
Rameswaram,Tamil Nadu,Spiritual,1500,3500,"Ramanathaswamy Temple, Pamban Bridge, Dhanushkodi",9.2876,79.3129,
Mahabalipuram,Tamil Nadu,Heritage & Royal,1800,4000,"Shore Temple, Pancha Rathas",12.6208,80.1932,Mamallapuram
Thanjavur,Tamil Nadu,Heritage & Royal,1500,3500,"Brihadeeswarar Temple, Maratha Palace",10.787,79.1378,Tanjore
Kanyakumari,Tamil Nadu,Beach & Islands,1800,4000,"Sunrise, Vivekananda Rock, Thiruvalluvar statue",8.0883,77.5385,
Chennai,Tamil Nadu,City & Culture,2000,5000,"Marina Beach, Kapaleeshwarar Temple",13.0827,80.2707,Madras
Pondicherry,Puducherry,Beach & Islands,2500,6000,"French Quarter, Auroville, Paradise Beach",11.9416,79.8083,Puducherry;Pondy
Kanchipuram,Tamil Nadu,Spiritual,1500,3500,Temple town and silk sarees,12.8342,79.7036,
Hyderabad,Telangana,Heritage & Royal,2500,6000,"Charminar, Golconda Fort, Ramoji Film City",17.385,78.4867,
Charminar,Telangana,Heritage & Royal,2000,5000,Iconic 1591 monument and Laad Bazaar,17.3616,78.4747,
Golconda Fort,Telangana,Heritage & Royal,2000,5000,"Sound-and-light show, Qutb Shahi tombs",17.3833,78.4011,
Falaknuma Palace,Telangana,Luxury Stay,25000,60000,"Nizam's palace, now a Taj heritage hotel",17.3314,78.4674,
Tirupati,Andhra Pradesh,Spiritual,1500,3500,Tirumala Venkateswara Temple,13.6288,79.4192,Tirumala
Visakhapatnam,Andhra Pradesh,Beach & Islands,2500,6000,"RK Beach, Kailasagiri, Borra Caves",17.6868,83.2185,Vizag
Araku Valley,Andhra Pradesh,Nature & Hills,2500,5000,"Coffee plantations, scenic train from Vizag",18.3333,82.8667,
Warangal,Telangana,Heritage & Royal,1500,3500,"Warangal Fort, Thousand Pillar Temple",17.9689,79.5941,
Mumbai,Maharashtra,City & Culture,3500,9000,"Gateway of India, Marine Drive, street food",19.076,72.8777,Bombay
Gateway of India,Maharashtra,Heritage & Royal,3000,8000,"Iconic harbour arch, Colaba, Elephanta ferry",18.922,72.8347,
Pune,Maharashtra,City & Culture,2000,5000,"Shaniwar Wada, Sinhagad Fort",18.5204,73.8567,
Lonavala,Maharashtra,Nature & Hills,2500,6000,"Bhushi Dam, Karla Caves, monsoon hills",18.7546,73.4062,Khandala
Mahabaleshwar,Maharashtra,Nature & Hills,3000,7000,"Strawberry farms, Venna Lake, viewpoints",17.9237,73.6586,Panchgani
Ajanta Caves,Maharashtra,Heritage & Royal,2000,4500,UNESCO Buddhist rock-cut cave paintings,20.5519,75.7033,
Ellora Caves,Maharashtra,Heritage & Royal,2000,4500,"UNESCO site, Kailasa Temple carved from one rock",20.0268,75.179,
Aurangabad,Maharashtra,Heritage & Royal,2000,4500,"Bibi Ka Maqbara, Daulatabad Fort",19.8762,75.3433,Chhatrapati Sambhajinagar
Nashik,Maharashtra,Spiritual,1500,3500,"Trimbakeshwar, Panchavati, vineyards",19.9975,73.7898,
Shirdi,Maharashtra,Spiritual,1200,3000,Sai Baba Temple,19.7667,74.4772,
Alibag,Maharashtra,Beach & Islands,2500,6000,Kolaba Fort and quiet beaches near Mumbai,18.6414,72.8722,
Goa,Goa,Beach & Islands,3000,9000,"Baga, Palolem, Old Goa churches, nightlife",15.2993,74.124,
Panaji,Goa,City & Culture,2500,6000,"Fontainhas Latin Quarter, riverfront",15.4909,73.8278,Panjim
Old Goa,Goa,Heritage & Royal,2000,4500,"Basilica of Bom Jesus, UNESCO churches",15.5009,73.9116,Basilica of Bom Jesus
Ahmedabad,Gujarat,Heritage & Royal,2000,5000,"Sabarmati Ashram, Adalaj stepwell, old city",23.0225,72.5714,
Statue of Unity,Gujarat,City & Culture,2000,5000,"World's tallest statue, Kevadia",21.838,73.7191,Kevadia
Dwarka,Gujarat,Spiritual,1800,4000,"Dwarkadhish Temple, Bet Dwarka",22.2394,68.9678,
Somnath,Gujarat,Spiritual,1500,3500,Somnath Jyotirlinga on the Arabian Sea,20.888,70.4013,
Rann of Kutch,Gujarat,Nature & Hills,4000,9000,"White salt desert, Rann Utsav",23.875,69.685,Dhordo;Kutch;Great Rann
Gir National Park,Gujarat,Wildlife & Adventure,4000,9000,Asiatic lion safari,21.1243,70.8242,Gir;Sasan Gir
Diu,Daman and Diu,Beach & Islands,2500,5500,"Diu Fort, Nagoa Beach",20.7144,70.9874,
Vadodara,Gujarat,Heritage & Royal,2000,5000,"Laxmi Vilas Palace, Champaner",22.3072,73.1812,Baroda
Laxmi Vilas Palace,Gujarat,Luxury Stay,12000,30000,"Gaekwad royal palace, bigger than Buckingham Palace",22.2979,73.1913,
Jaipur,Rajasthan,Heritage & Royal,2500,7000,"Amer Fort, Hawa Mahal, City Palace, bazaars",26.9124,75.7873,Pink City
Hawa Mahal,Rajasthan,Heritage & Royal,2000,6000,Palace of Winds with 953 windows,26.9239,75.8267,
Amer Fort,Rajasthan,Heritage & Royal,2000,6000,"Hilltop fort-palace, elephant and jeep rides",26.9855,75.8513,Amber Fort
Udaipur,Rajasthan,Heritage & Royal,3000,9000,"City Palace, Lake Pichola, boat rides",24.5854,73.7125,City of Lakes
City Palace Udaipur,Rajasthan,Heritage & Royal,3000,9000,Royal palace complex on Lake Pichola,24.5764,73.6835,
Jodhpur,Rajasthan,Heritage & Royal,2500,7000,"Mehrangarh Fort, the Blue City",26.2389,73.0243,Blue City
Mehrangarh Fort,Rajasthan,Heritage & Royal,2500,7000,Giant fort above the Blue City,26.2978,73.0184,
Jaisalmer,Rajasthan,Heritage & Royal,3000,8000,"Golden Fort, Sam sand dunes, camel safari",26.9157,70.9083,Golden City
Pushkar,Rajasthan,Spiritual,1800,4500,"Brahma Temple, holy lake, camel fair",26.49,74.55,
Bikaner,Rajasthan,Heritage & Royal,2000,5000,"Junagarh Fort, Karni Mata rat temple",28.0229,73.3119,
Chittorgarh,Rajasthan,Heritage & Royal,1500,3500,"Largest fort in India, Vijay Stambh",24.8887,74.6269,Chittor Fort
Mount Abu,Rajasthan,Nature & Hills,2500,6000,"Dilwara Jain Temples, Nakki Lake",24.5926,72.7156,
Ajmer,Rajasthan,Spiritual,1500,3500,"Ajmer Sharif Dargah, Ana Sagar",26.4499,74.6399,
Kumbhalgarh,Rajasthan,Heritage & Royal,2000,5000,"36 km fort wall, wildlife sanctuary",25.1528,73.587,
Ranthambore,Rajasthan,Wildlife & Adventure,5000,12000,Tiger safari and ruined fort,26.0173,76.5026,Ranthambhore
Bundi,Rajasthan,Heritage & Royal,1500,3500,"Taragarh Fort, stepwells, painted palace",25.4305,75.6499,
Mandawa,Rajasthan,Heritage & Royal,2000,5000,Shekhawati painted havelis,28.0524,75.147,
Taj Lake Palace,Rajasthan,Luxury Stay,30000,80000,Floating marble palace hotel on Lake Pichola,24.5754,73.6803,Lake Palace Udaipur
Umaid Bhawan Palace,Rajasthan,Luxury Stay,35000,90000,Art-deco royal palace hotel in Jodhpur,26.2795,73.0476,
Rambagh Palace,Rajasthan,Luxury Stay,30000,70000,Former Maharaja of Jaipur's residence,26.901,75.807,
Neemrana Fort-Palace,Rajasthan,Luxury Stay,12000,25000,15th-century hilltop fort hotel,27.9879,76.3871,Neemrana
Agra,Uttar Pradesh,Heritage & Royal,2000,5500,"Taj Mahal, Agra Fort, Mehtab Bagh",27.1767,78.0081,
Taj Mahal,Uttar Pradesh,Heritage & Royal,2000,5500,"Marble mausoleum, sunrise views",27.1751,78.0421,
Fatehpur Sikri,Uttar Pradesh,Heritage & Royal,1500,3500,"Mughal ghost city, Buland Darwaza",27.094,77.6679,
Varanasi,Uttar Pradesh,Spiritual,1800,4500,"Ganga Aarti, ghats, Kashi Vishwanath",25.3176,82.9739,Kashi;Benares
Lucknow,Uttar Pradesh,Heritage & Royal,2000,5000,"Bara Imambara, Awadhi food",26.8467,80.9462,
Ayodhya,Uttar Pradesh,Spiritual,1500,3500,"Ram Janmabhoomi, Saryu ghats",26.7922,82.1998,
Prayagraj,Uttar Pradesh,Spiritual,1500,3500,"Triveni Sangam, Allahabad Fort",25.4358,81.8463,Allahabad
Mathura,Uttar Pradesh,Spiritual,1500,3500,Krishna Janmabhoomi and Vrindavan,27.4924,77.6737,Vrindavan
Delhi,Delhi,City & Culture,3000,8000,"Red Fort, India Gate, Qutub Minar, Chandni Chowk",28.6139,77.209,New Delhi
Red Fort,Delhi,Heritage & Royal,2000,6000,"Mughal fort, Independence Day venue",28.6562,77.241,Lal Qila
India Gate,Delhi,City & Culture,2000,6000,War memorial and lawns,28.6129,77.2295,
Qutub Minar,Delhi,Heritage & Royal,2000,6000,73 m UNESCO minaret,28.5245,77.1855,
Khajuraho,Madhya Pradesh,Heritage & Royal,2000,5000,Chandela temples and sculptures,24.8318,79.9199,
Orchha,Madhya Pradesh,Heritage & Royal,1500,3500,Betwa river palaces and chhatris,25.3519,78.64,
Gwalior,Madhya Pradesh,Heritage & Royal,1500,3500,"Gwalior Fort, Jai Vilas Palace",26.2183,78.1828,
Bhopal,Madhya Pradesh,City & Culture,1800,4000,"Upper Lake, museums, old city",23.2599,77.4126,
Sanchi,Madhya Pradesh,Heritage & Royal,1200,3000,Great Stupa (UNESCO),23.4793,77.7396,
Ujjain,Madhya Pradesh,Spiritual,1500,3500,Mahakaleshwar Jyotirlinga,23.1765,75.7885,
Indore,Madhya Pradesh,City & Culture,1800,4000,"Sarafa street food, Rajwada",22.7196,75.8577,
Mandu,Madhya Pradesh,Heritage & Royal,1500,3500,"Ruined sultanate city, Jahaz Mahal",22.3586,75.4026,
Pachmarhi,Madhya Pradesh,Nature & Hills,2000,4500,Satpura hill station and caves,22.4674,78.4346,
Bandhavgarh,Madhya Pradesh,Wildlife & Adventure,5000,12000,Tiger safaris,23.7183,80.9611,
Shimla,Himachal Pradesh,Nature & Hills,3000,7000,"The Ridge, Mall Road, toy train",31.1048,77.1734,
Manali,Himachal Pradesh,Wildlife & Adventure,3500,8000,"Solang Valley, Rohtang, Old Manali",32.2396,77.1887,
Dharamshala,Himachal Pradesh,Nature & Hills,2500,6000,"Dalai Lama Temple, Triund trek, McLeod Ganj",32.219,76.3234,McLeod Ganj
Kasol,Himachal Pradesh,Nature & Hills,2000,5000,"Parvati Valley, Kheerganga trek",32.01,77.315,
Spiti Valley,Himachal Pradesh,Wildlife & Adventure,5000,12000,"Key Monastery, Chandratal, cold desert",32.2276,78.071,Kaza
Rishikesh,Uttarakhand,Wildlife & Adventure,2000,5500,"Rafting, Laxman Jhula, yoga, Ganga Aarti",30.0869,78.2676,
Haridwar,Uttarakhand,Spiritual,1500,3500,Har Ki Pauri Ganga Aarti,29.9457,78.1642,
Mussoorie,Uttarakhand,Nature & Hills,3000,7000,"Queen of the Hills, Kempty Falls",30.4598,78.0644,
Nainital,Uttarakhand,Nature & Hills,3000,7000,"Naini Lake, Snow View Point",29.3919,79.4542,
Auli,Uttarakhand,Wildlife & Adventure,4000,9000,Skiing and Himalayan views,30.5267,79.5667,
Jim Corbett,Uttarakhand,Wildlife & Adventure,5000,12000,"India's oldest national park, tiger reserve",29.53,78.7747,Corbett
Kedarnath,Uttarakhand,Spiritual,4000,9000,Himalayan Jyotirlinga trek,30.7352,79.0669,
Leh,Ladakh,Wildlife & Adventure,12000,25000,"Monasteries, Khardung La, mountain passes",34.1526,77.5771,Ladakh
Pangong Lake,Ladakh,Nature & Hills,13000,25000,High-altitude blue lake,33.7595,78.6674,Pangong Tso
Srinagar,Jammu & Kashmir,Nature & Hills,10000,22000,"Dal Lake houseboats, Mughal gardens",34.0837,74.7973,Kashmir
Gulmarg,Jammu & Kashmir,Wildlife & Adventure,10000,22000,"Gondola, skiing, meadows",34.0484,74.3805,
Pahalgam,Jammu & Kashmir,Nature & Hills,9000,18000,"Lidder Valley, Betaab Valley",34.0161,75.315,
Amritsar,Punjab,Spiritual,1800,4000,"Golden Temple, Wagah Border, Jallianwala Bagh",31.634,74.8723,
Golden Temple,Punjab,Spiritual,1500,3500,Harmandir Sahib and the free langar,31.62,74.8765,Harmandir Sahib
Chandigarh,Chandigarh,City & Culture,2000,5000,"Rock Garden, Sukhna Lake",30.7333,76.7794,
Kolkata,West Bengal,City & Culture,2000,5000,"Victoria Memorial, Howrah Bridge, Durga Puja",22.5726,88.3639,Calcutta
Victoria Memorial,West Bengal,Heritage & Royal,1800,4500,White-marble colonial museum,22.5448,88.3426,
Darjeeling,West Bengal,Nature & Hills,3000,7000,"Tiger Hill sunrise, toy train, tea estates",27.036,88.2627,
Sundarbans,West Bengal,Wildlife & Adventure,4000,9000,Mangrove delta and Bengal tigers,21.9497,89.1833,
Puri,Odisha,Spiritual,1500,3500,Jagannath Temple and beach,19.8135,85.8312,
Konark,Odisha,Heritage & Royal,1500,3500,Sun Temple (UNESCO),19.8876,86.0945,
Bhubaneswar,Odisha,Heritage & Royal,1500,3500,"Temple city, Lingaraj, Udayagiri caves",20.2961,85.8245,
Gangtok,Sikkim,Nature & Hills,5000,12000,"Tsomgo Lake, monasteries, Kanchenjunga views",27.3389,88.6065,
Shillong,Meghalaya,Nature & Hills,3000,7000,"Umiam Lake, Elephant Falls",25.5788,91.8933,
Cherrapunji,Meghalaya,Nature & Hills,3000,7000,"Living root bridges, Nohkalikai Falls",25.27,91.73,Sohra
Guwahati,Assam,Spiritual,2000,5000,"Kamakhya Temple, Brahmaputra",26.1445,91.7362,
Kaziranga,Assam,Wildlife & Adventure,5000,12000,One-horned rhino safari,26.5775,93.1711,
Tawang,Arunachal Pradesh,Nature & Hills,8000,15000,"Tawang Monastery, Sela Pass",27.586,91.8594,
Bodh Gaya,Bihar,Spiritual,1200,3000,Mahabodhi Temple (UNESCO),24.6961,84.9869,
Port Blair,Andaman and Nicobar,Beach & Islands,10000,20000,"Cellular Jail, Ross Island",11.6234,92.7265,Andaman
Havelock Island,Andaman and Nicobar,Beach & Islands,14000,35000,"Radhanagar Beach, scuba diving",11.974,92.985,Swaraj Dweep
Lakshadweep,Lakshadweep,Luxury Stay,25000,60000,Coral lagoons and Agatti island,10.85,72.1833,Agatti
Lalitha Mahal Palace (Mysuru),Karnataka,Luxury Stay,9000,22000,"Palace hotel facing Chamundi Hills",12.2950,76.6890,Lalitha Mahal
Evolve Back Hampi,Karnataka,Luxury Stay,15000,35000,"Luxury resort near Hampi ruins",15.3153,76.4747,Kamalapura Palace
Coorg Plantation Resorts,Karnataka,Nature & Hills,12000,28000,"Luxury coffee-estate resorts and spa",12.3375,75.8069,Coorg Luxury
Kabini Luxury Safari,Karnataka,Wildlife & Adventure,10000,25000,"Jungle lodges and boat safaris",11.9930,76.3030,Kabini
The Leela Palace Bengaluru,Karnataka,Luxury Stay,12000,30000,"5-star palace-style hotel",12.9605,77.6485,Leela Bengaluru
Taj West End Bengaluru,Karnataka,Luxury Stay,11000,28000,"Heritage hotel in 20 acres of gardens",12.9840,77.5830,Taj West End
Oberoi Udaivilas,Rajasthan,Luxury Stay,30000,70000,"Palace hotel on Lake Pichola",24.5654,73.6785,Udaivilas
Suryagarh Jaisalmer,Rajasthan,Luxury Stay,18000,45000,"Desert fort-style luxury stay",26.9157,70.9083,Jaisalmer Luxury
Ranthambore Luxury Camps,Rajasthan,Wildlife & Adventure,12000,40000,"Tiger safari with luxury tents",26.0173,76.5026,Aman-i-Khas
Oberoi Amarvilas Agra,Uttar Pradesh,Luxury Stay,25000,60000,"Rooms with Taj Mahal views",27.1670,78.0560,Amarvilas
Brijrama Palace Varanasi,Uttar Pradesh,Luxury Stay,12000,30000,"Ganga ghat palace hotel",25.3010,83.0090,Brijrama
Taj Mahal Palace Mumbai,Maharashtra,Luxury Stay,18000,45000,"Iconic harbour hotel by Gateway of India",18.9217,72.8332,Taj Mumbai
Taj Mahal Hotel New Delhi,Delhi,Luxury Stay,15000,40000,"Luxury hotel in Lutyens Delhi",28.6040,77.2250,Taj Delhi
Oberoi Grand Kolkata,West Bengal,Luxury Stay,10000,25000,"Colonial-era grand hotel",22.5614,88.3510,Oberoi Grand
Taj Coromandel Chennai,Tamil Nadu,Luxury Stay,10000,25000,"5-star hotel in Nungambakkam",13.0620,80.2500,Taj Coromandel
Goa Luxury Beach Resorts,Goa,Beach & Islands,10000,35000,"5-star beach resorts and spas",15.2993,74.1240,South Goa Resorts
Munnar Luxury Resorts,Kerala,Nature & Hills,8000,22000,"Tea-estate resorts with valley views",10.0889,77.0595,Munnar Resorts
Alleppey Luxury Houseboat,Kerala,Luxury Stay,9000,25000,"Private luxury houseboat on the backwaters",9.4981,76.3388,Alappuzha Houseboat
Wildflower Hall Shimla,Himachal Pradesh,Luxury Stay,15000,35000,"Himalayan luxury resort in the cedar forest",31.1130,77.2230,Wildflower Hall
Darjeeling Tea Estate Stay,West Bengal,Nature & Hills,8000,18000,"Heritage tea-estate bungalows",27.0410,88.2663,Darjeeling Luxury
Ananda in the Himalayas,Uttarakhand,Luxury Stay,15000,40000,"Luxury spa and wellness palace estate",30.1750,78.2980,Ananda Spa
Jim Corbett Luxury Lodges,Uttarakhand,Wildlife & Adventure,9000,25000,"Riverside jungle lodges",29.5300,78.7747,Corbett Luxury
"""


@st.cache_data
def load_india_places() -> pd.DataFrame:
    """All-India places, from cheap student trips to royal / luxury stays."""
    cols = ["place", "state", "category", "budget_min", "budget_max",
            "highlight", "latitude", "longitude", "aliases", "tier"]
    try:
        df = pd.read_csv(io.StringIO(_INDIA_PLACES_CSV))
        df["aliases"] = df["aliases"].fillna("")
        df["tier"] = df["budget_min"].apply(budget_tier)
        return df
    except Exception:
        return pd.DataFrame(columns=cols)



# ── Well-known stops along popular routes (instant, works offline) ──────────────
_ROUTE_STOPS_CSV = """name,kind,latitude,longitude
"Ramanagara (Sholay hills)","⛰️ Hills / Viewpoint",12.7150,77.2800
"Channapatna (toy town)","🛍️ Town / Shopping",12.6517,77.2067
"Maddur (Maddur vada)","🍽️ Food stop",12.5846,77.0446
"Mandya","🏙️ Town",12.5218,76.8951
"Srirangapatna","🏰 Fort / Heritage",12.4181,76.6946
"Ranganathittu Bird Sanctuary","🦜 Wildlife / Birds",12.4244,76.6580
"KRS Dam & Brindavan Gardens","💦 Dam / Garden",12.4255,76.5724
"Kunigal","🏙️ Town",13.0230,77.0230
"Shravanabelagola","🛕 Jain heritage",12.8548,76.4847
"Hassan","🏙️ Town",13.0068,76.1004
"Halebidu (Hoysaleswara Temple)","🛕 Heritage temple",13.2130,75.9948
"Belur (Chennakeshava Temple)","🛕 Heritage temple",13.1650,75.8648
"Chikkamagaluru","🏙️ Hill town",13.3153,75.7754
"Mullayanagiri","⛰️ Highest peak in Karnataka",13.3910,75.7230
"Baba Budangiri","⛰️ Hills / Viewpoint",13.3980,75.7410
"Hebbe Falls","💦 Waterfall",13.3040,75.6500
"Kemmannugundi","⛰️ Hill station",13.5280,75.7440
"Kudremukh","⛰️ Hills / Trek",13.2166,75.2500
"Horanadu (Annapoorneshwari)","🛕 Temple",13.2457,75.3567
"Kalasa","🏙️ Town",13.2379,75.3590
"Agumbe (sunset point)","🌄 Viewpoint",13.5034,75.0903
"Sringeri (Sharada Peetham)","🛕 Temple",13.4167,75.2500
"Tumakuru","🏙️ Town",13.3379,77.1173
"Sira","🏙️ Town",13.7410,76.9040
"Chitradurga Fort","🏰 Fort",14.2226,76.3980
"Davanagere (benne dosa)","🍽️ Food stop",14.4644,75.9218
"Haveri","🏙️ Town",14.7951,75.4000
"Hubballi","🏙️ City",15.3647,75.1240
"Dharwad (peda)","🍽️ Food stop",15.4589,75.0078
"Belagavi (Kittur / Fort)","🏰 Fort / City",15.8497,74.4977
"Dandeli (rafting)","🌿 Wildlife / Adventure",15.2500,74.6167
"Hampi","🏛️ World Heritage",15.3350,76.4600
"Badami caves","🛕 Cave temples",15.9149,75.6768
"Pattadakal","🛕 World Heritage",15.9486,75.8167
"Aihole","🛕 Heritage temples",16.0200,75.8800
"Bijapur (Gol Gumbaz)","🕌 Monument",16.8302,75.7100
"Bandipur National Park","🐅 Wildlife",11.6667,76.6333
"Mudumalai Tiger Reserve","🐅 Wildlife",11.5667,76.5333
"Gudalur","🏙️ Hill town",11.5030,76.4930
"Coonoor (Sim's Park)","🌿 Hill station",11.3530,76.7959
"Ooty Botanical Garden","🌿 Garden",11.4170,76.7110
"Bylakuppe (Golden Temple)","🛕 Tibetan monastery",12.4256,75.9654
"Kushalnagar","🏙️ Town",12.4604,75.9569
"Cauvery Nisargadhama","🌿 Nature / Island",12.4380,75.9340
"Madikeri (Raja's Seat)","🌄 Viewpoint",12.4244,75.7382
"Abbey Falls","💦 Waterfall",12.4353,75.7183
"Talakaveri","🛕 River origin",12.3833,75.4900
"Nagarhole National Park","🐅 Wildlife",12.0500,76.1500
"Somnathpur (Keshava Temple)","🛕 Heritage temple",12.2767,76.8776
"Talakadu","🛕 Temples / Sand dunes",12.1860,77.0260
"Shivanasamudra Falls","💦 Waterfall",12.2955,77.1650
"Chamundi Hills","🛕 Temple / Viewpoint",12.2724,76.6700
"Surathkal Beach","🏖️ Beach",12.9910,74.7940
"Udupi (Krishna Temple)","🛕 Temple",13.3409,74.7421
"Malpe Beach","🏖️ Beach",13.3790,74.7040
"St Mary's Island","🏝️ Island",13.3790,74.6760
"Maravanthe Beach","🏖️ Beach",13.7140,74.6360
"Kollur (Mookambika)","🛕 Temple",13.8630,74.8140
"Murudeshwar","🛕 Temple / Beach",14.0940,74.4850
"Jog Falls","💦 Waterfall",14.2290,74.8120
"Gokarna","🏖️ Temple / Beach",14.5479,74.3188
"Hindupur","🏙️ Town",13.8286,77.4910
"Lepakshi Temple","🛕 Heritage temple",13.8035,77.6082
"Penukonda Fort","🏰 Fort",14.0790,77.5970
"Anantapur","🏙️ City",14.6819,77.6006
"Gooty Fort","🏰 Fort",15.1230,77.6310
"Kurnool","🏙️ City",15.8281,78.0373
"Belum Caves","🕳️ Caves",15.1000,78.1100
"Hosur","🏙️ Town",12.7409,77.8253
"Krishnagiri","🏙️ Town",12.5186,78.2137
"Vellore Fort","🏰 Fort",12.9202,79.1328
"Kanchipuram (temples & silk)","🛕 Temple town",12.8342,79.7036
"Mahabalipuram (Shore Temple)","🏛️ World Heritage",12.6169,80.1993
"Pondicherry","🏖️ Beach / French quarter",11.9416,79.8083
"Auroville","🧘 Spiritual / Township",12.0058,79.8105
"Chidambaram (Nataraja Temple)","🛕 Temple",11.3993,79.6937
"Thanjavur (Brihadisvara)","🏛️ World Heritage",10.7828,79.1318
"Tiruchirappalli (Rockfort)","🛕 Rock fort temple",10.8277,78.6967
"Madurai (Meenakshi)","🛕 Temple",9.9195,78.1193
"Rameswaram","🛕 Temple / Island",9.2876,79.3129
"Kanyakumari","🌅 Sunrise / Sunset point",8.0883,77.5385
"Munnar tea gardens","🌿 Hill station",10.0889,77.0595
"Thekkady (Periyar)","🐘 Wildlife",9.6000,77.1700
"Alleppey backwaters","🛶 Backwaters",9.4981,76.3388
"Kochi (Fort Kochi)","🏖️ Heritage / Beach",9.9658,76.2422
"Thrissur (Vadakkunnathan)","🛕 Temple",10.5276,76.2144
"Lonavala","⛰️ Hill station",18.7557,73.4091
"Karla Caves","🕳️ Buddhist caves",18.7836,73.4725
"Lohagad Fort","🏰 Fort",18.7110,73.4770
"Pune (Shaniwar Wada)","🏰 Heritage",18.5195,73.8553
"Mahabaleshwar","🌄 Hill station",17.9237,73.6586
"Kolhapur (Mahalaxmi)","🛕 Temple",16.7050,74.2433
"Nashik","🛕 Temple city",19.9975,73.7898
"Aurangabad (Ajanta-Ellora)","🕳️ Cave temples",19.8762,75.3433
"Lonar Lake","🌊 Crater lake",19.9760,76.5080
"Hyderabad (Charminar)","🕌 Monument",17.3616,78.4747
"Golconda Fort","🏰 Fort",17.3833,78.4011
"Warangal Fort","🏰 Fort",17.9689,79.5941
"Mathura","🛕 Temple town",27.4924,77.6737
"Vrindavan","🛕 Temple town",27.5800,77.7000
"Fatehpur Sikri","🏰 World Heritage",27.0940,77.6679
"Agra (Taj Mahal)","🕌 World Wonder",27.1751,78.0421
"Jaipur (Amber Fort)","🏰 Fort",26.9855,75.8513
"Neemrana Fort","🏰 Heritage hotel",27.9879,76.3880
"Panipat","🏙️ Historic town",29.3909,76.9635
"Kurukshetra","🛕 Mahabharata site",29.9695,76.8783
"Chandigarh (Rock Garden)","🌿 Garden",30.7525,76.8101
"Rishikesh","🧘 Yoga / Rafting",30.0869,78.2676
"Haridwar","🛕 Ganga Aarti",29.9457,78.1642
"Varanasi","🛕 Ghats / Temples",25.3176,82.9739
"Sarnath","🛕 Buddhist site",25.3811,83.0214
"Ujjain (Mahakaleshwar)","🛕 Temple",23.1828,75.7682
"Udaipur (City Palace)","🏰 Palace / Lake",24.5764,73.6835
"Chittorgarh Fort","🏰 Fort",24.8879,74.6454
"Pushkar","🛕 Lake / Temple",26.4900,74.5513
"Ranthambore","🐅 Wildlife",26.0173,76.5026
"Gandhinagar (Akshardham)","🛕 Temple",23.2300,72.6740
"Somnath","🛕 Temple",20.8880,70.4010
"Konark Sun Temple","🏛️ World Heritage",19.8876,86.0945
"Puri (Jagannath)","🛕 Temple / Beach",19.8135,85.8312
"Bhubaneswar","🛕 Temple city",20.2961,85.8245
"""


def load_route_stops():
    """Famous places people stop at on the road: name, kind, latitude, longitude."""
    import io as _io
    import pandas as _pd
    return _pd.read_csv(_io.StringIO(_ROUTE_STOPS_CSV))
