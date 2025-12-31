# 🥊 Evidencia účasti na tréningoch

Jednoduchá Streamlit aplikácia na evidenciu účasti na tréningoch s Google Sheets ako databázou.

## Funkcie

- **Prihlásenie účastníkov** - cez QR kód alebo NFC tag
- **Evidencia údajov** - meno, typ členstva, typ tréningu
- **Prehľad pre trénera** - počet prihlásených, štatistiky
- **Automatické hárky** - pre každý deň sa vytvorí nový hárok

## Inštalácia

### 1. Klonovanie a závislosti

```bash
git clone <repo-url>
cd training_attendance
pip install -r requirements.txt
```

### 2. Nastavenie Google Sheets API

1. Choď na [Google Cloud Console](https://console.cloud.google.com/)
2. Vytvor nový projekt (alebo použi existujúci)
3. Povoľ **Google Sheets API** a **Google Drive API**:
   - APIs & Services > Library > vyhľadaj "Google Sheets API" > Enable
   - To isté pre "Google Drive API"
4. Vytvor Service Account:
   - APIs & Services > Credentials > Create Credentials > Service Account
   - Vyplň názov a popis
   - Klikni na vytvorený service account
   - Keys > Add Key > Create new key > JSON
   - Stiahni JSON súbor

### 3. Vytvorenie Google Sheetu

1. Vytvor nový Google Sheet
2. Skopíruj ID z URL: `https://docs.google.com/spreadsheets/d/[TOTO_JE_ID]/edit`
3. Zdieľaj Sheet s emailom service accountu (nájdeš v JSON ako `client_email`) - daj mu práva **Editor**

### 4. Konfigurácia aplikácie

Vytvor súbor `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "service-account@project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"

spreadsheet_id = "your-google-sheet-id"
```

**Tip:** Obsah JSON súboru zo Service Account skopíruj do `[gcp_service_account]` sekcie.

### 5. Spustenie

```bash
streamlit run app.py
```

Aplikácia beží na `http://localhost:8501`

## Použitie

### URL parametre

- **Účastník (default):** `http://localhost:8501/?view=participant`
- **Tréner:** `http://localhost:8501/?view=trainer`

### QR kódy a NFC

1. Vygeneruj QR kód s URL pre prihlásenie:
   - Použi [QR Code Generator](https://www.qr-code-generator.com/)
   - URL: `https://your-app.streamlit.app/?view=participant`

2. Pre NFC tagy:
   - Naprogramuj NFC tag s rovnakou URL
   - Účastník priloží telefón k tagu a otvorí sa stránka na prihlásenie

### Workflow

1. **Účastník** príde do gymu
2. Naskenuje QR kód alebo priloží telefón k NFC tagu
3. Zadá meno a vyberie typ členstva
4. Klikne "Prihlásiť sa"
5. **Tréner** má otvorený prehľad a vidí počet prihlásených

## Nasadenie na Streamlit Cloud

1. Pushni kód na GitHub
2. Choď na [share.streamlit.io](https://share.streamlit.io/)
3. Pripoj svoj GitHub repozitár
4. V Advanced settings pridaj secrets (obsah `secrets.toml`)
5. Deploy!

## Štruktúra Google Sheetu

Pre každý deň sa automaticky vytvorí nový hárok s názvom v formáte `YYYY-MM-DD`.

| Čas | Meno | Typ členstva | Tréning | Poznámka |
|-----|------|--------------|---------|----------|
| 18:30:15 | Ján Novák | Mesačné členstvo | Muay Thai | |
| 18:32:45 | Peter Horák | 10-vstupová permanentka | Box | |

## Prispôsobenie

### Typy členstva

Uprav zoznam `MEMBERSHIP_TYPES` v `app.py`:

```python
MEMBERSHIP_TYPES = [
    "Mesačné členstvo",
    "Štvrťročné členstvo",
    # ... pridaj vlastné
]
```

### Typy tréningov

Uprav selectbox v funkcii `participant_view()`:

```python
training = st.selectbox(
    "Typ tréningu",
    options=["", "Muay Thai", "Box", "MMA", ...],
)
```

## Licencia

MIT
