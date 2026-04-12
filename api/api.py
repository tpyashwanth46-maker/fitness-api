from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel, Field
import sys
import os
import joblib
import numpy as np
from sqlalchemy.exc import IntegrityError
import math
import logging
import smtplib
from email.mime.text import MIMEText
from db import SessionLocal
from sqlalchemy import text
from datetime import datetime, timedelta
from datetime import datetime






def send_otp_email(to_email, otp):
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASS")

    if not email_user or not email_pass:
        print("Email credentials not set")
        return

    msg = MIMEText(f"Your OTP is {otp}")
    msg["Subject"] = "OTP Verification"
    msg["From"] = email_user
    msg["To"] = to_email

    try:
        print("DEBUG OTP:", otp)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        server.login(email_user, email_pass)

        server.send_message(msg)
        server.quit()

        print(f"OTP sent to {to_email}")

    except Exception as e:
        print("Email sending failed:", e)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),   # file
        logging.StreamHandler()           # console (IMPORTANT)
    ]
)

logger = logging.getLogger(__name__)

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
logger.info("API started")
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import RedirectResponse

@app.middleware("http")
async def enforce_https(request: Request, call_next):
    # ✅ allow localhost
    if request.url.hostname in ["127.0.0.1", "localhost"]:
        return await call_next(request)

    # 🔒 enforce HTTPS only in production
    if request.url.scheme == "http":
        url = request.url.replace(scheme="https")
        return RedirectResponse(url)

    return await call_next(request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DB INIT ----------------


limiter = Limiter(key_func=user_key_func)
app.state.limiter = limiter
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    logger.warning("Rate limit exceeded")
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
        logger.error("Invalid token")
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
    logger.info("Models loaded successfully")

except Exception as e:

    logger.error(f"Model loading error: {e}")
    calories_model = None
    bio_age_model = None


# ---------------- AUTH ROUTES ----------------

import random
import time

@app.post("/register")
@limiter.limit("3/minute")
@limiter.limit("10/hour")
@limiter.limit("20/day")
def register(request: Request, username: str, password: str, email: str):
    logger.info(f"Register attempt: {username}")


    db = SessionLocal()

    try:
        hashed_pw = hash_password(password)

        # 🔥 generate OTP
        otp = str(random.randint(100000, 999999))
        otp_expiry = datetime.utcnow() + timedelta(minutes=5)  # 5 minutes

        db.execute(
            text("INSERT INTO users (username, password, email, is_verified, otp, otp_expiry) VALUES (:u, :p, :e, :v, :o, :oe)"),
            {"u": username, "p": hashed_pw, "e": email, "v": False, "o": otp, "oe": otp_expiry}
        )
        db.commit()

        # 🔥 for testing (check app.log)
        
        send_otp_email(email, otp)
        return {"message": "User created. Please verify OTP."}

    except IntegrityError:
        db.rollback()
        return {"error": "Username already exists"}

    except Exception as e:

        logger.error(f"Register error: {e}")
        return {"error": "Registration failed"}

    finally:
        db.close()
import time

@app.post("/verify")
def verify(username: str, otp: str):
    db = SessionLocal()

    result = db.execute(
        text("SELECT otp, otp_expiry, is_verified FROM users WHERE username=:u"),
        {"u": username}
    )
    user = result.fetchone()

    if user is None:
        db.close()
        return {"error": "User not found"}

    stored_otp = user[0]
    otp_expiry = user[1]
    is_verified = user[2]

    # already verified
    if is_verified == 1:
        db.close()
        return {"message": "Account already verified"}

    # check expiry
    if datetime.utcnow() > otp_expiry:
        db.close()
        return {"error": "OTP expired"}

    # check OTP match
    if otp != stored_otp:
        db.close()
        return {"error": "Invalid OTP"}

    # ✅ success → verify account
    db.execute(
        text("UPDATE users SET is_verified = TRUE, otp = NULL, otp_expiry = NULL WHERE username = :u"),
        {"u": username}
    )
    db.commit()
    db.close()

    return {"message": "Account verified successfully"}

@app.post("/login")
@limiter.limit("5/minute")
@limiter.limit("20/hour")
@limiter.limit("100/day")
def login(request: Request, username: str, password: str):
    logger.info(f"Login attempt: {username}")

    db = SessionLocal()

    result = db.execute(
        text("SELECT * FROM users WHERE username=:u"),
        {"u": username}
    )
    user = result.fetchone()
    # user[4] = is_verified
    if user is None:
        logger.warning("User not found")
        db.close()
        raise HTTPException(status_code=404, detail="User not found")

    if not user[4]:
        db.close()
        raise HTTPException(status_code=403, detail="Please verify your account using OTP")
   
    
    import time
    current_time = time.time()

    # user[4] = is_verified
    # user[7] = failed_attempts
    # user[8] = lock_until
    if user[8] is not None and current_time < user[8]:
        db.close()
        raise HTTPException(status_code=403, detail="Account is locked. Try later.")

    # ❌ Wrong password
    if not verify_password(password, user[2]):
        failed_attempts = user[7] + 1

        logger.warning(f"Wrong password attempt for user: {username}, attempt: {failed_attempts}")

        if failed_attempts >= 5:
            lock_until = time.time() + 600  # 10 minutes

            db.execute(
                text("UPDATE users SET failed_attempts = :fa, lock_until = :lu WHERE username = :u"),
                {"fa": failed_attempts, "lu": lock_until, "u": username}
            )
            db.commit()
            db.close()

            logger.error(f"Account locked for user: {username}")

            raise HTTPException(status_code=403, detail="Account locked for 10 minutes")

        else:
            db.execute(
                text("UPDATE users SET failed_attempts = :fa WHERE username = :u"),
                {"fa": failed_attempts, "u": username}
            )
            db.commit()
            db.close()
        

            return {"error": f"Wrong password. Attempts left: {5 - failed_attempts}"}

    # ✅ Correct password
    token = create_access_token({"sub": username})

    db.execute(
        text("UPDATE users SET failed_attempts = 0, lock_until = NULL WHERE username = :u"),
        {"u": username}
    )
    db.commit()
    db.close()

    logger.info(f"Login success: {username}")

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
    logger.info(f"Calories API called by {user}")

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
        logger.error(f"Calories prediction error: {e}")
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
    
    logger.info(f"Bio age API called by {user}")
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
        logger.error(f"Bio age prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))