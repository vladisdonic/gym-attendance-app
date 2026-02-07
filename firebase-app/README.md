# Gym Evidencia – PWA (Firebase)

PWA na evidenciu účasti na tréningoch: prihlásenie, registrácia, role (user / tréner / admin), štatistiky a check-in. Beží na Firebase (Auth + Firestore) a je pripravená na hostovanie na Firebase Hosting.

## Čo je v projekte

- **Prihlásenie / registrácia** – Firebase Auth (email + heslo)
- **Role** – `user`, `trainer`, `admin` (v Firestore kolekcii `profiles`)
- **Evidencia tréningov** – kolekcia `attendance` (userId, trainingType, timestamp)
- **PWA** – manifest + service worker (Vite PWA plugin), vhodné na iOS a Android (Pridať na plochu)
- **Routing** – hash routing: `#/`, `#/checkin`, `#/trainer`, `#/admin`, `#/register`

## Potrebné kroky pred spustením

### 1. Firebase projekt

1. Choď na [Firebase Console](https://console.firebase.google.com/) a vytvor nový projekt (alebo použi existujúci).
2. Pridaj **Web app** do projektu a skopíruj `firebaseConfig` objekt.
3. Zapni **Authentication** → Sign-in method → **Email/Password** (Enable).
4. Vytvor **Firestore Database** (production mode je OK – pravidlá nastavíme nižšie).
5. V **Firestore** → Rules vlož obsah súboru `firestore.rules` z tohto priečinka a publikuj.

### 2. Premenné prostredia

V koreni `firebase-app` vytvor súbor `.env` (necommituj ho – je v `.gitignore`):

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...firebaseapp.com
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

Hodnoty sú v Firebase Console → Project settings → Your apps → config objekt.

### 3. Firestore index (voliteľné)

Ak v konzole uvidíš chybu o chýbajúcom indexe pre `attendance`, v Firestore → Indexes vytvor zložený index:

- Kolekcia: `attendance`
- Polia: `userId` (Ascending), `timestamp` (Descending)

### 4. Ikony PWA (voliteľné)

Do priečinka `public/` môžeš pridať:

- `icon-192.png` (192×192 px)
- `icon-512.png` (512×512 px)

Ak ich nepridáš, PWA sa nainštaluje aj tak, prehliadač použije vlastnú ikonu.

## Inštalácia a spustenie

```bash
cd firebase-app
npm install
npm run dev
```

Otvor `http://localhost:5173`. Pre build na deploy:

```bash
npm run build
```

## Nasadenie na Firebase Hosting

1. Nainštaluj Firebase CLI: `npm i -g firebase-tools`
2. Prihlás sa: `firebase login`
3. V priečinku `firebase-app`: `firebase init` – vyber Hosting a Firestore (rules). Ak už máš `firebase.json` a `firestore.rules`, môžeš len prepojiť projekt: `firebase use --add` a vybrať projekt.
4. Build a deploy:

```bash
npm run build
firebase deploy
```

URL bude typu `https://tvoj-projekt.web.app`.

## Funkcie ako v Streamlit aplikácii

- **Časy tréningov** – Po–Pia: 7:00, 15:30, 17:00, 18:30; So–Ne: 9:00. V Ut a Št môže tréner manuálne pridať „17:30 - ženský tréning s Diankou”.
- **Typ členstva** – Skúšobný tréning, Mesačné členstvo, Jednorázový vstup, Ročné členstvo.
- **Prihlásenie na tréning** – používateľ vyberie typ členstva a čas tréningu, odošle. Podporuje predvyplnenie z URL (pre QR/NFC).
- **Generovanie QR kódu** – sekcia QR kód: meno, členstvo, čas; vygeneruje sa QR s odkazom na check-in (s parametrami a voliteľným auto=1).
- **Tréner** – prehľad dnešných prihlásení podľa času, manuálne prihlásenie člena (meno, členstvo, čas, poznámka), vymazanie záznamu.
- **PWA** – „Stiahnuť aplikáciu” banner (ak to prehliadač podporuje), manifest a service worker pre Pridať na plochu na iOS/Android.

## NFC check-in

NFC tag naprogramuj s URL, napr.:

- `https://tvoj-projekt.web.app/#/checkin`

Prípadne s parametrami pre predvyplnenie: `#/checkin?name=...&membership=...&time=...&auto=1`

Používateľ priloží telefón k tagu → otvorí sa PWA na check-in stránke. Ak je prihlásený, môže ihneď vybrať tréning a odoslať (alebo sa automaticky odošle pri auto=1); ak nie, zobrazí sa prihlásenie.

## Štruktúra dát (Firestore)

- **profiles** (dokument ID = `auth.uid`): `email`, `displayName`, `role` (`user` | `trainer` | `admin`), `createdAt`
- **attendance**: `userId`, `email`, `displayName`, `trainingType`, `trainingName`, `timestamp`

Prvý admin: v Firebase Console → Authentication vytvor používateľa, potom v Firestore pridaj dokument v `profiles` s tým istým UID a `role: 'admin'`. Ďalších adminov/trénerov meníš v PWA v sekcii Admin (ak ste prihlásený ako admin).
