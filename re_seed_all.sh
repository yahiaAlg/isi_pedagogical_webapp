#!/usr/bin/env bash
# re_seed_all.sh
# ──────────────────────────────────────────────────────────────────────────
# Wipes ALL data from the database (Django `flush`) and re-seeds every
# catalog / master table in the correct dependency order.
#
# Dependency graph (why this order):
#
#   flush  ─►  institute_seed   (admin user + InstituteInfo singleton)
#         ─►  branches_seed     (Branch — no deps)
#         ─►  categories_seed   (Category — no deps)
#         ─►  specialities_seed (Specialty → needs Branch)
#         ─►  formations_seed   (Formation → needs Category + Specialty)
#         ─►  trainers_seed     (Trainer — no hard deps; M2M to Formation)
#         ─►  clients_seed      (Client — no deps)
#
# Usage:
#   ./re_seed_all.sh            # re-seed (skips existing rows)
#   ./re_seed_all.sh --force    # overwrite existing rows
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
step "1/8  — Django flush (wipe ALL data)"
# --noinput skips the "Are you sure?" confirmation.
# --reset-static-sequences is included so AutoField PKs restart at 1 on Postgres.
$MANAGE flush --noinput --reset-static-sequences
ok "Database flushed"

# ── 2. migrate (safety net, in case migrations drifted) ──────────────────
step "2/8  — Django migrate (schema sync)"
$MANAGE migrate --noinput
ok "Schema up to date"

# ── 3. institute_seed ────────────────────────────────────────────────────
# Admin superuser + InstituteInfo singleton. No dependencies.
step "3/8  — institute_seed  (admin user + InstituteInfo)"
$MANAGE institute_seed $FORCE_FLAG
ok "Institute seeded"

# ── 4. branches_seed ─────────────────────────────────────────────────────
# Branch records. No dependencies — must come before specialities_seed.
step "4/8  — branches_seed  (Branches / الشعب)"
$MANAGE branches_seed $FORCE_FLAG
ok "Branches seeded"

# ── 5. categories_seed ───────────────────────────────────────────────────
# Category records. No dependencies — must come before formations_seed.
step "5/8  — categories_seed  (Categories)"
$MANAGE categories_seed $FORCE_FLAG
ok "Categories seeded"

# ── 6. specialities_seed ─────────────────────────────────────────────────
# Specialty records. Depends on Branch (requires branches_seed first).
step "6/8  — specialities_seed  (Specialties / التخصصات)"
$MANAGE specialities_seed $FORCE_FLAG
ok "Specialties seeded"

# ── 7. formations_seed ───────────────────────────────────────────────────
# Formation records. Depends on Category AND Specialty.
step "7/8  — formations_seed  (Formations catalogue)"
$MANAGE formations_seed $FORCE_FLAG
ok "Formations seeded"

# ── 8. trainers_seed ─────────────────────────────────────────────────────
# Trainer roster. No hard deps; Trainer.qualifications is M2M to Formation
# (left empty by the seed), so seeding after formations is harmless and
# keeps the script's logical grouping clean.
step "8a/8 — trainers_seed  (Trainer roster)"
$MANAGE trainers_seed $FORCE_FLAG
ok "Trainers seeded"

# ── 9. clients_seed ──────────────────────────────────────────────────────
# Client portfolio. No dependencies.
step "8b/8 — clients_seed  (Client portfolio)"
$MANAGE clients_seed $FORCE_FLAG
ok "Clients seeded"

# ── done ──────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD} ✅  Re-seed complete.${RESET}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "Login: ${BOLD}admin / admin1234!${RESET}"