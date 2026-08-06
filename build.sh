#!/usr/bin/env bash
set -e  # exit immediately on any error

echo "================================================"
echo " ISI Pedagogical System — Build Script"
echo "================================================"

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
echo ""
echo "[1/5] Installing Python dependencies..."
pip install -r requirements.txt
echo "      ✓ Dependencies installed."

# ---------------------------------------------------------------------------
# 2. Ensure static/ directory exists (prevents W004 warning)
# ---------------------------------------------------------------------------
echo ""
echo "[2/5] Ensuring static/ directory exists..."
mkdir -p static
echo "      ✓ static/ ready."

# ---------------------------------------------------------------------------
# 3. Make migrations for all apps (creates migration files if missing)
# ---------------------------------------------------------------------------
echo ""
echo "[3/5] Creating migrations..."

echo "  → core (InstituteInfo singleton)"
python manage.py makemigrations core --verbosity 1

echo "  → accounts (UserProfile)"
python manage.py makemigrations accounts --verbosity 1

echo "  → clients (Client directory)"
python manage.py makemigrations clients --verbosity 1

echo "  → resources (Trainer, Room)"
python manage.py makemigrations resources --verbosity 1

echo "  → formations (Category, Formation, Session, Participant)"
python manage.py makemigrations formations --verbosity 1

echo "  → documents (GeneratedDocument archive)"
python manage.py makemigrations documents --verbosity 1

echo "  → reporting (no models)"
python manage.py makemigrations reporting --verbosity 1

echo "      ✓ Migrations created."

# ---------------------------------------------------------------------------
# 4. Apply migrations — each app explicitly and verbosely
# ---------------------------------------------------------------------------
echo ""
echo "[4/5] Applying migrations..."

echo "  → contenttypes"
python manage.py migrate contenttypes --verbosity 1

echo "  → auth (users, permissions, groups)"
python manage.py migrate auth --verbosity 1

echo "  → accounts (UserProfile)"
python manage.py migrate accounts --verbosity 1

echo "  → admin"
python manage.py migrate admin --verbosity 1

echo "  → sessions (Django session framework)"
python manage.py migrate sessions --verbosity 1

echo "  → core (InstituteInfo singleton)"
python manage.py migrate core --verbosity 1

echo "  → clients (Client directory)"
python manage.py migrate clients --verbosity 1

echo "  → resources (Trainer, Room)"
python manage.py migrate resources --verbosity 1

echo "  → formations (Category, Formation, Session, Participant)"
python manage.py migrate formations --verbosity 1

echo "  → documents (GeneratedDocument archive)"
python manage.py migrate documents --verbosity 1

echo "  → reporting (no models — marks app as migrated)"
python manage.py migrate reporting --verbosity 1

echo "      ✓ All migrations applied."

# ---------------------------------------------------------------------------
# 5. Collect static files (WhiteNoise)
# ---------------------------------------------------------------------------
echo ""
echo "[5/5] Collecting static files..."
python manage.py collectstatic --no-input --verbosity 1
echo "      ✓ Static files collected."

# ---------------------------------------------------------------------------
# Seed the database (idempotent — skips existing records)
# ---------------------------------------------------------------------------
echo ""
echo "[seed] Seeding database..."
python manage.py seed_db
echo "       ✓ Database seeded."

echo ""
echo "================================================"
echo " Build complete. Starting Gunicorn..."
echo "================================================"