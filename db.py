from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:yash@localhost:5432/fitness_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)