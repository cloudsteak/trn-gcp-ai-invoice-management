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

Hozz létre egy Pull Request-et a `main` branch-re. A deploy automatikusan elindul, amikor a PR merge-elve lesz.

```bash
git checkout -b deploy/initial-setup
git add .
git commit -m "Initial deployment"
git push origin deploy/initial-setup
```

Majd GitHub-on: **New Pull Request → merge → Actions** fül.

A GitHub Actions automatikusan elindítja a deployt:
- Ha a `backend/` mappa változott → backend deploy fut
- Ha a `frontend/` mappa változott → frontend deploy fut

A folyamat élőben követhető: **GitHub → Actions** fül.

---

### 6. lépés – VITE_API_BASE_URL beállítása

Az első backend deploy után a Cloud Run megad egy URL-t (pl. `https://invoice-processor-backend-xyz-ew.a.run.app`).

1. Másold ki ezt az URL-t a GitHub Actions logból
2. Add hozzá GitHub Secrets-hez: `VITE_API_BASE_URL` = az URL
3. Hozz létre egy új PR-t a frontend újradeploy-ához:

```bash
git checkout -b deploy/set-frontend-url
git commit --allow-empty -m "Set VITE_API_BASE_URL, redeploy frontend"
git push origin deploy/set-frontend-url
```

Majd GitHub-on: **New Pull Request → merge**.

---

## Demo újraindítása

A demo naponta többször is lefuttatható. A teardown script minden GCP erőforrást töröl, utána a setup script újra elvégez mindent.

### Teardown – minden törlése

```bash
bash infra/teardown.sh <GCP_PROJECT_ID>
```

**Törli:**
- Cloud Run service-ek (`invoice-processor-backend`, `invoice-processor-frontend`)
- Secret Manager titkok (`invoice-gcp-processor-id`, `invoice-gemini-api-key`)
- Workload Identity Federation pool és provider
- Service Account (`invoice-processor-github`)

> A script megerősítést kér (`igen` beírása) – véletlenszerű futtatás ellen.

### Újraindítás

```bash
bash infra/setup.sh <GCP_PROJECT_ID> <GITHUB_ORG/REPO>
```

Ezután a GitHub Secrets értékeit frissíteni kell az új WIF provider és Service Account adataival (a script kiírja a végén), majd egy új PR merge-elésével indul a deployment.

---

## Lokális fejlesztés

### 1. .env fájl létrehozása

```bash
cp .env.example backend/.env
```

Nyisd meg a `backend/.env` fájlt és töltsd ki a kötelező értékeket:

| Változó | Hol szerzed meg |
|---------|----------------|
| `GCP_PROJECT_ID` | GCP Console → projekt azonosító |
| `GCP_PROCESSOR_ID` | Document AI → processzor részletek → Processor ID |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |

> A többi értéknek van alapértelmezése – lokális teszteléshez nem kell módosítani.

### 2. Backend indítása

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

Az API dokumentáció elérhető: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend indítása (új terminálban)

```bash
cd frontend
npm install
npm run dev
```

A frontend elérhető: [http://localhost:3000](http://localhost:3000)

> **Megjegyzés a proxyról:** fejlesztés közben a Vite dev szerver a `/api/*` kéréseket automatikusan átirányítja a `http://localhost:8000` backend felé. Ez csak lokálisan működik – Cloud Run-on a frontend közvetlenül a backend Cloud Run URL-jére hív (a `VITE_API_BASE_URL` build-time változóból), proxy nélkül.

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
