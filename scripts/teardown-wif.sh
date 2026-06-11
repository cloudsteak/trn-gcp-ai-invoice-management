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
CICD_SA_EMAIL="${CICD_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Hiba: allitsd be a GCP_PROJECT_ID vagy GOOGLE_CLOUD_PROJECT kornyezeti valtozot."
  exit 1
fi

echo "GCP projekt beallitasa: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

if [[ -z "${GITHUB_REPO}" ]]; then
  echo "Figyelem: GITHUB_REPO nincs megadva – a WIF principal binding torlese kihagyva."
  echo "  export GITHUB_REPO=<szervezet>/<repo-nev>"
fi

if [[ -n "${GITHUB_REPO}" ]] && gcloud iam service-accounts describe "${CICD_SA_EMAIL}" >/dev/null 2>&1; then
  echo "WIF kotes torlese a CI/CD service accountrol..."
  PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
  gcloud iam service-accounts remove-iam-policy-binding "${CICD_SA_EMAIL}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="${PRINCIPAL}" \
    --quiet 2>/dev/null || true
fi

echo "Service account szintu IAM kotések torlese..."
if gcloud iam service-accounts describe "${CICD_SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts remove-iam-policy-binding "${CICD_SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --member="serviceAccount:${CICD_SA_EMAIL}" \
    --quiet 2>/dev/null || true
fi

for BUILD_SA in "${CLOUDBUILD_SA}" "${COMPUTE_SA}"; do
  if gcloud iam service-accounts describe "${BUILD_SA}" >/dev/null 2>&1; then
    gcloud iam service-accounts remove-iam-policy-binding "${BUILD_SA}" \
      --role="roles/iam.serviceAccountUser" \
      --member="serviceAccount:${CICD_SA_EMAIL}" \
      --quiet 2>/dev/null || true
  fi
done

if gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" >/dev/null 2>&1; then
  for MEMBER in "serviceAccount:${CLOUDBUILD_SA}" "serviceAccount:${CICD_SA_EMAIL}"; do
    gcloud iam service-accounts remove-iam-policy-binding "${RUNTIME_SA_EMAIL}" \
      --role="roles/iam.serviceAccountUser" \
      --member="${MEMBER}" \
      --quiet 2>/dev/null || true
  done
fi

if gcloud iam service-accounts describe "${CLOUDBUILD_SA}" >/dev/null 2>&1; then
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/run.builder" \
    --quiet 2>/dev/null || true
fi

echo "WIF provider torlese..."
gcloud iam workload-identity-pools providers delete "${PROVIDER_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" \
  --quiet 2>/dev/null || echo "A provider nem letezik, kihagyva."

echo "WIF pool torlese..."
gcloud iam workload-identity-pools delete "${POOL_ID}" \
  --location=global \
  --quiet 2>/dev/null || echo "A pool nem letezik, kihagyva."

echo "CI/CD service account projekt IAM koteseinek torlese..."
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
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CICD_SA_EMAIL}" \
    --role="${role}" \
    --quiet 2>/dev/null || true
done

echo "CI/CD service account torlese..."
if gcloud iam service-accounts describe "${CICD_SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts delete "${CICD_SA_EMAIL}" --quiet
else
  echo "A CI/CD service account nem letezik, kihagyva."
fi

echo ""
echo "WIF teardown kesz."
