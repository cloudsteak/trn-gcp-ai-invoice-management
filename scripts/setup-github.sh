#!/usr/bin/env bash
# GitHub Actions secrets és variables beállítása – setup-wif.sh után
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
GITHUB_REPO="${GITHUB_REPO:-}"
POOL_ID="${WIF_POOL_ID:-invoice-processor-pool}"
PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider}"
CICD_SA="${CICD_SERVICE_ACCOUNT:-invoice-processor-cicd-sa}"
REGION="${GCP_REGION:-europe-west1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-invoice-processor-backend}"
AUTO_YES="${AUTO_YES:-false}"
SKIP_VARIABLES="${SKIP_VARIABLES:-false}"

usage() {
  cat <<'EOF'
Hasznalat:
  export GCP_PROJECT_ID=<a-gcp-projekt-id>
  export GITHUB_REPO=<szervezet>/<repo-nev>   # opcionalis, ha gh a cwd repot latja
  ./scripts/setup-github.sh [--yes] [--secrets-only]

Beallitja a deploy.yml altal hasznalt GitHub Actions secrets (es opcionalisan variables) ertekeket.

Elofeltetelek:
  - setup-wif.sh mar lefutott (WIF + CI/CD SA)
  - setup.sh mar lefutott (VITE_API_BASE_URL-hez a backend Cloud Run service)
  - gh CLI telepitve es bejelentkezve (gh auth login)
  - repo admin jogosultsag

Kornyezeti valtozok (felulirhatok, egyebkent automatikusan szamolva):
  GCP_WIF_PROVIDER           WIF provider teljes resource neve
  GCP_WIF_SERVICE_ACCOUNT    CI/CD service account e-mail
  VITE_API_BASE_URL          Backend Cloud Run URL
  GCP_LOCATION, GEMINI_MODEL, ...  (variables – deploy.yml alapertelmezesei)

Kapcsolok:
  --yes           Megerosites nelkul
  --secrets-only  Csak secrets, variables kihagyasa
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
    --secrets-only)
      SKIP_VARIABLES=true
      ;;
    *)
      echo "Ismeretlen argumentum: ${arg}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Hiba: allitsd be a GCP_PROJECT_ID vagy GOOGLE_CLOUD_PROJECT kornyezeti valtozot." >&2
  exit 1
fi

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

echo "GCP projekt: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CICD_SA_EMAIL="${GCP_WIF_SERVICE_ACCOUNT:-${CICD_SA}@${PROJECT_ID}.iam.gserviceaccount.com}"
WIF_PROVIDER="${GCP_WIF_PROVIDER:-projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}}"

BACKEND_URL="${VITE_API_BASE_URL:-}"
if [[ -z "${BACKEND_URL}" ]] && cloud_run_service_exists "${BACKEND_SERVICE}" "${REGION}"; then
  BACKEND_URL="$(cloud_run_service_url "${BACKEND_SERVICE}" "${REGION}" "${PROJECT_NUMBER}")"
fi

# Variables – deploy.yml alapertelmezesei (csak ha nem --secrets-only)
VAR_GCP_LOCATION="${GCP_LOCATION:-eu}"
VAR_GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-flash-lite}"
VAR_GEMINI_LOCATION="${GEMINI_LOCATION:-global}"
VAR_MAX_FILE_SIZE_MB="${MAX_FILE_SIZE_MB:-20}"
VAR_MAX_FILES_PER_BATCH="${MAX_FILES_PER_BATCH:-10}"
VAR_UPLOAD_DIR="${UPLOAD_DIR:-/tmp/invoices}"
VAR_CORS_ORIGINS="${CORS_ORIGINS:-*}"

echo ""
echo "Repository: ${GITHUB_REPO}"
echo ""
echo "Beallitando secrets:"
echo "  GCP_PROJECT_ID=${PROJECT_ID}"
echo "  GCP_WIF_PROVIDER=${WIF_PROVIDER}"
echo "  GCP_WIF_SERVICE_ACCOUNT=${CICD_SA_EMAIL}"
if [[ -n "${BACKEND_URL}" ]]; then
  echo "  VITE_API_BASE_URL=${BACKEND_URL}"
else
  echo "  VITE_API_BASE_URL=(kihagyva – backend service meg nem letezik; futtasd elobb a setup.sh-t)"
fi

if [[ "${SKIP_VARIABLES}" != "true" ]]; then
  echo ""
  echo "Beallitando variables:"
  echo "  GCP_LOCATION=${VAR_GCP_LOCATION}"
  echo "  GEMINI_MODEL=${VAR_GEMINI_MODEL}"
  echo "  GEMINI_LOCATION=${VAR_GEMINI_LOCATION}"
  echo "  MAX_FILE_SIZE_MB=${VAR_MAX_FILE_SIZE_MB}"
  echo "  MAX_FILES_PER_BATCH=${VAR_MAX_FILES_PER_BATCH}"
  echo "  UPLOAD_DIR=${VAR_UPLOAD_DIR}"
  echo "  CORS_ORIGINS=${VAR_CORS_ORIGINS}"
fi

echo ""
if [[ "${AUTO_YES}" != "true" ]]; then
  read -r -p "Folytatod a beallitast? [y/N] " confirm
  if [[ ! "${confirm}" =~ ^[yY]$ ]]; then
    echo "Megszakitva."
    exit 0
  fi
fi

set_github_secret() {
  local name="$1"
  local value="$2"
  echo "Secret beallitasa: ${name}"
  gh secret set "${name}" --repo "${GITHUB_REPO}" --app actions --body "${value}"
}

set_github_variable() {
  local name="$1"
  local value="$2"
  echo "Variable beallitasa: ${name}"
  gh variable set "${name}" --repo "${GITHUB_REPO}" --body "${value}"
}

set_github_secret "GCP_PROJECT_ID" "${PROJECT_ID}"
set_github_secret "GCP_WIF_PROVIDER" "${WIF_PROVIDER}"
set_github_secret "GCP_WIF_SERVICE_ACCOUNT" "${CICD_SA_EMAIL}"

if [[ -n "${BACKEND_URL}" ]]; then
  set_github_secret "VITE_API_BASE_URL" "${BACKEND_URL}"
else
  echo "Figyelem: VITE_API_BASE_URL secret nem lett beallitva."
fi

if [[ "${SKIP_VARIABLES}" != "true" ]]; then
  set_github_variable "GCP_LOCATION" "${VAR_GCP_LOCATION}"
  set_github_variable "GEMINI_MODEL" "${VAR_GEMINI_MODEL}"
  set_github_variable "GEMINI_LOCATION" "${VAR_GEMINI_LOCATION}"
  set_github_variable "MAX_FILE_SIZE_MB" "${VAR_MAX_FILE_SIZE_MB}"
  set_github_variable "MAX_FILES_PER_BATCH" "${VAR_MAX_FILES_PER_BATCH}"
  set_github_variable "UPLOAD_DIR" "${VAR_UPLOAD_DIR}"
  set_github_variable "CORS_ORIGINS" "${VAR_CORS_ORIGINS}"
fi

echo ""
echo "GitHub setup kesz: ${GITHUB_REPO}"
echo "Kovetkezo lepes: GitHub repoban PR nyitasa es merge a main branchre"
echo "  Pull requests -> New pull request -> Merge -> Actions -> Deploy"
