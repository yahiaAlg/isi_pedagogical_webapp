# ISI Pedagogical Management System

### Système de Gestion Pédagogique — Institut de Sécurité Industrielle

A web-based pedagogical administration system for a state-accredited Algerian vocational training institute (DEFP 003). Replaces a fully manual, Microsoft Word–based workflow with a single-entry data propagation system that generates all 8 official bilingual documents automatically.

---

## Features

- **Formation catalog** — bilingual (French/Arabic) training programs with categories, durations, evaluation types, and legal references
- **Session lifecycle** — `planned → in_progress → completed → archived / cancelled` with enforced transitions
- **Participant management** — bilingual personal data, per-day attendance, evaluation scores, automatic pass/fail computation
- **CSV/Excel import** — bulk participant registration with duplicate detection and capacity enforcement
- **Document generation** — all 8 official document types auto-generated from structured data:
  - Liste des candidats · Feuille de présence · Ordre de mission · Liste nominale
  - Liste des notes · Fiche d'évaluation · محضر مداولات · شهادة تكوين تأهيلي
- **Sequential certificate numbering** — assigned at generation time, never editable
- **Reporting & analytics** — fill rates, pass rates, sessions by formation/client/trainer, certificate volume, trainer activity
- **Role-based access** — Administrateur · Agent Administratif · Formateur · Consultant

---

## Tech Stack

| Layer               | Technology                               |
| ------------------- | ---------------------------------------- |
| Framework           | Django 5.1                               |
| Database            | PostgreSQL (production) · SQLite (local) |
| Static files        | WhiteNoise                               |
| Document generation | python-docx                              |
| Import              | openpyxl                                 |
| Server              | Gunicorn on Render                       |

---

## Project Structure

```
project/
├── accounts/       # Authentication, UserProfile, 4-role system
├── clients/        # Client (company) directory
├── core/           # InstituteInfo singleton, dashboard, seed command
├── documents/      # GeneratedDocument archive, generation engine
├── formations/     # Catalog, sessions, participants, import
├── reporting/      # Analytics, fill rates, pass rates, reports
├── resources/      # Trainer directory, room management
├── pedagogical/    # Django project settings & root URLs
├── templates/      # All HTML templates
├── static/         # CSS, JS, images
├── requirements.txt
├── .env.example
└── manage.py
```

---

## Local Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/your-org/isi-pedagogy.git
cd isi-pedagogy
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:

```env
SECRET_KEY=<generate with command below>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
# Leave DB_ENGINE unset to use SQLite locally
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Create the static directory

```bash
mkdir -p static
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Seed the database

```bash
python manage.py seed_db
```

This creates:

- InstituteInfo (ISI Sétif)
- 5 users across all roles
- 5 clients (GRAVEM, NAFTAL, SONELGAZ, CEVITAL, ACC)
- 4 rooms, 4 trainers, 5 formations
- 6 sessions across all statuses (planned · in_progress · completed · archived · cancelled)
- Participants with bilingual data, scores, and certificates

### 7. Run the development server

```bash
python manage.py runserver
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Seed Credentials

| Username     | Password     | Role                |
| ------------ | ------------ | ------------------- |
| `admin`      | `Admin@1234` | Administrateur      |
| `staff1`     | `Staff@1234` | Agent Administratif |
| `formateur1` | `Form@1234`  | Formateur           |
| `viewer1`    | `View@1234`  | Consultant          |

---

## Deployment on Render

### 1. Create a PostgreSQL service on Render

Note the **Host**, **Database**, **Username**, and **Password** from the service dashboard.

### 2. Create a Web Service

- **Environment:** Python
- **Build command:**
  ```
  pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
  ```
- **Start command:**
  ```
  gunicorn pedagogical.wsgi:application
  ```

### 3. Add a Persistent Disk

Mount path: `/var/data/media` — required so uploaded media files (logos, generated documents) survive redeploys.

### 4. Set environment variables

| Variable               | Value                           |
| ---------------------- | ------------------------------- |
| `SECRET_KEY`           | Generated secret key            |
| `DEBUG`                | `False`                         |
| `ALLOWED_HOSTS`        | `myapp.onrender.com`            |
| `CSRF_TRUSTED_ORIGINS` | `https://myapp.onrender.com`    |
| `DB_ENGINE`            | `django.db.backends.postgresql` |
| `DB_NAME`              | From Render PostgreSQL service  |
| `DB_USER`              | From Render PostgreSQL service  |
| `DB_PASSWORD`          | From Render PostgreSQL service  |
| `DB_HOST`              | From Render PostgreSQL service  |
| `DB_PORT`              | `5432`                          |
| `MEDIA_ROOT`           | `/var/data/media`               |

### 5. Seed on first deploy (optional)

Open a Render shell and run:

```bash
python manage.py seed_db
```

---

## Re-seed / Reset

```bash
# Wipe all app data (keeps superusers) and re-seed
python manage.py seed_db --flush
```

---

## Key Business Rules

| Rule                                                           | Enforcement                                          |
| -------------------------------------------------------------- | ---------------------------------------------------- |
| Participant result computed, never stored                      | `Participant.result` is a `@property`                |
| Certificate number auto-assigned at generation, never editable | `Participant.save()` strips external values          |
| Formation deactivation blocked if active sessions exist        | `Formation.clean()`                                  |
| Archived / cancelled sessions are immutable                    | `Session.clean()` + view guards                      |
| Committee minimum 2 members for deliberation report            | `documents/utils.py` + form validation               |
| Import stops at capacity; reports 3 counts                     | `formations/utils.py::import_participants_from_file` |
| Pre-session docs require `participant_count > 0`               | `documents/utils.py::check_document_requirements`    |
| Post-session docs require `status = completed`                 | Same function                                        |

---

## License

Internal system — Institut de Sécurité Industrielle, Sétif, Algeria.
