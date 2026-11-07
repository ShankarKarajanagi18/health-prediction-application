"""Runs the ten records from the task sheet exactly as given.

Expected outcome: 6 saved, 4 rejected (3 failed validation, 1 duplicate).
"""
import pytest

TASK_RECORDS = [
    (1, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
    (2, "John Hunter", "10.12.1990", "hunter@gmail", "94", "15", "200"),
    (3, "Darryl Tim", "12.11.1993", "timd@smh.com.au", "240", "18.6", "326"),
    (4, "Peter Larry", "31.11.2001", "Larry@hotmail.com", "88", "11.5", "165"),
    (5, "Sam Kerr", "09.12.2006", "sam@news.com.au", "198", "8.9", "192"),
    (6, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
    (7, "Madison XI", "12.09.1998", "madison@hotmail.com", "85", "7.6", "163"),
    (8, "Kris Wu", "19.10.2030", "Kris.wu.gmail.com", "79", "16.5", "197"),
    (9, "Tenille Singh", "30.11.1991", "Tenille@yahoo.com", "101", "15", "310"),
    (10, "Prem Kumar", "28.04.1990", "prem@telstra.com", "155", "12.5", "265"),
]

EXPECTED = {
    1: (201, None),
    2: (422, {"email"}),
    3: (201, None),
    4: (422, {"date_of_birth"}),
    5: (201, None),
    6: (409, {"email"}),
    7: (201, None),
    8: (422, {"email", "date_of_birth"}),
    9: (201, None),
    10: (201, None),
}


def payload(row):
    _, name, dob, email, glucose, haemoglobin, cholesterol = row
    return {
        "full_name": name,
        "date_of_birth": dob,
        "email": email,
        "glucose": glucose,
        "haemoglobin": haemoglobin,
        "cholesterol": cholesterol,
    }


@pytest.fixture
def loaded(client, ai_calls):
    results = {}
    for row in TASK_RECORDS:
        response = client.post("/api/patients", json=payload(row))
        results[row[0]] = response
    return client, results


@pytest.mark.parametrize("test_no", sorted(EXPECTED))
def test_each_task_record(loaded, test_no):
    _, results = loaded
    status, error_fields = EXPECTED[test_no]
    response = results[test_no]
    assert response.status_code == status
    if error_fields:
        assert set(response.get_json()["errors"]) == error_fields


def test_read_edit_delete_flow(loaded):
    client, _ = loaded
    records = client.get("/api/patients").get_json()
    assert len(records) == 6

    target = next(r for r in records if r["full_name"] == "Sam Kerr")
    edited = client.put(
        f"/api/patients/{target['id']}", json={**payload(TASK_RECORDS[4]), "email": "gokul@infocare.com"}
    )
    assert edited.status_code == 200
    assert edited.get_json()["email"] == "gokul@infocare.com"

    victim = next(r for r in records if r["full_name"] == "Prem Kumar")
    assert client.delete(f"/api/patients/{victim['id']}").status_code == 204

    remaining = client.get("/api/patients").get_json()
    assert len(remaining) == 5
    assert "gokul@infocare.com" in [r["email"] for r in remaining]
