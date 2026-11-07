"""SQLite persistence layer. All SQL lives in this module."""
import sqlite3
from datetime import date

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    glucose       REAL NOT NULL,
    haemoglobin   REAL NOT NULL,
    cholesterol   REAL NOT NULL,
    remarks       TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

COLUMNS = ("full_name", "date_of_birth", "email", "glucose", "haemoglobin", "cholesterol")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    get_db().executescript(SCHEMA)


def _to_dict(row):
    record = dict(row)
    record["date_of_birth"] = date.fromisoformat(record["date_of_birth"]).strftime("%d/%m/%Y")
    return record


def _values(clean):
    return (
        clean["full_name"],
        clean["date_of_birth"].isoformat(),
        clean["email"],
        clean["glucose"],
        clean["haemoglobin"],
        clean["cholesterol"],
    )


def list_patients():
    rows = get_db().execute("SELECT * FROM patients ORDER BY id").fetchall()
    return [_to_dict(r) for r in rows]


def get_patient(patient_id):
    row = get_db().execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return _to_dict(row) if row else None


def find_duplicate(clean, exclude_id=None):
    """Return {'field': ..., 'record': {...}} if another record clashes, else None."""
    db = get_db()
    skip = exclude_id if exclude_id is not None else -1

    row = db.execute(
        "SELECT * FROM patients WHERE email = ? AND id != ?", (clean["email"], skip)
    ).fetchone()
    if row:
        return {"field": "email", "record": _to_dict(row)}

    row = db.execute(
        "SELECT * FROM patients "
        "WHERE lower(full_name) = lower(?) AND date_of_birth = ? AND id != ?",
        (clean["full_name"], clean["date_of_birth"].isoformat(), skip),
    ).fetchone()
    if row:
        return {"field": "full_name", "record": _to_dict(row)}
    return None


def insert_patient(clean):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO patients (full_name, date_of_birth, email, glucose, haemoglobin, cholesterol) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _values(clean),
    )
    db.commit()
    return cursor.lastrowid


def update_patient(patient_id, clean):
    db = get_db()
    db.execute(
        "UPDATE patients SET full_name = ?, date_of_birth = ?, email = ?, glucose = ?, "
        "haemoglobin = ?, cholesterol = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        _values(clean) + (patient_id,),
    )
    db.commit()


def set_remarks(patient_id, remarks):
    db = get_db()
    db.execute(
        "UPDATE patients SET remarks = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (remarks, patient_id),
    )
    db.commit()


def delete_patient(patient_id):
    db = get_db()
    cursor = db.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    db.commit()
    return cursor.rowcount > 0
