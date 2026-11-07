# Patient Health Records

A small Flask app for managing patient blood test records. When a record is saved, glucose, haemoglobin and cholesterol values are sent to an AI API, and the returned health-risk remarks are stored with the record.

**Stack:** Python 3 · Flask · SQLite · Bootstrap 5 + vanilla JavaScript · Groq API

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then add your GROQ_API_KEY
python run.py
```

Open http://127.0.0.1:5000. The SQLite file (`patients.db`) is created on first run.

If no API key is set, records still save; the Remarks column shows a **Generate** button once a key is configured.

## Features

| Operation | How |
|-----------|-----|
| Create | **Add record** button. Validation runs first; the AI is only called for valid data. |
| Read | Table on the home page lists every record with its remarks. |
| Update | **Edit** button. Remarks are regenerated only if date of birth or a blood value changed. |
| Delete | **Delete** button with a confirmation dialog. |

## Validation

Checked on the server (`app/validators.py`), with every problem reported at once:

- **Full name:** required; letters, spaces, hyphens, apostrophes.
- **Date of birth:** `dd/mm/yyyy` (dots also accepted, e.g. `28.01.1960`); must be a real calendar date and not in the future.
- **Email:** required, standard `name@domain.tld` format.
- **Glucose, haemoglobin, cholesterol:** numeric and within plausible limits (20-600 mg/dL, 3-25 g/dL, 50-600 mg/dL).
- **Duplicates:** rejected when the email already exists, or when name and date of birth both match another record.

## AI integration

`app/ai_service.py` calls the Groq API with the patient's age and three blood values, plus a system prompt holding the reference ranges. It asks for a short, plain-text risk remark ending with a "not a diagnosis" note.

- Name, email and date of birth are **not** sent.
- Timeouts, bad keys, rate limits and malformed replies become a friendly `AIServiceError`; the record is still saved and can be retried with **Generate**.
- Model and timeout are configurable via `.env`.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/patients` | List all |
| GET | `/api/patients/<id>` | One record |
| POST | `/api/patients` | Create. 201, 422 (validation) or 409 (duplicate) |
| PUT | `/api/patients/<id>` | Update. Same error codes |
| POST | `/api/patients/<id>/remarks` | Regenerate remarks. 502 if the AI call fails |
| DELETE | `/api/patients/<id>` | 204 on success |

## Project structure

```
app/
  __init__.py      app factory
  config.py        settings from environment
  db.py            SQLite queries
  validators.py    input validation
  ai_service.py    external AI API client
  routes.py        REST endpoints + page
  templates/       index.html
  static/          app.js, style.css
tests/             pytest suite (AI API is stubbed)
run.py             entry point
```

## Tests

```bash
python -m pytest
```

`tests/test_assignment_records.py` loads the ten sample records and checks which are accepted or rejected.

## Security

`.env` and `*.db` are git-ignored. Only `.env.example` (no secrets) is committed.
