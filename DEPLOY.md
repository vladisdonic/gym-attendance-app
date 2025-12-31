# 🚀 Návod na nasadenie na Streamlit Cloud

## Krok 1: Vytvorenie GitHub repozitára

### 1.1 Inicializácia Git repozitára (ak ešte nie je)

```bash
cd "/Users/vladisdonic/appka na dochadzku do gymu"
git init
git add .
git commit -m "Initial commit - Gym attendance app"
```

### 1.2 Vytvorenie repozitára na GitHub

1. Choď na [GitHub.com](https://github.com) a prihlás sa
2. Klikni na **"New repository"** (alebo **"+"** > **"New repository"**)
3. Vyplň:
   - **Repository name:** `gym-attendance-app` (alebo iný názov)
   - **Description:** "Evidencia účasti na tréningoch"
   - **Visibility:** Private (odporúčané kvôli citlivým dátam) alebo Public
   - **NEOZAČÍNAJ** s README, .gitignore alebo licenciou (už máme)
4. Klikni **"Create repository"**

### 1.3 Push kódu na GitHub

GitHub ti zobrazí inštrukcie. Spusti tieto príkazy (nahraď `YOUR_USERNAME` a `YOUR_REPO_NAME`):

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

## Krok 2: Nastavenie Streamlit Cloud

### 2.1 Prihlásenie na Streamlit Cloud

1. Choď na [share.streamlit.io](https://share.streamlit.io/)
2. Klikni na **"Sign in"** a prihlás sa pomocou GitHub účtu
3. Povol prístup k tvojmu GitHub účtu

### 2.2 Vytvorenie novej aplikácie

1. Klikni na **"New app"**
2. Vyplň:
   - **Repository:** Vyber svoj repozitár (`gym-attendance-app`)
   - **Branch:** `main` (alebo `master`)
   - **Main file path:** `app.py`
   - **App URL:** Môžeš zvoliť vlastný (napr. `gym-attendance`)
3. Klikni na **"Advanced settings"** (dôležité!)

### 2.3 Nastavenie Secrets (KRITICKÉ!)

V sekcii **"Secrets"** pridaj obsah z tvojho `.streamlit/secrets.toml` súboru:

```toml
[gcp_service_account]
type = "service_account"
project_id = "sublime-wavelet-478010-u9"
private_key_id = "d55d311c08f125a3d6efbb9e523c7e74c6f8ae94"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCubgaWKbtjF6uw\nqrhdsYw9f+AO0MG6mjKuoeQyflEqrJ5YVJ4hbtd+lAUaca5VIqYAqTuIB7+FJ+us\n04XFPYxiS0lvv5gQmCrRgViRmPEZFKIKDTJQS1C1j2aweAeVUJPTMoEKXUQFE4+T\nfFBzLPrbfncU1gyUAT4HH1GAqvKDjfhRWwExfbEAt+fqKg0WSDALjBh+t403jD83\nJ0M8PtccgKZ+LMWUJtcAwaU4x2jud3xxrx+A69C/1+OW0WZVRQq90jOHc8Vk2nKX\n1HNSxJusergJNRQouDw3NxQS9dk+hpEx9rNoycdqZzQCCcmd2neT2QqdRWOcjHID\nBK+e4a3fAgMBAAECggEACQpz4JxIyvc4SL+4hEaxFaOcnzf2apprw72+ta1IE2BU\nvrr4DT87qnhilqnLbDyPrRttwKcM0rUsfniM3O8hPnECMpQUKNFc8B9Lp2mYHtbW\nb+iaMdY4Ld5BEibOgdCQ25KpDzqhTWq494nVzk/HsCZrEVM83f5TKDcD2EREA0nR\nFXon5gSn6DS15D8++Fl+978/+e19o2OI9QfiWuOhuKqt35dC/8pofsncIDZv8sIt\n1tg57wLUL8ZvEp0UuTgiwWebZoIyi6ANguLmcgCnIcfykk3OhRi8Mul+/u9vnWLV\n44/J8GYjRv5nyq7Q3TdP1meo8ZiQvB/NPBnUonBW3QKBgQDX4DU3NCJ0Z/98i5Lk\nBpL31flBjAdUl2OCs0yTvYrjwaGmY7lq4cdv5pMW3bjdaJh5ti9FAKW0xBggs6Zr\nbwBTD83aU2RANPZuCXlNVtJXdRI1h1sLnZXpiS965NeUAogfuMYSXCgA/EyUshFx\noAyDgMfcHUnbiMTWPnrmOU8MEwKBgQDO2bw2hrqXO4k/HwxJCKOF0PIiL5XQR75l\nehTWc0LYdxCZgxvf6Wu0CM8JzAXtxUsM9H66KhmhJPBrn95Yyxj+27kmSTsKAUIG\nRNhHQ8x/skikTT54Ny8jQ7nnmhUvbgbp4ClxvnxkySSS8ivNKv9M6aRd8pX6dBR6\nZregzir4hQKBgQDWUVmDvNaYCseytj7W80/ljSEw2fxNFx9MGwXjh0Hka9A4iLkE\nS7LcfWV6RhXKepUmAKFdOA9LL4Nks/Z8om8IB6CvKCtXMz2UcQNkrNWWzjuNuRvC\npGi4ueHReHAuGXVbSO4cPDHbCKBe34pB7EuAItJIzSsOMPJ6YP1So4K+0QKBgHwl\nxobbWgYGn5sY4WC8JJjeDVVjRgFZ7fYtzW/ggdA1terM+9/p0tCdMNXqc+x/K0o9\nPAoz1moXJ40QyHx2eSwNaBSIgzzAAIaOr1gmYwiJUnv6OHIifNInhd5xZiGvYcrg\n1T8FWteKub7QRmW/Vrcsy4/vVwCYxumn2LJUywmZAoGBAIi7snWuDyMbohPCX4Ci\ntLXU+akblDLYhP41UeO0RvQOY5zHetaACO84yAUGblVb55HYcxDVKFbexhYeADIE\nLF1LC7yxyl5mQuimpFS1qupy0g3lBzNJuiPn8/40PYzwL2sOEyAfLsVuY9D0peyW\nTXvPWC364pAdS7ERX61WJWx+\n-----END PRIVATE KEY-----\n"
client_email = "gym-attendance@sublime-wavelet-478010-u9.iam.gserviceaccount.com"
client_id = "112293347579556723171"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/gym-attendance%40sublime-wavelet-478010-u9.iam.gserviceaccount.com"
universe_domain = "googleapis.com"

spreadsheet_id = "136sfMrAvH6PqXZevImG3U9eGCremZ0xJt3SqSiU4TWI"
```

**Dôležité:**
- Skopíruj celý obsah z `.streamlit/secrets.toml`
- Presne tak, ako je (vrátane úvodzoviek a `\n` v private_key)
- Klikni **"Save"**

### 2.4 Deploy aplikácie

1. Klikni na **"Deploy!"**
2. Počkaj, kým sa aplikácia nasadí (zvyčajne 1-2 minúty)
3. Aplikácia bude dostupná na URL: `https://YOUR_APP_NAME.streamlit.app`

## Krok 3: Overenie

### 3.1 Testovanie aplikácie

1. Otvor URL tvojej aplikácie
2. Skús sa prihlásiť ako účastník
3. Skontroluj, či sa dáta ukladajú do Google Sheets

### 3.2 Kontrola Google Sheets

1. Otvor Google Sheet
2. Skontroluj, či sa vytvoril nový hárok pre dnešný deň
3. Over, či sa záznamy ukladajú správne

## Krok 4: Aktualizácia aplikácie

Keď urobíš zmeny v kóde:

```bash
git add .
git commit -m "Popis zmien"
git push
```

Streamlit Cloud automaticky deteguje zmeny a re-deployuje aplikáciu.

## Riešenie problémov

### Aplikácia sa nedeployuje

- Skontroluj, či máš správne nastavené secrets
- Over, či `requirements.txt` obsahuje všetky závislosti
- Pozri sa na logy v Streamlit Cloud dashboard

### Chyba pri pripojení k Google Sheets

- Over, či je Google Sheet zdieľaný s emailom: `gym-attendance@sublime-wavelet-478010-u9.iam.gserviceaccount.com`
- Skontroluj, či má service account práva **Editor**

### Secrets sa nenačítavajú

- Over formát v Secrets sekcii (musí byť presne ako TOML)
- Skontroluj, či sú všetky údaje správne skopírované

## Bezpečnosť

✅ **DOBRE:**
- Secrets sú uložené bezpečne v Streamlit Cloud
- `.streamlit/secrets.toml` je v `.gitignore`
- Service account má len potrebné oprávnenia

❌ **NIKDY:**
- Nekomituj `secrets.toml` do Git
- Nekomituj JSON súbory zo service accountu
- Nezdieľaj secrets s nikým

## Ďalšie kroky

1. Vytvor QR kódy s URL aplikácie
2. Nastav NFC tagy (ak používaš)
3. Informuj účastníkov o novej aplikácii

---

**URL tvojej aplikácie bude:** `https://YOUR_APP_NAME.streamlit.app`

**Pre prihlásenie:** `https://YOUR_APP_NAME.streamlit.app/?view=participant`
**Pre trénera:** `https://YOUR_APP_NAME.streamlit.app/?view=trainer`
**Pre štatistiky:** `https://YOUR_APP_NAME.streamlit.app/?view=statistics`

