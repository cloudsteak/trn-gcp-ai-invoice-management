#!/usr/bin/env bash
# GitHub Actions secrets és variables törlése – a setup-wif.sh által beállított értékek
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-}"
AUTO_YES="${AUTO_YES:-false}"

# A setup-wif.sh / README által dokumentált repository secrets
GITHUB_SECRETS=(
  GCP_PROJECT_ID
  GCP_WIF_PROVIDER
  GCP_WIF_SERVICE_ACCOUNT
  VITE_API_BASE_URL
  # Régi / alternatív nevek (CLAUDE.md, korábbi setup)
  GCP_WORKLOAD_IDENTITY_PROVIDER
  GCP_SERVICE_ACCOUNT
)

# Opcionális repository variables (deploy.yml alapértelmezései mellett felülírhatók)
GITHUB_VARIABLES=(
  GCP_LOCATION
  GEMINI_MODEL
  GEMINI_LOCATION
  MAX_FILE_SIZE_MB
  MAX_FILES_PER_BATCH
  UPLOAD_DIR
  CORS_ORIGINS
)

usage() {
  cat <<'EOF'
Hasznalat:
  export GITHUB_REPO=<szervezet>/<repo-nev>   # opcionalis, ha gh a cwd repot latja
  ./scripts/teardown-github.sh [--yes]

Torli a setup-wif.sh altal beallitott GitHub Actions secrets es variables ertekeket.

Elofeltetelek:
  - gh CLI telepitve es bejelentkezve (gh auth login)
  - repo admin jogosultsag a secrets/variables torleshez

Kornyezeti valtozok:
  GITHUB_REPO   Cel repository (pl. cloudsteak/trn-gcp-ai-invoice-management)
  AUTO_YES=true Ugyanaz, mint a --yes kapcsolo (nem interaktiv megerosites)
EOF
}

for arg in "$@"; do
  case "${arg}" in
    -h | --help)
      usage
      exit 0
      ;;
    -y | --yes)
      AUTO_YES=true
      ;;
    *)
      echo "Ismeretlen argumentum: ${arg}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "Hiba: a gh CLI nincs telepitve. Telepites: https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Hiba: nincs bejelentkezve a gh CLI-ba. Futtasd: gh auth login" >&2
  exit 1
fi

if [[ -z "${GITHUB_REPO}" ]]; then
  if GITHUB_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; then
    echo "Repository automatikusan felismerve: ${GITHUB_REPO}"
  else
    echo "Hiba: allitsd be a GITHUB_REPO kornyezeti valtozot (pl. export GITHUB_REPO=org/repo)." >&2
    exit 1
  fi
fi

# Meglevo nevek lekerdezese (idempotens torleshez)
EXISTING_SECRETS=()
while IFS= read -r line; do
  [[ -n "${line}" ]] && EXISTING_SECRETS+=("${line}")
done < <(gh secret list --repo "${GITHUB_REPO}" --app actions --json name -q '.[].name' 2>/dev/null || true)

EXISTING_VARIABLES=()
while IFS= read -r line; do
  [[ -n "${line}" ]] && EXISTING_VARIABLES+=("${line}")
done < <(gh variable list --repo "${GITHUB_REPO}" --json name -q '.[].name' 2>/dev/null || true)

secret_exists() {
  local name="$1"
  local item
  for item in "${EXISTING_SECRETS[@]}"; do
    [[ "${item}" == "${name}" ]] && return 0
  done
  return 1
}

variable_exists() {
  local name="$1"
  local item
  for item in "${EXISTING_VARIABLES[@]}"; do
    [[ "${item}" == "${name}" ]] && return 0
  done
  return 1
}

SECRETS_TO_DELETE=()
VARIABLES_TO_DELETE=()

for name in "${GITHUB_SECRETS[@]}"; do
  if secret_exists "${name}"; then
    SECRETS_TO_DELETE+=("${name}")
  fi
done

for name in "${GITHUB_VARIABLES[@]}"; do
  if variable_exists "${name}"; then
    VARIABLES_TO_DELETE+=("${name}")
  fi
done

if [[ ${#SECRETS_TO_DELETE[@]} -eq 0 && ${#VARIABLES_TO_DELETE[@]} -eq 0 ]]; then
  echo "Nincs torlendo GitHub secret vagy variable a ${GITHUB_REPO} repoban."
  exit 0
fi

echo "Repository: ${GITHUB_REPO}"
echo ""
echo "Torlendo secrets (${#SECRETS_TO_DELETE[@]}):"
if [[ ${#SECRETS_TO_DELETE[@]} -gt 0 ]]; then
  printf '  - %s\n' "${SECRETS_TO_DELETE[@]}"
else
  echo "  (nincs)"
fi
echo ""
echo "Torlendo variables (${#VARIABLES_TO_DELETE[@]}):"
if [[ ${#VARIABLES_TO_DELETE[@]} -gt 0 ]]; then
  printf '  - %s\n' "${VARIABLES_TO_DELETE[@]}"
else
  echo "  (nincs)"
fi
echo ""

if [[ "${AUTO_YES}" != "true" ]]; then
  read -r -p "Folytatod a torlest? [y/N] " confirm
  if [[ ! "${confirm}" =~ ^[yY]$ ]]; then
    echo "Megszakitva."
    exit 0
  fi
fi

for name in "${SECRETS_TO_DELETE[@]}"; do
  echo "Secret torlese: ${name}"
  gh secret delete "${name}" --repo "${GITHUB_REPO}" --app actions
done

for name in "${VARIABLES_TO_DELETE[@]}"; do
  echo "Variable torlese: ${name}"
  gh variable delete "${name}" --repo "${GITHUB_REPO}"
done

echo ""
echo "GitHub teardown kesz: ${GITHUB_REPO}"
