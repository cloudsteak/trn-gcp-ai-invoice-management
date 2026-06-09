# Intelligens Számlafeldolgozó
### Google Cloud Platform AI – Képzési Demo

Ez az alkalmazás bemutatja, hogyan lehet a **Google Cloud Document AI** és a **Gemini API** kombinációjával egy valós üzleti problémát – a számlafeldolgozást – automatizálni. A teljes megoldás forráskódból, Docker nélkül deployolható Google Cloud Run-ra GitHub Actions segítségével.

---

## Mit mutat be ez az alkalmazás?

| Google Cloud szolgáltatás | Szerepe |
|--------------------------|---------|
| **Document AI** – Invoice Parser | Strukturált adatkinyerés a számlából (partner, összegek, dátumok, tételek) |
| **Gemini API** | Hiányzó mezők pótlása, ÁFA-validáció, anomália-detektálás, könyvelői értékelés |
| **Cloud Run** | Szervernélküli futtatás – csak akkor fizetsz, ha kérés érkezik |
| **Cloud Build** | Automatikus build forráskódból, Dockerfile nélkül |
| **Secret Manager** | API kulcsok és azonosítók biztonságos tárolása |
| **Workload Identity Federation** | GitHub Actions hitelesítés service account JSON kulcs nélkül |

---

## Architektúra

```
GitHub (push → main)
    │
    ▼
GitHub Actions
    ├── deploy-backend  ──▶  Cloud Run (FastAPI)  ──▶  Document AI + Gemini
    └── deploy-frontend ──▶  Cloud Run (React/Vite)
```

A deployment **Docker nélkül** történik: a Cloud Build automatikusan felismeri a Python ill. Node.js környezetet (Cloud Buildpacks), és forráskódból build-eli az image-et.

---

## Telepítés – élő demo (10–15 perc)

### Előfeltételek

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) telepítve és bejelentkezve
- GCP projekt létrehozva, számlázás engedélyezve
- GitHub repository fork-olva vagy klónozva
- Gemini API kulcs (Google AI Studio)

---

### 1. lépés – Bejelentkezés és projekt beállítása

```bash
gcloud auth login
gcloud config set project <GCP_PROJECT_ID>
```

---

### 2. lépés – GCP automatikus beállítása

Ez az egyetlen script elvégez minden GCP-oldali előkészületet:

```bash
bash infra/setup.sh <GCP_PROJECT_ID> <GITHUB_ORG/REPO>
```

**Példa:**
```bash
bash infra/setup.sh my-gcp-project cloudsteak/trn-gcp-ai-invoice-management
```

**A script elvégzi:**
- Szükséges API-k engedélyezése (Document AI, Gemini, Cloud Run, Cloud Build, Secret Manager)
- Service Account létrehozása (`invoice-processor-github`)
- IAM jogosultságok kiosztása
- Workload Identity Federation beállítása (keyless GitHub auth)
- Gemini API kulcs és egyéb titkok feltöltése a Secret Manager-be

**A script végén** megjelenik a négy GitHub Secret értéke, készen a beillesztésre.

---

### 3. lépés – Document AI processzor létrehozása

Ez a lépés a GCP Console-ban történik, mert jól látható a felületen:

1. Nyisd meg: [GCP Console → Document AI](https://console.cloud.google.com/ai/document-ai)
2. **Create Processor** → **Invoice Parser**
3. Név: `invoice-processor`, Region: `eu`
4. A létrehozás után másold ki a **Processor ID**-t

Ezt az értéket add hozzá a Secret Manager-hez:

```bash
echo -n "<PROCESSOR_ID>" | gcloud secrets create invoice-gcp-processor-id --data-file=-
```

---

### 4. lépés – GitHub Secrets beállítása

GitHub repository → **Settings → Secrets and variables → Actions**

**Secrets** (titkos értékek – nem látszanak a logban):

| Secret neve | Értéke |
|-------------|--------|
| `GCP_PROJECT_ID` | GCP projekt azonosítója |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/.../providers/invoice-processor-github` |
| `GCP_SERVICE_ACCOUNT` | `invoice-processor-github@<project>.iam.gserviceaccount.com` |
| `VITE_API_BASE_URL` | *(az első backend deploy után töltsd ki)* |

**Variables** (nem titkos konfigurációs értékek – a GitHub Actions logban láthatók, bármikor szerkeszthetők):

| Variable neve | Alapértelmezett érték |
|---------------|----------------------|
| `GCP_LOCATION` | `eu` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `MAX_FILE_SIZE_MB` | `20` |
| `MAX_FILES_PER_BATCH` | `10` |
| `UPLOAD_DIR` | `/tmp/invoices` |
| `CORS_ORIGINS` | `*` |

---

### 5. lépés – Deployment indítása

```bash
git push origin main
```

A GitHub Actions automatikusan elindítja a deployt:
- Ha a `backend/` mappa változott → backend deploy fut
- Ha a `frontend/` mappa változott → frontend deploy fut

A folyamat élőben követhető: **GitHub → Actions** fül.

---

### 6. lépés – VITE_API_BASE_URL beállítása

Az első backend deploy után a Cloud Run megad egy URL-t (pl. `https://invoice-processor-backend-xyz-ew.a.run.app`).

1. Másold ki ezt az URL-t a GitHub Actions logból
2. Add hozzá GitHub Secrets-hez: `VITE_API_BASE_URL` = az URL
3. Triggereld a frontend deployt egy kis módosítással vagy manuálisan:

```bash
# Manuális trigger (workflow_dispatch hozzáadása után), vagy:
git commit --allow-empty -m "trigger frontend deploy" && git push origin main
```

---

## Lokális fejlesztés

```bash
# .env fájl létrehozása a sablon alapján
cp .env.example .env
# Töltsd ki a .env értékeit

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (új terminálban)
cd frontend
npm install
npm run dev
```

---

## Projekt struktúra

```
├── backend/               # FastAPI alkalmazás
│   ├── main.py
│   ├── config.py
│   ├── routers/           # API endpointok (upload, process, export)
│   ├── services/          # Document AI, Gemini, export logika
│   ├── models/            # Pydantic adatmodellek
│   └── utils/
├── frontend/              # React 18 + Vite + TailwindCSS
│   └── src/
│       ├── components/    # UI komponensek
│       ├── hooks/         # useUpload, useProcessing
│       └── services/      # Backend API hívások
├── infra/
│   └── setup.sh           # GCP egylépéses beállítás
├── .github/
│   └── workflows/
│       └── deploy.yml     # GitHub Actions CI/CD
└── .env.example           # Környezeti változók sablonja
```

---

## Hogyan működik a Workload Identity Federation?

A hagyományos megközelítés: GitHub Actions kap egy JSON kulcsfájlt, amit el kell tárolni GitHub Secrets-ben. Ez a kulcs bármikor kompromittálódhat.

A WIF megközelítés: GitHub Actions egy rövid életű tokent kap az OIDC protokollon keresztül, amelyet a GCP elfogad – **nincs hosszú életű kulcs, nincs mit ellopni.**

```
GitHub Actions runner
    │
    │  OIDC token (assertion.repository = "cloudsteak/...")
    ▼
Google STS (Security Token Service)
    │  Ellenőrzi: valóban ez a repo küldte?
    │  Kiad: rövid életű GCP access token
    ▼
Cloud Run deploy fut a Service Account nevében
```

---

## Technológiai stack

| Réteg | Technológia |
|-------|-------------|
| Frontend | React 18 + Vite + TailwindCSS |
| Backend | Python 3.12 + FastAPI |
| AI – Kinyerés | Google Cloud Document AI (Invoice Parser) |
| AI – Validáció | Google Gemini API (`gemini-flash-lite`) |
| Deployment | Google Cloud Run (source deploy, Docker nélkül) |
| CI/CD | GitHub Actions + Workload Identity Federation |
| Titkok | Google Cloud Secret Manager |
| Export | ReportLab (PDF), openpyxl (XLSX), csv |
