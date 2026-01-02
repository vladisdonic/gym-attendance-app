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
        today_str = date.today().strftime("%Y-%m-%d")
        
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


def add_attendance(worksheet, name, membership_type, training_time=""):
    """Pridanie záznamu o účasti."""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
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


def participant_view(worksheet, query_params=None):
    """Pohľad pre účastníka - prihlásenie na tréning."""
    st.title("🥊 Prihlásenie na tréning")
    st.markdown("---")
    
    # Načítanie parametrov z URL
    if query_params is None:
        query_params = st.query_params
    
    # Dekódovanie URL parametrov (pre diakritiku a špeciálne znaky)
    url_name = unquote(query_params.get("name", ""))
    url_membership = unquote(query_params.get("membership", ""))
    url_time = unquote(query_params.get("time", ""))
    auto_submit = query_params.get("auto", "0") == "1"
    
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
                # Automatické odoslanie
                if add_attendance(worksheet, final_name, final_membership, final_time):
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
                if add_attendance(worksheet, name.strip(), membership, training_time):
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
        "serialNumber": f"{name.replace(' ', '_')}_{int(datetime.now().timestamp())}",
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
                    "value": datetime.now().strftime("%d.%m.%Y")
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


def main():
    """Hlavná funkcia aplikácie."""
    
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
        st.markdown(f"📅 **{date.today().strftime('%d.%m.%Y')}**")
        
        # QR kód info
        st.markdown("---")
        st.markdown("### 📱 QR kódy a NFC tagy")
        st.markdown("""
        **Základné linky:**
        
        - Účastník: `https://giantgym.streamlit.app/?view=participant`
        - Tréner: `https://giantgym.streamlit.app/?view=trainer`
        - Štatistiky: `https://giantgym.streamlit.app/?view=statistics`
        
        **Unikátne URL pre automatické prihlásenie:**
        
        `https://giantgym.streamlit.app/?view=participant&name=MENO&membership=TYP&time=ČAS&auto=1`
        
        **Parametre:**
        - `name` - Meno a priezvisko (URL encoded, napr. `Ján%20Novák`)
        - `membership` - Typ členstva (presne: `Skúšobný tréning`, `Mesačné členstvo`, `Jednorázový vstup`, `Ročné členstvo`)
        - `time` - Čas tréningu (`9:00`, `17:00`, `18:30`)
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
    else:
        participant_view(worksheet, query_params)


if __name__ == "__main__":
    main()
