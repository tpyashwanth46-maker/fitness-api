from fastapi import FastAPI, HTTPException, Header
import sys
import os
import joblib
import numpy as np

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

# ---------------- API KEY ----------------
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY is not set in environment variables")

def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
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
    age: int,
    height: float,
    weight: float,
    duration: float,
    heart_rate: float,
    body_temp: float,
    x_api_key: str = Header(None)
):
    verify_api_key(x_api_key)

    if calories_model is None:
        raise HTTPException(status_code=500, detail="Calories model not loaded")

    try:
        BMI = weight / ((height / 100) ** 2)

        features = np.array([[age, height, weight, duration, heart_rate, body_temp, BMI]])

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
    age: int,
    gender: int,
    body_fat: float,
    diastolic: float,
    systolic: float,
    grip_force: float,
    flexibility: float,
    situps: int,
    broad_jump: float,
    x_api_key: str = Header(None)
):
    verify_api_key(x_api_key)

    if bio_age_model is None:
        raise HTTPException(status_code=500, detail="Bio age model not loaded")

    try:
        features = np.array([[
            age,
            gender,
            body_fat,
            diastolic,
            systolic,
            grip_force,
            flexibility,
            situps,
            broad_jump
        ]])

        prediction = bio_age_model.predict(features)

        return {
            "biological_age": float(prediction[0]),
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))