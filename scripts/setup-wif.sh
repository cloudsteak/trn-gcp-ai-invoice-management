#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
GITHUB_REPO="${GITHUB_REPO:-}"
POOL_ID="${WIF_POOL_ID:-invoice-processor-pool}"
PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider}"
CICD_SA="${CICD_SERVICE_ACCOUNT:-invoice-processor-cicd-sa}"
RUNTIME_SA="${SERVICE_ACCOUNT:-invoice-processor-sa}"
REGION="${GCP_REGION:-europe-west1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-invoice-processor-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-invoice-processor-frontend}"
CICD_SA_EMAIL="${CICD_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Hiba: allitsd be a GCP_PROJECT_ID vagy GOOGLE_CLOUD_PROJECT kornyezeti valtozot."
  exit 1
fi

if [[ -z "${GITHUB_REPO}" ]]; then
  echo "Hiba: allitsd be a GITHUB_REPO kornyezeti valtozot (pl. szervezet/repo-nev)."
  exit 1
fi

echo "GCP projekt beallitasa: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

echo "Szukseges API-k engedelyezese WIF-hez..."
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

echo "CI/CD service account letrehozasa: ${CICD_SA}"
if gcloud iam service-accounts describe "${CICD_SA_EMAIL}" >/dev/null 2>&1; then
  echo "A CI/CD service account mar letezik, kihagyva."
else
  gcloud iam service-accounts create "${CICD_SA}" \
    --display-name="Invoice Processor GitHub Actions Deploy"
fi

# IAM binding csak propagálás után – frissen létrehozott SA még nem látszik azonnal
wait_for_service_account "${CICD_SA_EMAIL}"

COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Deploy jogosultsagok hozzarendelese a CI/CD service accounthoz..."
for role in \
  roles/run.admin \
  roles/run.sourceDeveloper \
  roles/run.builder \
  roles/cloudbuild.builds.builder \
  roles/artifactregistry.writer \
  roles/storage.objectAdmin \
  roles/logging.logWriter \
  roles/serviceusage.serviceUsageConsumer \
  roles/secretmanager.secretAccessor; do
  add_project_iam_binding "${PROJECT_ID}" "serviceAccount:${CICD_SA_EMAIL}" "${role}"
done

echo "CI/CD service account onmagat hasznalhatja build service accountkent..."
add_sa_iam_binding "${CICD_SA_EMAIL}" "serviceAccount:${CICD_SA_EMAIL}" "roles/iam.serviceAccountUser"

echo "CI/CD service account hasznalhatja az alap Cloud Build / Compute accountokat..."
for BUILD_SA in "${CLOUDBUILD_SA}" "${COMPUTE_SA}"; do
  if gcloud iam service-accounts describe "${BUILD_SA}" >/dev/null 2>&1; then
    add_sa_iam_binding "${BUILD_SA}" "serviceAccount:${CICD_SA_EMAIL}" "roles/iam.serviceAccountUser"
  fi
done

echo "Cloud Build service account deployolhat a futo Cloud Run service accounttal..."
if gcloud iam service-accounts describe "${CLOUDBUILD_SA}" >/dev/null 2>&1; then
  add_project_iam_binding "${PROJECT_ID}" "serviceAccount:${CLOUDBUILD_SA}" "roles/run.builder"
  if gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" >/dev/null 2>&1; then
    add_sa_iam_binding "${RUNTIME_SA_EMAIL}" "serviceAccount:${CLOUDBUILD_SA}" "roles/iam.serviceAccountUser"
  else
    echo "Figyelem: a ${RUNTIME_SA} meg nem letezik. Futtasd elobb a setup.sh-t, majd ujra ezt a scriptet."
  fi
fi

echo "Jogosultsag a futo Cloud Run service account hasznalatahoz..."
if gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" >/dev/null 2>&1; then
  add_sa_iam_binding "${RUNTIME_SA_EMAIL}" "serviceAccount:${CICD_SA_EMAIL}" "roles/iam.serviceAccountUser"
else
  echo "Figyelem: a ${RUNTIME_SA} meg nem letezik. Futtasd elobb a setup.sh-t, majd ujra ezt a scriptet."
fi

echo "Workload Identity Pool letrehozasa: ${POOL_ID}"
if gcloud iam workload-identity-pools describe "${POOL_ID}" \
  --location=global >/dev/null 2>&1; then
  echo "A WIF pool mar letezik, kihagyva."
else
  gcloud iam workload-identity-pools create "${POOL_ID}" \
    --location=global \
    --display-name="Invoice Processor GitHub Actions"
fi

echo "GitHub OIDC provider letrehozasa: ${PROVIDER_ID}"
if gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" >/dev/null 2>&1; then
  echo "A WIF provider mar letezik, kihagyva."
else
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --display-name="GitHub Actions" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${GITHUB_REPO}'"
fi

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"

echo "WIF hozzaferest kotve a CI/CD service accounthoz..."
add_sa_iam_binding "${CICD_SA_EMAIL}" "${PRINCIPAL}" "roles/iam.workloadIdentityUser"

BACKEND_URL=""
FRONTEND_URL=""
if cloud_run_service_exists "${BACKEND_SERVICE}" "${REGION}"; then
  BACKEND_URL="$(cloud_run_service_url "${BACKEND_SERVICE}" "${REGION}" "${PROJECT_NUMBER}")"
fi
if cloud_run_service_exists "${FRONTEND_SERVICE}" "${REGION}"; then
  FRONTEND_URL="$(cloud_run_service_url "${FRONTEND_SERVICE}" "${REGION}" "${PROJECT_NUMBER}")"
fi

echo ""
echo "WIF setup kesz."
echo ""
echo "Kornyezeti valtozok (masold be vagy futtasd):"
echo ""
echo "export GCP_PROJECT_ID=${PROJECT_ID}"
echo "export GCP_REGION=${REGION}"
echo "export BACKEND_SERVICE=${BACKEND_SERVICE}"
echo "export FRONTEND_SERVICE=${FRONTEND_SERVICE}"
echo "export GITHUB_REPO=${GITHUB_REPO}"
echo "export WIF_POOL_ID=${POOL_ID}"
echo "export WIF_PROVIDER_ID=${PROVIDER_ID}"
echo "export CICD_SERVICE_ACCOUNT=${CICD_SA}"
echo "export SERVICE_ACCOUNT=${RUNTIME_SA}"
echo ""
echo "GitHub Secrets (Settings -> Secrets and variables -> Actions):"
echo ""
echo "  GCP_PROJECT_ID=${PROJECT_ID}"
echo "  GCP_WIF_PROVIDER=${WIF_PROVIDER}"
echo "  GCP_WIF_SERVICE_ACCOUNT=${CICD_SA_EMAIL}"
if [[ -n "${BACKEND_URL}" ]]; then
  echo "  VITE_API_BASE_URL=${BACKEND_URL}"
else
  echo "  VITE_API_BASE_URL=(a backend Cloud Run service meg nem letezik – futtasd elobb a setup.sh-t)"
fi
if [[ -n "${BACKEND_URL}" ]]; then
  echo ""
  echo "Backend URL (GCP konzol): ${BACKEND_URL}"
fi
if [[ -n "${FRONTEND_URL}" ]]; then
  echo "Frontend URL (GCP konzol): ${FRONTEND_URL}"
fi
echo ""
echo "GitHub Variables (opcionalis, alapertelmezett ertekek a deploy.yml-ben):"
echo "  GCP_LOCATION=eu"
echo "  GEMINI_MODEL=gemini-3.1-flash-lite"
echo ""
echo "A JSON kulcs nem szukseges – a deploy.yml Workload Identity Federation-t hasznal."
echo ""
echo "Kovetkezo lepes (GitHub secrets + variables, gh CLI):"
echo "  ./scripts/setup-github.sh"
echo ""
echo "Teardown (demo ujrainditashoz, forditott sorrendben):"
echo "  ./scripts/teardown.sh"
echo "  ./scripts/teardown-wif.sh"
echo "  ./scripts/teardown-github.sh   # GitHub secrets + variables (gh CLI)"
