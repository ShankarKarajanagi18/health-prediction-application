"""Input validation for patient records.

validate_patient() never raises; it returns the cleaned values together with a
dict of {field: message} so the API can report every problem in one response.
"""
import math
import re
from datetime import date, datetime

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$"
)
DATE_RE = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")

MIN_BIRTH_YEAR = 1900

# Plausible physiological limits, used only to catch typing mistakes.
LAB_LIMITS = {
    "glucose": ("Glucose", "mg/dL", 20, 600),
    "haemoglobin": ("Haemoglobin", "g/dL", 3, 25),
    "cholesterol": ("Cholesterol", "mg/dL", 50, 600),
}


def parse_dob(value):
    """Return (date, None) or (None, error message)."""
    match = DATE_RE.match(value)
    if not match:
        return None, "Use the format dd/mm/yyyy."
    day, month, year = (int(g) for g in match.groups())
    try:
        dob = date(year, month, day)
    except ValueError:
        return None, f"{value} is not a real calendar date."
    if dob > date.today():
        return None, "Date of birth cannot be in the future."
    if year < MIN_BIRTH_YEAR:
        return None, f"Year must be {MIN_BIRTH_YEAR} or later."
    return dob, None


def parse_lab_value(field, raw):
    label, unit, low, high = LAB_LIMITS[field]
    try:
        number = float(str(raw).strip())
    except ValueError:
        return None, f"{label} must be a number."
    if math.isnan(number) or math.isinf(number):
        return None, f"{label} must be a number."
    if not low <= number <= high:
        return None, f"{label} must be between {low} and {high} {unit}."
    return number, None


def validate_patient(payload):
    """Validate a request payload.

    Returns (clean, errors). `clean` only holds fields that passed.
    """
    clean, errors = {}, {}
    payload = payload or {}

    def text(field):
        value = payload.get(field)
        return "" if value is None else str(value).strip()

    name = " ".join(text("full_name").split())
    if not name:
        errors["full_name"] = "Full name is required."
    elif not NAME_RE.match(name):
        errors["full_name"] = "Use letters, spaces, hyphens or apostrophes only (2-100 characters)."
    else:
        clean["full_name"] = name

    dob_text = text("date_of_birth")
    if not dob_text:
        errors["date_of_birth"] = "Date of birth is required."
    else:
        dob, problem = parse_dob(dob_text)
        if problem:
            errors["date_of_birth"] = problem
        else:
            clean["date_of_birth"] = dob

    email = text("email").lower()
    if not email:
        errors["email"] = "Email address is required."
    elif len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address, e.g. name@example.com."
    else:
        clean["email"] = email

    for field, (label, *_rest) in LAB_LIMITS.items():
        raw = text(field)
        if not raw:
            errors[field] = f"{label} is required."
            continue
        number, problem = parse_lab_value(field, raw)
        if problem:
            errors[field] = problem
        else:
            clean[field] = number

    return clean, errors


def format_dob(dob):
    return dob.strftime("%d/%m/%Y")


def age_on(dob, today=None):
    today = today or datetime.now().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
