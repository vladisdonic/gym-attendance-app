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


def participant_view(worksheet):
    """Pohľad pre účastníka - prihlásenie na tréning."""
    st.title("🥊 Prihlásenie na tréning")
    st.markdown("---")
    
    # Formulár na prihlásenie
    with st.form("attendance_form", clear_on_submit=True):
        name = st.text_input(
            "Meno a priezvisko *",
            placeholder="Zadaj svoje meno..."
        )
        
        membership = st.selectbox(
            "Typ členstva *",
            options=MEMBERSHIP_TYPES,
            index=1  # Predvolená hodnota: Mesačné členstvo
        )
        
        training_time = st.selectbox(
            "Čas tréningu *",
            options=TRAINING_TIMES,
            index=0
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


def statistics_view(client, spreadsheet_id):
    """Pohľad so štatistikami - najaktívnejší členovia za mesiace."""
    st.title("📊 Štatistiky")
    st.markdown("---")
    
    # Tlačidlo na obnovenie
    if st.button("🔄 Obnoviť štatistiky", use_container_width=True):
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
    st.title("👨‍🏫 Prehľad trénera")
    st.markdown("---")
    
    # Tlačidlo na obnovenie
    if st.button("🔄 Obnoviť údaje", use_container_width=True):
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
                        st.dataframe(
                            time_df[['Čas', 'Meno', 'Typ členstva']],
                            use_container_width=True,
                            hide_index=True
                        )
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
        
        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True
        )
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
    
    if "spreadsheet_id" not in st.secrets:
        st.error("⚠️ Chýba ID Google Sheetu v secrets!")
        return
    
    # Pripojenie k Google Sheets
    client = get_google_sheets_client()
    if not client:
        return
    
    worksheet = get_or_create_sheet(client, st.secrets["spreadsheet_id"])
    if not worksheet:
        return
    
    # Navigácia cez URL parametre
    query_params = st.query_params
    view = query_params.get("view", "participant")
    
    # Sidebar navigácia
    with st.sidebar:
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
        
        st.markdown("---")
        st.markdown(f"📅 **{date.today().strftime('%d.%m.%Y')}**")
        
        # QR kód info
        st.markdown("---")
        st.markdown("### 📱 QR kódy")
        st.markdown("""
        Pre prihlásenie vytvor QR kód s URL:
        
        `https://your-app.streamlit.app/?view=participant`
        
        Pre trénerský prehľad:
        
        `https://your-app.streamlit.app/?view=trainer`
        """)
    
    # Zobrazenie správneho pohľadu
    if view == "trainer":
        trainer_view(worksheet)
    elif view == "statistics":
        statistics_view(client, st.secrets["spreadsheet_id"])
    else:
        participant_view(worksheet)


if __name__ == "__main__":
    main()
