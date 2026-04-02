from fastapi import FastAPI, HTTPException, Header, Depends, Request
import sys
import os
import joblib
import numpy as np
import sqlite3

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# ---------------- JWT IMPORTS ----------------
from auth.jwt_handler import create_access_token, verify_token

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.password_handler import hash_password, verify_password
from fastapi.security import HTTPBearer

# ✅ ADD THIS (NEW)
from pydantic import BaseModel

class CaloriesInput(BaseModel):
    age: int
    height: float
    weight: float
    duration: float
    heart_rate: float
    body_temp: float

class BioAgeInput(BaseModel):
    gender: int
    body_fat: float
    diastolic: float
    systolic: float
    grip_force: float
    flexibility: float
    situps: int
    broad_jump: float


app = FastAPI()

# ---------------- DB INIT ----------------
from database import create_table
create_table()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

# ---------------- JWT SECURITY ----------------
security = HTTPBearer()

def get_current_user(token=Depends(security)):
    payload = verify_token(token.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# ---------------- API KEY ----------------
def verify_api_key(x_api_key: str = Header(None)):
    current_key = os.getenv("API_KEY")

    if x_api_key != current_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

# ---------------- PATH FIX ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# ---------------- LOAD MODELS ----------------
try:
    calories_model_path = os.path.join(BASE_DIR, "models", "calories_model.pkl")
    bio_age_model_path = os.path.join(BASE_DIR, "models", "bio_age_model.pkl")

    if not os.path.exists(calories_model_path):
        raise Exception("Calories model not found")

    if not os.path.exists(bio_age_model_path):
        raise Exception("Bio age model not found")

    calories_model = joblib.load(calories_model_path)
    bio_age_model = joblib.load(bio_age_model_path)

except Exception as e:
    print("Model loading error:", e)
    calories_model = None
    bio_age_model = None


# ---------------- AUTH ROUTES ----------------

@app.post("/register")
def register(username: str, password: str):
    import sqlite3

    conn = sqlite3.connect("fitness.db", check_same_thread=False)
    cursor = conn.cursor()

    try:
        hashed_pw = hash_password(password)

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_pw)
        )
        conn.commit()

        return {"message": "User created successfully"}

    except sqlite3.IntegrityError:
        return {"error": "Username already exists"}

    except Exception as e:
        print("REGISTER ERROR:", e)
        return {"error": "Registration failed"}

    finally:
        conn.close()

@app.post("/login")
def login(username: str, password: str):
    conn = sqlite3.connect("fitness.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    conn.close()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password, user[2]):
        return {"error": "Invalid password"}

    token = create_access_token({"sub": username})

    return {"access_token": token}


# ---------------- HOME ----------------
@app.get("/")
def home():
    return {"message": "Fitness API is running successfully"}


# ---------------- HEALTH CHECK ----------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "calories_model_loaded": calories_model is not None,
        "bio_age_model_loaded": bio_age_model is not None
    }


# ---------------- CALORIES API ----------------
@limiter.limit("10/minute")
@app.post("/predict_calories")

def predict_calories(
    request: Request,
    data: CaloriesInput,
    x_api_key: str = Header(None),
    user=Depends(get_current_user)
):
    verify_api_key(x_api_key)

    if calories_model is None:
        raise HTTPException(status_code=500, detail="Calories model not loaded")

    try:
        BMI = data.weight / ((data.height / 100) ** 2)

        features = np.array([[
            data.age,
            data.height,
            data.weight,
            data.duration,
            data.heart_rate,
            data.body_temp,
            BMI
        ]])

        prediction = calories_model.predict(features)

        return {
            "calories_burned": float(prediction[0]),
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- BIO AGE API ----------------
@limiter.limit("10/minute")
@app.post("/predict_bio_age")
def predict_bio_age(
    request: Request,
    data: BioAgeInput,
    x_api_key: str = Header(None),
    user=Depends(get_current_user)
):
    verify_api_key(x_api_key)

    if bio_age_model is None:
        raise HTTPException(status_code=500, detail="Bio age model not loaded")

    try:
        features = np.array([
        data.gender,
        data.body_fat,
        data.diastolic,
        data.systolic,
        data.grip_force,
        data.situps,
        data.broad_jump
    ]).reshape(1, -1)

        prediction = bio_age_model.predict(features)[0]

        # ---------------- BASE SMOOTHING ----------------
        bio_age = (prediction * 0.85) + (0.15 * 30)

        # FAT
        fat_correction = (data.body_fat - 20) * 1.6
        bio_age += fat_correction

        # BP
        bp_score = (data.systolic - 120) * 0.045 + (data.diastolic - 80) * 0.028
        bio_age += bp_score

        # FITNESS
        fitness_correction = (

            data.situps * 0.018 +
            data.broad_jump * 0.018
        )
        bio_age -= fitness_correction

        # GRIP
        grip_correction = data.grip_force * 0.02
        bio_age -= grip_correction

        # 🔁 SOFT LOW-END CONTROL (MOVE UP)
        if bio_age < 25:
            bio_age += (25 - bio_age) * 0.3


        # FLEXIBILITY (final fix)
        # FLEXIBILITY (aggressive override)
        flex_correction = data.flexibility * 0.1
        bio_age -= flex_correction

        # CLAMP
        bio_age = max(18, min(65, bio_age))

        # ROUND
        bio_age = round(bio_age, 1)

        return {
            "biological_age": float(bio_age),
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))