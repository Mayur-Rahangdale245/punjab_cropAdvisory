# backend/main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sqlite3, hashlib, requests
from datetime import datetime, timedelta
from googletrans import Translator
import speech_recognition as sr
from gtts import gTTS

# -------------------------
# DATABASE
# -------------------------
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    pref_lang TEXT DEFAULT 'en'
                )""")
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def signup_user(username, password, pref_lang="en"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, pref_lang) VALUES (?, ?, ?)",
                  (username, hash_password(password), pref_lang))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == hash_password(password))

def get_user_lang(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT pref_lang FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "en"

def set_user_lang(username, lang_code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET pref_lang=? WHERE username=?", (lang_code, username))
    conn.commit()
    conn.close()

init_db()

# -------------------------
# WEATHER
# -------------------------
DISTRICT_COORDS = {
    "Amritsar": (31.634, 74.872),
    "Ludhiana": (30.901, 75.857),
    "Patiala": (30.339, 76.386),
    "Bathinda": (30.210, 74.945),
    "Ferozepur": (30.933, 74.622),
    "Hoshiarpur": (31.532, 75.905),
    "Jalandhar": (31.326, 75.576),
}

def fetch_weather(district):
    lat, lon = DISTRICT_COORDS.get(district, (30.901, 75.857))
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5)
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,RH2M,PRECTOTCORR",
        "community": "ag",
        "latitude": lat,
        "longitude": lon,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()["properties"]["parameter"]
        dates = sorted(data["T2M"].keys())
        forecast = []
        for d in dates:
            forecast.append({
                "date": d,
                "temperature": round(data["T2M"][d], 1),
                "humidity": round(data["RH2M"][d], 1),
                "rainfall": round(data.get("PRECTOTCORR", {}).get(d, 0), 1)
            })
        return forecast[-1], forecast
    except Exception:
        today = datetime.today().strftime("%Y-%m-%d")
        return ({"date": today, "temperature": 25, "humidity": 70, "rainfall": 100}, [])

# -------------------------
# MANDI PRICE
# -------------------------
def get_mandi_price(crop, state="Punjab", api_key="YOUR_API_KEY"):
    try:
        url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": 5,
            "filters[state]": state,
            "filters[commodity]": crop.capitalize()
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        records = r.json().get("records", [])
        if records:
            val = records[0].get("modal_price") or records[0].get("min_price") or records[0].get("max_price")
            return int(val) if val else None
    except Exception:
        pass
    fallback = {"Rice": 1900, "Wheat": 2000, "Maize": 1800, "Cotton": 6200, "Pulses": 6000}
    return fallback.get(crop.capitalize(), 1500)

# -------------------------
# CROP RECOMMENDATION
# -------------------------
def crop_recommendation(N, P, K, temp, humidity, ph, rainfall):
    if ph < 6.0:
        return "Rice"
    if N > 100 and 6.0 <= ph <= 7.5:
        return "Wheat"
    if rainfall > 120:
        return "Maize"
    if temp > 30 and K > 50:
        return "Cotton"
    return "Pulses"

# -------------------------
# TRANSLATION
# -------------------------
translator = Translator()
def translate_text(text, dest="pa"):
    try:
        return translator.translate(text, dest=dest).text
    except Exception:
        return text

# -------------------------
# CHATBOT
# -------------------------
IRR_KEYS = ["irrigate", "water", "watering", "irrigation", "ਸਿੰਚਾਈ", "ਪਾਣੀ"]
PRICE_KEYS = ["price", "rate", "mandi", "ਭਾਅ", "ਦਾਮ"]
WEATHER_KEYS = ["weather", "rain", "forecast", "temperature", "humidity", "ਮੌਸਮ", "ਮੀਹ", "ਤਾਪਮਾਨ", "ਨਮੀ"]
SOIL_KEYS = ["soil", "fertilizer", "nutrient", "ph", "ਮਿੱਟੀ", "ਖਾਦ", "ਪੋਸ਼ਕ"]

def detect_intent(q: str):
    qlow = q.lower()
    if any(k in qlow for k in IRR_KEYS): return "irrigation"
    if any(k in qlow for k in PRICE_KEYS): return "price"
    if any(k in qlow for k in WEATHER_KEYS): return "weather"
    if any(k in qlow for k in SOIL_KEYS): return "soil"
    return "unknown"

def irrigation_advice(crop, forecast, lang="en"):
    if not forecast:
        return "No forecast data available." if lang=="en" else "ਕੋਈ ਮੌਸਮ ਡਾਟਾ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।"
    rain_next3 = sum(d["rainfall"] for d in forecast[-3:])
    latest = forecast[-1]
    if rain_next3 > 15:
        return (f"Rain expected (~{rain_next3} mm). Delay irrigation for {crop}."
                if lang=="en" else f"ਅਗਲੇ ਦਿਨਾਂ ਵਿੱਚ ਮੀਂਹ (~{rain_next3} mm)। {crop} ਦੀ ਸਿੰਚਾਈ ਰੋਕੋ।")
    if latest["temperature"] > 32 and latest["humidity"] < 50:
        return ("High temp & low humidity. Irrigate {crop} in 1–2 days."
                if lang=="en" else f"ਤਾਪਮਾਨ ਜ਼ਿਆਦਾ ਤੇ ਨਮੀ ਘੱਟ। {crop} ਦੀ 1–2 ਦਿਨਾਂ ਵਿੱਚ ਸਿੰਚਾਈ ਕਰੋ।")
    return "Soil moisture OK. Irrigate every 7–10 days." if lang=="en" else "ਮਿੱਟੀ ਦੀ ਨਮੀ ਠੀਕ ਹੈ। 7–10 ਦਿਨਾਂ 'ਚ ਸਿੰਚਾਈ ਕਰੋ।"

def nutrient_advice(N, P, K, pH, lang="en"):
    return (f"N={N}, P={P}, K={K}, pH={pH} → adjust fertilizers as needed."
            if lang=="en" else f"N={N}, P={P}, K={K}, pH={pH} → ਲੋੜ ਅਨੁਸਾਰ ਖਾਦ ਵਰਤੋਂ।")

# -------------------------
# VOICE SUPPORT
# -------------------------
def speech_to_text(audio_file, lang="en-IN"):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data, language=lang)
    except Exception as e:
        return f"Speech recognition failed: {e}"

def text_to_speech(text, lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        filename = "reply.mp3"
        tts.save(filename)
        return filename
    except Exception:
        return None

# -------------------------
# FASTAPI APP + CORS
# -------------------------
app = FastAPI()

# CORS: allow React dev server (both localhost and 127.0.0.1 on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],   # includes handling of OPTIONS preflight
    allow_headers=["*"],   # allow Content-Type, Authorization, etc.
)

# -------------------------
# MODELS
# -------------------------
class User(BaseModel):
    username: str
    password: str
    pref_lang: str = "en"

class CropInput(BaseModel):
    N: float
    P: float
    K: float
    temp: float
    humidity: float
    ph: float
    rainfall: float

class ChatInput(BaseModel):
    query: str
    district: str
    crop: str
    N: float = 50
    P: float = 50
    K: float = 50
    ph: float = 6.5
    lang: str = "en"

# -------------------------
# ROUTES
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/signup")
def signup(user: User):
    return {"success": signup_user(user.username, user.password, user.pref_lang)}

@app.post("/login")
def login(user: User):
    return {"success": login_user(user.username, user.password)}

@app.get("/weather")
def weather(district: str):
    latest, forecast = fetch_weather(district)
    return {"latest": latest, "forecast": forecast}

@app.get("/mandi-price")
def mandi(crop: str, state: str = "Punjab"):
    return {"price": get_mandi_price(crop, state)}

@app.post("/recommend-crop")
def recommend(inputs: CropInput):
    crop = crop_recommendation(inputs.N, inputs.P, inputs.K,
                               inputs.temp, inputs.humidity,
                               inputs.ph, inputs.rainfall)
    return {"crop": crop}

@app.post("/chatbot")
def chatbot(chat: ChatInput):
    intent = detect_intent(chat.query)
    if intent == "irrigation":
        _, forecast = fetch_weather(chat.district)
        reply = irrigation_advice(chat.crop, forecast, lang=chat.lang)
    elif intent == "price":
        price = get_mandi_price(chat.crop)
        reply = f"Current mandi price for {chat.crop}: ₹{price}"
    elif intent == "weather":
        latest, _ = fetch_weather(chat.district)
        reply = f"{latest['temperature']}°C, {latest['humidity']}% humidity, {latest['rainfall']} mm rain"
    elif intent == "soil":
        reply = nutrient_advice(chat.N, chat.P, chat.K, chat.ph, lang=chat.lang)
    else:
        reply = "I’m still learning. Ask about irrigation, soil, weather, or mandi prices."

    audio_file = text_to_speech(reply, lang="en" if chat.lang=="en" else "pa")
    return {"reply": reply, "audio_url": f"/audio/{audio_file}" if audio_file else None}

@app.post("/voice-query")
async def voice_query(file: UploadFile = File(...), district: str = "Ludhiana", crop: str = "Wheat", lang: str = "en"):
    audio_path = f"temp_{file.filename}"
    with open(audio_path, "wb") as f:
        f.write(await file.read())

    try:
        query_text = speech_to_text(audio_path, lang="en-IN" if lang=="en" else "pa-IN")
        intent = detect_intent(query_text or "")
        if intent == "irrigation":
            _, forecast = fetch_weather(district)
            reply_text = irrigation_advice(crop, forecast, lang=lang)
        elif intent == "price":
            price = get_mandi_price(crop)
            reply_text = f"Current mandi price for {crop}: ₹{price}"
        elif intent == "weather":
            latest, _ = fetch_weather(district)
            reply_text = f"{latest['temperature']}°C, {latest['humidity']}% humidity, {latest['rainfall']} mm rain"
        elif intent == "soil":
            reply_text = nutrient_advice(50, 50, 50, 6.5, lang=lang)
        else:
            reply_text = "I’m still learning. Ask about irrigation, soil, weather, or mandi prices."

        audio_file = text_to_speech(reply_text, lang="en" if lang=="en" else "pa")
        return {
            "query_text": query_text,
            "reply_text": reply_text,
            "audio_url": f"/audio/{audio_file}" if audio_file else None
        }
    finally:
        # Cleanup temp audio file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass

@app.get("/audio/{filename}")
def get_audio(filename: str):
    if os.path.exists(filename):
        return FileResponse(filename, media_type="audio/mpeg")
    return {"error": "File not found"}
