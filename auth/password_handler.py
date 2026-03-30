print("🔥 USING NEW PASSWORD HANDLER SHA256 VERSION")
from passlib.context import CryptContext
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    # First hash using SHA256 (no limit)
    hashed = hashlib.sha256(password.encode()).hexdigest()
    # Then apply bcrypt
    return pwd_context.hash(hashed)

def verify_password(plain_password: str, hashed_password: str):
    hashed = hashlib.sha256(plain_password.encode()).hexdigest()
    return pwd_context.verify(hashed, hashed_password)