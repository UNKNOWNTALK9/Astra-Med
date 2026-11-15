import hashlib
import hmac
import os
from datetime import datetime, timedelta

from config import PERMISSIONS
from utils.helpers import TS_FMT
from utils.validators import ValidationError, validate_password, validate_username

PBKDF2_ITERATIONS = 200_000
MAX_ATTEMPTS = 5
LOCK_MINUTES = 5


def hash_password(password: str, salt_hex: str | None = None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt_hex)[0], hash_hex)


def can(user, permission: str) -> bool:
    return bool(user) and permission in PERMISSIONS.get(user["role"], set())


class AuthService:
    def __init__(self, db):
        self.db = db

    def login(self, username, password):
        """Return (user_dict | None, message)."""
        user = self.db.get_user(username=(username or "").strip())
        if not user or not user["is_active"]:
            self.db.log("WARNING", "auth", f"Failed login for '{username}'")
            return None, "Invalid username or password."
        if user["locked_until"] and datetime.strptime(user["locked_until"], TS_FMT) > datetime.now():
            return None, f"Account locked after repeated failures. Try again in {LOCK_MINUTES} minutes."
        if not verify_password(password or "", user["password_hash"], user["salt"]):
            fails = user["failed_attempts"] + 1
            lock = None
            if fails >= MAX_ATTEMPTS:
                lock = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime(TS_FMT)
                fails = 0
            self.db.update_user(user["id"], failed_attempts=fails, locked_until=lock)
            self.db.log("WARNING", "auth", f"Failed login for '{username}'", user["id"])
            return None, "Invalid username or password."
        self.db.update_user(user["id"], failed_attempts=0, locked_until=None,
                            last_login=datetime.now().strftime(TS_FMT))
        self.db.log("INFO", "auth", f"User '{user['username']}' logged in", user["id"])
        return self.db.get_user(user_id=user["id"]), "OK"

    def uses_default_password(self, user):
        defaults = {"admin": "admin123", "medic": "medic123"}
        pw = defaults.get(user["username"].lower())
        return bool(pw) and verify_password(pw, user["password_hash"], user["salt"])

    def change_password(self, user, old, new):
        if not verify_password(old or "", user["password_hash"], user["salt"]):
            raise ValidationError("Current password is incorrect.")
        validate_password(new)
        h, s = hash_password(new)
        self.db.update_user(user["id"], password_hash=h, salt=s)
        self.db.log("INFO", "auth", "Password changed", user["id"])

    def create_user(self, acting_user, username, password, role, full_name=""):
        if not can(acting_user, "manage_users"):
            raise PermissionError("Only administrators can manage users.")
        username = validate_username(username)
        validate_password(password)
        if self.db.get_user(username=username):
            raise ValidationError("That username already exists.")
        h, s = hash_password(password)
        uid = self.db.create_user(username=username, password_hash=h, salt=s, role=role, full_name=full_name)
        self.db.log("INFO", "auth", f"User '{username}' created ({role})", acting_user["id"])
        return uid

    def reset_password(self, acting_user, user_id, new_password):
        if not can(acting_user, "manage_users"):
            raise PermissionError("Only administrators can manage users.")
        validate_password(new_password)
        h, s = hash_password(new_password)
        self.db.update_user(user_id, password_hash=h, salt=s, failed_attempts=0, locked_until=None)
        self.db.log("INFO", "auth", f"Password reset for user id {user_id}", acting_user["id"])
