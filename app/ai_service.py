"""Health-risk remarks from an external AI API (Groq, OpenAI-compatible chat completions).

Only age and the three blood values are sent. Name, email and date of birth
never leave the application.

The model is asked for a small JSON object (risk + follow_up) and the remark is
assembled here, so the length and format do not depend on the model obeying
free-text instructions.
"""
import json
import re

import requests

from .validators import age_on

API_URL = "https://api.groq.com/openai/v1/chat/completions"

DISCLAIMER = "Not a diagnosis - please consult a doctor."

SYSTEM_PROMPT = (
    "You are a clinical decision-support assistant summarising routine blood test results. "
    "Each value is already labelled normal, low, elevated or high, and the abnormal ones are listed for you. "
    "Base your answer ONLY on those labels: never call a value abnormal if it is labelled normal. "
    "Interpretation rules: high or elevated glucose points to diabetes or prediabetes risk; "
    "LOW haemoglobin points to anaemia; HIGH haemoglobin does NOT mean anaemia, it can point to dehydration or "
    "polycythaemia; high or elevated cholesterol points to cardiovascular risk. "
    "'Haemoglobin' is the oxygen-carrying protein in red blood cells and is not HbA1c. "
    "Do not mention tests or history that were not provided. "
    "Respond with a JSON object with exactly two string keys. "
    "\"risk\": ONE sentence (under 35 words) naming the most likely health conditions or risks and the values "
    "behind them. Cover EVERY value in the abnormal list. If there are none, say the risk looks low. "
    "\"follow_up\": ONE sentence (under 20 words) with one follow-up suggestion; do not repeat the risk sentence. "
    "No lists, no numbering, no markdown, no disclaimer."
)


def classify_glucose(value):
    if value < 70:
        return "low"
    if value < 100:
        return "normal"
    if value < 126:
        return "elevated (prediabetes range)"
    return "high (diabetes range)"


def classify_haemoglobin(value):
    if value < 12:
        return "low (anaemia range)"
    if value <= 17.5:
        return "normal"
    return "high"


def classify_cholesterol(value):
    if value < 200:
        return "normal (desirable)"
    if value < 240:
        return "elevated (borderline high)"
    return "high"


class AIServiceError(Exception):
    """Raised when remarks cannot be generated. The message is safe to show to users."""


def error_detail(response):
    """Return the API's own error message (e.g. 'model does not exist'), if it sent one."""
    try:
        return str(response.json()["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return ""


def abnormal_summary(glucose, haemoglobin, cholesterol):
    """Name every value outside its normal range, so none gets left out of the remark."""
    readings = (
        ("glucose", classify_glucose(glucose)),
        ("haemoglobin", classify_haemoglobin(haemoglobin)),
        ("total cholesterol", classify_cholesterol(cholesterol)),
    )
    found = [f"{name} {label}" for name, label in readings if not label.startswith("normal")]
    return "; ".join(found) if found else "none"


def build_prompt(age, glucose, haemoglobin, cholesterol):
    return (
        f"Patient age: {age} years\n"
        f"Glucose: {glucose:g} mg/dL (fasting status unknown) -> {classify_glucose(glucose)}\n"
        f"Haemoglobin: {haemoglobin:g} g/dL -> {classify_haemoglobin(haemoglobin)}\n"
        f"Total cholesterol: {cholesterol:g} mg/dL -> {classify_cholesterol(cholesterol)}\n"
        f"Abnormal values: {abnormal_summary(glucose, haemoglobin, cholesterol)}"
    )


def finalise(text, truncated):
    """Tidy the model output and always end with the disclaimer."""
    text = " ".join(text.replace("*", "").replace("#", "").split())
    if truncated and "." in text:
        text = text[: text.rindex(".") + 1]
    if "not a diagnosis" not in text.lower():
        text = f"{text} {DISCLAIMER}"
    return text


def _as_sentence(value):
    text = " ".join(str(value or "").split())
    if text and text[-1] not in ".!?":
        text += "."
    return text


def first_sentences(text, count=2):
    """Fallback for plain-text replies: drop list numbering and keep the first sentences."""
    text = re.sub(r"(?:(?<=\s)|^)\d+[.)]\s+", "", text)
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:count])


def parse_reply(raw, truncated):
    """Turn the model's reply into the final remark."""
    try:
        data = json.loads(raw)
    except ValueError:
        data = None

    if isinstance(data, dict):
        risk = _as_sentence(first_sentences(str(data.get("risk") or ""), 1))
        if not risk:
            raise AIServiceError("The AI service returned an empty response.")
        follow_up = _as_sentence(first_sentences(str(data.get("follow_up") or ""), 1))
        return finalise(f"{risk} {follow_up}".strip(), False)

    # Model ignored the JSON instruction: keep the first two sentences of whatever it wrote.
    return finalise(first_sentences(raw), truncated)


def generate_remarks(dob, glucose, haemoglobin, cholesterol, *, api_key, model, timeout):
    if not api_key:
        raise AIServiceError("AI API key is not configured. Set GROQ_API_KEY in the .env file.")

    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_prompt(age_on(dob), glucose, haemoglobin, cholesterol),
            },
        ],
    }
    if model.startswith("openai/gpt-oss"):
        # Reasoning models spend part of the token budget on thinking, so keep that small
        # and leave room for the answer.
        body["reasoning_effort"] = "low"
        body["max_completion_tokens"] = 1000
    else:
        body["max_tokens"] = 200
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
    except requests.Timeout:
        raise AIServiceError("The AI service timed out. Try again in a moment.")
    except requests.RequestException:
        raise AIServiceError("Could not reach the AI service. Check your internet connection.")

    if response.status_code == 401:
        raise AIServiceError("The AI API key was rejected. Check GROQ_API_KEY.")
    if response.status_code == 429:
        raise AIServiceError("The AI service is rate limited. Try again shortly.")
    if not response.ok:
        detail = error_detail(response)
        message = f"The AI service returned an error (HTTP {response.status_code})."
        raise AIServiceError(f"{message} {detail}".strip())

    try:
        choice = response.json()["choices"][0]
        text = (choice["message"]["content"] or "").strip()
        truncated = choice.get("finish_reason") == "length"
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError("The AI service returned an unexpected response.")

    if not text:
        raise AIServiceError("The AI service returned an empty response.")
    return parse_reply(text, truncated)