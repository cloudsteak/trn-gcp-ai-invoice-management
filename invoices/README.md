# Fiktív demó számlák

Minden fájl **oktatási és tesztelési célú**, fiktív adatokkal. Könyvelésre, NAV adatszolgáltatásra és fizetésre **nem használható**.

A repóban lévő PDF/JPG minták **eredeti demó anyagok** – ne módosítsd és ne írd felül őket a generátor scripttel.

## Tesztkészlet

| Fájl | Leírás | Elvárt eredmény |
|------|--------|-----------------|
| `01_helyes_alap.pdf` | Helyes magyar minta, alap mezőkkel | ✅ Rendben |
| `02_helyes_minta_tobb_tetel.pdf` | Helyes minta több tételsorral | ✅ Rendben *(DocAI 500 esetén PDF+Gemini fallback)* |
| `03_helyes_angol.pdf` | Szabályos angol PDF számla | ✅ Rendben |
| `04_hibas_hianyzo_teljesitesi_datum.pdf` | Hiányzó teljesítés dátuma | ⚠️ Figyelmeztetés *(DocAI gyakran 500 – fallback)* |
| `05_hibas_nem_teteles_afa_osszesito.pdf` | Nem tételsoros ÁFA összesítő | ⚠️ Figyelmeztetés |
| `06_hibas_hianyzo_vevoi_adoszam.pdf` | Hiányzó vevői adószám | ⚠️ Figyelmeztetés |
| `07_hibas_kezzel_irt.jpg` | Kézzel írt stílus, **eladó adószám nélkül** | ❌ Hiba |

### Státusz jelentés

| Ikon | Jelentés |
|------|----------|
| ✅ | Minden lényeges mező rendben, nincs blokkoló hiba |
| ⚠️ | Feldolgozható, de validációs figyelmeztetés (pl. hiányzó dátum, összeg-eltérés) |
| ❌ | Blokkoló hiba (pl. hiányzó eladó adószám) |

## Ajánlott demo forgatókönyvek

### Gyors batch (4 fájl)

Töltsd fel egyszerre: `01`, `03`, `06`, `07` → összesített táblázat → részletes riport → export (PDF / XLSX / könyvelői adatlap).

### Teljes batch (7 fájl)

Mind a hét fájl – Document AI terhelés miatt a feldolgozás **fájlonként sorban** fut, eredmények fokozatosan jelennek meg.

> **DocAI 500:** Egyes PDF-eknél (pl. `02`, `04`) a Document AI átmeneti hibát adhat. Ilyenkor a backend automatikusan a **PDF beágyazott szövegéből + Gemini** fallbacket használ – a helyes minták továbbra is ✅ státuszt kaphatnak.

## Fájlok és feldolgozás

| # | Típus | Document AI | Megjegyzés |
|---|-------|-------------|------------|
| 01–03 | Helyes minták | Normál | DocAI + Gemini validáció |
| 04 | Hiányzó mező | Gyakran 500 | Fallback + Gemini jelzi a hiányt |
| 05 | ÁFA összesítő | Normál / vegyes | Gemini / szabályalapú ellenőrzés |
| 06 | Hiányzó vevő adószám | Normál | ⚠️ – vevő adószám nem blokkoló |
| 07 | JPG, kézzel írt | OCR | ❌ – **eladó** adószám hiánya hiba |

## Generátor script (opcionális)

A `scripts/generate_demo_invoices.py` **csak** két extra fájlt készít régi néven (`szamla_ok_en.pdf`, `szamla_kezzel_irt.jpg`) – ezek **nem** azonosak a fenti `03` / `07` fájlokkal, és **nem írják felül** a számozott mintákat.

```bash
cd backend
uv run --with pillow python ../scripts/generate_demo_invoices.py
```

A batch demóhoz használd a fenti **`01`–`07`** fájlokat.
