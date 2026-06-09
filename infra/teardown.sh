#!/bin/bash
# =============================================================================
# GCP teardown szkript – Intelligens Számlafeldolgozó
# Minden létrehozott GCP erőforrást töröl, hogy a demo újrafuttatható legyen.
# Használat: bash infra/teardown.sh <GCP_PROJECT_ID>
# Példa:     bash infra/teardown.sh my-gcp-project
# =============================================================================

set -euo pipefail

# --- Színek a kimenethez ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }
ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
warn()  { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
fatal() { echo -e "\n${RED}❌ HIBA: $1${NC}\n"; exit 1; }

# =============================================================================
# Előfeltételek és paraméterek
# =============================================================================
command -v gcloud &>/dev/null || fatal "A Google Cloud SDK (gcloud) nincs telepítve."
gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q "@" || fatal "Nincs aktív gcloud bejelentkezés. Futtasd: gcloud auth login"

[[ $# -lt 1 ]] && fatal "Használat: bash infra/teardown.sh <GCP_PROJECT_ID>"

PROJECT_ID="$1"
REGION="europe-west1"
SA_NAME="invoice-processor-github"
POOL_NAME="invoice-processor-pool"
PROVIDER_NAME="invoice-processor-github"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo -e "${RED}${BOLD}============================================================${NC}"
echo -e "${RED}${BOLD}  ⚠️  FIGYELEM: Ez a szkript MINDENT töröl!${NC}"
echo -e "${RED}${BOLD}============================================================${NC}"
echo ""
echo -e "  Projekt:  ${YELLOW}${PROJECT_ID}${NC}"
echo -e "  Törli:    Cloud Run service-ek, Service Account, WIF pool, Secrets"
echo ""
echo -ne "${BOLD}Biztosan folytatod? (igen/nem): ${NC}"
read -r confirm
[[ "$confirm" != "igen" ]] && { echo "Megszakítva."; exit 0; }

gcloud config set project "$PROJECT_ID" --quiet

# =============================================================================
# 1. Cloud Run service-ek törlése
# =============================================================================
step "Cloud Run service-ek törlése"

for service in invoice-processor-backend invoice-processor-frontend; do
  if gcloud run services describe "$service" --region="$REGION" --quiet &>/dev/null; then
    gcloud run services delete "$service" --region="$REGION" --quiet
    ok "Törölve: $service"
  else
    warn "Nem található, kihagyva: $service"
  fi
done

# =============================================================================
# 2. Secret Manager – titkok törlése
# =============================================================================
step "Secret Manager – titkok törlése"

for secret in invoice-gcp-processor-id invoice-gemini-api-key; do
  if gcloud secrets describe "$secret" --quiet &>/dev/null; then
    gcloud secrets delete "$secret" --quiet
    ok "Törölve: $secret"
  else
    warn "Nem található, kihagyva: $secret"
  fi
done

# =============================================================================
# 3. Workload Identity Federation törlése
# =============================================================================
step "WIF Provider törlése"

if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
     --workload-identity-pool="$POOL_NAME" --location=global --quiet &>/dev/null; then
  gcloud iam workload-identity-pools providers delete "$PROVIDER_NAME" \
    --workload-identity-pool="$POOL_NAME" \
    --location=global \
    --quiet
  ok "Provider törölve: $PROVIDER_NAME"
else
  warn "Provider nem található, kihagyva"
fi

step "WIF Pool törlése"

if gcloud iam workload-identity-pools describe "$POOL_NAME" \
     --location=global --quiet &>/dev/null; then
  gcloud iam workload-identity-pools delete "$POOL_NAME" \
    --location=global \
    --quiet
  ok "Pool törölve: $POOL_NAME"
else
  warn "Pool nem található, kihagyva"
fi

# =============================================================================
# 4. Service Account törlése
# =============================================================================
step "Service Account törlése"

if gcloud iam service-accounts describe "$SA_EMAIL" --quiet &>/dev/null; then
  gcloud iam service-accounts delete "$SA_EMAIL" --quiet
  ok "Törölve: $SA_EMAIL"
else
  warn "Nem található, kihagyva: $SA_EMAIL"
fi

# =============================================================================
# Kész
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ Teardown kész – a projekt újra tiszta!${NC}"
echo -e "${GREEN}${BOLD}============================================================${NC}"
echo ""
echo -e "${BLUE}${BOLD}Újra futtatható:${NC} bash infra/setup.sh ${PROJECT_ID} <GITHUB_ORG/REPO>"
echo ""
