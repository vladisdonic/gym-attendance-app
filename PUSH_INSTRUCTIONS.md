# 🚀 Rýchly návod na Push na GitHub

## Krok 1: Vytvorenie Personal Access Token

1. Choď na: **https://github.com/settings/tokens**
2. Klikni **"Generate new token"** > **"Generate new token (classic)"**
3. Vyplň:
   - **Note:** `Streamlit Deploy`
   - **Expiration:** Vyber si (napr. 90 dní alebo No expiration)
   - **Select scopes:** Zaškrtni **`repo`** (celé oprávnenie)
4. Klikni **"Generate token"** (dole)
5. **SKOPÍRUJ TOKEN** (zobrazí sa len raz!)

## Krok 2: Push na GitHub

Spusti tento príkaz:

```bash
cd "/Users/vladisdonic/appka na dochadzku do gymu"
git push -u origin main
```

Keď sa ťa opýta:
- **Username:** `vladisdonic`
- **Password:** Vlož **skopírovaný token** (nie heslo!)

## Alternatíva: Použitie tokenu priamo v URL

Ak nechceš zadávať údaje zakaždým, môžeš použiť:

```bash
git remote set-url origin https://vladisdonic:TVOJ_TOKEN@github.com/vladisdonic/gym-attendance-app.git
git push -u origin main
```

(Nahraď `TVOJ_TOKEN` skutočným tokenom)

## Po úspešnom pushi:

1. Choď na: **https://github.com/vladisdonic/gym-attendance-app**
2. Over, či sú tam všetky súbory
3. Potom pokračuj na Streamlit Cloud: **https://share.streamlit.io/**





