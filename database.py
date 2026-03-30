import sqlite3

def create_connection():
    return sqlite3.connect("fitness.db")

def create_table():
    conn = create_connection()
    cursor = conn.cursor()

    # fitness data table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fitness_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        age REAL,
        height REAL,
        weight REAL,
        duration REAL,
        heart_rate REAL,
        body_temp REAL,
        gender REAL,
        body_fat REAL,
        diastolic REAL,
        systolic REAL,
        grip REAL,
        flexibility REAL,
        situps REAL,
        jump REAL,
        calories REAL,
        bio_age REAL
    )
    """)

    # users table (for JWT authentication)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

def insert_data(age, height, weight, calories, bio_age):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO fitness_data (age, height, weight, calories, bio_age)
    VALUES (?, ?, ?, ?, ?)
    """, (age, height, weight, calories, bio_age))

    conn.commit()
    conn.close()

def insert_data_full(age, height, weight, duration, heart_rate, body_temp,
                     gender, body_fat, diastolic, systolic, grip,
                     flexibility, situps, jump,
                     calories, bio_age):

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO fitness_data VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        age, height, weight, duration, heart_rate, body_temp,
        gender, body_fat, diastolic, systolic, grip,
        flexibility, situps, jump,
        calories, bio_age
    ))

    conn.commit()
    conn.close()