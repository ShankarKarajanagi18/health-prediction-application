import pytest

from app import create_app, routes
from app.ai_service import AIServiceError


@pytest.fixture
def ai_calls(monkeypatch):
    """Replace the external AI call with a stub and record how often it runs."""
    calls = []

    def fake_generate(dob, glucose, haemoglobin, cholesterol, **_kwargs):
        calls.append((glucose, haemoglobin, cholesterol))
        return "Stub remarks. Not a diagnosis - please consult a doctor."

    monkeypatch.setattr(routes, "generate_remarks", fake_generate)
    return calls


@pytest.fixture
def ai_down(monkeypatch):
    def failing(*_args, **_kwargs):
        raise AIServiceError("The AI service timed out. Try again in a moment.")

    monkeypatch.setattr(routes, "generate_remarks", failing)


@pytest.fixture
def client(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    return app.test_client()


@pytest.fixture
def valid_payload():
    return {
        "full_name": "Anita Rao",
        "date_of_birth": "14/03/1985",
        "email": "anita.rao@example.com",
        "glucose": "95",
        "haemoglobin": "13.2",
        "cholesterol": "180",
    }
