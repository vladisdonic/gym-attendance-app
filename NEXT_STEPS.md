# 🚀 Ďalšie kroky - Nasadenie na Streamlit Cloud

## ✅ Čo je hotové:

- ✅ Všetky zmeny sú commitnuté (3 commity)
- ✅ Ochrana heslom pre trénerskú časť (`supernova`)
- ✅ Aplikácia funguje lokálne

## 📤 Krok 1: Push na GitHub

Spusti jeden z týchto príkazov:

```bash
./push_to_github.sh
```

alebo manuálne:

```bash
git push -u origin main
```

**Ak sa ťa opýta na prihlasovacie údaje:**
- **Username:** `vladisdonic`
- **Password:** Použij **Personal Access Token** (nie heslo!)

### Ako vytvoriť Personal Access Token:

1. Choď na: https://github.com/settings/tokens
2. Klikni **"Generate new token"** > **"Generate new token (classic)"**
3. Daj mu názov: `Streamlit Deploy`
4. Vyber oprávnenie: **`repo`** (celé)
5. Klikni **"Generate token"**
6. **Skopíruj token** (zobrazí sa len raz!)
7. Použij ho ako heslo pri pushi

---

## 🌐 Krok 2: Nasadenie na Streamlit Cloud

### 2.1 Prihlásenie

1. Choď na **https://share.streamlit.io/**
2. Klikni **"Sign in"**
3. Prihlás sa pomocou **GitHub účtu** (rovnaký ako `vladisdonic`)

### 2.2 Vytvorenie aplikácie

1. Klikni na **"New app"** (alebo **"Deploy an app"**)
2. Vyplň formulár:
   - **Repository:** `vladisdonic/gym-attendance-app`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** (môžeš zvoliť vlastný, napr. `gym-attendance`)
3. Klikni na **"Advanced settings"** ⚙️ (dôležité!)

### 2.3 Nastavenie Secrets (KRITICKÉ!)

V sekcii **"Secrets"** pridaj tento obsah:

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
- Skopíruj celý obsah presne tak, ako je
- Klikni **"Save"**

### 2.4 Deploy

1. Klikni na **"Deploy!"**
2. Počkaj 1-2 minúty, kým sa aplikácia nasadí
3. Aplikácia bude dostupná na: `https://TVAJA-APP-URL.streamlit.app`

---

## ✅ Krok 3: Overenie

### 3.1 Testovanie aplikácie

1. Otvor URL tvojej aplikácie
2. **Test účastníka:**
   - URL: `https://TVAJA-APP-URL.streamlit.app/?view=participant`
   - Skús sa prihlásiť na tréning
   - Over, či sa dáta ukladajú do Google Sheets

3. **Test trénera:**
   - URL: `https://TVAJA-APP-URL.streamlit.app/?view=trainer`
   - Mala by sa zobraziť prihlasovacia stránka
   - Zadaj heslo: `supernova`
   - Mala by sa zobraziť trénerská časť

4. **Test štatistík:**
   - URL: `https://TVAJA-APP-URL.streamlit.app/?view=statistics`
   - Mala by sa zobraziť prihlasovacia stránka
   - Zadaj heslo: `supernova`
   - Mala by sa zobraziť sekcia štatistík

### 3.2 Kontrola Google Sheets

1. Otvor Google Sheet: https://docs.google.com/spreadsheets/d/136sfMrAvH6PqXZevImG3U9eGCremZ0xJt3SqSiU4TWI/edit
2. Skontroluj, či sa vytvoril nový hárok pre dnešný deň
3. Over, či sa záznamy ukladajú správne

---

## 🔐 Dôležité informácie

### Heslo pre trénera:
- **Heslo:** `supernova`
- Platí pre: Trénerský prehľad a Štatistiky

### URL linky pre aplikáciu:

- **Účastník:** `https://TVAJA-APP-URL.streamlit.app/?view=participant`
- **Tréner:** `https://TVAJA-APP-URL.streamlit.app/?view=trainer`
- **Štatistiky:** `https://TVAJA-APP-URL.streamlit.app/?view=statistics`

### Google Sheet:
- **ID:** `136sfMrAvH6PqXZevImG3U9eGCremZ0xJt3SqSiU4TWI`
- **Service Account Email:** `gym-attendance@sublime-wavelet-478010-u9.iam.gserviceaccount.com`
- **Uisti sa, že Sheet je zdieľaný s týmto emailom s právami Editor!**

---

## 🐛 Riešenie problémov

### Aplikácia sa nedeployuje
- Skontroluj, či máš správne nastavené secrets
- Over, či `requirements.txt` obsahuje všetky závislosti
- Pozri sa na logy v Streamlit Cloud dashboard

### Chyba pri pripojení k Google Sheets
- Over, či je Google Sheet zdieľaný s emailom service accountu
- Skontroluj, či má service account práva **Editor**

### Secrets sa nenačítavajú
- Over formát v Secrets sekcii (musí byť presne ako TOML)
- Skontroluj, či sú všetky údaje správne skopírované

---

## 📝 Aktualizácia aplikácie

Keď urobíš zmeny v kóde:

```bash
git add .
git commit -m "Popis zmien"
git push
```

Streamlit Cloud automaticky deteguje zmeny a re-deployuje aplikáciu (zvyčajne do 1-2 minút).

---

**Veľa šťastia s nasadením! 🚀**

