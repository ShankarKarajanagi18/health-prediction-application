def test_create_stores_record_with_ai_remarks(client, ai_calls, valid_payload):
    response = client.post("/api/patients", json=valid_payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["remarks"].startswith("Stub remarks")
    assert body["date_of_birth"] == "14/03/1985"
    assert len(ai_calls) == 1


def test_invalid_record_is_not_saved_and_ai_not_called(client, ai_calls, valid_payload):
    response = client.post("/api/patients", json={**valid_payload, "email": "nope"})
    assert response.status_code == 422
    assert "email" in response.get_json()["errors"]
    assert client.get("/api/patients").get_json() == []
    assert ai_calls == []


def test_duplicate_email_rejected(client, ai_calls, valid_payload):
    client.post("/api/patients", json=valid_payload)
    response = client.post("/api/patients", json={**valid_payload, "full_name": "Someone Else"})
    assert response.status_code == 409
    assert "already registered" in response.get_json()["errors"]["email"]


def test_duplicate_name_and_dob_rejected(client, ai_calls, valid_payload):
    client.post("/api/patients", json=valid_payload)
    response = client.post(
        "/api/patients", json={**valid_payload, "email": "other@example.com"}
    )
    assert response.status_code == 409
    assert "full_name" in response.get_json()["errors"]


def test_record_saved_when_ai_is_down(client, ai_down, valid_payload):
    response = client.post("/api/patients", json=valid_payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["remarks"] is None
    assert "timed out" in body["warning"]


def test_regenerate_remarks_reports_failure(client, ai_down, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    assert client.post(f"/api/patients/{patient_id}/remarks").status_code == 502


def test_regenerate_remarks_succeeds_when_ai_returns(client, ai_calls, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    response = client.post(f"/api/patients/{patient_id}/remarks")
    assert response.status_code == 200
    assert response.get_json()["remarks"].startswith("Stub remarks")


def test_edit_email_keeps_remarks_and_skips_ai(client, ai_calls, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    response = client.put(
        f"/api/patients/{patient_id}", json={**valid_payload, "email": "new@example.com"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["email"] == "new@example.com"
    assert body["remarks"].startswith("Stub remarks")
    assert len(ai_calls) == 1


def test_edit_lab_value_regenerates_remarks(client, ai_calls, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    client.put(f"/api/patients/{patient_id}", json={**valid_payload, "glucose": "240"})
    assert len(ai_calls) == 2
    assert ai_calls[-1][0] == 240.0


def test_edit_to_existing_email_rejected(client, ai_calls, valid_payload):
    client.post("/api/patients", json=valid_payload)
    other = {**valid_payload, "full_name": "Ravi Menon", "email": "ravi@example.com"}
    other_id = client.post("/api/patients", json=other).get_json()["id"]
    response = client.put(
        f"/api/patients/{other_id}", json={**other, "email": valid_payload["email"]}
    )
    assert response.status_code == 409


def test_edit_keeping_own_email_is_allowed(client, ai_calls, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    response = client.put(f"/api/patients/{patient_id}", json=valid_payload)
    assert response.status_code == 200


def test_delete_then_missing(client, ai_calls, valid_payload):
    patient_id = client.post("/api/patients", json=valid_payload).get_json()["id"]
    assert client.delete(f"/api/patients/{patient_id}").status_code == 204
    assert client.get(f"/api/patients/{patient_id}").status_code == 404
    assert client.delete(f"/api/patients/{patient_id}").status_code == 404


def test_unknown_record_update_returns_404(client, valid_payload):
    assert client.put("/api/patients/999", json=valid_payload).status_code == 404


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Patient Health Records" in response.data
