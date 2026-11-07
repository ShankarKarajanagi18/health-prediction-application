from flask import Blueprint, current_app, jsonify, render_template, request

from . import db
from .ai_service import AIServiceError, generate_remarks
from .validators import parse_dob, validate_patient

bp = Blueprint("main", __name__)

LAB_FIELDS = ("glucose", "haemoglobin", "cholesterol")


def _error(message, status, errors=None):
    body = {"message": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status


def _duplicate_errors(clean, exclude_id=None):
    clash = db.find_duplicate(clean, exclude_id)
    if not clash:
        return None
    other = clash["record"]
    if clash["field"] == "email":
        text = f"This email is already registered to {other['full_name']} (record #{other['id']})."
    else:
        text = (
            f"A record for {other['full_name']} with the same date of birth "
            f"already exists (record #{other['id']})."
        )
    return {clash["field"]: text}


def _refresh_remarks(patient_id, clean):
    """Ask the AI API for remarks and store them. Returns a warning string on failure."""
    cfg = current_app.config
    try:
        remarks = generate_remarks(
            clean["date_of_birth"],
            clean["glucose"],
            clean["haemoglobin"],
            clean["cholesterol"],
            api_key=cfg["GROQ_API_KEY"],
            model=cfg["GROQ_MODEL"],
            timeout=cfg["AI_TIMEOUT_SECONDS"],
        )
    except AIServiceError as exc:
        db.set_remarks(patient_id, None)
        return str(exc)
    db.set_remarks(patient_id, remarks)
    return None


def _clean_from_record(record):
    dob, _ = parse_dob(record["date_of_birth"])
    return {
        "date_of_birth": dob,
        **{field: record[field] for field in LAB_FIELDS},
    }


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api/patients")
def list_patients():
    return jsonify(db.list_patients())


@bp.get("/api/patients/<int:patient_id>")
def get_patient(patient_id):
    record = db.get_patient(patient_id)
    if record is None:
        return _error("Record not found.", 404)
    return jsonify(record)


@bp.post("/api/patients")
def create_patient():
    clean, errors = validate_patient(request.get_json(silent=True))
    if errors:
        return _error("Please correct the highlighted fields.", 422, errors)

    duplicate = _duplicate_errors(clean)
    if duplicate:
        return _error("Duplicate record.", 409, duplicate)

    patient_id = db.insert_patient(clean)
    warning = _refresh_remarks(patient_id, clean)

    body = db.get_patient(patient_id)
    if warning:
        body["warning"] = warning
    return jsonify(body), 201


@bp.put("/api/patients/<int:patient_id>")
def update_patient(patient_id):
    existing = db.get_patient(patient_id)
    if existing is None:
        return _error("Record not found.", 404)

    clean, errors = validate_patient(request.get_json(silent=True))
    if errors:
        return _error("Please correct the highlighted fields.", 422, errors)

    duplicate = _duplicate_errors(clean, exclude_id=patient_id)
    if duplicate:
        return _error("Duplicate record.", 409, duplicate)

    previous = _clean_from_record(existing)
    needs_new_remarks = any(
        previous[field] != clean[field] for field in ("date_of_birth", *LAB_FIELDS)
    )

    db.update_patient(patient_id, clean)
    warning = _refresh_remarks(patient_id, clean) if needs_new_remarks else None

    body = db.get_patient(patient_id)
    if warning:
        body["warning"] = warning
    return jsonify(body)


@bp.post("/api/patients/<int:patient_id>/remarks")
def regenerate_remarks(patient_id):
    record = db.get_patient(patient_id)
    if record is None:
        return _error("Record not found.", 404)

    warning = _refresh_remarks(patient_id, _clean_from_record(record))
    if warning:
        return _error(warning, 502)
    return jsonify(db.get_patient(patient_id))


@bp.delete("/api/patients/<int:patient_id>")
def delete_patient(patient_id):
    if not db.delete_patient(patient_id):
        return _error("Record not found.", 404)
    return "", 204
