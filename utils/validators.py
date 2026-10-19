"""Input validation used by registration, search, admin forms."""

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\- ]{8,20}$")
FLIGHT_NO_RE = re.compile(r"^[A-Z0-9]{2,10}$")


def valid_email(value):
    return bool(value and EMAIL_RE.match(value.strip()))


def valid_phone(value):
    return bool(value and PHONE_RE.match(value.strip()))


def valid_age(age):
    try:
        n = int(age)
    except (TypeError, ValueError):
        return False
    return 0 <= n <= 120


def valid_password(value):
    return bool(value) and len(value) >= 6


def valid_airport_code(code):
    return bool(code) and 2 <= len(code.strip()) <= 10 and code.strip().isalpha()


def valid_flight_number(value):
    return bool(value) and bool(FLIGHT_NO_RE.match(value.strip().upper()))


def sanitize_reason(text, max_len=255):
    if not text:
        return "Cancelled by passenger"
    return str(text).strip()[:max_len]
