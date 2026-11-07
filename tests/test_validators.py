from datetime import date, timedelta

import pytest

from app.validators import age_on, parse_dob, validate_patient


def test_valid_payload_passes(valid_payload):
    clean, errors = validate_patient(valid_payload)
    assert errors == {}
    assert clean["email"] == "anita.rao@example.com"
    assert clean["date_of_birth"] == date(1985, 3, 14)
    assert clean["glucose"] == 95.0


@pytest.mark.parametrize("email", ["hunter@gmail", "Kris.wu.gmail.com", "a@b", "@x.com", "a b@x.com"])
def test_invalid_emails_rejected(valid_payload, email):
    _, errors = validate_patient({**valid_payload, "email": email})
    assert "email" in errors


@pytest.mark.parametrize("text", ["28/01/1960", "28.01.1960", "1/2/2000"])
def test_accepted_date_formats(text):
    dob, problem = parse_dob(text)
    assert problem is None and dob is not None


def test_impossible_date_rejected():
    _, problem = parse_dob("31.11.2001")
    assert "not a real calendar date" in problem


def test_future_date_rejected():
    future = date.today() + timedelta(days=1)
    _, problem = parse_dob(future.strftime("%d/%m/%Y"))
    assert "future" in problem


@pytest.mark.parametrize("text", ["2001-11-30", "30-11-2001", "30/11/01", "abc"])
def test_wrong_date_format_rejected(text):
    _, problem = parse_dob(text)
    assert problem == "Use the format dd/mm/yyyy."


@pytest.mark.parametrize("value", ["abc", "12,5", "nan", "inf", "-5", "0", "9999"])
def test_bad_lab_values_rejected(valid_payload, value):
    _, errors = validate_patient({**valid_payload, "glucose": value})
    assert "glucose" in errors


def test_missing_fields_all_reported():
    _, errors = validate_patient({})
    assert set(errors) == {
        "full_name", "date_of_birth", "email", "glucose", "haemoglobin", "cholesterol"
    }


def test_multiple_errors_reported_together(valid_payload):
    payload = {**valid_payload, "email": "Kris.wu.gmail.com", "date_of_birth": "19.10.2030"}
    _, errors = validate_patient(payload)
    assert set(errors) == {"email", "date_of_birth"}


def test_age_on_birthday_boundary():
    dob = date(2000, 6, 15)
    assert age_on(dob, today=date(2026, 6, 14)) == 25
    assert age_on(dob, today=date(2026, 6, 15)) == 26
