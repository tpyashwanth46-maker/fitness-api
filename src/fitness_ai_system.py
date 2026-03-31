import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import insert_data_full
import whisper
import sounddevice as sd
import numpy as np
import pandas as pd
import math
import re
import pyttsx3
import time
import os
import requests   # ✅ NEW
# ✅ ADD THIS FUNCTION HERE
def get_token():
    import requests

    BASE_URL = "https://fitness-api-691p.onrender.com"

    username = input("Enter username: ")
    password = input("Enter password: ")

    choice = input("Do you have an account? (yes/no): ")

    # 🔹 Register if new user
    if choice.lower() == "no":
        print("Creating account...")
        reg_response = requests.post(
            f"{BASE_URL}/register",
            params={"username": username, "password": password}
        )
        print("Register Response:", reg_response.json())

    # 🔹 Login
    response = requests.post(
        f"{BASE_URL}/login",
        params={"username": username, "password": password}
    )

    print("Login Status:", response.status_code)
    print("Login Response:", response.text)

    if response.status_code == 200:
        data = response.json()

        if "access_token" in data:
            print("Token received")
            return data["access_token"]
        else:
            print("Token missing:", data)
            return None
    else:
        print("Login failed:", response.text)
        return None
print("Waking up server...")

try:
    requests.get("https://fitness-api-691p.onrender.com", timeout=30)
    print("Server is awake")
except:
    print("Server may be sleeping, continuing...")

print("------ AI FITNESS SYSTEM (WHISPER VOICE ASSISTANT) ------")

# ---------------- SPEECH FUNCTION ----------------

def speak(text):
    print(text)
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate',170)
    engine.setProperty('volume',1.0)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    time.sleep(1.5)

# ---------------- LOAD WHISPER MODEL ----------------

model = whisper.load_model("small")

samplerate = 16000
duration = 6

# ---------------- RECORD VOICE ----------------

def listen():
    try:
        time.sleep(1)
        print("Speak now...")
        audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1)
        sd.wait()
        audio = audio.flatten()

        if np.max(np.abs(audio)) != 0:
            audio = audio / np.max(np.abs(audio))

        audio = audio.astype(np.float32)

        result = model.transcribe(audio, language="en")
        text = result["text"].strip()

        print("You said:", text)
        return text.lower()

    except Exception as e:
        print("Voice error:", e)
        return ""

# ---------------- NUMBER EXTRACTOR ----------------

def extract_number(text):
    if text is None or text.strip() == "":
        return None

    numbers = re.findall(r'\d+\.?\d*', text)

    if numbers:
        if len(numbers) == 1:
            return float(numbers[0])

        total = 0
        for n in numbers:
            total += float(n)
        return total

    word_numbers = {
        "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,
        "six":6,"seven":7,"eight":8,"nine":9,"ten":10,
        "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,
        "fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,
        "nineteen":19,"twenty":20,"thirty":30,"forty":40,
        "fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90
    }

    words = text.split()
    total = 0

    for w in words:
        if w in word_numbers:
            total += word_numbers[w]

    if total > 0:
        return float(total)

    return None

# ---------------- GET NUMBER ----------------

def get_number(prompt):
    attempts = 0

    while attempts < 5:
        speak(prompt)
        speech = listen()
        number = extract_number(speech)

        if number is not None:
            return float(number)

        speak("I could not detect a number. Please repeat.")
        attempts += 1

    speak("Using default value zero")
    return 0

# ---------------- GREETING ----------------

speak("Hello. I am your AI fitness assistant. i was created by yashwanth")
speak("I will analyze your health and fitness.")

# ---------------- USER INPUT ----------------

age = get_number("Please say your age")

speak("Please say your gender. Male or female")

while True:
    gender_text = listen()

    if gender_text.startswith("m"):
        gender = 1
        speak("Male detected")
        break

    elif gender_text.startswith("f"):
        gender = 0
        speak("Female detected")
        break

    else:
        speak("I could not detect gender. Please say male or female")

height = get_number("Please say your height in centimeters")
weight = get_number("Please say your weight in kilograms")
waist = get_number("Please say your waist circumference")
neck = get_number("Please say your neck circumference")

# ---------------- BODY FAT ----------------

if gender == 1:
    diff = max(waist - neck, 1)
    bodyfat = 86.010 * math.log10(diff) - 70.041 * math.log10(height) + 36.76
else:
    hip = get_number("Please say your hip circumference")
    diff = max(waist + hip - neck, 1)
    bodyfat = 163.205 * math.log10(diff) - 97.684 * math.log10(height) - 78.387

bodyfat = round(bodyfat, 2)
speak(f"Estimated body fat percentage is {bodyfat}")

# ---------------- BMI ----------------

bmi = weight / ((height / 100) ** 2)
bmi = round(bmi, 2)

speak(f"Your body mass index is {bmi}")

# ---------------- EXERCISE INPUT ----------------

duration_ex = get_number("Please say your exercise duration in minutes")
heart_rate = get_number("Please say your heart rate")
body_temp = get_number("Please say your body temperature")

# ---------------- 🔥 CALORIES VIA API ----------------
# ---------------- 🔥 CALORIES VIA API ----------------
token = get_token()
print("Calling Calories API...")

try:
    response = requests.post(
        "https://fitness-api-691p.onrender.com/predict_calories",
        params={
            "age": age,
            "height": height,
            "weight": weight,
            "duration": duration_ex,
            "heart_rate": heart_rate,
            "body_temp": body_temp
        },
        headers={
            "x-api-key": "askyashwanth346",
            "Authorization": f"Bearer {token}"
        },
        timeout=30
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

    if response.status_code == 200 and response.text.strip():
        try:
            data = response.json()
            calories_pred = round(data["calories_burned"], 2)
        except:
            print("JSON error in calories response")
            calories_pred = 0
    else:
        calories_pred = 0

except Exception as e:
    print("API Error:", e)
    calories_pred = 0

speak(f"Estimated calories burned during exercise is {calories_pred}")

# ---------------- BIO AGE INPUT ----------------

diastolic = get_number("Please say your diastolic blood pressure")
systolic = get_number("Please say your systolic blood pressure")
grip = get_number("Please say your grip strength")
flexibility = get_number("Please say your sit and bend forward value in centimeters")
situps = get_number("Please say the number of sit ups you can perform")
jump = get_number("Please say your broad jump distance in centimeters")

# ---------------- 🔥 BIO AGE VIA API ----------------

# ---------------- 🔥 BIO AGE VIA API ----------------

print("Calling Bio Age API...")

try:
    response = requests.post(
        "https://fitness-api-691p.onrender.com/predict_bio_age",
        params={
            "age": age,
            "gender": gender,
            "body_fat": bodyfat,
            "diastolic": diastolic,
            "systolic": systolic,
            "grip_force": grip,
            "flexibility": flexibility,
            "situps": situps,
            "broad_jump": jump
        },
        headers={
            "x-api-key": "askyashwanth346",
            "Authorization": f"Bearer {token}"
        },
        timeout=30
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

    if response.status_code == 200 and response.text.strip():
        try:
            data = response.json()
            bio_pred = round(data["biological_age"], 2)
        except:
            print("JSON error in bio age response")
            bio_pred = age
    else:
        bio_pred = age

except Exception as e:
    print("API Error:", e)
    bio_pred = age

# ---------------- FITNESS INTERPRETATION ----------------

if bmi < 18.5:
    bmi_status = "Underweight"
elif bmi < 25:
    bmi_status = "Normal"
elif bmi < 30:
    bmi_status = "Overweight"
else:
    bmi_status = "Obese"

if bodyfat < 10:
    fat_status = "Athletic"
elif bodyfat < 20:
    fat_status = "Fit"
elif bodyfat < 30:
    fat_status = "Average"
else:
    fat_status = "High body fat"

if bio_pred <= age:
    fitness_status = "Your body is younger than your actual age"
else:
    fitness_status = "Your body is aging faster than expected"

# ---------------- FINAL REPORT ----------------
insert_data_full(
    age, height, weight, duration_ex, heart_rate, body_temp,
    gender, bodyfat, diastolic, systolic, grip,
    flexibility, situps, jump,
    calories_pred, bio_pred
)
print("\n------ FITNESS REPORT ------")
print("Actual Age        :", age)
print("Biological Age    :", bio_pred)
print("BMI               :", bmi)
print("BMI Status        :", bmi_status)
print("Body Fat %        :", bodyfat)
print("Body Fat Status   :", fat_status)
print("Calories Burned   :", calories_pred)

speak("Fitness analysis complete")
speak(f"Your biological age is {bio_pred}")
speak(f"Your BMI status is {bmi_status}")
speak(f"Your body fat category is {fat_status}")
speak(f"Estimated calories burned is {calories_pred}")
speak(fitness_status)

print("\nSystem Analysis Complete")