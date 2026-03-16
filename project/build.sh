#!/usr/bin/env bash
set -e  # exit immediately on any error

echo "================================================"
echo " ISI Pedagogical System — Build Script"
echo "================================================"

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
echo ""
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt
echo "      ✓ Dependencies installed."

# ---------------------------------------------------------------------------
# 2. Run migrations — each app explicitly and verbosely
# ---------------------------------------------------------------------------
echo ""
echo "[2/4] Running database migrations..."

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
# 3. Collect static files (WhiteNoise)
# ---------------------------------------------------------------------------
echo ""
echo "[3/4] Collecting static files..."
python manage.py collectstatic --no-input --verbosity 1
echo "      ✓ Static files collected."

# ---------------------------------------------------------------------------
# 4. Seed the database (skips existing records — safe on redeploy)
# ---------------------------------------------------------------------------
echo ""
echo "[4/4] Seeding database..."
python manage.py seed_db
echo "      ✓ Database seeded."

echo ""
echo "================================================"
echo " Build complete. Starting Gunicorn..."
echo "================================================"