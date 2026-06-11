#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${GCP_REGION:-europe-west1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-invoice-processor-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-invoice-processor-frontend}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-invoice-processor-sa}"
SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
DOCAI_LOCATION="${DOCAI_LOCATION:-eu}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Hiba: allitsd be a GCP_PROJECT_ID vagy GOOGLE_CLOUD_PROJECT kornyezeti valtozot."
  exit 1
fi

echo "GCP projekt beallitasa: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

echo "Szukseges API-k engedelyezese..."
gcloud services enable \
  documentai.googleapis.com \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com

echo "Service account letrehozasa (futasi): ${SERVICE_ACCOUNT}"
if gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  echo "A service account mar letezik, kihagyva."
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
    --display-name="Invoice Processor Runtime Service Account"
fi

wait_for_service_account "${SA_EMAIL}"

echo "IAM szerepkorok hozzarendelese a futasi service accounthoz..."
for role in roles/documentai.apiUser roles/secretmanager.secretAccessor roles/aiplatform.user; do
  add_project_iam_binding "${PROJECT_ID}" "serviceAccount:${SA_EMAIL}" "${role}"
done

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
if gcloud iam service-accounts describe "${CLOUDBUILD_SA}" >/dev/null 2>&1; then
  add_project_iam_binding "${PROJECT_ID}" "serviceAccount:${CLOUDBUILD_SA}" "roles/secretmanager.secretAccessor"
fi

create_secret() {
  local name="$1"
  local prompt="$2"
  local value

  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    echo "Secret mar letezik, kihagyva: ${name}"
  else
    echo -n "${prompt}: "
    read -r value
    if [[ -z "${value}" ]]; then
      echo "Hiba: a ${name} secret erteke nem lehet ures."
      exit 1
    fi
    echo -n "${value}" | gcloud secrets create "${name}" \
      --data-file=- \
      --replication-policy=automatic \
      --quiet
    echo "Secret letrehozva: ${name}"
  fi
}

echo "Cloud Secret Manager – titkok beallitasa..."
create_secret "invoice-gcp-processor-id" "Document AI Processor ID"

echo "Cloud Run backend service letrehozasa placeholder image-dzsel..."
if gcloud run services describe "${BACKEND_SERVICE}" --region="${REGION}" >/dev/null 2>&1; then
  echo "A backend service mar letezik, kihagyva."
else
  gcloud run deploy "${BACKEND_SERVICE}" \
    --image="gcr.io/cloudrun/hello" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --service-account="${SA_EMAIL}" \
    --quiet
fi

echo "Cloud Run frontend service letrehozasa placeholder image-dzsel..."
if gcloud run services describe "${FRONTEND_SERVICE}" --region="${REGION}" >/dev/null 2>&1; then
  echo "A frontend service mar letezik, kihagyva."
else
  gcloud run deploy "${FRONTEND_SERVICE}" \
    --image="gcr.io/cloudrun/hello" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --service-account="${SA_EMAIL}" \
    --quiet
fi

echo "Nyilvanos hozzaferes (allUsers invoker) – szukseges a --allow-unauthenticated deploy-hoz..."
for SVC in "${BACKEND_SERVICE}" "${FRONTEND_SERVICE}"; do
  if cloud_run_service_exists "${SVC}" "${REGION}"; then
    if gcloud run services add-iam-policy-binding "${SVC}" \
      --region="${REGION}" \
      --member="allUsers" \
      --role="roles/run.invoker" \
      --quiet 2>/dev/null; then
      echo "  OK: ${SVC}"
    else
      echo "  Figyelem: ${SVC} – allUsers IAM nem sikerult (org policy?)"
    fi
  fi
done

BACKEND_URL=""
FRONTEND_URL=""
if cloud_run_service_exists "${BACKEND_SERVICE}" "${REGION}"; then
  BACKEND_URL="$(cloud_run_service_url "${BACKEND_SERVICE}" "${REGION}" "${PROJECT_NUMBER}")"
fi
if cloud_run_service_exists "${FRONTEND_SERVICE}" "${REGION}"; then
  FRONTEND_URL="$(cloud_run_service_url "${FRONTEND_SERVICE}" "${REGION}" "${PROJECT_NUMBER}")"
fi

echo ""
echo "Setup kesz."
if [[ -n "${BACKEND_URL}" ]]; then
  echo "Backend URL:  ${BACKEND_URL}"
fi
if [[ -n "${FRONTEND_URL}" ]]; then
  echo "Frontend URL: ${FRONTEND_URL}"
fi
echo ""
echo "Kornyezeti valtozok (masold be vagy futtasd):"
echo ""
echo "export GCP_PROJECT_ID=${PROJECT_ID}"
echo "export GCP_REGION=${REGION}"
echo "export BACKEND_SERVICE=${BACKEND_SERVICE}"
echo "export FRONTEND_SERVICE=${FRONTEND_SERVICE}"
echo ""
echo "Kovetkezo lepes: GitHub Actions WIF beallitasa (JSON kulcs nelkul):"
echo "  export GITHUB_REPO=<szervezet>/<repo-nev>"
echo "  ./scripts/setup-wif.sh"
