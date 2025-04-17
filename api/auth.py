import secrets
import hashlib

def generate_api_key(length=20):
    return "eh_arc_" + secrets.token_urlsafe(length)

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()
