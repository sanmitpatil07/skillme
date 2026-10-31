import hashlib, hmac, os, time
import jwt
from fastapi import Header, HTTPException
from .config import SECRET
from . import db

def hash_pw(pw, salt=None):
    salt = salt or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + h.hex()

def check_pw(pw, stored):
    s, h = stored.split("$")
    return hmac.compare_digest(hash_pw(pw, bytes.fromhex(s)).split("$")[1], h)

def make_token(uid):
    return jwt.encode({"sub": str(uid), "exp": int(time.time()) + 7 * 86400}, SECRET, algorithm="HS256")

def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in.")
    try:
        uid = int(jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired. Please log in again.")
    with db.connect() as c:
        if not c.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
            raise HTTPException(401, "Account not found.")
    return uid
