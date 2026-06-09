#!/bin/bash
# =============================================================================
# GCP setup szkript – Intelligens Számlafeldolgozó
# Használat: bash infra/setup.sh <GCP_PROJECT_ID> <GITHUB_ORG/REPO>
# Példa:     bash infra/setup.sh my-gcp-project cloudsteak/trn-gcp-ai-invoice-management
# =============================================================================

set -euo pipefail

# --- Színek a kimenethez ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

step()  { echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }
ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
warn()  { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
fatal() { echo -e "\n${RED}❌ HIBA: $1${NC}\n"; exit 1; }

# =============================================================================
# 1. Paraméterek ellenőrzése
# =============================================================================
step "Paraméterek ellenőrzése"

[[ $# -lt 2 ]] && fatal "Használat: bash infra/setup.sh <GCP_PROJECT_ID> <GITHUB_ORG/REPO>"

PROJECT_ID="$1"
GITHUB_REPO="$2"   # pl. cloudsteak/trn-gcp-ai-invoice-management
REGION="europe-west1"
SA_NAME="invoice-processor-github"
POOL_NAME="invoice-processor-pool"
PROVIDER_NAME="invoice-processor-github"

ok "Project:     $PROJECT_ID"
ok "GitHub repo: $GITHUB_REPO"
ok "Region:      $REGION"

# =============================================================================
# 2. GCP projekt beállítása és PROJECT_NUMBER lekérése
# =============================================================================
step "GCP projekt beállítása"

gcloud config set project "$PROJECT_ID" --quiet
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

ok "Projekt beállítva (number: $PROJECT_NUMBER)"

# =============================================================================
# 3. Szükséges API-k engedélyezése
# =============================================================================
step "API-k engedélyezése (ez eltarthat 1-2 percig)"

APIS=(
  "documentai.googleapis.com"
  "aiplatform.googleapis.com"
  "run.googleapis.com"
  "cloudbuild.googleapis.com"
  "secretmanager.googleapis.com"
  "iam.googleapis.com"
  "iamcredentials.googleapis.com"
)

for api in "${APIS[@]}"; do
  gcloud services enable "$api" --quiet
  ok "$api"
done

# =============================================================================
# 4. Service Account létrehozása
# =============================================================================
step "Service Account létrehozása"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" --quiet &>/dev/null; then
  warn "Service Account már létezik, kihagyva: $SA_EMAIL"
else
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Deploy" \
    --quiet
  ok "Létrehozva: $SA_EMAIL"
fi

# =============================================================================
# 5. IAM jogosultságok kiosztása
# =============================================================================
step "IAM jogosultságok kiosztása"

ROLES=(
  "roles/run.admin"
  "roles/cloudbuild.builds.builder"
  "roles/secretmanager.secretAccessor"
  "roles/iam.serviceAccountUser"
  "roles/storage.admin"
)

for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --quiet &>/dev/null
  ok "$role"
done

# Cloud Build service account-nak is kell Secret Manager hozzáférés
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet &>/dev/null
ok "Cloud Build SA – secretmanager.secretAccessor"

# =============================================================================
# 6. Workload Identity Federation beállítása
# =============================================================================
step "Workload Identity Federation – Pool létrehozása"

if gcloud iam workload-identity-pools describe "$POOL_NAME" \
     --location=global --quiet &>/dev/null; then
  warn "WIF Pool már létezik, kihagyva"
else
  gcloud iam workload-identity-pools create "$POOL_NAME" \
    --location=global \
    --display-name="GitHub Actions Pool" \
    --quiet
  ok "Pool létrehozva: $POOL_NAME"
fi

step "Workload Identity Federation – Provider létrehozása"

if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
     --workload-identity-pool="$POOL_NAME" \
     --location=global --quiet &>/dev/null; then
  warn "WIF Provider már létezik, kihagyva"
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
    --location=global \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --quiet
  ok "Provider létrehozva: $PROVIDER_NAME"
fi

step "WIF – Service Account binding"

PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL" \
  --quiet &>/dev/null
ok "Binding beállítva"

# =============================================================================
# 7. Cloud Secret Manager – titkok létrehozása
# =============================================================================
step "Cloud Secret Manager – titkok beállítása"
echo ""
echo -e "  ${YELLOW}Az API kulcsok és azonosítók most kerülnek a Secret Manager-be."
echo -e "  Ezek soha nem kerülnek a git repóba.${NC}"
echo ""

create_secret() {
  local name="$1"
  local prompt="$2"
  local value

  if gcloud secrets describe "$name" --quiet &>/dev/null; then
    warn "Secret már létezik, kihagyva: $name"
  else
    echo -ne "  ${BOLD}${prompt}:${NC} "
    read -r value
    [[ -z "$value" ]] && fatal "Nem lehet üres: $name"
    echo -n "$value" | gcloud secrets create "$name" \
      --data-file=- \
      --replication-policy=automatic \
      --quiet
    ok "Secret létrehozva: $name"
  fi
}

create_secret "invoice-gcp-processor-id" "Document AI Processor ID"
create_secret "invoice-gemini-api-key"   "Gemini API Key"

# =============================================================================
# 8. Eredmény – GitHub Secrets értékei
# =============================================================================
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

echo ""
echo -e "${GREEN}${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ Setup sikeresen befejezve!${NC}"
echo -e "${GREEN}${BOLD}============================================================${NC}"
echo ""
echo -e "${BOLD}Másold be ezeket a GitHub Secrets-be${NC}"
echo -e "(Repo → Settings → Secrets and variables → Actions → New repository secret)"
echo ""
echo -e "  ${BOLD}GCP_PROJECT_ID${NC}"
echo -e "  ${YELLOW}${PROJECT_ID}${NC}"
echo ""
echo -e "  ${BOLD}GCP_WORKLOAD_IDENTITY_PROVIDER${NC}"
echo -e "  ${YELLOW}${WIF_PROVIDER}${NC}"
echo ""
echo -e "  ${BOLD}GCP_SERVICE_ACCOUNT${NC}"
echo -e "  ${YELLOW}${SA_EMAIL}${NC}"
echo ""
echo -e "  ${BOLD}VITE_API_BASE_URL${NC}"
echo -e "  ${YELLOW}(az első backend deploy után lesz ismert a Cloud Run URL)${NC}"
echo ""
echo -e "${BLUE}${BOLD}Következő lépés:${NC} Document AI processzor létrehozása a GCP Console-ban"
echo -e "  GCP Console → Document AI → Processors → Create → Invoice Parser"
echo ""
