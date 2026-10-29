#!/usr/bin/env bash
#
# session_seed_automation.sh
#
# Runs the project's Django seed management commands in dependency order:
#   1. Foundational/reference data (institute, branches, categories, specialities)
#   2. People/entities that depend on the above (clients, trainers)
#   3. Formations (depend on categories/specialities/trainers)
#   4. General initial data
#   5. Session batches (2026_1 -> 2026_5), which depend on everything above
#   6. Exemplary/demo batch (optional, off by default)
#
# Usage:
#   ./session_seed_automation.sh                # run full seed order
#   ./session_seed_automation.sh --with-example  # also run seed_session_batch_examplary
#   ./session_seed_automation.sh --dry-run       # print commands without executing
#   ./session_seed_automation.sh --from formations_seed   # resume starting at a given step
#
# Assumes it is run from the Django project root (where manage.py lives).

set -euo pipefail

# ---- config -----------------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-python}"
MANAGE_PY="${MANAGE_PY:-manage.py}"

# Force UTF-8 I/O so Django's styled/unicode output (e.g. "►") doesn't crash
# on Windows terminals defaulting to cp1252.
export PYTHONIOENCODING="utf-8"
export PYTHONUTF8=1
LOG_DIR="${LOG_DIR:-./seed_logs}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/seed_run_${TIMESTAMP}.log"

WITH_EXAMPLE=0
DRY_RUN=0
FROM_STEP=""

# ---- ordered list of seed commands (filename without .py == command name) --
STEPS=(
    institute_seed
    branches_seed
    categories_seed
    specialities_seed
    clients_seed
    trainers_seed
    formations_seed
    seed_session_batch_examplary
    seed_session_batch_2026_1
    seed_session_batch_2026_2
    seed_session_batch_2026_3
    seed_session_batch_2026_4
    seed_session_batch_2026_5
)

EXAMPLE_STEP="seed_session_batch_examplary"

# ---- arg parsing --------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-example)
            WITH_EXAMPLE=1
            shift
        ;;
        --dry-run)
            DRY_RUN=1
            shift
        ;;
        --from)
            FROM_STEP="${2:-}"
            shift 2
        ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^#//'
            exit 0
        ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
        ;;
    esac
done

if [[ "${WITH_EXAMPLE}" -eq 1 ]]; then
    STEPS+=("${EXAMPLE_STEP}")
fi

# ---- helpers -------------------------------------------------------------
c_green="\033[0;32m"
c_red="\033[0;31m"
c_yellow="\033[0;33m"
c_reset="\033[0m"

log() {
    echo -e "$1" | tee -a "${LOG_FILE}"
}

fail() {
    log "${c_red}✗ $1${c_reset}"
    exit 1
}

# ---- pre-flight checks ----------------------------------------------------
mkdir -p "${LOG_DIR}"

if [[ ! -f "${MANAGE_PY}" ]]; then
    fail "Could not find ${MANAGE_PY} in the current directory. Run this script from the Django project root, or set MANAGE_PY=/path/to/manage.py."
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    fail "Python interpreter '${PYTHON_BIN}' not found. Set PYTHON_BIN to your venv's python."
fi

# If --from is given, drop every step before it
if [[ -n "${FROM_STEP}" ]]; then
    found=0
    new_steps=()
    for step in "${STEPS[@]}"; do
        if [[ "${step}" == "${FROM_STEP}" ]]; then
            found=1
        fi
        if [[ "${found}" -eq 1 ]]; then
            new_steps+=("${step}")
        fi
    done
    if [[ "${found}" -eq 0 ]]; then
        fail "Step '${FROM_STEP}' not found in the seed order. Valid steps: ${STEPS[*]} ${EXAMPLE_STEP}"
    fi
    STEPS=("${new_steps[@]}")
fi

log "${c_yellow}Seed run started: ${TIMESTAMP}${c_reset}"
log "Steps to run: ${STEPS[*]}"
log "Log file: ${LOG_FILE}"
log "---"

# ---- run steps -------------------------------------------------------------
step_num=0
total_steps=${#STEPS[@]}

for step in "${STEPS[@]}"; do
    step_num=$((step_num + 1))
    cmd=("${PYTHON_BIN}" "${MANAGE_PY}" "${step}")
    
    log "${c_yellow}[${step_num}/${total_steps}] ${step}${c_reset}"
    
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  (dry-run) ${cmd[*]}"
        continue
    fi
    
    if "${cmd[@]}" >>"${LOG_FILE}" 2>&1; then
        log "${c_green}  ✓ ${step} completed${c_reset}"
    else
        log "${c_red}  ✗ ${step} failed — see ${LOG_FILE} for details${c_reset}"
        log "${c_yellow}  Resume from this step with: $0 --from ${step}$( [[ ${WITH_EXAMPLE} -eq 1 ]] && echo ' --with-example' )${c_reset}"
        exit 1
    fi
done

log "---"
log "${c_green}All seed steps completed successfully.${c_reset}"