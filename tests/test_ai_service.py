from datetime import date

import pytest
import requests

from app import ai_service
from app.ai_service import (
    AIServiceError,
    classify_cholesterol,
    classify_glucose,
    classify_haemoglobin,
    finalise,
    generate_remarks,
)

DOB = date(1990, 5, 1)
KWARGS = {"api_key": "test-key", "model": "test-model", "timeout": 5}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def patch_post(monkeypatch, response=None, exc=None):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        if exc:
            raise exc
        return response

    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    return captured


def test_success_returns_text_and_sends_only_clinical_values(monkeypatch):
    reply = FakeResponse(payload={"choices": [{"message": {"content": " *Low risk.* "}}]})
    captured = patch_post(monkeypatch, reply)

    assert generate_remarks(DOB, 95, 13.5, 180, **KWARGS) == (
        "Low risk. Not a diagnosis - please consult a doctor."
    )

    sent = captured["body"]["messages"][1]["content"]
    assert "Glucose: 95 mg/dL (fasting status unknown) -> normal" in sent
    assert "Haemoglobin: 13.5 g/dL -> normal" in sent
    assert "Total cholesterol: 180 mg/dL -> normal (desirable)" in sent
    assert "1990" not in sent and "@" not in sent
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["url"].startswith("https://api.groq.com/")


@pytest.mark.parametrize(
    "value, label",
    [
        (69.9, "low"),
        (70, "normal"),
        (99, "normal"),
        (100, "elevated (prediabetes range)"),
        (125, "elevated (prediabetes range)"),
        (126, "high (diabetes range)"),
    ],
)
def test_classify_glucose_boundaries(value, label):
    assert classify_glucose(value) == label


@pytest.mark.parametrize(
    "value, label",
    [(11.9, "low (anaemia range)"), (12, "normal"), (17.5, "normal"), (17.6, "high")],
)
def test_classify_haemoglobin_boundaries(value, label):
    assert classify_haemoglobin(value) == label


@pytest.mark.parametrize(
    "value, label",
    [
        (199.9, "normal (desirable)"),
        (200, "elevated (borderline high)"),
        (239, "elevated (borderline high)"),
        (240, "high"),
    ],
)
def test_classify_cholesterol_boundaries(value, label):
    assert classify_cholesterol(value) == label


def test_finalise_adds_disclaimer_once_and_strips_markdown():
    assert finalise(" **Low risk**. Not a diagnosis - please consult a doctor. ", False) == (
        "Low risk. Not a diagnosis - please consult a doctor."
    )


def test_finalise_trims_cut_off_sentence():
    assert finalise("Low risk. Follow up with a doctor if symptoms continue", True) == (
        "Low risk. Not a diagnosis - please consult a doctor."
    )


def test_missing_key_raises_without_calling_api(monkeypatch):
    captured = patch_post(monkeypatch, FakeResponse())
    with pytest.raises(AIServiceError, match="not configured"):
        generate_remarks(DOB, 95, 13.5, 180, api_key="", model="m", timeout=5)
    assert captured == {}


@pytest.mark.parametrize(
    "response, message",
    [
        (FakeResponse(401), "rejected"),
        (FakeResponse(429), "rate limited"),
        (FakeResponse(500), "HTTP 500"),
        (FakeResponse(200, {"unexpected": True}), "unexpected response"),
        (FakeResponse(200, {"choices": []}), "unexpected response"),
        (FakeResponse(200, {"choices": [{"message": {"content": "  "}}]}), "empty response"),
    ],
)
def test_api_failures_become_friendly_errors(monkeypatch, response, message):
    patch_post(monkeypatch, response)
    with pytest.raises(AIServiceError, match=message):
        generate_remarks(DOB, 95, 13.5, 180, **KWARGS)


@pytest.mark.parametrize(
    "exc, message",
    [(requests.Timeout(), "timed out"), (requests.ConnectionError(), "Could not reach")],
)
def test_network_failures_become_friendly_errors(monkeypatch, exc, message):
    patch_post(monkeypatch, exc=exc)
    with pytest.raises(AIServiceError, match=message):
        generate_remarks(DOB, 95, 13.5, 180, **KWARGS)
