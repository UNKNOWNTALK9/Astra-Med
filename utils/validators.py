import re
from datetime import datetime

from config import BLOOD_GROUPS


class ValidationError(ValueError):
    pass


def required(value, label):
    v = (value or "").strip()
    if not v:
        raise ValidationError(f"{label} is required.")
    return v


def validate_age(value, lo=18, hi=75):
    try:
        n = int(str(value).strip())
    except ValueError:
        raise ValidationError("Age must be a whole number.")
    if not lo <= n <= hi:
        raise ValidationError(f"Age must be between {lo} and {hi}.")
    return n


def validate_date(value, label="Date", allow_blank=False):
    v = (value or "").strip()
    if not v and allow_blank:
        return ""
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{label} must be in YYYY-MM-DD format.")


def validate_phone(value, allow_blank=True):
    v = (value or "").strip()
    if not v and allow_blank:
        return ""
    if not re.fullmatch(r"\+?[0-9][0-9 \-()]{6,19}", v):
        raise ValidationError("Phone number looks invalid (digits, spaces, - ( ) and optional +).")
    return v


def validate_blood_group(value):
    v = (value or "").strip()
    if v not in BLOOD_GROUPS:
        raise ValidationError("Unknown blood group.")
    return v


def validate_username(value):
    v = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", v):
        raise ValidationError("Username: 3-32 chars, letters, digits, . _ - only.")
    return v


def validate_password(value):
    v = value or ""
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValidationError("Password needs at least 8 characters, including a letter and a digit.")
    return v


def validate_float(value, label, lo=None, hi=None):
    try:
        f = float(str(value).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a number.")
    if (lo is not None and f < lo) or (hi is not None and f > hi):
        raise ValidationError(f"{label} must be between {lo} and {hi}.")
    return f
