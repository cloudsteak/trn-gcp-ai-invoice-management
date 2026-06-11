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

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Hiba: allitsd be a GCP_PROJECT_ID vagy GOOGLE_CLOUD_PROJECT kornyezeti valtozot."
  exit 1
fi

echo "GCP projekt beallitasa: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Cloud Run backend service torlese..."
if cloud_run_service_exists "${BACKEND_SERVICE}" "${REGION}"; then
  gcloud run services delete "${BACKEND_SERVICE}" --region="${REGION}" --quiet
else
  echo "A backend service nem letezik, kihagyva."
fi

echo "Cloud Run frontend service torlese..."
if cloud_run_service_exists "${FRONTEND_SERVICE}" "${REGION}"; then
  gcloud run services delete "${FRONTEND_SERVICE}" --region="${REGION}" --quiet
else
  echo "A frontend service nem letezik, kihagyva."
fi

echo "Secret Manager titkok torlese..."
for secret in invoice-gcp-processor-id; do
  if gcloud secrets describe "${secret}" >/dev/null 2>&1; then
    gcloud secrets delete "${secret}" --quiet
    echo "Torolve: ${secret}"
  else
    echo "Secret nem letezik, kihagyva: ${secret}"
  fi
done

echo "Service account IAM koteseinek torlese (${SERVICE_ACCOUNT})..."
for role in roles/documentai.apiUser roles/secretmanager.secretAccessor roles/aiplatform.user; do
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --quiet 2>/dev/null || true
done

echo "Cloud Build SA IAM koteseinek torlese..."
if gcloud iam service-accounts describe "${CLOUDBUILD_SA}" >/dev/null 2>&1; then
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || true
fi

echo "Service account torlese..."
if gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts delete "${SA_EMAIL}" --quiet
else
  echo "A service account nem letezik, kihagyva."
fi

echo ""
echo "Teardown kesz (runtime infrastruktura)."
echo "Kovetkezo lepes: ./scripts/teardown-wif.sh (GitHub Actions WIF + CI/CD SA)"
