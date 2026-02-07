# Bod 1: Firebase projekt a Hosting

## Čo už máš v projekte

- **firebase.json** – Hosting je nakonfigurovaný: `public: "dist"`, všetky cesty smerujú na `index.html` (SPA). Stačí.
- **firestore.rules** – pravidlá pre Firestore (už máš).
- **.firebaserc** – zatiaľ chýba (projekt ešte nie je prepojený).

---

## Kroky na dokončenie bodu 1

### 1. Firebase Console – projekt a Hosting

1. Otvor [Firebase Console](https://console.firebase.google.com/).
2. Vyber existujúci projekt (ten, v ktorom máš Auth a Firestore) alebo vytvor nový.
3. V ľavom menu: **Build** → **Hosting**.
4. Ak Hosting ešte nebol zapnutý, klikni **Get started** a dokonči úvodný wizard (môžeš nahrávať prázdny placeholder – potom nahradíme deployom z CLI).
5. Poznač si **Project ID** (v nastaveniach projektu: ikona ozubeného kolieska → Project settings → Project ID).

---

### 2. Firebase CLI (už nainštalované v projekte)

V tomto projekte je **firebase-tools** pridané ako dev závislosť – nemusíš inštalovať nič globálne.

Overenie (v priečinku `firebase-app`):

```bash
npx firebase --version
```

Všetky ďalšie príkazy spúšťaj ako **`npx firebase ...`** (alebo `npm run firebase -- ...`).

---

### 3. Prihlásenie a prepojenie projektu

1. Prihlás sa do Firebase (otvorí sa prehliadač). V priečinku `firebase-app`:

```bash
cd firebase-app
npx firebase login
```

2. Prepoj tento priečinok s Firebase projektom:

```bash
npx firebase use --add
```

3. Vyber projekt z listu (šípky + Enter). Keď pýta **alias**, stlač Enter (použije sa `default`).
4. V priečinku `firebase-app` sa vytvorí súbor **.firebaserc** s tvojím Project ID.

---

### 4. Overenie

- Súbor **.firebaserc** by mal obsahovať niečo ako:
  ```json
  {
    "projects": {
      "default": "tvoj-project-id"
    }
  }
  ```
- Hosting v Console môže byť zatiaľ prázdny – po prvom `firebase deploy` sa nahrajú súbory z `dist/`.

Bod 1 je hotový, keď máš prihlásený účet (`npx firebase login`) a prepojený projekt (`npx firebase use --add`).

---

## Bod 2: Route #/card (hotové)

Pridaná route **#/card** – bez prihlásenia. Parametre v URL: **u** = zakódovaná Streamlit prihlasovacia URL, **name** = meno člena. Zobrazí sa meno, QR kód a tlačidlo „Prihlásiť na tréning“ (otvorí Streamlit).

Príklad odkazu po nasadení:
`https://TVOJ_PROJEKT.web.app/#/card?u=...&name=...`

---

## Deploy a prepojenie so Streamlitom

1. **Build a deploy PWA:**
   ```bash
   cd firebase-app
   npm run build
   npx firebase deploy
   ```
   Poznač si URL Hosting (napr. `https://tvoj-projekt.web.app`).

2. **V Streamlit aplikácii** (app.py v koreni projektu) nastav konštantu:
   ```python
   PWA_BASE_URL = "https://tvoj-projekt.web.app"
   ```
   Po uložení a nasadení Streamlit appky sa v sekcii „Vygenerovať klubovú kartu“ zobrazí odkaz **Otvoriť PWA kartu**. Člen si vygeneruje kartu, klikne na odkaz, otvorí sa PWA s menom, QR a tlačidlom – na mobile môže pridať na plochu.
