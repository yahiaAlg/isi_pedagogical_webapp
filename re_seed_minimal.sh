#!/usr/bin/env bash
# re_seed_minimal.sh
# ──────────────────────────────────────────────────────────────────────────
# Wipes ALL data from the database (Django `flush`) and re-seeds ONLY the
# core structural tables (Institute, Branches, Categories, Specialties).
# Formations, Trainers, and Clients are NOT seeded.
#
# Usage:
#   ./re_seed_minimal.sh            # re-seed (skips existing rows)
#   ./re_seed_minimal.sh --force    # overwrite existing rows
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── colours ───────────────────────────────────────────────────────────────
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BOLD="\033[1m"
RESET="\033[0m"

# ── config ────────────────────────────────────────────────────────────────
MANAGE="python manage.py"
FORCE_FLAG=""

if [[ "${1:-}" == "--force" ]]; then
    FORCE_FLAG="--force"
fi

step() {
    echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
    echo -e "${CYAN}${BOLD} ▶ $1${RESET}"
    echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
}

ok() {
    echo -e "${GREEN}✓ $1${RESET}"
}

fail() {
    echo -e "${RED}✗ $1${RESET}"
    exit 1
}

# ── pre-flight ────────────────────────────────────────────────────────────
step "Pre-flight checks"
command -v python >/dev/null 2>&1 || fail "python interpreter not found in PATH"
[[ -f "manage.py" ]] || fail "manage.py not found — run this script from the project root."
ok "Environment OK"

# ── 1. flush ──────────────────────────────────────────────────────────────
step "1/6  — Django flush (wipe ALL data)"
# --noinput skips the "Are you sure?" confirmation.
# Note: `manage.py flush` has no --reset-static-sequences flag (that's not
# a real Django option); flush already resets AutoField sequences on its own.
$MANAGE flush --noinput
ok "Database flushed"

# ── 2. migrate (safety net, in case migrations drifted) ──────────────────
step "2/6  — Django migrate (schema sync)"
$MANAGE migrate --noinput
ok "Schema up to date"

# ── 3. institute_seed ────────────────────────────────────────────────────
# Admin superuser + InstituteInfo singleton. No dependencies.
step "3/6  — institute_seed  (admin user + InstituteInfo)"
$MANAGE institute_seed $FORCE_FLAG
ok "Institute seeded"

# ── 4. branches_seed ─────────────────────────────────────────────────────
# Branch records. No dependencies — must come before specialities_seed.
step "4/6  — branches_seed  (Branches / الشعب)"
$MANAGE branches_seed $FORCE_FLAG
ok "Branches seeded"

# ── 5. categories_seed ───────────────────────────────────────────────────
# Category records. No dependencies.
step "5/6  — categories_seed  (Categories)"
$MANAGE categories_seed $FORCE_FLAG
ok "Categories seeded"

# ── 6. specialities_seed ─────────────────────────────────────────────────
# Specialty records. Depends on Branch (requires branches_seed first).
step "6/6  — specialities_seed  (Specialties / التخصصات)"
$MANAGE specialities_seed $FORCE_FLAG
ok "Specialties seeded"

# ── done ──────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD} ✅  Minimal re-seed complete.${RESET}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "Login: ${BOLD}admin / admin1234!${RESET}"