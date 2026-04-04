from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel, Field
import sys
import os
import joblib
import numpy as np
import sqlite3
import math

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# ---------------- JWT IMPORTS ----------------
from auth.jwt_handler import create_access_token, verify_token
def user_key_func(request: Request):
    auth = request.headers.get("Authorization")

    if auth and "Bearer " in auth:
        try:
            token = auth.split(" ")[1]
            payload = verify_token(token)
            return payload.get("sub")
        except:
            pass

    return get_remote_address(request)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.password_handler import hash_password, verify_password
from fastapi.security import HTTPBearer

# ✅ ADD THIS (NEW)
from pydantic import BaseModel

class CaloriesInput(BaseModel):
    age: int = Field(..., ge=10, le=100)
    height: float = Field(..., gt=50, lt=250)
    weight: float = Field(..., gt=20, lt=300)
    duration: float = Field(..., gt=1, lt=300)
    heart_rate: float = Field(..., gt=40, lt=220)
    body_temp: float = Field(..., gt=30, lt=45)
    

class BioAgeInput(BaseModel):
    gender: int = Field(..., ge=0, le=1)
    body_fat: float = Field(..., ge=1, le=60)
    diastolic: float = Field(..., ge=40, le=120)
    systolic: float = Field(..., ge=80, le=200)
    grip_force: float = Field(..., ge=1, le=100)
    flexibility: float = Field(..., ge=0, le=100)
    situps: int = Field(..., ge=0, le=200)
    broad_jump: float = Field(..., ge=0, le=300)


app = FastAPI()

# ---------------- DB INIT ----------------
from database import create_table
create_table()

limiter = Limiter(key_func=user_key_func)
app.state.limiter = limiter
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

# ---------------- JWT SECURITY ----------------
security = HTTPBearer()

def get_current_user(token=Depends(security)):
    try:
        payload = verify_token(token.credentials)
        
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return payload

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
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
@limiter.limit("3/minute")
def register(request: Request, username: str, password: str):
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
@limiter.limit("5/minute")
def login(request: Request, username: str, password: str):
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

@app.post("/predict_calories")
@limiter.limit("10/minute")  
@limiter.limit("50/minute", key_func=user_key_func)
@limiter.limit("500/day", key_func=user_key_func)
def predict_calories(
    request: Request,
    data: CaloriesInput,

    user=Depends(get_current_user)
):
    

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

@app.post("/predict_bio_age")
@limiter.limit("10/minute")  
@limiter.limit("50/minute", key_func=user_key_func)
@limiter.limit("500/day", key_func=user_key_func)
def predict_bio_age(
    request: Request,
    data: BioAgeInput,

    user=Depends(get_current_user)
):
    

    if bio_age_model is None:
        raise HTTPException(status_code=500, detail="Bio age model not loaded")

    try:
        features = np.array([
        data.gender,
        data.body_fat,
        data.diastolic,
        data.systolic,
        data.grip_force,
        data.flexibility,   # ✅ KEEP THIS
        data.situps,
        data.broad_jump
    ]).reshape(1, -1)
        prediction = bio_age_model.predict(features)[0]

       # 🔥 remove model's flexibility bias
        prediction = prediction - (data.flexibility * 0.08)

        # 🔥 BASE LIFT (IMPORTANT)
        bio_age = (prediction * 1.02) + 2.5   # 🔥 increased

        # FAT
        fat_correction = (data.body_fat - 20) * 1.7
        bio_age += fat_correction

        # BP
        bp_score = (data.systolic - 120) * 0.045 + (data.diastolic - 80) * 0.03
        bio_age += bp_score

        # 🔥 SATURATED FITNESS
        situp_effect = math.log1p(data.situps) * 0.9
        jump_effect = data.broad_jump * 0.013

        fitness_score = situp_effect + jump_effect
        fitness_correction = min(fitness_score, 2.5)
        bio_age -= fitness_correction

        # GRIP (keep same)
        grip_correction = min(data.grip_force * 0.014, 2.5)
        bio_age -= grip_correction

        # 🔥 MID RANGE BOOST (keep)
        if 30 < bio_age < 50:
            bio_age += 3

        # 🔁 LOW-END CONTROL
        if bio_age < 25:
            bio_age += (25 - bio_age) * 0.6

        # 🔥 LOW PERFORMANCE PENALTY (keep)
        low_penalty = 0

        if data.situps < 45:
            low_penalty += (45 - data.situps) * 0.09

        if data.broad_jump < 130:
            low_penalty += (130 - data.broad_jump) * 0.06

        if data.flexibility < 28:
            low_penalty += (28 - data.flexibility) * 0.08

        if data.grip_force < 50:
            low_penalty += (50 - data.grip_force) * 0.05

        bio_age += low_penalty

        # FLEXIBILITY (keep perfect)
        flex_correction = (data.flexibility ** 1.15) * 0.16
        bio_age -= flex_correction
        # 🔥 HIGH-END COMPRESSION (VERY IMPORTANT)
        # 🔥 FINAL HIGH-END COMPRESSION
        if bio_age > 45:
            bio_age = 45 + (bio_age - 45) * 0.45# compress growth

        # 🔥 MID-RANGE BOOST (small correction)
        if 30 < bio_age < 40:
            bio_age += 1.5

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