"""
Aplikácia na evidenciu účasti na tréningoch
- Účastníci sa prihlasujú cez QR kód/NFC
- Tréner vidí počet prihlásených
- Dáta sa ukladajú do Google Sheets
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import pandas as pd
import json
from urllib.parse import unquote, quote
import qrcode
import zipfile
import io
import base64
import hashlib
import pytz

# Konfigurácia stránky
st.set_page_config(
    page_title="Evidencia tréningov",
    page_icon="🥊",
    layout="centered"
)

# Štýly
st.markdown("""
<style>
    .big-number {
        font-size: 72px;
        font-weight: bold;
        text-align: center;
        color: #FF4B4B;
    }
    .subtitle {
        font-size: 24px;
        text-align: center;
        color: #666;
    }
    .success-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #D4EDDA;
        border: 1px solid #C3E6CB;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Typy členstva
MEMBERSHIP_TYPES = [
    "Skúšobný tréning",
    "Mesačné členstvo",
    "Jednorázový vstup",
    "Ročné členstvo"
]

# Časy tréningov
TRAINING_TIMES = [
    "9:00",
    "17:00",
    "18:30"
]

# Heslo pre trénerskú časť
TRAINER_PASSWORD = "supernova"

# Časové pásmo pre Slovensko
TIMEZONE = pytz.timezone('Europe/Bratislava')


def get_local_time():
    """
    Vráti aktuálny čas v časovom pásme Europe/Bratislava (Slovensko).
    """
    utc_now = datetime.now(pytz.UTC)
    local_time = utc_now.astimezone(TIMEZONE)
    return local_time


def get_google_sheets_client():
    """Pripojenie k Google Sheets pomocou service account."""
    try:
        # Načítanie credentials zo Streamlit secrets
        credentials_dict = st.secrets["gcp_service_account"]
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Chyba pri pripojení k Google Sheets: {e}")
        return None


def get_or_create_sheet(client, spreadsheet_id):
    """Získanie alebo vytvorenie hárku pre dnešný deň."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        # Použiť lokálny dátum (Europe/Bratislava)
        today = get_local_time().date()
        today_str = today.strftime("%Y-%m-%d")
        
        # Skúsime nájsť hárok pre dnešný deň
        try:
            worksheet = spreadsheet.worksheet(today_str)
        except gspread.WorksheetNotFound:
            # Vytvoríme nový hárok
            worksheet = spreadsheet.add_worksheet(
                title=today_str,
                rows=1000,
                cols=5
            )
            # Pridáme hlavičku
            worksheet.update('A1:E1', [['Čas', 'Meno', 'Typ členstva', 'Čas tréningu', 'Poznámka']])
            worksheet.format('A1:E1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
        
        return worksheet
    except Exception as e:
        st.error(f"Chyba pri prístupe k spreadsheet: {e}")
        return None


def add_attendance(worksheet, name, membership_type, training_time="", client_timestamp=None):
    """Pridanie záznamu o účasti."""
    try:
        # Použiť čas klienta ak je k dispozícii, inak lokálny serverový čas (Europe/Bratislava)
        if client_timestamp:
            timestamp = client_timestamp
        else:
            local_time = get_local_time()
            timestamp = local_time.strftime("%H:%M:%S")
        row = [timestamp, name, membership_type, training_time, ""]
        worksheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Chyba pri ukladaní: {e}")
        return False


def get_today_attendance(worksheet):
    """Získanie dnešnej účasti."""
    try:
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Chyba pri načítaní dát: {e}")
        return pd.DataFrame()


def delete_attendance(worksheet, name, timestamp, membership_type, training_time=""):
    """Vymazanie záznamu o účasti z Google Sheet."""
    try:
        # Načítanie všetkých dát
        all_values = worksheet.get_all_values()
        
        # Hlavička je na riadku 1 (index 0), dáta začínajú od riadku 2 (index 1)
        # Hľadáme riadok, ktorý zodpovedá všetkým parametrom
        row_to_delete = None
        
        for i, row in enumerate(all_values[1:], start=2):  # Začíname od riadku 2 (index 1 v liste, ale riadok 2 v Sheet)
            if len(row) >= 4:
                row_timestamp = row[0] if len(row) > 0 else ""
                row_name = row[1] if len(row) > 1 else ""
                row_membership = row[2] if len(row) > 2 else ""
                row_time = row[3] if len(row) > 3 else ""
                
                # Porovnanie - tolerancia na malé rozdiely v čase (môže byť sekunda rozdiel)
                if (row_name == name and 
                    row_membership == membership_type and 
                    row_time == training_time and
                    row_timestamp.startswith(timestamp[:5])):  # Porovnávame len hodiny:minúty
                    row_to_delete = i
                    break
        
        if row_to_delete:
            worksheet.delete_rows(row_to_delete)
            return True
        else:
            return False
    except Exception as e:
        st.error(f"Chyba pri vymazávaní: {e}")
        return False


def get_all_worksheets(client, spreadsheet_id):
    """Získanie všetkých hárkov zo spreadsheetu."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        return worksheets
    except Exception as e:
        st.error(f"Chyba pri načítaní hárkov: {e}")
        return []


def get_all_attendance_data(client, spreadsheet_id):
    """Získanie všetkých dát o účasti zo všetkých hárkov."""
    try:
        worksheets = get_all_worksheets(client, spreadsheet_id)
        all_data = []
        
        for worksheet in worksheets:
            try:
                # Skúsime načítať dáta z hárku
                records = worksheet.get_all_records()
                if records:
                    df = pd.DataFrame(records)
                    # Pridáme dátum z názvu hárku
                    sheet_name = worksheet.title
                    df['Dátum'] = sheet_name
                    all_data.append(df)
            except Exception as e:
                # Preskočíme hárky, ktoré nemajú správny formát
                continue
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Chyba pri načítaní všetkých dát: {e}")
        return pd.DataFrame()


def get_monthly_statistics(client, spreadsheet_id):
    """Výpočet štatistík za jednotlivé mesiace - top 3 najaktívnejší členovia."""
    try:
        df = get_all_attendance_data(client, spreadsheet_id)
        
        if df.empty:
            return {}
        
        # Konverzia dátumov
        df['Dátum_parsed'] = pd.to_datetime(df['Dátum'], errors='coerce', format='%Y-%m-%d')
        df = df.dropna(subset=['Dátum_parsed'])
        
        # Pridanie mesiaca a roka
        df['Mesiac'] = df['Dátum_parsed'].dt.to_period('M')
        df['Mesiac_str'] = df['Mesiac'].astype(str)
        
        # Zoskupenie podľa mesiaca a mena
        monthly_stats = {}
        
        for month in df['Mesiac_str'].unique():
            month_df = df[df['Mesiac_str'] == month]
            # Počítanie tréningov pre každého člena
            member_counts = month_df['Meno'].value_counts()
            # Top 3 najaktívnejší
            top_3 = member_counts.head(3).to_dict()
            monthly_stats[month] = top_3
        
        return monthly_stats
    except Exception as e:
        st.error(f"Chyba pri výpočte štatistík: {e}")
        return {}


def get_next_training_time():
    """
    Určí najbližší čas tréningu na základe aktuálneho času.
    Ak uplynula 1 hodina od začiatku tréningu, vyberie sa najbližší ďalší.
    
    Logika:
    - Pred 9:00 → 9:00
    - 9:00-9:59 → 9:00 (ešte neuplynula 1 hodina)
    - 10:00-16:59 → 17:00 (po uplynutí 1 hodiny od 9:00)
    - 17:00-17:59 → 17:00 (ešte neuplynula 1 hodina)
    - 18:00-19:29 → 18:30 (po 18:00 sa vyberie 18:30)
    - 19:30+ → 9:00 (na ďalší deň, po uplynutí 1 hodiny od 18:30)
    
    Returns:
        str: Čas tréningu (napr. "9:00", "17:00", "18:30")
    """
    # Použiť lokálny čas (Europe/Bratislava)
    now = get_local_time()
    current_hour = now.hour
    current_minute = now.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # Časy tréningov v minútach od polnoci
    training_9_00 = 9 * 60  # 540 minút
    training_17_00 = 17 * 60  # 1020 minút
    training_18_30 = 18 * 60 + 30  # 1110 minút
    
    # Pred 9:00 → 9:00
    if current_time_minutes < training_9_00:
        return "9:00"
    
    # 9:00-9:59 → 9:00 (ešte neuplynula 1 hodina)
    if training_9_00 <= current_time_minutes < training_9_00 + 60:
        return "9:00"
    
    # 10:00-16:59 → 17:00 (po uplynutí 1 hodiny od 9:00)
    if training_9_00 + 60 <= current_time_minutes < training_17_00:
        return "17:00"
    
    # 17:00-17:59 → 17:00 (ešte neuplynula 1 hodina)
    if training_17_00 <= current_time_minutes < training_17_00 + 60:
        return "17:00"
    
    # 18:00-19:29 → 18:30 (po 18:00 sa vyberie 18:30)
    if current_time_minutes >= 18 * 60 and current_time_minutes < training_18_30 + 60:
        return "18:30"
    
    # 19:30+ → 9:00 (na ďalší deň, po uplynutí 1 hodiny od 18:30)
    return "9:00"


def participant_view(worksheet, query_params=None):
    """Pohľad pre účastníka - prihlásenie na tréning."""
    st.title("🥊 Prihlásenie na tréning")
    st.markdown("---")
    
    # Načítanie parametrov z URL
    if query_params is None:
        query_params = st.query_params
    
    # Detekcia NFC módu (nový spôsob)
    nfc_mode = query_params.get("nfc", "0") == "1"
    
    # NFC mód - upozornenie a pokyny (localStorage/cookies nefungujú kvôli cross-origin obmedzeniu)
    if nfc_mode:
        st.warning("⚠️ **NFC tag bez osobných údajov**")
        st.markdown("""
        **Tento NFC tag neobsahuje tvoje údaje v URL.**
        
        **Ako to vyriešiť:**
        1. 👇 Otvor sekciu **"Vygenerovať osobnú URL"** nižšie
        2. Zadaj svoje meno a typ členstva
        3. Klikni na **"Generovať URL pre NFC tag"**
        4. Skopíruj vygenerovanú URL
        5. Naprogramuj NFC tag s touto URL pomocou aplikácie **NFC Tools**
        
        **✅ Potom bude NFC tag fungovať automaticky!**
        """)
        st.markdown("---")
    
    # STARÉ NFC riešenie - DEAKTIVOVANÉ (nefunguje kvôli cross-origin obmedzeniu Streamlit iframe)
    if False:
        # Použijeme components.html namiesto markdown, aby sa JavaScript správne spustil
        html_code = """
        <script>
        (function() {
            const DB_NAME = 'GiantGymDB';
            const DB_VERSION = 1;
            const STORE_NAME = 'userData';
            
            // Funkcia na inicializáciu IndexedDB s retry logikou
            function initDB() {
                return new Promise((resolve, reject) => {
                    if (!window.indexedDB) {
                        reject(new Error('IndexedDB nie je podporovaný'));
                        return;
                    }
                    
                    const request = indexedDB.open(DB_NAME, DB_VERSION);
                    
                    request.onerror = () => {
                        console.warn('IndexedDB open error:', request.error);
                        reject(request.error);
                    };
                    
                    request.onsuccess = () => {
                        resolve(request.result);
                    };
                    
                    request.onupgradeneeded = (event) => {
                        const db = event.target.result;
                        if (!db.objectStoreNames.contains(STORE_NAME)) {
                            db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                        }
                    };
                    
                    request.onblocked = () => {
                        console.warn('IndexedDB je blokovaný - možno je otvorený v inej záložke');
                    };
                });
            }
            
            // Funkcia na načítanie údajov z IndexedDB s retry
            async function loadFromIndexedDB(retries = 2) {
                for (let i = 0; i <= retries; i++) {
                try {
                    const db = await initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction([STORE_NAME], 'readonly');
                        const store = transaction.objectStore(STORE_NAME);
                        const request = store.get(1);
                        
                        request.onsuccess = () => {
                            const data = request.result;
                            if (data && data.name && data.membership) {
                                resolve({ name: data.name, membership: data.membership });
                            } else {
                                resolve(null);
                            }
                        };
                            request.onerror = () => {
                                if (i === retries) {
                                    reject(request.error);
                                } else {
                                    setTimeout(() => resolve(loadFromIndexedDB(retries - 1)), 100);
                                }
                            };
                    });
                } catch (e) {
                        if (i === retries) {
                            console.log('IndexedDB nie je dostupné po', retries + 1, 'pokusoch:', e);
                    return null;
                }
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                }
                return null;
            }
            
            // Funkcia na načítanie cookie
            function getCookie(name) {
                try {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                    if (parts.length === 2) {
                        const decoded = decodeURIComponent(parts.pop().split(';').shift());
                        return decoded || '';
                    }
                } catch (e) {
                    console.warn('Chyba pri načítaní cookie:', e);
                }
                return '';
            }
            
            // Funkcia na uloženie údajov do IndexedDB
            async function saveToIndexedDB(name, membership) {
                try {
                    const db = await initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction([STORE_NAME], 'readwrite');
                        const store = transaction.objectStore(STORE_NAME);
                        const request = store.put({ id: 1, name: name, membership: membership });
                        
                        request.onsuccess = () => resolve();
                        request.onerror = () => reject(request.error);
                    });
                } catch (e) {
                    console.log('Chyba pri ukladaní do IndexedDB:', e);
                    throw e;
                }
            }
            
            // Funkcia na uloženie cookie (optimalizované pre Safari)
            function setCookie(name, value, days = 365) {
                try {
                const encodedValue = encodeURIComponent(value);
                const expires = new Date();
                expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
                    
                    // Pre Safari: použiť Secure len ak je HTTPS, inak môže byť problém
                    const isSecure = window.location.protocol === 'https:';
                    const secureFlag = isSecure ? ';Secure' : '';
                    
                    // SameSite=Lax funguje lepšie v Safari ako Strict
                    document.cookie = `${name}=${encodedValue};expires=${expires.toUTCString()};path=/;SameSite=Lax${secureFlag}`;
                } catch (e) {
                    console.warn('Chyba pri ukladaní cookie:', e);
                }
            }
            
            // Funkcia na načítanie údajov z localStorage (najspoľahlivejšie pre Safari)
            function loadFromLocalStorage() {
                try {
                    const name = localStorage.getItem('gym_name');
                    const membership = localStorage.getItem('gym_membership');
                    if (name && membership) {
                        return { name: name, membership: membership };
                    }
                } catch (e) {
                    console.warn('localStorage nie je dostupné:', e);
                }
                return null;
            }
            
            // Funkcia na načítanie údajov z sessionStorage (funguje aj v privátnom režime Safari)
            function loadFromSessionStorage() {
                try {
                    const name = sessionStorage.getItem('gym_name');
                    const membership = sessionStorage.getItem('gym_membership');
                    if (name && membership) {
                        return { name: name, membership: membership };
                    }
                } catch (e) {
                    console.warn('sessionStorage nie je dostupné:', e);
                }
                return null;
            }
            
            // Funkcia na uloženie údajov do všetkých úložísk
            async function saveToAllStorages(name, membership) {
                // localStorage (primárne pre Safari)
                try {
                    localStorage.setItem('gym_name', name);
                    localStorage.setItem('gym_membership', membership);
                    console.log('✅ Údaje uložené do localStorage');
                } catch (e) {
                    console.warn('⚠️ localStorage nie je dostupné:', e);
                }
                
                // sessionStorage (záložné)
                try {
                    sessionStorage.setItem('gym_name', name);
                    sessionStorage.setItem('gym_membership', membership);
                    console.log('✅ Údaje uložené do sessionStorage');
                } catch (e) {
                    console.warn('⚠️ sessionStorage nie je dostupné:', e);
                }
                
                // IndexedDB (záložné)
                try {
                    await saveToIndexedDB(name, membership);
                    console.log('✅ Údaje uložené do IndexedDB');
                } catch (e) {
                    console.warn('⚠️ IndexedDB nie je dostupné:', e);
                }
                
                // Cookies (záložné)
                try {
                    setCookie('gym_name', name);
                    setCookie('gym_membership', membership);
                    console.log('✅ Údaje uložené do cookies');
                } catch (e) {
                    console.warn('⚠️ Cookies nie sú dostupné:', e);
                }
            }
            
            // Počkáme, kým sa stránka úplne načíta (pre Safari kompatibilitu)
            async function initNFC() {
                console.log('🚀 NFC Mode - Inicializácia začala');
                
                // Počkať na window.load event (dôležité pre Safari)
                if (document.readyState === 'loading') {
                    await new Promise(resolve => {
                        window.addEventListener('load', resolve, { once: true });
                    });
                }
                
                // Malé oneskorenie pre istotu
                await new Promise(resolve => setTimeout(resolve, 100));
                
                console.log('🚀 NFC Mode - Začínam processNFC');
                await processNFC();
            }
            
            // Uložiť referenciu na funkciu do window pre debug
            window.debugGymApp = {
                loadFromIndexedDB: loadFromIndexedDB,
                loadFromLocalStorage: loadFromLocalStorage,
                loadFromSessionStorage: loadFromSessionStorage,
                getCookie: getCookie,
                initDB: initDB,
                testStorage: async function() {
                    console.log('=== TEST ÚLOŽISK ===');
                    console.log('IndexedDB podporovaný:', !!window.indexedDB);
                    console.log('localStorage dostupný:', typeof(Storage) !== "undefined");
                    console.log('sessionStorage dostupný:', typeof(Storage) !== "undefined");
                    console.log('Cookies:', document.cookie);
                    
                    try {
                        const data = await loadFromIndexedDB();
                        console.log('IndexedDB dáta:', data);
                    } catch (e) {
                        console.error('IndexedDB chyba:', e);
                    }
                    
                    try {
                        const localData = loadFromLocalStorage();
                        console.log('localStorage dáta:', localData);
                    } catch (e) {
                        console.error('localStorage chyba:', e);
                    }
                    
                    try {
                        const sessionData = loadFromSessionStorage();
                        console.log('sessionStorage dáta:', sessionData);
                    } catch (e) {
                        console.error('sessionStorage chyba:', e);
                    }
                    
                    const cookieName = getCookie('gym_name');
                    const cookieMembership = getCookie('gym_membership');
                    console.log('Cookies dáta:', { name: cookieName, membership: cookieMembership });
                }
            };
            
            // Spustiť inicializáciu
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    console.log('📱 DOMContentLoaded - spúšťam NFC');
                    initNFC().catch(e => {
                        console.error('❌ Chyba pri inicializácii NFC:', e);
                        alert('Chyba pri načítaní údajov: ' + e.message);
                    });
                });
            } else {
                console.log('📱 DOM už načítaný - spúšťam NFC');
                initNFC().catch(e => {
                    console.error('❌ Chyba pri inicializácii NFC:', e);
                    alert('Chyba pri načítaní údajov: ' + e.message);
                });
            }
            
            async function processNFC() {
                try {
                    console.log('NFC Mode - Začínam načítavanie údajov...');
                    let userData = null;
                    let storageSource = '';
                    
                    // PRIMÁRNE: localStorage (najspoľahlivejšie pre Safari na iPhone)
                    try {
                        console.log('NFC Mode - Pokúšam sa načítať z localStorage...');
                        userData = loadFromLocalStorage();
                        if (userData && userData.name && userData.membership) {
                            storageSource = 'localStorage';
                            console.log('NFC Mode - ✅ Načítané z localStorage:', userData);
                        }
                    } catch (e) {
                        console.warn('NFC Mode - ⚠️ localStorage nie je dostupné:', e);
                    }
                    
                    // ZÁLOŽNÉ 1: sessionStorage (funguje aj v privátnom režime Safari)
                    if (!userData || !userData.name || !userData.membership) {
                        try {
                            console.log('NFC Mode - Pokúšam sa načítať z sessionStorage...');
                            userData = loadFromSessionStorage();
                            if (userData && userData.name && userData.membership) {
                                storageSource = 'sessionStorage';
                                console.log('NFC Mode - ✅ Načítané z sessionStorage:', userData);
                            }
                        } catch (e) {
                            console.warn('NFC Mode - ⚠️ sessionStorage nie je dostupné:', e);
                        }
                    }
                    
                    // ZÁLOŽNÉ 2: IndexedDB
                    if (!userData || !userData.name || !userData.membership) {
                    try {
                        console.log('NFC Mode - Pokúšam sa načítať z IndexedDB...');
                        userData = await loadFromIndexedDB();
                        if (userData && userData.name && userData.membership) {
                                storageSource = 'IndexedDB';
                            console.log('NFC Mode - ✅ Načítané z IndexedDB:', userData);
                        }
                    } catch (e) {
                            console.warn('NFC Mode - ⚠️ IndexedDB nie je dostupné:', e);
                        }
                    }
                    
                    // ZÁLOŽNÉ 3: Cookies
                    if (!userData || !userData.name || !userData.membership) {
                        console.log('NFC Mode - Pokúšam sa načítať z cookies...');
                        const cookieName = getCookie('gym_name');
                        const cookieMembership = getCookie('gym_membership');
                        if (cookieName && cookieMembership) {
                            userData = {
                                name: cookieName,
                                membership: cookieMembership
                            };
                            storageSource = 'cookies';
                            console.log('NFC Mode - ✅ Načítané z cookies:', userData);
                        }
                    }
                    
                    // Ak sa údaje našli, migrujeme ich do všetkých úložísk pre budúce použitie
                    if (userData && userData.name && userData.membership && storageSource !== 'localStorage') {
                        try {
                            console.log('NFC Mode - Migrujem údaje do localStorage...');
                            await saveToAllStorages(userData.name, userData.membership);
                                    console.log('NFC Mode - ✅ Migrácia úspešná');
                                } catch (e) {
                            console.warn('NFC Mode - ⚠️ Chyba pri migrácii:', e);
                        }
                    }
                    
                    if (!userData || !userData.name || !userData.membership) {
                        console.error('NFC Mode - ❌ Údaje neboli nájdené v žiadnom úložisku');
                        console.log('NFC Mode - Debug: IndexedDB podporovaný:', !!window.indexedDB);
                        console.log('NFC Mode - Debug: localStorage dostupný:', typeof(Storage) !== "undefined");
                        console.log('NFC Mode - Debug: sessionStorage dostupný:', typeof(Storage) !== "undefined");
                        console.log('NFC Mode - Debug: Cookies:', document.cookie);
                        
                        // Zobraziť alert s inštrukciami
                        alert('⚠️ Údaje nie sú uložené!\\n\\nProsím:\\n1. Choď na https://giantgym.streamlit.app/?view=participant\\n2. Klikni na "💾 Uložiť údaje pre NFC"\\n3. Vyplň údaje a ulož ich\\n4. Potom skús znova naskenovať NFC tag\\n\\nPre debug: Otvor konzolu a spusti window.debugGymApp.testStorage()');
                        return;
                    }
                    
                    console.log('NFC Mode - ✅ Finálne načítané údaje z', storageSource + ':', userData);
                    
                    // Automatický výber času tréningu podľa aktuálneho času
                    const now = new Date();
                    const currentHour = now.getHours();
                    const currentMinute = now.getMinutes();
                    const currentTimeMinutes = currentHour * 60 + currentMinute;
                    
                    let selectedTime = '9:00'; // Predvolená hodnota
                    
                    // Časy tréningov v minútach
                    const training_9_00 = 9 * 60;      // 540 minút
                    const training_17_00 = 17 * 60;    // 1020 minút
                    const training_18_30 = 18 * 60 + 30; // 1110 minút
                    
                    // Pred 9:00 → 9:00
                    if (currentTimeMinutes < training_9_00) {
                        selectedTime = '9:00';
                    }
                    // 9:00-9:59 → 9:00 (ešte neuplynula 1 hodina)
                    else if (training_9_00 <= currentTimeMinutes && currentTimeMinutes < training_9_00 + 60) {
                        selectedTime = '9:00';
                    }
                    // 10:00-16:59 → 17:00 (po uplynutí 1 hodiny od 9:00)
                    else if (training_9_00 + 60 <= currentTimeMinutes && currentTimeMinutes < training_17_00) {
                        selectedTime = '17:00';
                    }
                    // 17:00-17:59 → 17:00 (ešte neuplynula 1 hodina)
                    else if (training_17_00 <= currentTimeMinutes && currentTimeMinutes < training_17_00 + 60) {
                        selectedTime = '17:00';
                    }
                    // 18:00-19:29 → 18:30 (po 18:00 sa vyberie 18:30)
                    else if (currentTimeMinutes >= 18 * 60 && currentTimeMinutes < training_18_30 + 60) {
                        selectedTime = '18:30';
                    }
                    // 19:30+ → 9:00 (na ďalší deň, po uplynutí 1 hodiny od 18:30)
                    else {
                        selectedTime = '9:00';
                    }
                    
                    console.log('NFC Mode - Vybratý čas:', selectedTime);
                    
                    // Ak sú všetky údaje dostupné, presmeruj s parametrami
                    if (userData.name && userData.membership) {
                        // Použiť window.top pre presmerovanie celej stránky (nie len iframe)
                        const topWindow = window.top || window.parent || window;
                        const baseUrl = 'https://giantgym.streamlit.app/';
                        const params = new URLSearchParams({
                            view: 'participant',
                            name: userData.name,
                            membership: userData.membership,
                            time: selectedTime, // Automaticky vybraný čas
                            auto: '1'
                        });
                        const newUrl = baseUrl + '?' + params.toString();
                        console.log('NFC Mode - Presmerovanie na:', newUrl);
                        try {
                            topWindow.location.href = newUrl;
                        } catch (e) {
                            // Ak window.top nie je dostupný (cross-origin), skúsime window.location
                            console.log('NFC Mode - window.top nie je dostupný, používam window.location');
                        window.location.href = newUrl;
                        }
                    } else {
                        console.log('NFC Mode - Údaje chýbajú, pokračujeme normálne');
                    }
                } catch (e) {
                    console.error('NFC Mode - Chyba:', e);
                    alert('Chyba pri načítaní údajov: ' + e.message);
                }
            }
        })();
        </script>
        <style>
        /* Skryť akýkoľvek zobrazený JavaScript kód */
        script {
            display: none !important;
            visibility: hidden !important;
        }
        </style>
        <script>
        // Skryť zobrazený JavaScript kód pomocou JavaScript (CSS selektory :has-text a :contains neexistujú)
        (function() {
            function hideJavaScriptCode() {
                const allElements = document.querySelectorAll('p, div, span, pre, code');
                allElements.forEach(function(el) {
                    const text = el.textContent || el.innerText || '';
                    // Skryť ak obsahuje JavaScript syntax
                    if (text.includes('})();') || 
                        text.includes('(function()') ||
                        (text.includes('})') && text.includes('();')) ||
                        (text.includes('async function') && text.includes('processNFC'))) {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.height = '0';
                        el.style.width = '0';
                        el.style.overflow = 'hidden';
                        el.style.opacity = '0';
                        el.style.position = 'absolute';
                        el.style.left = '-9999px';
                    }
                });
            }
            
            // Spustiť po načítaní
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', hideJavaScriptCode);
            } else {
                hideJavaScriptCode();
            }
            
            // Spustiť aj po malom oneskorení
            setTimeout(hideJavaScriptCode, 100);
            setTimeout(hideJavaScriptCode, 500);
        })();
        </script>
        """
        # Použijeme components.v1.html - JavaScript beží v iframe
        # Používame window.top.location na presmerovanie celej stránky
        st.components.v1.html(html_code, height=0)
        
        # Zobrazíme informáciu - ak JavaScript presmeroval, táto časť sa nezobrazí
        # Ak údaje chýbajú, zobrazíme varovanie a pokračujeme ďalej
        st.info("📱 Načítavam tvoje údaje a vyberám najbližší tréning...")
        
        # Ak údaje chýbajú, JavaScript nepresmeruje a zobrazíme varovanie
        st.warning("⚠️ **Údaje nie sú uložené v telefóne.**")
        st.markdown("""
        **Aby NFC/QR kód fungoval automaticky, musíš si najprv uložiť údaje:**
        
        1. Klikni na "💾 Uložiť údaje pre NFC" nižšie
        2. Vyplň svoje meno a typ členstva  
        3. Klikni na "💾 Uložiť údaje"
        4. Potom môžeš naskenovať NFC čip alebo QR kód znova
        """)
        st.markdown("---")
        # Pokračujeme ďalej, aby sa zobrazil formulár
    
    # PÔVODNÝ SPÔSOB - URL parametre (zachovaný)
    # Dekódovanie URL parametrov (pre diakritiku a špeciálne znaky)
    url_name = unquote(query_params.get("name", ""))
    url_membership = unquote(query_params.get("membership", ""))
    url_time = unquote(query_params.get("time", ""))
    auto_submit = query_params.get("auto", "0") == "1"
    
    # Ak čas nie je v URL, automaticky vyberieme najbližší
    if not url_time:
        url_time = get_next_training_time()
    
    # Určenie predvolených hodnôt z URL parametrov
    default_name = url_name if url_name else ""
    
    # Nájdenie indexu pre typ členstva (case-insensitive a s toleranciou na diakritiku)
    default_membership_index = 1  # Predvolená: Mesačné členstvo
    if url_membership:
        url_membership_clean = url_membership.strip()
        # Skús nájsť presný match
        for i, mem_type in enumerate(MEMBERSHIP_TYPES):
            if mem_type == url_membership_clean:
                default_membership_index = i
                break
        else:
            # Ak sa nenašiel presný match, skús case-insensitive
            for i, mem_type in enumerate(MEMBERSHIP_TYPES):
                if mem_type.lower() == url_membership_clean.lower():
                    default_membership_index = i
                    break
    
    # Nájdenie indexu pre čas tréningu
    default_time_index = 0  # Predvolená: 9:00
    if url_time:
        url_time_clean = url_time.strip()
        for i, time in enumerate(TRAINING_TIMES):
            if time == url_time_clean:
                default_time_index = i
                break
    
    # Automatické odoslanie ak sú všetky údaje v URL a auto=1
    auto_submit_ready = (auto_submit and url_name and url_membership and url_time and 
                        url_membership in MEMBERSHIP_TYPES and url_time in TRAINING_TIMES)
    
    # Sekcia na generovanie osobnej URL pre NFC/QR kód
    with st.expander("📱 Vygenerovať osobnú URL pre NFC tag / QR kód", expanded=nfc_mode):
        st.markdown("""
        **Vygeneruj si osobnú URL s tvojimi údajmi.**
        
        Táto URL obsahuje tvoje meno a typ členstva priamo v adrese.
        Pri naskenovaní NFC tagu alebo QR kódu sa automaticky:
        - Načítajú tvoje údaje
        - Vyberie najbližší tréning podľa aktuálneho času
        - Automaticky ťa prihlási
        
        **✅ Funguje spoľahlivo na všetkých telefónoch (vrátane iPhone/Safari)!**
        """)
        
        st.markdown("---")
        
        save_name = st.text_input("Meno a priezvisko *", key="save_name", placeholder="Zadaj svoje meno...")
        save_membership = st.selectbox("Typ členstva *", MEMBERSHIP_TYPES, key="save_membership", index=1)
        
        st.markdown("**💡 Tip:** Čas tréningu sa vyberie automaticky podľa aktuálneho času pri naskenovaní.")
        
        # Generovať QR kód
        if st.button("📱 Generovať QR kód", key="generate_qr", use_container_width=True, type="primary"):
            if save_name.strip():
                base_url = "https://giantgym.streamlit.app/?view=participant"
                params = {"name": save_name.strip(), "membership": save_membership}
                query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                url = f"{base_url}&{query_string}&auto=1"
                try:
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    qr_img_buffer = io.BytesIO()
                    img.save(qr_img_buffer, format='PNG')
                    qr_img_buffer.seek(0)
                    st.session_state['personal_qr_code'] = qr_img_buffer.getvalue()
                    st.session_state['personal_qr_url'] = url
                    st.session_state['personal_qr_filename'] = f"giantgym_{save_name.strip().replace(' ', '_')}.png"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Chyba pri generovaní QR kódu: {e}")
            else:
                st.warning("⚠️ Prosím, zadaj meno.")
        
        # Generovať URL pre NFC tag
        if st.button("🔗 Generovať URL pre NFC tag", key="generate_nfc_url", use_container_width=True):
            if save_name.strip():
                base_url = "https://giantgym.streamlit.app/?view=participant"
                params = {"name": save_name.strip(), "membership": save_membership}
                query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                url = f"{base_url}&{query_string}&auto=1"
                st.session_state['personal_nfc_url'] = url
                st.rerun()
            else:
                st.warning("⚠️ Prosím, zadaj meno.")
        
        # Zobrazenie vygenerovaného QR kódu
        if st.session_state.get('personal_qr_code'):
            st.markdown("---")
            st.success("✅ **QR kód vygenerovaný!**")
            st.markdown("### 📱 Tvoj osobný QR kód")
            st.image(st.session_state['personal_qr_code'], caption="Tvoj QR kód - naskenuj pri príchode do gymu", width=300)
            if 'personal_qr_url' in st.session_state:
                st.markdown("### 🔗 URL adresa (pre NFC tag):")
                st.code(st.session_state['personal_qr_url'], language="text")
                st.info("💡 **Pre NFC tag:** Skopíruj túto URL a naprogramuj ju do NFC tagu pomocou aplikácie ako NFC Tools.")
            st.download_button(
                label="📥 Stiahnuť QR kód (.png)",
                data=st.session_state['personal_qr_code'],
                file_name=st.session_state.get('personal_qr_filename', 'giantgym_qr.png'),
                mime="image/png",
                use_container_width=True
            )
            
        # Zobrazenie vygenerovanej URL pre NFC
        if st.session_state.get('personal_nfc_url') and not st.session_state.get('personal_qr_code'):
        st.markdown("---")
            st.success("✅ **URL pre NFC tag vygenerovaná!**")
            st.markdown("### 🔗 Tvoja osobná URL:")
            st.code(st.session_state['personal_nfc_url'], language="text")
            st.markdown("""
            **Ako naprogramovať NFC tag:**
            1. Stiahni si aplikáciu **NFC Tools** (dostupná pre iOS aj Android)
            2. Otvor aplikáciu a vyber **Write**
            3. Pridaj záznam **URL/URI**
            4. Vlož túto URL adresu
            5. Prilož NFC tag a naprogramuj ho
            
            **✅ Hotovo!** Teraz stačí priložiť telefón k NFC tagu a automaticky sa prihlásiš na tréning.
            """)
    
    st.markdown("---")
    
    # Formulár na prihlásenie
    with st.form("attendance_form", clear_on_submit=True):
        name = st.text_input(
            "Meno a priezvisko *",
            value=default_name,
            placeholder="Zadaj svoje meno...",
            key="name_input"
        )
        
        membership = st.selectbox(
            "Typ členstva *",
            options=MEMBERSHIP_TYPES,
            index=default_membership_index,
            key="membership_select"
        )
        
        training_time = st.selectbox(
            "Čas tréningu *",
            options=TRAINING_TIMES,
            index=default_time_index,
            key="time_select"
        )
        
        # Honeypot pole - skryté pre užívateľov, viditeľné pre botov
        # CSS na úplné skrytie poľa
        st.markdown("""
        <style>
        div[data-testid="stTextInput"]:has(input[aria-label*="website"]) {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Skryté pole - bežní užívatelia ho neuvidia, boti ho vyplnia
        honeypot = st.text_input(
            "website",
            key="honeypot",
            label_visibility="collapsed",
            help=""
        )
        
        # Hidden field pre čas klienta (získaný cez JavaScript)
        client_time = st.text_input(
            "client_time",
            key="client_time",
            label_visibility="collapsed",
            help="",
            value=""
        )
        
        # JavaScript na nastavenie času klienta pred odoslaním formulára
        st.markdown("""
        <script>
        (function() {
            // Funkcia na získanie aktuálneho času klienta
            function getClientTime() {
                const now = new Date();
                const hours = String(now.getHours()).padStart(2, '0');
                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = String(now.getSeconds()).padStart(2, '0');
                return hours + ':' + minutes + ':' + seconds;
            }
            
            // Nastaviť čas klienta do hidden fieldu
            function setClientTime() {
                const timeInput = document.querySelector('input[aria-label*="client_time"]');
                if (timeInput) {
                    timeInput.value = getClientTime();
                }
            }
            
            // Nastaviť čas pri načítaní stránky
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', setClientTime);
            } else {
                setClientTime();
            }
            
            // Aktualizovať čas pred odoslaním formulára
            const form = document.querySelector('form[data-testid*="attendance_form"]');
            if (form) {
                form.addEventListener('submit', function() {
                    setClientTime();
                });
            }
            
            // Aktualizovať čas každú sekundu (pre prípad, že používateľ čaká)
            setInterval(setClientTime, 1000);
        })();
        </script>
        """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "✅ Prihlásiť sa",
            use_container_width=True,
            type="primary"
        )
        
        # Automatické odoslanie ak sú všetky údaje v URL
        if auto_submit_ready and not submitted:
            # Použijeme údaje z URL
            final_name = url_name.strip()
            final_membership = url_membership
            final_time = url_time
            
            # Kontrola honeypot (musí byť prázdny)
            if not honeypot or not honeypot.strip():
                # Získať čas klienta z JavaScriptu (ak je k dispozícii)
                client_timestamp = client_time if client_time else None
                # Automatické odoslanie
                if add_attendance(worksheet, final_name, final_membership, final_time, client_timestamp):
                    st.success("🎉 Úspešne prihlásený/á!")
                    st.balloons()
                    
                    # Po úspešnom odoslaní presmeruj na čistú stránku (bez parametrov)
                    st.markdown("""
                    <script>
                    setTimeout(function() {
                        window.location.href = 'https://giantgym.streamlit.app/?view=participant';
                    }, 2000);
                    </script>
                    """, unsafe_allow_html=True)
                    return
        
        if submitted:
            # Kontrola honeypot poľa - ak je vyplnené, ide o bota
            if honeypot and honeypot.strip():
                st.error("⚠️ Bot detekovaný. Prihlásenie bolo zamietnuté.")
            elif not name.strip():
                st.warning("⚠️ Prosím, zadaj svoje meno.")
            elif not membership:
                st.warning("⚠️ Prosím, vyber typ členstva.")
            elif not training_time:
                st.warning("⚠️ Prosím, vyber čas tréningu.")
            else:
                # Získať čas klienta z JavaScriptu (ak je k dispozícii)
                client_timestamp = client_time if client_time else None
                if add_attendance(worksheet, name.strip(), membership, training_time, client_timestamp):
                    st.success("🎉 Úspešne prihlásený/á!")
                    st.balloons()
                    
                    # Ak bolo odoslanie cez URL parametre, presmeruj
                    if auto_submit:
                        st.markdown("""
                        <script>
                        setTimeout(function() {
                            window.location.href = 'https://giantgym.streamlit.app/?view=participant';
                        }, 2000);
                        </script>
                        """, unsafe_allow_html=True)


def generate_wallet_pass(name, membership, time, auto=True):
    """
    Generuje .pkpass súbor pre Apple Wallet a Google Wallet.
    """
    # Vytvorenie URL
    base_url = "https://giantgym.streamlit.app/?view=participant"
    params = {
        "name": name,
        "membership": membership,
        "time": time
    }
    if auto:
        params["auto"] = "1"
    
    query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
    url = f"{base_url}&{query_string}"
    
    # Generovanie QR kódu
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Uloženie QR kódu do bufferu
    qr_buffer = io.BytesIO()
    img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # JSON pre pass.json (bez podpisu - pre testovanie)
    # Poznámka: Apple Wallet môže vyžadovať digitálny podpis pre automatické otvorenie
    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": "pass.com.giantgym.attendance",
        "serialNumber": f"{name.replace(' ', '_')}_{int(get_local_time().timestamp())}",
        "teamIdentifier": "GIANTGYM",
        "organizationName": "Giant Gym",
        "description": "Gym Attendance Pass",
        "logoText": "Giant Gym",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(0, 0, 0)",
        "webServiceURL": "https://giantgym.streamlit.app",
        "authenticationToken": "",
        "generic": {
            "primaryFields": [
                {
                    "key": "name",
                    "label": "Člen",
                    "value": name
                }
            ],
            "secondaryFields": [
                {
                    "key": "membership",
                    "label": "Typ členstva",
                    "value": membership
                },
                {
                    "key": "time",
                    "label": "Čas tréningu",
                    "value": time
                }
            ],
            "auxiliaryFields": [
                {
                    "key": "date",
                    "label": "Vytvorené",
                    "value": get_local_time().strftime("%d.%m.%Y")
                }
            ],
            "barcode": {
                "message": url,
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1",
                "altText": "Naskenuj pre prihlásenie"
            }
        }
    }
    
    # Vytvorenie obsahu súborov
    pass_json = json.dumps(pass_data, ensure_ascii=False, indent=2).encode('utf-8')
    barcode_png = qr_buffer.getvalue()
    
    # Vytvorenie manifest.json (SHA1 hashe všetkých súborov)
    manifest = {
        "pass.json": hashlib.sha1(pass_json).hexdigest(),
        "barcode.png": hashlib.sha1(barcode_png).hexdigest()
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    
    # Vytvorenie prázdneho signature súboru
    # Poznámka: Pre produkčné použitie by toto malo byť digitálne podpísané Apple Developer certifikátom
    signature = b""  # Prázdny signature (Apple Wallet môže odmietnuť, ale súbor bude správne formátovaný)
    
    # Vytvorenie ZIP archívu (.pkpass)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # pass.json
        zip_file.writestr("pass.json", pass_json)
        
        # QR kód ako obrázok
        zip_file.writestr("barcode.png", barcode_png)
        
        # manifest.json (vyžaduje Apple Wallet)
        zip_file.writestr("manifest.json", manifest_json)
        
        # signature (vyžaduje Apple Wallet - prázdny, lebo nemáme Apple Developer certifikát)
        zip_file.writestr("signature", signature)
    
    zip_buffer.seek(0)
    return zip_buffer


def wallet_pass_view():
    """Pohľad pre generovanie Wallet Pass."""
    st.title("📱 Generovanie Wallet Pass")
    st.markdown("---")
    
    st.info("💡 **Wallet Pass** obsahuje QR kód, ktorý môžeš pridať do Apple Wallet alebo Google Wallet. Pri otvorení karty sa automaticky otvorí aplikácia s vyplneným formulárom.")
    
    # Tab pre výber typu
    tab1, tab2 = st.tabs(["📱 Wallet Pass (.pkpass)", "🖼️ QR Kód Obrázok"])
    
    with tab1:
        st.markdown("### 📱 Wallet Pass súbor")
        st.markdown("Pre Apple Wallet a Google Wallet (môže vyžadovať manuálne otvorenie)")
        
        with st.form("wallet_pass_form"):
            name = st.text_input(
                "Meno a priezvisko *",
                placeholder="Zadaj svoje meno..."
            )
            
            membership = st.selectbox(
                "Typ členstva *",
                options=MEMBERSHIP_TYPES,
                index=1  # Predvolená: Mesačné členstvo
            )
            
            time = st.selectbox(
                "Čas tréningu *",
                options=TRAINING_TIMES,
                index=0
            )
            
            auto = st.checkbox("Automatické odoslanie pri otvorení", value=True)
            
            submitted = st.form_submit_button(
                "📥 Generovať Wallet Pass",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                if name and membership and time:
                    try:
                        pass_file = generate_wallet_pass(name.strip(), membership, time, auto)
                        
                        # Uloženie do session state (mimo formulára)
                        st.session_state['wallet_pass_data'] = pass_file.getvalue()
                        st.session_state['wallet_pass_filename'] = f"giantgym_{name.strip().replace(' ', '_')}.pkpass"
                        st.session_state['wallet_pass_generated'] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Chyba pri generovaní: {e}")
            else:
                    st.warning("⚠️ Prosím, vyplň všetky polia.")
        
        # Download button mimo formulára (ale vnútri tab1)
        if st.session_state.get('wallet_pass_generated', False):
            st.markdown("---")
            st.success("✅ Wallet Pass pripravený!")
            
            # Konverzia binárnych dát na base64 pre JavaScript
            pass_data_b64 = base64.b64encode(st.session_state['wallet_pass_data']).decode('utf-8')
            filename = st.session_state['wallet_pass_filename']
            
            # JavaScript funkcia pre stiahnutie v Safari
            download_js = f"""
            <script>
            function downloadPkpass() {{
                // Konverzia base64 na blob
                const byteCharacters = atob('{pass_data_b64}');
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {{
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }}
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {{ type: 'application/vnd.apple.pkpass' }});
                
                // Vytvorenie URL pre blob
                const url = window.URL.createObjectURL(blob);
                
                // Vytvorenie linku a automatické kliknutie
                const a = document.createElement('a');
                a.href = url;
                a.download = '{filename}';
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                
                // Vyčistenie
                setTimeout(() => {{
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }}, 100);
            }}
            </script>
            """
            st.markdown(download_js, unsafe_allow_html=True)
            
            # Tlačidlo, ktoré volá JavaScript funkciu
            st.markdown(f"""
            <button onclick="downloadPkpass()" style="
                width: 100%;
                padding: 0.5rem 1rem;
                background-color: #FF4B4B;
                color: white;
                border: none;
                border-radius: 0.5rem;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                margin: 10px 0;
            ">📥 Stiahnuť .pkpass súbor</button>
            """, unsafe_allow_html=True)
            
            # Záložné riešenie pre Streamlit download button
            st.download_button(
                label="📥 Stiahnuť .pkpass súbor (záložné)",
                data=st.session_state['wallet_pass_data'],
                file_name=st.session_state['wallet_pass_filename'],
                mime="application/vnd.apple.pkpass",
                use_container_width=True,
                key="pkpass_download_fallback"
            )
            
            st.markdown("---")
            st.markdown("### 📖 Ako pridať do Wallet:")
            st.markdown("""
            **⚠️ Dôležité:** Bez Apple Developer certifikátu sa `.pkpass` súbor nemusí automaticky otvoriť v Apple Wallet.
            Pre jednoduchšie použitie odporúčame použiť **QR Kód Obrázok** (druhý tab).
            
            **iPhone/iPad - Pokus o otvorenie .pkpass:**
            1. Stiahni súbor v Safari (nie v Chrome)
            2. Otvor stiahnutý súbor v Safari alebo Files app
            3. Ak sa zobrazí chyba o podpise, súbor nie je digitálne podpísaný
            4. V tomto prípade použij **QR Kód Obrázok** namiesto toho
            
            **✅ Odporúčané riešenie - QR Kód Obrázok:**
            - Prejdi na tab "🖼️ QR Kód Obrázok"
            - Vygeneruj QR kód
            - Ulož si ho do galérie
            - Môžeš ho použiť priamo alebo pridať do Apple Wallet ako obrázok (cez aplikácie tretích strán)
            
            **Android:**
            1. Stiahni súbor
            2. Otvor súbor (môžeš potrebovať Google Wallet app)
            3. Klikni na "Pridať do Google Wallet"
            
            **Použitie QR kódu:**
            - Otvor fotoaparát na iPhone alebo Camera app na Android
            - Namieri na QR kód
            - Klikni na notifikáciu/odkaz
            - Aplikácia sa otvorí s vyplneným formulárom
            """)
    
    with tab2:
        st.markdown("### 🖼️ QR Kód Obrázok")
        st.markdown("Jednoduchší spôsob - stiahni QR kód ako obrázok a použij ho ako wallpaper alebo ulož do galérie")
        
        with st.form("qr_code_form"):
            qr_name = st.text_input(
                "Meno a priezvisko *",
                placeholder="Zadaj svoje meno...",
                key="qr_name"
            )
            
            qr_membership = st.selectbox(
                "Typ členstva *",
                options=MEMBERSHIP_TYPES,
                index=1,
                key="qr_membership"
            )
            
            qr_time = st.selectbox(
                "Čas tréningu *",
                options=TRAINING_TIMES,
                index=0,
                key="qr_time"
            )
            
            qr_auto = st.checkbox("Automatické odoslanie pri otvorení", value=True, key="qr_auto")
            
            qr_submitted = st.form_submit_button(
                "🖼️ Generovať QR Kód",
                use_container_width=True,
                type="primary"
            )
            
            if qr_submitted:
                if qr_name and qr_membership and qr_time:
                    try:
                        # Vytvorenie URL
                        base_url = "https://giantgym.streamlit.app/?view=participant"
                        params = {
                            "name": qr_name,
                            "membership": qr_membership,
                            "time": qr_time
                        }
                        if qr_auto:
                            params["auto"] = "1"
                        
                        query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                        url = f"{base_url}&{query_string}"
                        
                        # Generovanie QR kódu
                        qr = qrcode.QRCode(version=1, box_size=10, border=5)
                        qr.add_data(url)
                        qr.make(fit=True)
                        
                        img = qr.make_image(fill_color="black", back_color="white")
                        
                        # Uloženie do bufferu
                        qr_img_buffer = io.BytesIO()
                        img.save(qr_img_buffer, format='PNG')
                        qr_img_buffer.seek(0)
                        
                        # Uloženie do session state
                        st.session_state['qr_code_data'] = qr_img_buffer.getvalue()
                        st.session_state['qr_code_filename'] = f"giantgym_{qr_name.strip().replace(' ', '_')}.png"
                        st.session_state['qr_code_url'] = url  # Uloženie URL pre zobrazenie
                        st.session_state['qr_code_generated'] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Chyba pri generovaní: {e}")
                else:
                    st.warning("⚠️ Prosím, vyplň všetky polia.")
        
        # Download QR kódu mimo formulára
        if st.session_state.get('qr_code_generated', False):
            st.markdown("---")
            st.success("✅ QR kód pripravený!")
            
            # Zobrazenie QR kódu
            st.image(st.session_state['qr_code_data'], caption="Tvoj QR kód", width=300)
            
            # Zobrazenie URL na skopírovanie
            if 'qr_code_url' in st.session_state:
                st.markdown("### 🔗 URL adresa:")
                st.text_input(
                    "Klikni a skopíruj URL",
                    value=st.session_state['qr_code_url'],
                    key="qr_url_display",
                    help="Klikni do poľa a stlač Ctrl+C (Cmd+C na Mac) alebo vyber text a skopíruj",
                    label_visibility="visible"
                )
            
            st.download_button(
                label="📥 Stiahnuť QR kód (.png)",
                data=st.session_state['qr_code_data'],
                file_name=st.session_state['qr_code_filename'],
                mime="image/png",
                use_container_width=True
            )
            
            st.markdown("---")
            st.markdown("### 💡 Ako použiť QR kód:")
            st.markdown("""
            **Možnosti použitia:**
            1. **Ulož do galérie** - naskenuj QR kód pri každom príchode
            2. **Nastav ako wallpaper** - rýchly prístup k QR kódu
            3. **Vytlač a nos so sebou** - vytlač na papier alebo kartičku
            4. **Pridaj do Apple Wallet ako obrázok** - niektoré aplikácie to podporujú
            
            **Naskenovanie:**
            - Otvor fotoaparát na iPhone alebo Camera app na Android
            - Namieri na QR kód
            - Klikni na notifikáciu/odkaz
            - Aplikácia sa otvorí s vyplneným formulárom
            """)


def check_trainer_auth():
    """Kontrola, či je používateľ prihlásený ako tréner."""
    if 'trainer_authenticated' not in st.session_state:
        st.session_state.trainer_authenticated = False
    return st.session_state.trainer_authenticated


def trainer_login():
    """Formulár na prihlásenie trénera."""
    st.title("🔐 Prihlásenie trénera")
    st.markdown("---")
    
    with st.form("trainer_login_form"):
        password = st.text_input(
            "Heslo",
            type="password",
            placeholder="Zadaj heslo..."
        )
        
        submitted = st.form_submit_button(
            "🔓 Prihlásiť sa",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            if password == TRAINER_PASSWORD:
                st.session_state.trainer_authenticated = True
                st.success("✅ Úspešne prihlásený!")
                st.rerun()
            else:
                st.error("❌ Nesprávne heslo!")


def statistics_view(client, spreadsheet_id):
    """Pohľad so štatistikami - najaktívnejší členovia za mesiace."""
    # Kontrola autentifikácie
    if not check_trainer_auth():
        trainer_login()
        return
    
    st.title("📊 Štatistiky")
    st.markdown("---")
    
    # Tlačidlo na odhlásenie
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔄 Obnoviť štatistiky", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🚪 Odhlásiť sa", use_container_width=True):
            st.session_state.trainer_authenticated = False
            st.rerun()
    
    # Načítanie štatistík
    with st.spinner("Načítavam štatistiky..."):
        monthly_stats = get_monthly_statistics(client, spreadsheet_id)
    
    if monthly_stats:
        # Zoradenie mesiacov od najnovšieho
        sorted_months = sorted(monthly_stats.keys(), reverse=True)
        
        for month in sorted_months:
            stats = monthly_stats[month]
            if stats:
                # Formátovanie názvu mesiaca
                try:
                    year, month_num = month.split('-')
                    month_names = {
                        '01': 'Január', '02': 'Február', '03': 'Marec',
                        '04': 'Apríl', '05': 'Máj', '06': 'Jún',
                        '07': 'Júl', '08': 'August', '09': 'September',
                        '10': 'Október', '11': 'November', '12': 'December'
                    }
                    month_name = month_names.get(month_num, month_num)
                    month_display = f"{month_name} {year}"
                except:
                    month_display = month
                
                st.markdown(f"### 📅 {month_display}")
                
                # Zobrazenie top 3
                cols = st.columns(3)
                for i, (name, count) in enumerate(stats.items()):
                    with cols[i]:
                        st.metric(
                            label=f"{i+1}. miesto",
                            value=name,
                            delta=f"{count} tréningov"
                        )
                
                st.markdown("---")
    else:
        st.info("Zatiaľ nie sú dostupné žiadne štatistiky.")


def trainer_view(worksheet):
    """Pohľad pre trénera - prehľad účasti."""
    # Kontrola autentifikácie
    if not check_trainer_auth():
        trainer_login()
        return
    
    st.title("👨‍🏫 Prehľad trénera")
    st.markdown("---")
    
    # Tlačidlá na obnovenie a odhlásenie
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔄 Obnoviť údaje", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🚪 Odhlásiť sa", use_container_width=True):
            st.session_state.trainer_authenticated = False
            st.rerun()
    
    # Načítanie dát
    df = get_today_attendance(worksheet)
    
    # Zobrazenie počtu
    count = len(df)
    
    st.markdown(f"""
    <div style="text-align: center; padding: 30px; background-color: #f0f2f6; border-radius: 15px; margin: 20px 0;">
        <div class="big-number">{count}</div>
        <div class="subtitle">prihlásených na dnešný tréning</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not df.empty:
        # Prehľad podľa času tréningu
        st.markdown("### ⏰ Prehľad podľa času tréningu")
        
        # Získanie názvu stĺpca (môže byť "Čas tréningu" alebo "Tréning" pre staré dáta)
        time_column = 'Čas tréningu' if 'Čas tréningu' in df.columns else 'Tréning'
        
        if time_column in df.columns:
            # Zoskupenie podľa času tréningu
            for training_time in TRAINING_TIMES:
                time_df = df[df[time_column] == training_time]
                count = len(time_df)
                
                with st.expander(f"🕐 {training_time} - {count} prihlásených", expanded=True):
                    if not time_df.empty:
                        # Zobrazenie každého účastníka s tlačidlom na vymazanie
                        for idx, row in time_df.iterrows():
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"**{row['Meno']}** - {row['Typ členstva']} ({row['Čas']})")
                            with col2:
                                delete_key = f"delete_{training_time}_{idx}_{row['Čas']}"
                                if st.button("🗑️ Vymazať", key=delete_key, use_container_width=True):
                                    if delete_attendance(worksheet, row['Meno'], row['Čas'], row['Typ členstva'], training_time):
                                        st.success(f"✅ {row['Meno']} bol/a vymazaný/á")
                                        st.rerun()
                                    else:
                                        st.error("❌ Chyba pri vymazávaní")
                    else:
                        st.info("Zatiaľ sa nikto neprihlásil na tento čas.")
        
        st.markdown("---")
        
        # Štatistiky podľa typu členstva
        st.markdown("### 📊 Podľa typu členstva")
        membership_counts = df['Typ členstva'].value_counts()
        
        cols = st.columns(min(4, len(membership_counts)))
        for i, (membership, cnt) in enumerate(membership_counts.items()):
            with cols[i % 4]:
                st.metric(membership, cnt)
        
        st.markdown("---")
        
        # Celkový zoznam účastníkov
        st.markdown("### 📋 Celkový zoznam účastníkov")
        display_columns = ['Čas', 'Meno', 'Typ členstva']
        if time_column in df.columns:
            display_columns.append(time_column)
        
        # Zobrazenie každého účastníka s tlačidlom na vymazanie
        for idx, row in df.iterrows():
            col1, col2 = st.columns([4, 1])
            with col1:
                time_info = f" - {row[time_column]}" if time_column in row else ""
                st.markdown(f"**{row['Meno']}** - {row['Typ členstva']}{time_info} ({row['Čas']})")
            with col2:
                delete_key = f"delete_all_{idx}_{row['Čas']}"
                if st.button("🗑️ Vymazať", key=delete_key, use_container_width=True):
                    training_time_val = row[time_column] if time_column in row else ""
                    if delete_attendance(worksheet, row['Meno'], row['Čas'], row['Typ členstva'], training_time_val):
                        st.success(f"✅ {row['Meno']} bol/a vymazaný/á")
                        st.rerun()
                    else:
                        st.error("❌ Chyba pri vymazávaní")
    else:
        st.info("Zatiaľ sa nikto neprihlásil.")


def scanner_view(worksheet):
    """Pohľad pre QR kód scanner v gyme - scanner + formulár."""
    
    st.title("📷 QR Kód Scanner - Gym")
    st.markdown("**Naskenuj QR kód alebo vyplň formulár manuálne**")
    
    # Spracovať údaje z query params (ak prídu cez postMessage a reload)
    query_params = st.query_params
    qr_submit = query_params.get("qr_submit", "0") == "1"
    if qr_submit and not st.session_state.get('qr_scanned_data'):
        # Extrahovať údaje z query params a uložiť do session state
        name = unquote(query_params.get("qr_name", ""))
        membership = unquote(query_params.get("qr_membership", ""))
        time = unquote(query_params.get("qr_time", ""))
        
        if name and membership:
            st.session_state['qr_scanned_data'] = {
                'name': name,
                'membership': membership,
                'time': time
            }
            # Vyčistiť query params
            st.query_params.clear()
            st.rerun()
    
    # Načítať naskenované údaje (ak existujú)
    scanned_data = st.session_state.get('qr_scanned_data', {})
    default_name = scanned_data.get('name', '')
    default_membership = scanned_data.get('membership', '')
    default_time = scanned_data.get('time', '')
    
    # Ak čas nie je v údajoch, automaticky vyberieme najbližší
    if not default_time:
        default_time = get_next_training_time()
    
    # Nájsť indexy pre selectboxy
    default_membership_index = 0
    if default_membership:
        try:
            default_membership_index = MEMBERSHIP_TYPES.index(default_membership)
        except ValueError:
            default_membership_index = 1  # Predvolená: Mesačné členstvo
    
    default_time_index = 0
    if default_time:
        try:
            default_time_index = TRAINING_TIMES.index(default_time)
        except ValueError:
            default_time_index = 0
    
    st.markdown("---")
    
    # Sekcia 1: QR Scanner
    st.markdown("### 📷 QR Kód Scanner")
    st.info("""
    **Ako to funguje:**
    1. **Povol prístup ku kamere** - klikni na ikonu kamery v adresnom riadku a povoľ prístup
    2. Používateľ otvorí svoj QR kód na telefóne
    3. Zameria fotoaparát tabletu/počítača na QR kód
    4. **Automaticky sa vyplní formulár nižšie**
    """)
    
    # JavaScript listener pre postMessage z iframe (pre QR scanner) - musí byť aj tu
    st.markdown("""
    <script>
    (function() {
        console.log('🔍 PostMessage listener sa inicializuje v scanner_view...');
        // Počúvať na správy z iframe (QR scanner)
        function handleMessage(event) {
            console.log('📨 Správa prijatá v scanner_view:', event);
            console.log('📨 event.data:', event.data);
            console.log('📨 event.origin:', event.origin);
            
            if (event.data && event.data.type === 'QR_SCAN_DATA') {
                console.log('✅ QR scan data received:', event.data.data);
                const scanData = event.data.data;
                
                // Uložiť údaje do session storage a spustiť rerun
                // Použijeme Streamlit's rerun mechanism cez query params
                const params = new URLSearchParams(window.location.search);
                params.set('qr_name', scanData.name);
                params.set('qr_membership', scanData.membership);
                if (scanData.time) {
                    params.set('qr_time', scanData.time);
                }
                params.set('qr_submit', '1');
                
                // Aktualizovať URL a spustiť rerun
                window.history.replaceState({}, '', window.location.pathname + '?' + params.toString());
                window.location.reload();
            }
        }
        
        // Odstrániť existujúci listener, ak existuje
        window.removeEventListener('message', handleMessage);
        // Pridať nový listener
        window.addEventListener('message', handleMessage);
        console.log('✅ PostMessage listener registrovaný v scanner_view');
    })();
    </script>
    """, unsafe_allow_html=True)
    
    # Spracovať údaje z query params (ak prídu cez postMessage a reload)
    query_params = st.query_params
    qr_submit = query_params.get("qr_submit", "0") == "1"
    if qr_submit and not st.session_state.get('qr_scanned_data'):
        # Extrahovať údaje z query params a uložiť do session state
        name = unquote(query_params.get("qr_name", ""))
        membership = unquote(query_params.get("qr_membership", ""))
        time = unquote(query_params.get("qr_time", ""))
        
        if name and membership:
            st.session_state['qr_scanned_data'] = {
                'name': name,
                'membership': membership,
                'time': time
            }
            # Vyčistiť query params
            st.query_params.clear()
            st.rerun()
    
    # Automaticky spustiť scanner po úspešnom prihlásení
    if st.session_state.get('restart_scanner_after_success'):
        st.markdown("""
        <script>
        if (window.restartScanner) {
            setTimeout(function() {
                window.restartScanner();
            }, 500);
        }
        </script>
        """, unsafe_allow_html=True)
        del st.session_state['restart_scanner_after_success']
    
    # Tlačidlo na manuálne spustenie scanneru
    if st.button("🔄 Spustiť Scanner", key="start_scanner", use_container_width=True, type="primary"):
        st.session_state['restart_scanner'] = True
        st.rerun()
    
    # JavaScript na manuálne spustenie scanneru (ak bolo stlačené tlačidlo)
    if st.session_state.get('restart_scanner'):
        st.markdown("""
        <script>
        if (window.restartScanner) {
            setTimeout(function() {
                window.restartScanner();
            }, 500);
        }
        </script>
        """, unsafe_allow_html=True)
        del st.session_state['restart_scanner']
    
    st.markdown("---")
    
    # Sekcia 2: Formulár na prihlásenie
    st.markdown("### 📝 Formulár na prihlásenie")
    
    # Zobraziť hlášku, ak boli údaje naskenované
    if scanned_data:
        st.success("✅ **QR kód naskenovaný!** Formulár je automaticky vyplnený.")
    
    # Formulár na prihlásenie
    with st.form("scanner_attendance_form", clear_on_submit=True):
        name = st.text_input(
            "Meno a priezvisko *",
            value=default_name,
            placeholder="Zadaj meno alebo naskenuj QR kód...",
            key="scanner_name_input"
        )
        
        membership = st.selectbox(
            "Typ členstva *",
            options=MEMBERSHIP_TYPES,
            index=default_membership_index,
            key="scanner_membership_select"
        )
        
        training_time = st.selectbox(
            "Čas tréningu *",
            options=TRAINING_TIMES,
            index=default_time_index,
            key="scanner_time_select"
        )
        
        # Honeypot pole
        st.markdown("""
        <style>
        div[data-testid="stTextInput"]:has(input[aria-label*="website"]) {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        honeypot = st.text_input(
            "website",
            key="scanner_honeypot",
            label_visibility="collapsed",
            help=""
        )
        
        # Hidden field pre čas klienta
        client_time = st.text_input(
            "client_time",
            key="scanner_client_time",
            label_visibility="collapsed",
            help="",
            value=""
        )
        
        # JavaScript na nastavenie času klienta
        st.markdown("""
        <script>
        (function() {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            const timeString = hours + ':' + minutes + ':' + seconds;
            
            const clientTimeInput = document.querySelector('input[aria-label*="client_time"]');
            if (clientTimeInput) {
                clientTimeInput.value = timeString;
            }
        })();
        </script>
        """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "✅ Prihlásiť na tréning",
            use_container_width=True,
            type="primary"
        )
        
        # Automatické odoslanie, ak boli údaje naskenované
        auto_submit = st.session_state.get('auto_submit_scanner', False)
        if auto_submit and name.strip() and membership and training_time:
            # Odoslať automaticky
            client_timestamp = client_time if client_time else None
            if add_attendance(worksheet, name.strip(), membership, training_time, client_timestamp):
                st.success(f"🎉 **{name.strip()}** úspešne prihlásený/á na tréning **{training_time}**!")
                st.balloons()
                
                # Vyčistiť session state
                if 'qr_scanned_data' in st.session_state:
                    del st.session_state['qr_scanned_data']
                if 'auto_submit_scanner' in st.session_state:
                    del st.session_state['auto_submit_scanner']
                st.session_state['restart_scanner_after_success'] = True
                
                # Rerun po 2 sekundách
                st.markdown("""
                <script>
                setTimeout(function() {
                    if (window.restartScanner) {
                        window.restartScanner();
                    }
                }, 2000);
                </script>
                """, unsafe_allow_html=True)
            else:
                st.error("❌ Chyba pri prihlásení. Skús znova.")
                if 'auto_submit_scanner' in st.session_state:
                    del st.session_state['auto_submit_scanner']
        
        if submitted:
            # Kontrola honeypot poľa
            if honeypot and honeypot.strip():
                st.error("⚠️ Bot detekovaný. Prihlásenie bolo zamietnuté.")
            elif not name.strip():
                st.warning("⚠️ Prosím, zadaj meno alebo naskenuj QR kód.")
            elif not membership:
                st.warning("⚠️ Prosím, vyber typ členstva.")
            elif not training_time:
                st.warning("⚠️ Prosím, vyber čas tréningu.")
            else:
                # Získať čas klienta
                client_timestamp = client_time if client_time else None
                if add_attendance(worksheet, name.strip(), membership, training_time, client_timestamp):
                    st.success(f"🎉 **{name.strip()}** úspešne prihlásený/á na tréning **{training_time}**!")
                    st.balloons()
                    
                    # Vyčistiť session state a znova spustiť scanner
                    if 'qr_scanned_data' in st.session_state:
                        del st.session_state['qr_scanned_data']
                    st.session_state['restart_scanner_after_success'] = True
                    
                    # Rerun po 2 sekundách
                    st.markdown("""
                    <script>
                    setTimeout(function() {
                        if (window.restartScanner) {
                            window.restartScanner();
                        }
                    }, 2000);
                    </script>
                    """, unsafe_allow_html=True)
                else:
                    st.error("❌ Chyba pri prihlásení. Skús znova.")
    
    # JavaScript riešenie s html5-qrcode knižnicou
    scanner_html = """
    <div id="qr-scanner-debug" style="padding: 10px; background: #f0f0f0; border: 1px solid #ccc; margin: 10px 0; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; position: relative; z-index: 1000;"></div>
    <div id="qr-reader" style="width: 100%; max-width: 600px; margin: 0 auto;"></div>
    <div id="qr-reader-results" style="margin-top: 20px;"></div>
    
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <script>
    // Debug funkcia - pridá správu do debug divu
    function addDebugMsg(msg) {
        try {
            let debugDiv = document.getElementById('qr-scanner-debug');
            // Ak debug div neexistuje, vytvor ho
            if (!debugDiv) {
                debugDiv = document.createElement('div');
                debugDiv.id = 'qr-scanner-debug';
                debugDiv.style.cssText = 'padding: 10px; background: #f0f0f0; border: 1px solid #ccc; margin: 10px 0; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; position: relative; z-index: 1000;';
                // Vložiť na začiatok body alebo pred qr-reader
                const qrReader = document.getElementById('qr-reader');
                if (qrReader && qrReader.parentNode) {
                    qrReader.parentNode.insertBefore(debugDiv, qrReader);
                } else {
                    document.body.insertBefore(debugDiv, document.body.firstChild);
                }
            }
            const timestamp = new Date().toLocaleTimeString();
            debugDiv.innerHTML += '[' + timestamp + '] ' + msg + '<br>';
            debugDiv.scrollTop = debugDiv.scrollHeight; // Auto-scroll
            // Zabezpečiť, že debug div je viditeľný
            debugDiv.style.display = 'block';
            debugDiv.style.visibility = 'visible';
            console.log(msg);
        } catch (e) {
            console.error('Chyba pri pridávaní debug správy:', e);
        }
    }
    
    // Debug - zobraziť, či sa JavaScript spúšťa
    try {
        // Zabezpečiť, že debug div existuje a je viditeľný
        setTimeout(function() {
            const debugDiv = document.getElementById('qr-scanner-debug');
            if (debugDiv) {
                debugDiv.style.display = 'block';
                debugDiv.style.visibility = 'visible';
                debugDiv.style.opacity = '1';
            }
        }, 100);
        
        addDebugMsg('🔍 QR Scanner Script sa začal načítavať...');
        addDebugMsg('🔍 document.readyState: ' + document.readyState);
        addDebugMsg('🔍 window.location: ' + window.location.href);
    } catch (e) {
        console.error('Chyba pri inicializácii debug:', e);
    }
    
    // Skontrolovať, či sa knižnica načítala
    setTimeout(function() {
        if (typeof Html5Qrcode === 'undefined') {
            console.error('❌ Html5Qrcode knižnica sa nenačítala!');
            const resultsDiv = document.getElementById('qr-reader-results');
            if (resultsDiv) {
                resultsDiv.innerHTML = '<div style="padding: 15px; background-color: #f8d7da; border-radius: 5px; color: #721c24;">❌ Chyba: QR scanner knižnica sa nenačítala. Skús obnoviť stránku.</div>';
            }
        } else {
            console.log('✅ Html5Qrcode knižnica sa načítala');
        }
    }, 1000);
    
    (function() {
        console.log('🔍 QR Scanner IIFE sa spúšťa...');
        let html5QrcodeScanner = null;
        let isScanning = false;
        let lastScannedCode = null;
        let scanCooldown = false;
        let isProcessing = false; // Flag na zabránenie opakovanému spracovaniu
        
        function onScanSuccess(decodedText, decodedResult) {
            // Ak už spracovávame, ignorovať
            if (isProcessing) {
                addDebugMsg('⏸️ Už spracovávam, ignorujem');
                return;
            }
            
            // Debug - zobraziť všetky parametre
            addDebugMsg('✅ onScanSuccess called');
            console.log('onScanSuccess called with:', { decodedText, decodedResult });
            
            // Skontrolovať, či je decodedText definovaný
            if (!decodedText) {
                console.error('decodedText je undefined!', decodedResult);
                // Skúsiť získať text z decodedResult
                if (decodedResult && decodedResult.text) {
                    decodedText = decodedResult.text;
                } else if (decodedResult && typeof decodedResult === 'string') {
                    decodedText = decodedResult;
                } else {
                    console.error('Nepodarilo sa získať text z QR kódu');
                    return;
                }
            }
            
            // Ignorovať duplikáty (rovnaký QR kód skenovaný viackrát)
            if (decodedText === lastScannedCode && scanCooldown) {
                addDebugMsg('⏸️ Duplikát, ignorujem');
                return;
            }
            
            lastScannedCode = decodedText;
            scanCooldown = true;
            isProcessing = true; // Nastaviť flag, že spracovávame
            
            // Resetovať cooldown po 5 sekundách (dlhšie, aby sa zabránilo opakovanému skenu)
            setTimeout(() => {
                scanCooldown = false;
                lastScannedCode = null;
            }, 5000);
            
            addDebugMsg('📱 QR kód naskenovaný: ' + (decodedText ? decodedText.substring(0, 50) + '...' : 'PRÁZDNY'));
            console.log('QR kód naskenovaný:', decodedText);
            console.log('Typ decodedText:', typeof decodedText);
            console.log('Obsahuje giantgym.streamlit.app?', decodedText.includes('giantgym.streamlit.app'));
            console.log('Obsahuje view=participant?', decodedText.includes('view=participant'));
            
            // Kontrola validity - skontrolovať, či je to string
            const isValid = typeof decodedText === 'string' && 
                           decodedText.includes('giantgym.streamlit.app') && 
                           decodedText.includes('view=participant');
            
            addDebugMsg('🔍 Validácia výsledok: ' + isValid);
            console.log('Validácia výsledok:', isValid);
            
            if (isValid) {
                addDebugMsg('✅ Validný QR kód - extrahujem údaje');
                console.log('✅ Validný QR kód - extrahujem údaje');
                
                // Zobraziť úspech OKAMŽITE (pred extrahovaním)
                const resultsDiv = document.getElementById('qr-reader-results');
                if (resultsDiv) {
                    resultsDiv.innerHTML = '<div style="padding: 15px; background-color: #d4edda; border-radius: 5px; color: #155724; font-weight: bold;">✅ QR kód rozpoznaný! Registrujem na pozadí...</div>';
                    addDebugMsg('✅ Hláška zobrazená v resultsDiv');
                    console.log('Hláška zobrazená');
                } else {
                    addDebugMsg('❌ resultsDiv nie je dostupný!');
                    console.error('resultsDiv nie je dostupný!');
                }
                
                // Extrahovať parametre z URL PRED zastavením scanneru
                addDebugMsg('🔍 Začínam extrahovanie údajov z URL (PRED zastavením scanneru)');
                try {
                    addDebugMsg('🔍 Začínam extrahovanie údajov z URL');
                    console.log('Začínam extrahovanie údajov z URL:', decodedText);
                    const url = new URL(decodedText);
                    addDebugMsg('✅ URL objekt vytvorený');
                    console.log('URL objekt vytvorený:', url);
                    const params = new URLSearchParams(url.search);
                    addDebugMsg('✅ URLSearchParams vytvorené');
                    console.log('URLSearchParams vytvorené');
                    const name = params.get('name') || '';
                    const membership = params.get('membership') || '';
                    const time = params.get('time') || '';
                    
                    addDebugMsg('📋 Extrahované údaje: name=' + name + ', membership=' + membership + ', time=' + time);
                    console.log('Extrahované údaje:', { name, membership, time });
                    
                    // Uložiť údaje do Streamlit session state a spustiť rerun
                    addDebugMsg('💾 Ukladám údaje do Streamlit session state...');
                    console.log('Ukladám údaje do Streamlit session state...');
                    
                    // Použiť Streamlit's JavaScript API na komunikáciu s Python kódom
                    // Namiesto presmerovania použijeme postMessage na komunikáciu s hlavnou stránkou
                    const scanData = {
                        name: name,
                        membership: membership,
                        time: time || ''
                    };
                    
                    addDebugMsg('📨 Posielam údaje cez postMessage...');
                    console.log('Posielam údaje:', scanData);
                    
                    // Poslať správu hlavnej stránke (nie iframe)
                    try {
                        if (window.parent && window.parent !== window) {
                            // Ak sme v iframe, poslať správu hlavnej stránke
                            window.parent.postMessage({
                                type: 'QR_SCAN_DATA',
                                data: scanData
                            }, '*');
                            addDebugMsg('✅ Správa odoslaná cez postMessage');
                        } else {
                            // Ak nie sme v iframe, použiť Streamlit's setComponentValue
                            // Alebo použiť window.location.search na aktualizáciu URL
                            addDebugMsg('🌐 Nie sme v iframe, používam window.location.search');
                            const params = new URLSearchParams();
                            params.set('qr_name', name);
                            params.set('qr_membership', membership);
                            if (time) {
                                params.set('qr_time', time);
                            }
                            params.set('qr_submit', '1');
                            window.location.search = params.toString();
                        }
                    } catch (e) {
                        addDebugMsg('❌ Chyba pri odosielaní údajov: ' + (e.message || e.toString()));
                        console.error('Chyba pri odosielaní údajov:', e);
                    }
                    
                } catch (e) {
                    const errorMsg = e && e.message ? e.message : (e && e.toString ? e.toString() : 'Neznáma chyba');
                    addDebugMsg('❌ Chyba pri extrahovaní údajov z URL: ' + errorMsg);
                    addDebugMsg('❌ Stack trace: ' + (e && e.stack ? e.stack.substring(0, 200) : 'N/A'));
                    addDebugMsg('❌ decodedText: ' + (decodedText ? decodedText.substring(0, 100) : 'PRÁZDNY'));
                    console.error('Chyba pri extrahovaní údajov z URL:', e);
                    console.error('Stack trace:', e && e.stack ? e.stack : 'N/A');
                    console.error('decodedText hodnota:', decodedText);
                    if (resultsDiv) {
                        resultsDiv.innerHTML = '<div style="padding: 15px; background-color: #f8d7da; border-radius: 5px; color: #721c24;">❌ Chyba pri spracovaní QR kódu: ' + errorMsg + '<br><br>Skopíruj túto chybu a pošli ju vývojárovi.</div>';
                    }
                    // Resetovať flag, aby sa mohol skúsiť ďalší sken
                    isProcessing = false;
                }
            } else {
                // Neplatný QR kód alebo chyba
                const resultsDiv = document.getElementById('qr-reader-results');
                let errorMsg = '⚠️ Tento QR kód nie je pre túto aplikáciu.';
                
                // Debug - zobraziť, čo bolo naskenované
                if (decodedText) {
                    errorMsg += '<br><br><small>Naskenovaný text: ' + decodedText.substring(0, 100) + '</small>';
                    console.log('Neplatný QR kód:', decodedText);
                } else {
                    errorMsg += '<br><br><small>QR kód sa naskenoval, ale text je prázdny.</small>';
                    console.error('QR kód bez textu:', decodedResult);
                }
                
                resultsDiv.innerHTML = '<div style="padding: 15px; background-color: #fff3cd; border-radius: 5px; color: #856404; font-weight: bold;">' + errorMsg + '</div>';
                
                // Resetovať po 5 sekundách
                setTimeout(() => {
                    resultsDiv.innerHTML = '';
                    lastScannedCode = null;
                }, 5000);
            }
        }
        
        function onScanFailure(error) {
            // Ignorovať chyby - len logovať
            // console.log('Skenovanie pokračuje...', error);
        }
        
        async function startScanner() {
            addDebugMsg('🎬 startScanner volaná');
            console.log('🔍 startScanner volaná');
            console.log('🔍 isScanning:', isScanning);
            
            if (isScanning) {
                addDebugMsg('⏸️ Scanner už beží, preskakujem');
                console.log('🔍 Scanner už beží, preskakujem');
                return;
            }
            
            const resultsDiv = document.getElementById('qr-reader-results');
            addDebugMsg('🔍 resultsDiv: ' + (resultsDiv ? 'OK' : 'NIE JE DOSTUPNÝ'));
            console.log('🔍 resultsDiv:', resultsDiv);
            
            if (!resultsDiv) {
                addDebugMsg('❌ resultsDiv nie je dostupný!');
                console.error('🔍 resultsDiv nie je dostupný!');
            }
            
            // Skúsiť najprv zadnú kameru (environment), potom prednú (user)
            const cameraConfigs = [
                { facingMode: "environment" }, // Zadná kamera (pre tablety/telefóny)
                { facingMode: "user" },         // Predná kamera (pre počítače)
                { facingMode: { exact: "environment" } }, // Presne zadná
                { facingMode: { exact: "user" } }        // Presne predná
            ];
            
            for (let i = 0; i < cameraConfigs.length; i++) {
                try {
                    isScanning = true;
                    html5QrcodeScanner = new Html5Qrcode("qr-reader");
                    
                    // Zobraziť správu o pokuse
                    if (i > 0) {
                        resultsDiv.innerHTML = '<div style="padding: 10px; background-color: #d1ecf1; border-radius: 5px; color: #0c5460;">🔄 Skúšam inú kameru...</div>';
                    }
                    
                    await html5QrcodeScanner.start(
                        cameraConfigs[i],
                        {
                            fps: 10,
                            qrbox: function(viewfinderWidth, viewfinderHeight) {
                                // Dynamická veľkosť skenovacieho boxu (50% viewfinder)
                                let minEdgePercentage = 0.5;
                                let minEdgeSize = Math.min(viewfinderWidth, viewfinderHeight);
                                let qrboxSize = Math.floor(minEdgeSize * minEdgePercentage);
                                return {
                                    width: qrboxSize,
                                    height: qrboxSize
                                };
                            },
                            aspectRatio: 1.0,
                            disableFlip: false
                        },
                        (decodedText, decodedResult) => {
                            // Wrapper pre callback - zabezpečí správne parametre
                            console.log('QR scanner callback:', { decodedText, decodedResult });
                            onScanSuccess(decodedText, decodedResult);
                        },
                        (errorMessage) => {
                            // Wrapper pre error callback
                            onScanFailure(errorMessage);
                        }
                    );
                    
                    addDebugMsg('✅ QR scanner spustený s konfiguráciou: ' + JSON.stringify(cameraConfigs[i]));
                    console.log('QR scanner spustený s konfiguráciou:', cameraConfigs[i]);
                    resultsDiv.innerHTML = '<div style="padding: 10px; background-color: #d4edda; border-radius: 5px; color: #155724;">✅ Kamera pripravená! Namier na QR kód...</div>';
                    addDebugMsg('📷 Kamera pripravená!');
                    return; // Úspešne spustené
                    
                } catch (err) {
                    console.log('Pokus ' + (i + 1) + ' zlyhal:', err.message);
                    
                    // Ak už máme scanner, skúsime ho zastaviť
                    if (html5QrcodeScanner) {
                        try {
                            await html5QrcodeScanner.clear();
                        } catch (clearErr) {
                            console.log('Chyba pri cleanup:', clearErr);
                        }
                        html5QrcodeScanner = null;
                    }
                    
                    // Ak je to posledný pokus, zobraziť chybu
                    if (i === cameraConfigs.length - 1) {
                        let errorMsg = '❌ Nepodarilo sa spustiť kameru.';
                        
                        if (err.name === 'NotAllowedError' || err.message.includes('Permission denied')) {
                            errorMsg += '<br><br><strong>Kamera nemá povolený prístup.</strong><br><br>';
                            errorMsg += '1. Klikni na ikonu kamery v adresnom riadku prehliadača<br>';
                            errorMsg += '2. Povoľ prístup ku kamere<br>';
                            errorMsg += '3. Obnov stránku (F5 alebo Cmd+R)';
                        } else if (err.name === 'NotFoundError' || err.message.includes('No camera')) {
                            errorMsg += '<br><br><strong>Kamera sa nenašla.</strong><br><br>';
                            errorMsg += 'Skontroluj, či je kamera pripojená a funguje.';
                        } else {
                            errorMsg += '<br><br>Chyba: ' + err.message;
                        }
                        
                        resultsDiv.innerHTML = '<div style="padding: 15px; background-color: #f8d7da; border-radius: 5px; color: #721c24;">' + errorMsg + '</div>';
                        isScanning = false;
                    }
                }
            }
        }
        
        // Funkcia na manuálne spustenie scanneru
        window.restartScanner = function() {
            if (html5QrcodeScanner) {
                html5QrcodeScanner.clear().then(() => {
                    html5QrcodeScanner = null;
                    isScanning = false;
                    startScanner();
                }).catch(err => {
                    console.error('Chyba pri cleanup:', err);
                    html5QrcodeScanner = null;
                    isScanning = false;
                    startScanner();
                });
            } else {
                startScanner();
            }
        };
        
        // Debug - zobraziť, že JavaScript sa načítal
        addDebugMsg('✅ QR Scanner JavaScript sa načítal');
        addDebugMsg('🔍 Html5Qrcode dostupný: ' + (typeof Html5Qrcode !== 'undefined'));
        addDebugMsg('🔍 qr-reader element: ' + (document.getElementById('qr-reader') ? 'OK' : 'NIE JE'));
        addDebugMsg('🔍 qr-reader-results element: ' + (document.getElementById('qr-reader-results') ? 'OK' : 'NIE JE'));
        addDebugMsg('🔍 window.top: ' + (window.top ? 'OK' : 'NIE JE'));
        addDebugMsg('🔍 window.parent: ' + (window.parent ? 'OK' : 'NIE JE'));
        console.log('🔍 QR Scanner JavaScript sa načítal');
        console.log('🔍 Html5Qrcode dostupný:', typeof Html5Qrcode !== 'undefined');
        console.log('🔍 qr-reader element:', document.getElementById('qr-reader'));
        console.log('🔍 qr-reader-results element:', document.getElementById('qr-reader-results'));
        console.log('🔍 window:', window);
        console.log('🔍 window.top:', window.top);
        console.log('🔍 window.parent:', window.parent);
        
        // Spustiť scanner po načítaní stránky
        function initScanner() {
            addDebugMsg('🚀 initScanner volaná');
            addDebugMsg('🔍 document.readyState: ' + document.readyState);
            addDebugMsg('🔍 isScanning: ' + isScanning);
            console.log('🔍 initScanner volaná');
            console.log('🔍 document.readyState:', document.readyState);
            console.log('🔍 isScanning:', isScanning);
            if (!isScanning) {
                addDebugMsg('▶️ Volám startScanner...');
                console.log('🔍 Volám startScanner...');
                startScanner();
            } else {
                addDebugMsg('⏸️ Scanner už beží, preskakujem');
                console.log('🔍 Scanner už beží, preskakujem');
            }
        }
        
        if (document.readyState === 'loading') {
            addDebugMsg('⏳ DOM sa ešte načítava, čakám na DOMContentLoaded');
            console.log('🔍 DOM sa ešte načítava, čakám na DOMContentLoaded');
            document.addEventListener('DOMContentLoaded', function() {
                addDebugMsg('✅ DOMContentLoaded - spúšťam scanner');
                console.log('🔍 DOMContentLoaded - spúšťam scanner');
                setTimeout(initScanner, 500);
            });
        } else {
            // Malé oneskorenie pre istotu
            addDebugMsg('✅ DOM už načítaný - spúšťam scanner');
            console.log('🔍 DOM už načítaný - spúšťam scanner');
            setTimeout(initScanner, 500);
        }
        
        // Backup - spustiť aj po window.load
        window.addEventListener('load', function() {
            addDebugMsg('✅ window.load event - kontrolujem scanner');
            console.log('🔍 window.load event - kontrolujem scanner');
            if (!isScanning) {
                addDebugMsg('▶️ Scanner nebeží, spúšťam...');
                console.log('🔍 Scanner nebeží, spúšťam...');
                setTimeout(initScanner, 1000);
            }
        });
        
        // Cleanup pri opustení stránky
        window.addEventListener('beforeunload', () => {
            if (html5QrcodeScanner) {
                html5QrcodeScanner.clear().catch(err => {
                    console.error('Chyba pri cleanup:', err);
                });
            }
        });
    })();
    </script>
    """
    
    st.components.v1.html(scanner_html, height=600)


def main():
    """Hlavná funkcia aplikácie."""
    
    # JavaScript listener pre postMessage z iframe (pre QR scanner)
    # Musí byť v každom view, nie len v main()
    st.markdown("""
    <script>
    (function() {
        console.log('🔍 PostMessage listener sa inicializuje...');
        // Počúvať na správy z iframe (QR scanner)
        function handleMessage(event) {
            console.log('📨 Správa prijatá:', event);
            console.log('📨 event.data:', event.data);
            console.log('📨 event.origin:', event.origin);
            console.log('📨 event.source:', event.source);
            
            // Bezpečnostná kontrola - skontrolovať origin (voliteľné)
            // if (event.origin !== 'https://giantgym.streamlit.app') return;
            
            if (event.data && event.data.type === 'QR_SCAN_SUCCESS') {
                console.log('✅ QR scan success message received:', event.data.url);
                // Presmerovať hlavnú stránku na novú URL
                console.log('🌐 Presmerovávam na:', event.data.url);
                window.location.href = event.data.url;
            } else {
                console.log('⚠️ Správa neobsahuje QR_SCAN_SUCCESS:', event.data);
            }
        }
        
        // Odstrániť existujúci listener, ak existuje
        window.removeEventListener('message', handleMessage);
        // Pridať nový listener
        window.addEventListener('message', handleMessage);
        console.log('✅ PostMessage listener registrovaný');
    })();
    </script>
    """, unsafe_allow_html=True)
    
    # CSS na skrytie akéhokoľvek zobrazeného JavaScript kódu
    st.markdown("""
    <style>
    /* Skryť akýkoľvek zobrazený JavaScript kód */
    script {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    <script>
    (function() {
        // Skryť akékoľvek zobrazené JavaScript kódy po načítaní stránky
        function hideJavaScriptCode() {
            // Skryť všetky elementy obsahujúce JavaScript kód
            const allElements = document.querySelectorAll('*');
            allElements.forEach(function(el) {
                // Preskočiť script tagy (tie už sú skryté cez CSS)
                if (el.tagName === 'SCRIPT') return;
                
                const text = el.textContent || el.innerText || '';
                // Skryť ak obsahuje JavaScript syntax
                if (text.includes('})();') || 
                    text.includes('(function()') ||
                    text.includes('function()') ||
                    (text.includes('})') && text.includes('();'))) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.height = '0';
                    el.style.width = '0';
                    el.style.overflow = 'hidden';
                    el.style.opacity = '0';
                    el.style.position = 'absolute';
                    el.style.left = '-9999px';
                }
            });
            
            // Špecificky skryť všetky <p> tagy obsahujúce JavaScript
            const paragraphs = document.querySelectorAll('p');
            paragraphs.forEach(function(p) {
                const text = p.textContent || p.innerText || '';
                if (text.includes('})();') || 
                    text.includes('(function()') ||
                    (text.includes('})') && text.includes('();'))) {
                    p.style.display = 'none';
                    p.style.visibility = 'hidden';
                    p.style.height = '0';
                    p.style.width = '0';
                    p.style.overflow = 'hidden';
                    p.style.opacity = '0';
                    p.style.position = 'absolute';
                    p.style.left = '-9999px';
                }
            });
        }
        
        // Spustiť po načítaní DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', hideJavaScriptCode);
        } else {
            hideJavaScriptCode();
        }
        
        // Spustiť aj po úplnom načítaní stránky
        window.addEventListener('load', hideJavaScriptCode);
        
        // Spustiť aj po malom oneskorení (pre Streamlit renderovanie)
        setTimeout(hideJavaScriptCode, 100);
        setTimeout(hideJavaScriptCode, 500);
        setTimeout(hideJavaScriptCode, 1000);
        
        // MutationObserver na sledovanie zmien v DOM (pre Streamlit dynamické renderovanie)
        const observer = new MutationObserver(function(mutations) {
            hideJavaScriptCode();
        });
        
        // Začať pozorovanie zmien v DOM
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });
    })();
    </script>
    """, unsafe_allow_html=True)
    
    # Kontrola konfigurácie
    if "gcp_service_account" not in st.secrets:
        st.error("⚠️ Chýba konfigurácia Google Sheets!")
        st.markdown("""
        ### Nastavenie:
        1. Vytvor Google Cloud projekt a service account
        2. Povoľ Google Sheets API
        3. Vytvor súbor `.streamlit/secrets.toml`:
        
        ```toml
        [gcp_service_account]
        type = "service_account"
        project_id = "your-project-id"
        private_key_id = "..."
        private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
        client_email = "your-service-account@your-project.iam.gserviceaccount.com"
        client_id = "..."
        auth_uri = "https://accounts.google.com/o/oauth2/auth"
        token_uri = "https://oauth2.googleapis.com/token"
        
        spreadsheet_id = "your-spreadsheet-id"
        ```
        
        4. Zdieľaj Google Sheet s emailom service accountu
        """)
        return
    
    # Kontrola spreadsheet_id - môže byť na top level alebo vnútri gcp_service_account
    spreadsheet_id = None
    
    # Skús najprv top level
    if "spreadsheet_id" in st.secrets:
        spreadsheet_id = st.secrets["spreadsheet_id"]
    # Ak nie je na top level, skús vnútri gcp_service_account
    elif "gcp_service_account" in st.secrets and "spreadsheet_id" in st.secrets["gcp_service_account"]:
        spreadsheet_id = st.secrets["gcp_service_account"]["spreadsheet_id"]
    
    if not spreadsheet_id:
        st.error("⚠️ Chýba ID Google Sheetu v secrets!")
        # Diagnostika pre debug
        with st.expander("🔍 Diagnostika secrets (pre debug)"):
            st.write("**Dostupné kľúče v st.secrets:**")
            try:
                secrets_keys = list(st.secrets.keys())
                st.write(secrets_keys)
                if "gcp_service_account" in st.secrets:
                    st.write("**Kľúče v gcp_service_account:**")
                    st.write(list(st.secrets["gcp_service_account"].keys()))
            except Exception as e:
                st.write(f"Chyba pri načítaní secrets: {e}")
        return
    
    # Overenie, či spreadsheet_id nie je prázdny
    if not str(spreadsheet_id).strip():
        st.error("⚠️ spreadsheet_id je prázdny alebo neplatný!")
        return
    
    # Pripojenie k Google Sheets
    client = get_google_sheets_client()
    if not client:
        return
    
    worksheet = get_or_create_sheet(client, spreadsheet_id)
    if not worksheet:
        return
    
    # Navigácia cez URL parametre
    query_params = st.query_params
    view = query_params.get("view", "participant")
    
    # Sidebar navigácia
    with st.sidebar:
        # Logo
        try:
            st.image("giantgym.png", use_container_width=True)
        except:
            # Ak logo neexistuje, zobrazíme placeholder
            st.markdown("### 🥊 Giant Gym")
        
        st.markdown("---")
        st.markdown("## 📱 Navigácia")
        
        if st.button("👤 Účastník", use_container_width=True):
            st.query_params["view"] = "participant"
            st.rerun()
        
        if st.button("👨‍🏫 Tréner", use_container_width=True):
            st.query_params["view"] = "trainer"
            st.rerun()
        
        if st.button("📊 Štatistiky", use_container_width=True):
            st.query_params["view"] = "statistics"
            st.rerun()
        
        if st.button("📱 Wallet Pass", use_container_width=True):
            st.query_params["view"] = "wallet"
            st.rerun()
        
        st.markdown("---")
        # Zobrazenie lokálneho dátumu
        today = get_local_time().date()
        st.markdown(f"📅 **{today.strftime('%d.%m.%Y')}**")
        
        # QR kód info
        st.markdown("---")
        st.markdown("### 📱 QR kódy a NFC tagy")
        st.markdown("""
        **Základné linky:**
        
        - Účastník: `https://giantgym.streamlit.app/?view=participant`
        - Tréner: `https://giantgym.streamlit.app/?view=trainer`
        - Štatistiky: `https://giantgym.streamlit.app/?view=statistics`
        
        **QR kód scanner v gyme:**
        
        `https://giantgym.streamlit.app/?view=scanner`
        
        Pre použitie v gyme:
        - Otvor na tablete/počítači s kamerou
        - Používateľ ukáže svoj QR kód (vygenerovaný v aplikácii)
        - Automaticky sa načíta URL a prihlási používateľa
        
        **NFC čip v gyme (DEPRECATED - nefunguje kvôli cross-origin obmedzeniu):**
        
        `https://giantgym.streamlit.app/?view=participant&nfc=1`
        
        ⚠️ Toto riešenie nefunguje - použite QR kód scanner namiesto toho.
        
        **Unikátne URL pre automatické prihlásenie (pôvodný spôsob):**
        
        `https://giantgym.streamlit.app/?view=participant&name=MENO&membership=TYP&time=ČAS&auto=1`
        
        **Parametre:**
        - `name` - Meno a priezvisko (URL encoded, napr. `Ján%20Novák`)
        - `membership` - Typ členstva (presne: `Skúšobný tréning`, `Mesačné členstvo`, `Jednorázový vstup`, `Ročné členstvo`)
        - `time` - Čas tréningu (`9:00`, `17:00`, `18:30`) - ak chýba, vyberie sa automaticky
        - `auto=1` - Automatické odoslanie (voliteľné)
        
        **Príklad:**
        `https://giantgym.streamlit.app/?view=participant&name=Ján%20Novák&membership=Mesačné%20členstvo&time=17:00&auto=1`
        """)
    
    # Zobrazenie správneho pohľadu
    if view == "trainer":
        trainer_view(worksheet)
    elif view == "statistics":
        statistics_view(client, spreadsheet_id)
    elif view == "wallet":
        wallet_pass_view()
    elif view == "scanner":
        scanner_view(worksheet)
    else:
        participant_view(worksheet, query_params)


if __name__ == "__main__":
    main()
