import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

with engine.connect() as conn:
    # ✅ Create table with ALL required columns
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            otp TEXT,
            otp_expiry TIMESTAMP,
            is_verified BOOLEAN DEFAULT FALSE,
            failed_attempts INTEGER DEFAULT 0,
            lock_until FLOAT
        );
    """))

    # ✅ If table already exists, add missing columns safely
    conn.execute(text("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0;
    """))

    conn.execute(text("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS lock_until FLOAT;
    """))

    conn.commit()