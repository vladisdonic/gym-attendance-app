"""
Aplikácia na evidenciu účasti na tréningoch
- Účastníci sa prihlasujú cez QR kód
- Tréner vidí počet prihlásených
- Dáta sa ukladajú do Google Sheets
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import time
import pandas as pd
import json
from urllib.parse import unquote, quote
import qrcode
import zipfile
import io
import base64
import hashlib
import pytz
from PIL import Image, ImageDraw, ImageFont
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

# Časy tréningov - všetky (pre trénerský prehľad a štatistiky)
TRAINING_TIMES = [
    "7:00",
    "9:00",
    "15:30",
    "17:00",
    "18:30"
]

# Časy tréningov podľa dňa: víkend len 9:00, týždeň bez 9:00
TRAINING_TIMES_WEEKDAY = ["7:00", "15:30", "17:00", "18:30"]  # Po–Pia
TRAINING_TIMES_WEEKEND = ["9:00"]  # So–Ne

# Iba manuálne prihlásenie (Tréner): Ut a Št 17:30 – nie je v QR/participant formulári
MANUAL_ONLY_TRAINING = "17:30 - ženský tréning s Diankou"
MANUAL_ONLY_WEEKDAYS = (1, 3)  # Tuesday=1, Thursday=3


def get_training_times_for_today():
    """Vráti zoznam časov tréningov dostupných dnes. Cez víkend len 9:00, cez týždeň bez 9:00."""
    now = get_local_time()
    # Python: Monday=0, Sunday=6
    if now.weekday() >= 5:  # Sobota(5) alebo Nedeľa(6)
        return TRAINING_TIMES_WEEKEND
    return TRAINING_TIMES_WEEKDAY


def get_training_times_for_manual_form():
    """
    Časy tréningov pre manuálny formulár (Tréner).
    Cez týždeň obsahuje aj „17:30 - ženský tréning s Diankou“ v Ut a Št.
    Tento tréning nie je dostupný cez QR ani cez formulár účastníka.
    """
    times = get_training_times_for_today()
    now = get_local_time()
    if now.weekday() in MANUAL_ONLY_WEEKDAYS:  # Ut=1, Št=3
        return times + [MANUAL_ONLY_TRAINING]
    return times


# Heslo pre trénerskú časť
TRAINER_PASSWORD = "supernova"

# Heslo pre dokumentáciu
DOCS_PASSWORD = "supernova"

# URL PWA (Firebase Hosting) pre kartu člena
PWA_BASE_URL = "https://giantgym-app.web.app"

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
    """Získanie alebo vytvorenie hárku pre dnešný deň (YYYY-MM-DD)."""
    today = get_local_time().date()
    today_str = today.strftime("%Y-%m-%d")
    cache_key = f"cached_today_worksheet_{spreadsheet_id}_{today_str}"

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(today_str)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=today_str,
                rows=1000,
                cols=5,
                index=0
            )
            worksheet.update('A1:E1', [['Čas', 'Meno', 'Typ členstva', 'Čas tréningu', 'Poznámka']])
            worksheet.format('A1:E1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
        st.session_state[cache_key] = worksheet
        return worksheet
    except Exception as e:
        error_msg = str(e)
        if '429' in error_msg or 'Quota exceeded' in error_msg or 'quota' in error_msg.lower():
            if cache_key in st.session_state:
                st.warning("⚠️ API limit prekročený – zobrazujem posledný načítaný hárok.")
                return st.session_state[cache_key]
            st.warning("⚠️ **API limit prekročený** – počkaj 1–2 minúty a obnov stránku.")
        else:
            st.error(f"Chyba pri prístupe k spreadsheet: {e}")
        return None


def is_already_registered(worksheet, name, training_time):
    """Skontroluje, či je člen už prihlásený na daný tréning v ten istý deň."""
    try:
        records = worksheet.get_all_records()
        if not records:
            return False
        time_col = 'Čas tréningu' if 'Čas tréningu' in records[0] else ('Tréning' if 'Tréning' in records[0] else None)
        name_col = 'Meno' if 'Meno' in records[0] else None
        if not time_col or not name_col:
            return False
        for row in records:
            if str(row.get(name_col, '')).strip() == str(name).strip() and str(row.get(time_col, '')).strip() == str(training_time).strip():
                return True
        return False
    except Exception:
        return False


def add_attendance(worksheet, name, membership_type, training_time="", client_timestamp=None, note=""):
    """Pridanie záznamu o účasti. Poznámka sa zapíše do stĺpca Poznámka v Google Sheet."""
    try:
        if is_already_registered(worksheet, name, training_time):
            return "duplicate"
        if client_timestamp:
            timestamp = client_timestamp
        else:
            timestamp = get_local_time().strftime("%H:%M:%S")
        note_str = (note or "").strip()
        row = [timestamp, name, membership_type, training_time, note_str]
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
        all_values = worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) >= 4:
                row_timestamp = row[0] if len(row) > 0 else ""
                row_name = row[1] if len(row) > 1 else ""
                row_membership = row[2] if len(row) > 2 else ""
                row_time = row[3] if len(row) > 3 else ""
                if (row_name == name and row_membership == membership_type and
                        row_time == training_time and row_timestamp.startswith(timestamp[:5])):
                    worksheet.delete_rows(i)
                    return True
        return False
    except Exception as e:
        st.error(f"Chyba pri vymazávaní: {e}")
        return False


def get_all_worksheets(client, spreadsheet_id, use_cache=True, cache_ttl=120):
    """Získanie všetkých hárkov zo spreadsheetu. Cache 120 s (obmedzenie API quota)."""
    cache_key = f"worksheets_list_{spreadsheet_id}"
    cache_time_key = f"worksheets_list_time_{spreadsheet_id}"
    if use_cache and cache_key in st.session_state and cache_time_key in st.session_state:
        if time.time() - st.session_state[cache_time_key] < cache_ttl:
            return st.session_state[cache_key]
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        if use_cache:
            st.session_state[cache_key] = worksheets
            st.session_state[cache_time_key] = time.time()
        return worksheets
    except Exception as e:
        error_msg = str(e)
        if ('429' in error_msg or 'Quota exceeded' in error_msg) and cache_key in st.session_state:
            st.warning("⚠️ API limit – používam zoznam hárkov z cache.")
            return st.session_state[cache_key]
        st.error(f"Chyba pri načítaní hárkov: {e}")
        return []


def get_all_attendance_data(client, spreadsheet_id, use_cache=True, cache_ttl=600):
    """
    Získanie všetkých dát o účasti zo všetkých hárkov.
    
    Args:
        client: Google Sheets klient
        spreadsheet_id: ID spreadsheetu
        use_cache: Použiť cache (default: True)
        cache_ttl: Cache TTL v sekundách (default: 600 = 10 minút)
    
    Returns:
        DataFrame s dátami o dochádzke
    """
    import time
    
    # Cache key
    cache_key = f'attendance_data_{spreadsheet_id}'
    cache_time_key = f'attendance_data_time_{spreadsheet_id}'
    
    # Skontrolovať cache
    if use_cache and cache_key in st.session_state:
        cache_time = st.session_state.get(cache_time_key, 0)
        current_time = time.time()
        
        # Ak je cache ešte platný (menej ako cache_ttl sekúnd starý)
        if current_time - cache_time < cache_ttl:
            return st.session_state[cache_key].copy()
    
    try:
        worksheets = get_all_worksheets(client, spreadsheet_id)
        all_data = []
        
        for worksheet in worksheets:
            try:
                records = worksheet.get_all_records()
                if records:
                    df = pd.DataFrame(records)
                    sheet_name = worksheet.title
                    df['Dátum'] = sheet_name
                    all_data.append(df)
            except Exception:
                continue
        
        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            
            # Uložiť do cache
            if use_cache:
                st.session_state[cache_key] = result_df.copy()
                st.session_state[cache_time_key] = time.time()
            
            return result_df
        return pd.DataFrame()
    except Exception as e:
        error_msg = str(e)
        
        # Špeciálna správa pre API quota exceeded
        if '429' in error_msg or 'Quota exceeded' in error_msg or 'quota' in error_msg.lower():
            st.warning("⚠️ **API limit prekročený**")
            st.info("""
            Google Sheets API má limit na počet požiadaviek za minútu. 
            Aplikácia používa cache na zníženie počtu volaní.
            
            **Riešenie:**
            - Počkaj 1-2 minúty a skús znova
            - Použi tlačidlo "💾 Obnoviť cache" len keď je to nevyhnutné
            - Cache sa automaticky obnoví každých 10 minút
            """)
            
            # Skúsiť vrátiť cache aj keď je starý
            if use_cache and cache_key in st.session_state:
                st.info("📦 Zobrazujem dáta z cache (môžu byť staršie)")
                return st.session_state[cache_key].copy()
        
        st.error(f"Chyba pri načítaní všetkých dát: {e}")
        return pd.DataFrame()


def get_monthly_statistics(client, spreadsheet_id, df=None):
    """
    Výpočet štatistík za jednotlivé mesiace - top 3 najaktívnejší členovia.
    
    Args:
        client: Google Sheets klient (použije sa len ak df nie je poskytnutý)
        spreadsheet_id: ID spreadsheetu (použije sa len ak df nie je poskytnutý)
        df: DataFrame s dátami (voliteľné, ak nie je poskytnutý, načíta sa)
    """
    try:
        # Ak nie je poskytnutý DataFrame, načítať ho
        if df is None:
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


def prepare_attendance_dataframe(client, spreadsheet_id, df=None):
    """
    Pripraví DataFrame s dátami o dochádzke pre analýzy.
    
    Args:
        client: Google Sheets klient (použije sa len ak df nie je poskytnutý)
        spreadsheet_id: ID spreadsheetu (použije sa len ak df nie je poskytnutý)
        df: DataFrame s dátami (voliteľné, ak nie je poskytnutý, načíta sa)
    """
    try:
        # Ak nie je poskytnutý DataFrame, načítať ho
        if df is None:
            df = get_all_attendance_data(client, spreadsheet_id)
        
        if df.empty:
            return pd.DataFrame()
        
        # Konverzia dátumov
        df['Dátum_parsed'] = pd.to_datetime(df['Dátum'], errors='coerce', format='%Y-%m-%d')
        df = df.dropna(subset=['Dátum_parsed'])
        
        # Pridanie dodatočných stĺpcov pre analýzy
        df['Dátum_only'] = df['Dátum_parsed'].dt.date
        df['Týždeň'] = df['Dátum_parsed'].dt.to_period('W')
        df['Mesiac'] = df['Dátum_parsed'].dt.to_period('M')
        df['Deň_v_týždni'] = df['Dátum_parsed'].dt.dayofweek  # 0 = Monday, 6 = Sunday
        df['Deň_v_týždni_názov'] = df['Dátum_parsed'].dt.day_name()  # Názov dňa v angličtine
        df['Deň_v_mesiaci'] = df['Dátum_parsed'].dt.day
        df['Týždeň_v_roku'] = df['Dátum_parsed'].dt.isocalendar().week
        
        # Získanie času tréningu
        time_column = 'Čas tréningu' if 'Čas tréningu' in df.columns else 'Tréning'
        if time_column in df.columns:
            df['Čas_tréningu'] = df[time_column]
        else:
            df['Čas_tréningu'] = ''
        
        return df
    except Exception as e:
        st.error(f"Chyba pri príprave dát: {e}")
        return pd.DataFrame()


def get_attendance_trends(df, period='denne'):
    """Vráti trendy dochádzky podľa periódy (denne/týždenne/mesačne)."""
    if df.empty:
        return pd.DataFrame()
    
    if period == 'denne':
        trends = df.groupby('Dátum_only').size().reset_index(name='Počet')
        trends.columns = ['Dátum', 'Počet']
        trends = trends.sort_values('Dátum')
    elif period == 'týždenne':
        trends = df.groupby('Týždeň').size().reset_index(name='Počet')
        trends['Týždeň_str'] = trends['Týždeň'].astype(str)
        trends = trends.sort_values('Týždeň')
        trends.columns = ['Týždeň', 'Počet', 'Týždeň_str']
    elif period == 'mesačne':
        trends = df.groupby('Mesiac').size().reset_index(name='Počet')
        trends['Mesiac_str'] = trends['Mesiac'].astype(str)
        trends = trends.sort_values('Mesiac')
        trends.columns = ['Mesiac', 'Počet', 'Mesiac_str']
    else:
        return pd.DataFrame()
    
    return trends


def get_average_attendance_per_member(df):
    """Vypočíta priemernú dochádzku na člena."""
    if df.empty:
        return 0.0, {}
    
    member_counts = df['Meno'].value_counts()
    if len(member_counts) == 0:
        return 0.0, {}
    
    average = member_counts.mean()
    member_stats = {
        'Priemer': average,
        'Medián': member_counts.median(),
        'Maximum': member_counts.max(),
        'Minimum': member_counts.min(),
        'Celkový_počet_členov': len(member_counts),
        'Celkový_počet_tréningov': len(df)
    }
    
    return average, member_stats


def get_most_active_days_weeks(df):
    """Vráti najaktívnejšie dni a týždne."""
    if df.empty:
        return {}, {}
    
    # Najaktívnejšie dni
    daily_counts = df.groupby('Dátum_only').size().sort_values(ascending=False)
    top_days = daily_counts.head(10).to_dict()
    
    # Najaktívnejšie týždne
    weekly_counts = df.groupby('Týždeň').size().sort_values(ascending=False)
    top_weeks = {}
    for week, count in weekly_counts.head(10).items():
        top_weeks[str(week)] = count
    
    return top_days, top_weeks


def get_training_time_comparison(df):
    """Porovnanie dochádzky medzi rôznymi časmi tréningov."""
    if df.empty or 'Čas_tréningu' not in df.columns:
        return pd.DataFrame()
    
    time_counts = df['Čas_tréningu'].value_counts().reset_index()
    time_counts.columns = ['Čas', 'Počet']
    time_counts = time_counts.sort_values('Čas')
    
    return time_counts


def create_attendance_heatmap(df):
    """Vytvorí heatmapu dochádzky (kalendárny pohľad)."""
    if df.empty:
        return None
    
    # Pripraviť dáta pre heatmapu
    df['Rok'] = df['Dátum_parsed'].dt.year
    df['Mesiac_num'] = df['Dátum_parsed'].dt.month
    df['Deň'] = df['Dátum_parsed'].dt.day
    
    # Zoskupiť podľa dátumu
    daily_counts = df.groupby(['Dátum_only']).size().reset_index(name='Počet')
    daily_counts['Dátum_parsed'] = pd.to_datetime(daily_counts['Dátum_only'])
    daily_counts['Rok'] = daily_counts['Dátum_parsed'].dt.year
    daily_counts['Mesiac'] = daily_counts['Dátum_parsed'].dt.month
    daily_counts['Deň'] = daily_counts['Dátum_parsed'].dt.day
    daily_counts['Deň_v_týždni'] = daily_counts['Dátum_parsed'].dt.dayofweek
    daily_counts['Týždeň'] = daily_counts['Dátum_parsed'].dt.isocalendar().week
    
    # Vytvoriť pivot tabuľku pre heatmapu
    if len(daily_counts) > 0:
        try:
            # Zoskupiť podľa týždňa a dňa v týždni
            heatmap_data = daily_counts.groupby(['Týždeň', 'Deň_v_týždni'])['Počet'].sum().reset_index()
            
            if heatmap_data.empty:
                return None
            
            # Vytvoriť pivot tabuľku
            pivot_table = heatmap_data.pivot(index='Týždeň', columns='Deň_v_týždni', values='Počet').fillna(0)
            
            # Kontrola, či pivot_table nie je prázdny
            if pivot_table.empty or len(pivot_table) == 0 or len(pivot_table.columns) == 0:
                return None
            
            # Zabezpečiť, aby pivot_table mal aspoň 7 stĺpcov (pre všetky dni v týždni)
            # Ak chýbajú nejaké dni, pridať ich s hodnotou 0
            day_names = ['Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota', 'Nedeľa']
            
            # Pridať chýbajúce stĺpce (dni v týždni)
            for day_idx in range(7):
                if day_idx not in pivot_table.columns:
                    pivot_table[day_idx] = 0
            
            # Zoradiť stĺpce podľa dní v týždni (0-6)
            pivot_table = pivot_table[[col for col in range(7) if col in pivot_table.columns]]
            
            # Kontrola, či pivot_table má správny formát
            if pivot_table.empty or len(pivot_table.columns) == 0:
                return None
            
            # Vytvoriť heatmapu pomocou plotly
            fig = px.imshow(
                pivot_table,
                labels=dict(x="Deň v týždni", y="Týždeň v roku", color="Počet prihlásení"),
                x=[day_names[i] for i in pivot_table.columns],
                color_continuous_scale='YlOrRd',
                title='Heatmapa dochádzky (Týždeň vs. Deň v týždni)',
                aspect="auto"
            )
            
            return fig
        except Exception as e:
            # V prípade chyby vrátiť None namiesto crashu
            return None
    
    return None


def get_next_training_time():
    """
    Určí čas tréningu na základe aktuálneho času a dňa v týždni.
    
    Cez víkend (So–Ne): iba tréning o 9:00.
    Cez týždeň (Po–Pia): 7:00, 15:30, 17:00, 18:30 (bez 9:00).
    
    Logika cez týždeň:
    - 00:00 - 07:59 → 7:00 (ranný)
    - 08:00 - 16:29 → 15:30 (popoludňajší)
    - 16:30 - 17:59 → 17:00 (popoludňajší)
    - 18:00 - 23:59 → 18:30 (večerný)
    
    Logika cez víkend:
    - celý deň → 9:00
    
    Returns:
        str: Čas tréningu
    """
    now = get_local_time()
    current_hour = now.hour
    current_minute = now.minute
    
    # Cez víkend (Sobota=5, Nedeľa=6) – iba 9:00
    if now.weekday() >= 5:
        return "9:00"
    
    # Cez týždeň – bez 9:00
    # 00:00 - 07:59 → 7:00 (ranný tréning)
    if current_hour < 8:
        return "7:00"
    
    # 08:00 - 16:29 → 15:30 (popoludňajší tréning)
    if current_hour < 16 or (current_hour == 16 and current_minute < 30):
        return "15:30"
    
    # 16:30 - 17:59 → 17:00 (popoludňajší tréning)
    if current_hour < 18:
        return "17:00"
    
    # 18:00 - 23:59 → 18:30 (večerný tréning)
    return "18:30"
    

def generate_club_card(name, membership, qr_url):
    """
    Generuje klubovú kartu s QR kódom ako PNG obrázok.
    Vertikálna orientácia v štýle Decathlon karty.
    
    Args:
        name: Meno člena
        membership: Typ členstva
        qr_url: URL pre QR kód
    
    Returns:
        bytes: PNG obrázok klubovej karty
    """
    # Rozmery karty - vertikálna orientácia (podobne ako Decathlon)
    card_width = 600
    card_height = 900
    
    # Klubové farby Giant Gym - čierna s červenými akcentami
    primary_color = '#0a0a0a'  # Čierna
    accent_color = '#E31E24'  # Červená Giant Gym
    text_color = '#FFFFFF'  # Biela
    
    # Vytvorenie karty
    card = Image.new('RGB', (card_width, card_height), primary_color)
    draw = ImageDraw.Draw(card)
    
    # Gradient pozadie - jemný prechod od tmavo šedej po čiernu
    for y in range(card_height):
        ratio = y / card_height
        shade = int(20 - ratio * 15)
        for x in range(card_width):
            draw.point((x, y), fill=(shade, shade, shade))
    
    # Zaoblené rohy - vytvoríme masku
    corner_radius = 40
    
    # Fonty
    try:
        logo_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        membership_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        try:
            logo_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
            name_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            membership_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
            small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        except:
            logo_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            membership_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    
    # Logo Giant Gym - pokus o načítanie loga
    try:
        import os
        logo_path = os.path.join(os.path.dirname(__file__), 'giantgym.png')
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            # Zväčšenie loga
            logo_width = 350
            logo_ratio = logo_width / logo.width
            logo_height = int(logo.height * logo_ratio)
            logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            # Centrovanie loga hore
            logo_x = (card_width - logo_width) // 2
            logo_y = 50
            
            # Ak má logo alpha kanál, použijeme ho ako masku
            if logo.mode == 'RGBA':
                card.paste(logo, (logo_x, logo_y), logo)
            else:
                card.paste(logo, (logo_x, logo_y))
        else:
            # Fallback - textové logo
            draw.text((card_width // 2, 80), "GIANT", font=logo_font, fill=text_color, anchor="mm")
            draw.text((card_width // 2, 140), "GYM", font=logo_font, fill=text_color, anchor="mm")
    except:
        # Fallback - textové logo
        draw.text((card_width // 2, 80), "GIANT", font=logo_font, fill=text_color, anchor="mm")
        draw.text((card_width // 2, 140), "GYM", font=logo_font, fill=text_color, anchor="mm")
    
    # Meno člena - pod logom
    name_y = 220
    draw.text((50, name_y), name.upper(), font=name_font, fill=text_color)
    
    # Typ členstva pod menom
    membership_y = name_y + 45
    draw.text((50, membership_y), membership, font=membership_font, fill=text_color)
    
    # QR kód - generovanie
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color='black', back_color='white')
    qr_img = qr_img.convert('RGB')
    
    # Veľkosť QR kódu - väčšia časť karty
    qr_size = 420
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    
    # Biely zaoblený obdĺžnik pre QR kód - väčší
    qr_box_padding = 30
    qr_box_width = qr_size + qr_box_padding * 2
    qr_box_height = qr_size + qr_box_padding * 2
    qr_box_x = (card_width - qr_box_width) // 2
    qr_box_y = card_height - qr_box_height - 50
    
    # Kreslenie bieleho zaokrúhleného obdĺžnika
    qr_box_radius = 25
    draw.rounded_rectangle(
        [(qr_box_x, qr_box_y), (qr_box_x + qr_box_width, qr_box_y + qr_box_height)],
        radius=qr_box_radius,
        fill='white'
    )
    
    # Vloženie QR kódu do stredu bieleho boxu
    qr_x = qr_box_x + qr_box_padding
    qr_y = qr_box_y + qr_box_padding
    card.paste(qr_img, (qr_x, qr_y))
    
    # Uloženie do bufferu
    buffer = io.BytesIO()
    card.save(buffer, format='PNG', quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()


def participant_view(worksheet, query_params=None):
    """Pohľad pre účastníka - prihlásenie na tréning."""
    st.title("🥊 Prihlásenie na tréning")
    st.markdown("---")
    
    # Načítanie parametrov z URL
    if query_params is None:
        query_params = st.query_params
    
    # URL parametre pre automatické prihlásenie
    # Dekódovanie URL parametrov (pre diakritiku a špeciálne znaky)
    url_name = unquote(query_params.get("name", ""))
    url_membership = unquote(query_params.get("membership", ""))
    url_time = unquote(query_params.get("time", ""))
    auto_submit = query_params.get("auto", "0") == "1"
    _return_url_raw = unquote(query_params.get("return_url", "")).strip()
    return_url = _return_url_raw if (_return_url_raw.startswith("https://") and " " not in _return_url_raw) else ""  # len HTTPS, bez open redirect
    
    # Časy tréningov dostupné dnes (víkend len 9:00, týždeň bez 9:00)
    training_times_today = get_training_times_for_today()
    
    # Ak čas nie je v URL, automaticky vyberieme najbližší
    if not url_time:
        url_time = get_next_training_time()
    
    # Ak URL čas nie je dostupný dnes (napr. 9:00 cez týždeň), použiť najbližší
    if url_time not in training_times_today:
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
    
    # Nájdenie indexu pre čas tréningu (v rámci dnešných časov)
    default_time_index = 0
    if url_time and url_time in training_times_today:
        for i, t in enumerate(training_times_today):
            if t == url_time.strip():
                default_time_index = i
                break
    else:
        next_time = get_next_training_time()
        for i, t in enumerate(training_times_today):
            if t == next_time:
                default_time_index = i
                break
    
    # Automatické odoslanie ak sú všetky údaje v URL a auto=1
    auto_submit_ready = (auto_submit and url_name and url_membership and url_time and 
                        url_membership in MEMBERSHIP_TYPES and url_time in training_times_today)
    
    # Sekcia na generovanie osobnej klubovej karty
    with st.expander("🎴 Vygenerovať klubovú kartu", expanded=False):
        save_name = st.text_input("Meno a priezvisko *", key="save_name", placeholder="Zadaj svoje meno...")
        save_membership = st.selectbox("Typ členstva *", MEMBERSHIP_TYPES, key="save_membership", index=1)
        
        # Generovať klubovú kartu
        if st.button("🎴 Generovať klubovú kartu", key="generate_qr", use_container_width=True, type="primary"):
            if save_name.strip():
                base_url = "https://giantgym.streamlit.app/?view=participant"
                params = {"name": save_name.strip(), "membership": save_membership}
                query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                url = f"{base_url}&{query_string}&auto=1"
                try:
                    # Generovanie klubovej karty
                    club_card_data = generate_club_card(save_name.strip(), save_membership, url)
                    st.session_state['personal_club_card'] = club_card_data
                    st.session_state['personal_qr_url'] = url
                    st.session_state['personal_qr_name'] = save_name.strip()
                    st.session_state['personal_qr_membership'] = save_membership
                    st.session_state['personal_qr_filename'] = f"giantgym_karta_{save_name.strip().replace(' ', '_')}.png"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Chyba pri generovaní karty: {e}")
            else:
                st.warning("⚠️ Prosím, zadaj meno.")
        
        # Zobrazenie vygenerovanej klubovej karty
        if st.session_state.get('personal_club_card'):
            st.markdown("---")
            st.success("✅ **Klubová karta vygenerovaná!**")
            st.markdown("### 🎴 Tvoja osobná klubová karta")
            st.image(st.session_state['personal_club_card'], caption="Tvoja klubová karta", use_container_width=True)
            st.download_button(
                label="📥 Stiahnuť klubovú kartu (.png)",
                data=st.session_state['personal_club_card'],
                file_name=st.session_state.get('personal_qr_filename', 'giantgym_karta.png'),
                mime="image/png",
                use_container_width=True
            )
            if PWA_BASE_URL and st.session_state.get('personal_qr_url'):
                pwa_card_url = f"{PWA_BASE_URL.rstrip('/')}/#/card?u={quote(st.session_state['personal_qr_url'])}&name={quote(st.session_state.get('personal_qr_name', ''))}"
                st.markdown("### 📱 PWA karta (pridať na plochu)")
                st.markdown(f"Otvoriť ako aplikáciu – zobrazí meno, QR a tlačidlo **Prihlásiť na tréning**. [Otvoriť PWA kartu]({pwa_card_url})")
            
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
            options=training_times_today,
            index=default_time_index,
            key="time_select"
        )
        
        note = st.text_input(
            "Poznámka",
            placeholder="Voliteľná poznámka",
            key="note_input"
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
                # Čas sa zapíše serverový (Europe/Bratislava)
                client_timestamp = None
                # Automatické odoslanie (bez poznámky z URL)
                result = add_attendance(worksheet, final_name, final_membership, final_time, client_timestamp, note="")
                if result is True:
                    st.success("🎉 Úspešne prihlásený/á!")
                    st.balloons()
                    
                    # Po úspešnom odoslaní presmeruj späť do PWA alebo na čistú participant stránku
                    redirect_target = return_url if return_url else 'https://giantgym.streamlit.app/?view=participant'
                    st.markdown(f"""
                    <script>
                    setTimeout(function() {{
                        window.location.href = {json.dumps(redirect_target)};
                    }}, 2000);
                    </script>
                    """, unsafe_allow_html=True)
                    return
                elif result == "duplicate":
                    st.warning("⚠️ Už si prihlásený/á na tento tréning. Nemôžeš sa prihlásiť dvakrát.")
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
                client_timestamp = None
                result = add_attendance(worksheet, name.strip(), membership, training_time, client_timestamp, note=(note or "").strip())
                if result is True:
                    st.success("🎉 Úspešne prihlásený/á!")
                    st.balloons()
                    
                    # Ak bolo odoslanie cez URL parametre, presmeruj (späť do PWA ak je return_url)
                    if auto_submit or return_url:
                        redirect_target = return_url if return_url else 'https://giantgym.streamlit.app/?view=participant'
                        st.markdown(f"""
                        <script>
                        setTimeout(function() {{
                            window.location.href = {json.dumps(redirect_target)};
                        }}, 2000);
                        </script>
                        """, unsafe_allow_html=True)
                elif result == "duplicate":
                    st.warning("⚠️ Už si prihlásený/á na tento tréning. Nemôžeš sa prihlásiť dvakrát.")


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
            
            wallet_times_today = get_training_times_for_today()
            wallet_next_t = get_next_training_time()
            wallet_time_index = wallet_times_today.index(wallet_next_t) if wallet_next_t in wallet_times_today else 0
            time = st.selectbox(
                "Čas tréningu *",
                options=wallet_times_today,
                index=wallet_time_index
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
            
            qr_times_today = get_training_times_for_today()
            qr_next_t = get_next_training_time()
            qr_time_index = qr_times_today.index(qr_next_t) if qr_next_t in qr_times_today else 0
            qr_time = st.selectbox(
                "Čas tréningu *",
                options=qr_times_today,
                index=qr_time_index,
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
    """Pohľad so štatistikami - pokročilé analýzy a grafy."""
    # Kontrola autentifikácie
    if not check_trainer_auth():
        trainer_login()
        return
    
    st.title("📊 Pokročilé Štatistiky")
    st.markdown("---")
    
    # Tlačidlá na obnovenie a odhlásenie
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 Obnoviť štatistiky", use_container_width=True):
            # Vymazať cache pre vynútené obnovenie
            cache_key = f'attendance_data_{spreadsheet_id}'
            cache_time_key = f'attendance_data_time_{spreadsheet_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            if cache_time_key in st.session_state:
                del st.session_state[cache_time_key]
            st.rerun()
    with col2:
        if st.button("💾 Obnoviť cache", use_container_width=True, help="Vynútiť nové načítanie dát z Google Sheets"):
            # Vymazať cache
            cache_key = f'attendance_data_{spreadsheet_id}'
            cache_time_key = f'attendance_data_time_{spreadsheet_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            if cache_time_key in st.session_state:
                del st.session_state[cache_time_key]
            st.rerun()
    with col3:
        if st.button("🚪 Odhlásiť sa", use_container_width=True):
            st.session_state.trainer_authenticated = False
            st.rerun()
    
    # Načítanie dát s cache
    cache_key = f'attendance_data_{spreadsheet_id}'
    cache_time_key = f'attendance_data_time_{spreadsheet_id}'
    is_cached = cache_key in st.session_state
    
    with st.spinner("Načítavam dáta..."):
        # Načítať dáta len raz (s cache)
        raw_df = get_all_attendance_data(client, spreadsheet_id, use_cache=True, cache_ttl=300)
        
        # Pripraviť DataFrame pre analýzy (bez ďalšieho API volania)
        df = prepare_attendance_dataframe(client, spreadsheet_id, df=raw_df)
        
        # Vypočítať štatistiky (bez ďalšieho API volania)
        monthly_stats = get_monthly_statistics(client, spreadsheet_id, df=raw_df)
    
    # Zobraziť informáciu o cache
    if is_cached and cache_time_key in st.session_state:
        import time
        cache_age = int(time.time() - st.session_state[cache_time_key])
        cache_age_min = cache_age // 60
        cache_age_sec = cache_age % 60
        
        if cache_age < 300:  # Menej ako 5 minút
            st.info(f"💾 Dáta z cache (staré {cache_age_min}m {cache_age_sec}s). Pre najnovšie dáta klikni 'Obnoviť cache'.")
        else:
            st.warning(f"⚠️ Cache je starý ({cache_age_min}m {cache_age_sec}s). Dáta sa automaticky obnovia pri ďalšom načítaní.")
    
    if df.empty:
        st.info("Zatiaľ nie sú dostupné žiadne dáta pre analýzu.")
        return
    
    # Taby pre rôzne sekcie štatistík
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Trendy", 
        "👥 Priemerná dochádzka", 
        "🏆 Najaktívnejšie", 
        "⏰ Časy tréningov", 
        "🗓️ Heatmapa", 
        "📅 Top členovia"
    ])
    
    # TAB 1: Trendy dochádzky
    with tab1:
        st.markdown("### 📈 Trendy dochádzky")
        st.markdown("---")
        
        period = st.radio(
            "Vyber periódu:",
            ["denne", "týždenne", "mesačne"],
            horizontal=True,
            key="trend_period"
        )
        
        trends = get_attendance_trends(df, period)
        
        if not trends.empty:
            if period == 'denne':
                fig = px.line(
                    trends, 
                    x='Dátum', 
                    y='Počet',
                    title=f'Denný trend dochádzky',
                    labels={'Dátum': 'Dátum', 'Počet': 'Počet prihlásení'},
                    markers=True
                )
            elif period == 'týždenne':
                fig = px.bar(
                    trends,
                    x='Týždeň_str',
                    y='Počet',
                    title='Týždenný trend dochádzky',
                    labels={'Týždeň_str': 'Týždeň', 'Počet': 'Počet prihlásení'}
                )
                fig.update_xaxes(tickangle=45)
            else:  # mesačne
                fig = px.bar(
                    trends,
                    x='Mesiac_str',
                    y='Počet',
                    title='Mesačný trend dochádzky',
                    labels={'Mesiac_str': 'Mesiac', 'Počet': 'Počet prihlásení'}
                )
                fig.update_xaxes(tickangle=45)
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Zobrazenie tabuľky
            with st.expander("📋 Detailné dáta"):
                st.dataframe(trends, use_container_width=True)
        else:
            st.info("Žiadne dáta pre zobrazenie trendov.")
    
    # TAB 2: Priemerná dochádzka na člena
    with tab2:
        st.markdown("### 👥 Priemerná dochádzka na člena")
        st.markdown("---")
        
        average, member_stats = get_average_attendance_per_member(df)
        
        if average > 0:
            # Metriky
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Priemerná dochádzka", f"{average:.1f}", "tréningov/člen")
            with col2:
                st.metric("Medián", f"{member_stats['Medián']:.1f}", "tréningov")
            with col3:
                st.metric("Maximum", f"{member_stats['Maximum']}", "tréningov")
            with col4:
                st.metric("Celkový počet členov", f"{member_stats['Celkový_počet_členov']}", "")
            
            st.markdown("---")
            
            # Graf distribúcie dochádzky
            member_counts = df['Meno'].value_counts()
            
            st.markdown("#### 📊 Distribúcia dochádzky")
            fig = px.histogram(
                x=member_counts.values,
                nbins=20,
                title='Rozdelenie počtu tréningov medzi členmi',
                labels={'x': 'Počet tréningov', 'y': 'Počet členov'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Top 10 najaktívnejších
            st.markdown("#### 🏆 Top 10 najaktívnejších členov")
            top_members = member_counts.head(10).reset_index()
            top_members.columns = ['Meno', 'Počet tréningov']
            top_members['Poradie'] = range(1, len(top_members) + 1)
            
            fig = px.bar(
                top_members,
                x='Počet tréningov',
                y='Meno',
                orientation='h',
                title='Top 10 najaktívnejších členov',
                labels={'Počet tréningov': 'Počet tréningov', 'Meno': 'Meno'}
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("📋 Zoznam všetkých členov"):
                all_members = member_counts.reset_index()
                all_members.columns = ['Meno', 'Počet tréningov']
                all_members = all_members.sort_values('Počet tréningov', ascending=False)
                st.dataframe(all_members, use_container_width=True)
        else:
            st.info("Žiadne dáta pre výpočet priemernej dochádzky.")
    
    # TAB 3: Najaktívnejšie dni a týždne
    with tab3:
        st.markdown("### 🏆 Najaktívnejšie dni a týždne")
        st.markdown("---")
        
        top_days, top_weeks = get_most_active_days_weeks(df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📅 Top 10 najaktívnejších dní")
            if top_days:
                days_df = pd.DataFrame(list(top_days.items()), columns=['Dátum', 'Počet'])
                days_df['Dátum'] = pd.to_datetime(days_df['Dátum'])
                days_df = days_df.sort_values('Počet', ascending=True)
                
                fig = px.bar(
                    days_df,
                    x='Počet',
                    y='Dátum',
                    orientation='h',
                    title='Najaktívnejšie dni',
                    labels={'Počet': 'Počet prihlásení', 'Dátum': 'Dátum'}
                )
                fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("📋 Zoznam dní"):
                    days_df_display = days_df.sort_values('Počet', ascending=False)
                    days_df_display['Dátum'] = days_df_display['Dátum'].dt.strftime('%d.%m.%Y')
                    st.dataframe(days_df_display[['Dátum', 'Počet']], use_container_width=True)
            else:
                st.info("Žiadne dáta pre najaktívnejšie dni.")
        
        with col2:
            st.markdown("#### 📆 Top 10 najaktívnejších týždňov")
            if top_weeks:
                weeks_df = pd.DataFrame(list(top_weeks.items()), columns=['Týždeň', 'Počet'])
                weeks_df = weeks_df.sort_values('Počet', ascending=True)
                
                fig = px.bar(
                    weeks_df,
                    x='Počet',
                    y='Týždeň',
                    orientation='h',
                    title='Najaktívnejšie týždne',
                    labels={'Počet': 'Počet prihlásení', 'Týždeň': 'Týždeň'}
                )
                fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("📋 Zoznam týždňov"):
                    weeks_df_display = weeks_df.sort_values('Počet', ascending=False)
                    st.dataframe(weeks_df_display, use_container_width=True)
            else:
                st.info("Žiadne dáta pre najaktívnejšie týždne.")
        
        # Analýza podľa dní v týždni
        st.markdown("---")
        st.markdown("#### 📊 Dochádzka podľa dní v týždni")
        day_counts = df.groupby('Deň_v_týždni').size().reset_index(name='Počet')
        day_names = ['Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota', 'Nedeľa']
        
        # Mapovať indexy (0-6) na slovenské názvy dní
        day_counts['Deň'] = day_counts['Deň_v_týždni'].apply(
            lambda x: day_names[int(x)] if isinstance(x, (int, float)) and 0 <= int(x) < len(day_names) else 'Neznámy'
        )
        day_counts = day_counts.sort_values('Deň_v_týždni')
        
        fig = px.bar(
            day_counts,
            x='Deň',
            y='Počet',
            title='Priemerná dochádzka podľa dní v týždni',
            labels={'Počet': 'Počet prihlásení', 'Deň': 'Deň v týždni'}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # TAB 4: Porovnanie časov tréningov
    with tab4:
        st.markdown("### ⏰ Porovnanie dochádzky medzi časmi tréningov")
        st.markdown("---")
        
        time_comparison = get_training_time_comparison(df)
        
        if not time_comparison.empty:
            # Graf
            fig = px.bar(
                time_comparison,
                x='Čas',
                y='Počet',
                title='Dochádzka podľa času tréningu',
                labels={'Počet': 'Počet prihlásení', 'Čas': 'Čas tréningu'},
                color='Počet',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Koláčový graf
            fig_pie = px.pie(
                time_comparison,
                values='Počet',
                names='Čas',
                title='Rozdelenie dochádzky podľa času tréningu'
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Metriky
            st.markdown("#### 📊 Štatistiky")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Najobľúbenejší čas", time_comparison.loc[time_comparison['Počet'].idxmax(), 'Čas'])
            with col2:
                st.metric("Celkový počet", f"{time_comparison['Počet'].sum()}")
            with col3:
                st.metric("Priemer na čas", f"{time_comparison['Počet'].mean():.1f}")
            
            # Tabuľka
            with st.expander("📋 Detailné porovnanie"):
                time_comparison_display = time_comparison.copy()
                time_comparison_display['Percento'] = (time_comparison_display['Počet'] / time_comparison_display['Počet'].sum() * 100).round(2)
                st.dataframe(time_comparison_display, use_container_width=True)
        else:
            st.info("Žiadne dáta pre porovnanie časov tréningov.")
    
    # TAB 5: Heatmapa dochádzky
    with tab5:
        st.markdown("### 🗓️ Heatmapa dochádzky (Kalendárny pohľad)")
        st.markdown("---")
        
        heatmap_fig = create_attendance_heatmap(df)
        
        if heatmap_fig:
            st.plotly_chart(heatmap_fig, use_container_width=True)
            
            # Alternatívna heatmapa - podľa dní v týždni a mesiacov
            st.markdown("---")
            st.markdown("#### 📅 Heatmapa podľa mesiacov a dní")
            
            df['Mesiac_názov'] = df['Dátum_parsed'].dt.strftime('%Y-%m')
            monthly_daily = df.groupby(['Mesiac_názov', 'Deň_v_týždni']).size().reset_index(name='Počet')
            
            if not monthly_daily.empty:
                try:
                    # Vytvoriť pivot tabuľku
                    pivot_data = monthly_daily.pivot(index='Mesiac_názov', columns='Deň_v_týždni', values='Počet').fillna(0)
                    
                    # Kontrola, či pivot_data nie je prázdny
                    if pivot_data.empty or len(pivot_data) == 0 or len(pivot_data.columns) == 0:
                        st.info("Žiadne dáta pre vytvorenie heatmapy podľa mesiacov.")
                    else:
                        # Pridať chýbajúce stĺpce (dni v týždni)
                        for day_idx in range(7):
                            if day_idx not in pivot_data.columns:
                                pivot_data[day_idx] = 0
                        
                        # Zoradiť stĺpce podľa dní v týždni (0-6)
                        pivot_data = pivot_data[[col for col in range(7) if col in pivot_data.columns]]
                        
                        # Definovať názvy dní
                        day_names_heat = ['Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota', 'Nedeľa']
                        
                        fig_heat = px.imshow(
                            pivot_data,
                            labels=dict(x="Deň v týždni", y="Mesiac", color="Počet"),
                            x=[day_names_heat[i] for i in pivot_data.columns],
                            color_continuous_scale='YlOrRd',
                            title='Heatmapa dochádzky: Mesiac vs. Deň v týždni',
                            aspect="auto"
                        )
                        fig_heat.update_layout(height=500)
                        st.plotly_chart(fig_heat, use_container_width=True)
                except Exception as e:
                    st.info("Žiadne dáta pre vytvorenie heatmapy podľa mesiacov.")
            else:
                st.info("Žiadne dáta pre vytvorenie heatmapy podľa mesiacov.")
        else:
            st.info("Žiadne dáta pre vytvorenie heatmapy.")
    
    # TAB 6: Top členovia (pôvodná funkcionalita)
    with tab6:
        st.markdown("### 📅 Top členovia podľa mesiacov")
        st.markdown("---")
        
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
                    
                    st.markdown(f"#### 📅 {month_display}")
                    
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
            # Zoskupenie podľa času tréningu (vrátane manuálneho „17:30 - ženský tréning s Diankou“ v Ut/Št)
            for training_time in get_training_times_for_manual_form():
                time_df = df[df[time_column] == training_time]
                count = len(time_df)
                
                with st.expander(f"🕐 {training_time} - {count} prihlásených", expanded=True):
                    if not time_df.empty:
                        # Zobrazenie každého účastníka s tlačidlom na vymazanie
                        for idx, row in time_df.iterrows():
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                note_text = row.get('Poznámka', '') or ''
                                note_part = f" — _{note_text}_" if note_text else ""
                                st.markdown(f"**{row['Meno']}** - {row['Typ členstva']} ({row['Čas']}){note_part}")
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
                note_text = row.get('Poznámka', '') or ''
                note_part = f" — _{note_text}_" if note_text else ""
                st.markdown(f"**{row['Meno']}** - {row['Typ členstva']}{time_info} ({row['Čas']}){note_part}")
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
    """Pohľad pre QR kód scanner v gyme - všetko v jednej karte."""
    
    st.title("📷 QR Kód Scanner - Gym")
    
    # Inicializácia session state pre posledné prihlásenie
    if 'last_scan_success' not in st.session_state:
        st.session_state.last_scan_success = None
    if 'last_scan_time' not in st.session_state:
        st.session_state.last_scan_time = 0
    
    # Zobraziť upozornenie na duplicitu (ak sa člen pokúsil prihlásiť 2x)
    if st.session_state.get('scan_duplicate_message'):
        st.warning(f"⚠️ {st.session_state.scan_duplicate_message}")
        del st.session_state.scan_duplicate_message
    
    # Zobraziť posledné úspešné prihlásenie (ak bolo v posledných 5 sekundách)
    import time
    current_time = time.time()
    if st.session_state.last_scan_success and (current_time - st.session_state.last_scan_time) < 5:
        scan_data = st.session_state.last_scan_success
        st.markdown(f"""
        <div style="padding: 25px; border-radius: 15px; background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; text-align: center; margin: 10px 0 20px 0; animation: fadeIn 0.3s;">
            <h1 style="margin: 0; font-size: 42px;">✅</h1>
            <h2 style="margin: 8px 0; font-size: 24px;">{scan_data['name']}</h2>
            <p style="margin: 5px 0; font-size: 16px; opacity: 0.95;">Úspešne prihlásený/á</p>
            <p style="margin: 3px 0; font-size: 14px; opacity: 0.85;">{scan_data['membership']} • {scan_data['time']}</p>
        </div>
        <style>@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}</style>
        """, unsafe_allow_html=True)
    
    # Spracovať údaje z query params
    query_params = st.query_params
    qr_name = unquote(query_params.get("qr_name", ""))
    qr_membership = unquote(query_params.get("qr_membership", ""))
    qr_time = unquote(query_params.get("qr_time", ""))
    
    # Ak máme údaje z QR kódu - spracovať a uložiť
    if qr_name and qr_membership:
        training_times_today = get_training_times_for_today()
        if not qr_time:
            qr_time = get_next_training_time()
        # Ak čas z QR nie je dostupný dnes (napr. 9:00 cez týždeň), použiť najbližší
        if qr_time not in training_times_today:
            qr_time = get_next_training_time()
        
        # Validácia (iba dnešné časy)
        is_valid = qr_membership in MEMBERSHIP_TYPES and qr_time in training_times_today
        
        if is_valid:
            # Uložiť dochádzku (kontrola duplicity je v add_attendance)
            result = add_attendance(worksheet, qr_name, qr_membership, qr_time)
            if result is True:
                # Uložiť do session state pre zobrazenie
                st.session_state.last_scan_success = {
                    'name': qr_name,
                    'membership': qr_membership,
                    'time': qr_time
                }
                st.session_state.last_scan_time = time.time()
                st.balloons()
            elif result == "duplicate":
                st.session_state.scan_duplicate_message = f"{qr_name} je už prihlásený/á na tréning o {qr_time}."
        
        # Vyčistiť query params a reloadnúť
        st.query_params.clear()
        st.query_params["view"] = "scanner"
        st.rerun()
    
    st.markdown("---")
    
    # Sekcia: QR Scanner
    # Tlačidlo na reštartovanie scanneru
    if st.button("🔄 Reštartovať Scanner", key="start_scanner", use_container_width=True):
        st.rerun()
    
    # QR Scanner - zobrazuje úspech priamo v scanneri, automaticky reštartuje
    scanner_html = """
    <style>
        #qr-scanner-container {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            position: relative;
        }
        #qr-scanner-status {
            padding: 12px 16px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 14px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .status-ready { background: #d4edda; color: #155724; }
        .status-scanning { background: #cce5ff; color: #004085; }
        .status-success { background: #28a745; color: white; font-size: 18px; padding: 20px; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-warning { background: #fff3cd; color: #856404; }
        #qr-reader {
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
            border-radius: 12px;
            overflow: hidden;
        }
        #success-overlay {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(40, 167, 69, 0.95);
            border-radius: 12px;
            z-index: 1000;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            color: white;
            text-align: center;
            animation: fadeIn 0.3s ease;
        }
        #success-overlay.visible { display: flex; }
        #success-overlay h1 { font-size: 64px; margin: 0; }
        #success-overlay h2 { font-size: 28px; margin: 10px 0; }
        #success-overlay p { font-size: 16px; opacity: 0.9; margin: 5px 0; }
        #success-overlay .countdown { font-size: 14px; margin-top: 20px; opacity: 0.8; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        #scan-history {
            margin-top: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            max-height: 150px;
            overflow-y: auto;
        }
        .history-item {
            padding: 8px 12px;
            margin: 5px 0;
            background: white;
            border-radius: 6px;
            border-left: 4px solid #28a745;
            font-size: 14px;
        }
        .history-item .time { color: #666; font-size: 12px; }
    </style>
    
    <div id="qr-scanner-container">
        <div id="qr-scanner-status" class="status-scanning">⏳ Načítavam kameru...</div>
        <div id="qr-reader"></div>
        
        <!-- Overlay pre úspešné prihlásenie -->
        <div id="success-overlay">
            <h1>✅</h1>
            <h2 id="success-name"></h2>
            <p id="success-details"></p>
            <p class="countdown">Pokračujem za <span id="countdown">3</span>s...</p>
        </div>
        
        <!-- História prihlásení -->
        <div id="scan-history">
            <strong>📋 Dnes prihlásení:</strong>
            <div id="history-list"></div>
        </div>
    </div>
    
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <script>
    (function() {
        const statusDiv = document.getElementById('qr-scanner-status');
        const successOverlay = document.getElementById('success-overlay');
        const successName = document.getElementById('success-name');
        const successDetails = document.getElementById('success-details');
        const countdownSpan = document.getElementById('countdown');
        const historyList = document.getElementById('history-list');
        
        let html5QrcodeScanner = null;
        let isScanning = false;
        let lastScannedCode = null;
        let isProcessing = false;
        let scanHistory = [];
        
        function setStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = 'status-' + type;
        }
        
        function playSuccessSound() {
            try {
                const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleVE2WImx0rtvKRY/f6/WsHpQOE14mr+4ZzkWO3Gd0bp2RTVXZ5O4t21AHi1eb7XDgUc2UluMsMN2NSQsV3OxvHI6LEpdhrC7eDEnJE1xr7lwNidHVYCtuHUvJiJHcK21ci0mQ1B7qrRxKyQfQm2rsXAqIx47aKuubikgGTdkqattJx4VM2KoqWsjHBEvX6eoaCEZDitcpKZmHxcKJ1mjpGQdFQYjVaCiYhsUAh9Tn6BgGRIAG0+eoF4XDwAXT5ydXRYNABNLm5tbFA0AEEmamVoTCwANRpiXWBEJAAo+mJZWEAgACD2WlFQPBgAGO5WTUQ4EAAQzk5FQDAIAAjCQkE4MAgACMI+QTgsA');
                audio.volume = 0.5;
                audio.play().catch(() => {});
            } catch (e) {}
        }
        
        function showSuccess(name, membership, time) {
            successName.textContent = name;
            successDetails.textContent = membership + ' • ' + time;
            successOverlay.classList.add('visible');
            playSuccessSound();
            
            // Pridať do histórie
            const now = new Date().toLocaleTimeString('sk-SK', {hour: '2-digit', minute: '2-digit'});
            scanHistory.unshift({name, membership, time: now});
            updateHistoryDisplay();
            
            // Odpočítavanie
            let countdown = 3;
            countdownSpan.textContent = countdown;
            const countdownInterval = setInterval(() => {
                countdown--;
                countdownSpan.textContent = countdown;
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    successOverlay.classList.remove('visible');
                    restartScanner();
        }
    }, 1000);
        }
        
        function updateHistoryDisplay() {
            historyList.innerHTML = scanHistory.slice(0, 10).map(item => 
                '<div class="history-item"><strong>' + item.name + '</strong> <span class="time">' + item.time + '</span></div>'
            ).join('');
        }
        
        function saveAttendance(name, membership, time) {
            // Otvoriť URL na pozadí pre uloženie do Google Sheets
            const redirectParams = new URLSearchParams();
            redirectParams.set('view', 'scanner');
            redirectParams.set('qr_name', name);
            redirectParams.set('qr_membership', membership);
            if (time) redirectParams.set('qr_time', time);
            redirectParams.set('qr_auto', '1');
            
            const saveUrl = 'https://giantgym.streamlit.app/?' + redirectParams.toString();
            
            // Pokus o otvorenie na pozadí
            try {
                const saveWindow = window.open(saveUrl, 'giantgym_save', 'width=400,height=300,left=10000,top=10000');
                if (saveWindow) {
                    // Zavrieť okno po 5 sekundách
            setTimeout(() => {
                        try { saveWindow.close(); } catch(e) {}
            }, 5000);
                }
            } catch (e) {
                console.log('Nepodarilo sa otvoriť okno na uloženie');
            }
        }
        
        function onScanSuccess(decodedText) {
            if (isProcessing) return;
            if (decodedText === lastScannedCode) return;
            
            lastScannedCode = decodedText;
            isProcessing = true;
            
            // Validácia
            if (!decodedText.includes('giantgym.streamlit.app')) {
                setStatus('⚠️ Neplatný QR kód', 'warning');
            setTimeout(() => {
                    isProcessing = false;
                lastScannedCode = null;
                    setStatus('📷 Namier kameru na QR kód...', 'ready');
                }, 2000);
                return;
            }
            
            try {
                    const url = new URL(decodedText);
                    const params = new URLSearchParams(url.search);
                    const name = params.get('name') || '';
                    const membership = params.get('membership') || '';
                
                // Automatický výber času ak nie je v QR kóde, alebo ak čas z QR nie je platný dnes
                // Cez víkend (So–Ne) iba 9:00; cez týždeň 7:00, 15:30, 17:00, 18:30 (bez 9:00)
                let time = params.get('time');
                const now = new Date();
                const day = now.getDay();  // 0=Nedeľa, 6=Sobota
                const isWeekend = (day === 0 || day === 6);
                const currentHour = now.getHours();
                const currentMinute = now.getMinutes();
                
                if (!time || (isWeekend && time !== '9:00') || (!isWeekend && time === '9:00')) {
                    if (isWeekend) {
                        time = '9:00';
                    } else {
                        if (currentHour < 8) {
                            time = '7:00';
                        } else if (currentHour < 16 || (currentHour === 16 && currentMinute < 30)) {
                            time = '15:30';
                        } else if (currentHour < 18) {
                            time = '17:00';
                        } else {
                            time = '18:30';
                        }
                    }
                }
                
                if (!name || !membership) {
                    setStatus('⚠️ Chýbajúce údaje v QR', 'warning');
                    setTimeout(() => {
                    isProcessing = false;
                        lastScannedCode = null;
                        setStatus('📷 Namier kameru na QR kód...', 'ready');
                    }, 2000);
                    return;
                }
                
                // Zastaviť scanner počas zobrazovania úspechu
                if (html5QrcodeScanner) {
                    html5QrcodeScanner.stop().catch(() => {});
                    isScanning = false;
                }
                
                // Zobraziť úspech
                showSuccess(name, membership, time);
                
                // Uložiť dochádzku na pozadí
                saveAttendance(name, membership, time);
                
                    } catch (e) {
                setStatus('❌ Chyba pri spracovaní', 'error');
                setTimeout(() => {
                    isProcessing = false;
                    lastScannedCode = null;
                    setStatus('📷 Namier kameru na QR kód...', 'ready');
                }, 2000);
            }
        }
        
        function restartScanner() {
            isProcessing = false;
                    lastScannedCode = null;
            isScanning = false;
            startScanner();
        }
        
        function debug(msg) {
            console.log('[QR Scanner]', msg);
        }
        
        async function startScanner() {
            if (isScanning) return;
            
            debug('Spúšťam scanner...');
            setStatus('⏳ Spúšťam kameru...', 'scanning');
            
            const cameraConfigs = [
                { facingMode: "environment" },
                { facingMode: "user" },
                { facingMode: { exact: "environment" } },
                { facingMode: { exact: "user" } }
            ];
            
            for (let i = 0; i < cameraConfigs.length; i++) {
                try {
                    html5QrcodeScanner = new Html5Qrcode("qr-reader");
                    
                    await html5QrcodeScanner.start(
                        cameraConfigs[i],
                        {
                            fps: 10,
                            qrbox: function(w, h) {
                                const size = Math.floor(Math.min(w, h) * 0.6);
                                return { width: size, height: size };
                            },
                            aspectRatio: 1.0
                        },
                        onScanSuccess,
                        () => {}
                    );
                    
                    isScanning = true;
                    debug('Kamera spustená: ' + JSON.stringify(cameraConfigs[i]));
                    setStatus('📷 Namier kameru na QR kód člena...', 'ready');
                    return;
                    
                } catch (err) {
                    debug('Pokus ' + (i + 1) + ' zlyhal: ' + err.message);
                    if (html5QrcodeScanner) {
                        try { await html5QrcodeScanner.clear(); } catch (e) {}
                        html5QrcodeScanner = null;
                    }
                    
                    if (i === cameraConfigs.length - 1) {
                        if (err.name === 'NotAllowedError') {
                            setStatus('❌ Kamera nie je povolená. Povoľ prístup v prehliadači a obnov stránku.', 'error');
                        } else if (err.name === 'NotFoundError') {
                            setStatus('❌ Kamera sa nenašla. Skontroluj pripojenie kamery.', 'error');
                        } else {
                            setStatus('❌ Chyba kamery: ' + err.message, 'error');
                        }
                    }
                }
            }
        }
        
        // Počkať na načítanie knižnice
        function init() {
            if (typeof Html5Qrcode === 'undefined') {
                debug('Čakám na Html5Qrcode knižnicu...');
                setTimeout(init, 200);
                return;
            }
            debug('Html5Qrcode knižnica načítaná');
                startScanner();
        }
        
        // Štart
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            setTimeout(init, 100);
        }
        
        // Cleanup
        window.addEventListener('beforeunload', () => {
            if (html5QrcodeScanner) {
                html5QrcodeScanner.stop().catch(() => {});
            }
        });
    })();
    </script>
    """
    
    st.components.v1.html(scanner_html, height=500)
    
    # Polling script na kontrolu localStorage - toto beží v samostatnom iframe
    # ktorý pravidelne kontroluje či scanner uložil nejaké údaje
    polling_html = """
    <script>
    (function() {
        let checkCount = 0;
        const maxChecks = 300; // 5 minút (300 * 1000ms)
        
        function checkForScanData() {
            checkCount++;
            try {
                const scanData = localStorage.getItem('giantgym_qr_scan');
                if (scanData) {
                    console.log('Našiel som scan data v localStorage:', scanData);
                    // Vymazať údaje aby sa nezopakovali
                    localStorage.removeItem('giantgym_qr_scan');
                    
                    const data = JSON.parse(scanData);
                    if (data.name && data.membership) {
                        // Vytvoriť URL a presmerovať
                        const params = new URLSearchParams();
                        params.set('view', 'scanner');
                        params.set('qr_name', data.name);
                        params.set('qr_membership', data.membership);
                        if (data.time) params.set('qr_time', data.time);
                        params.set('qr_auto', '1');
                        
                        const redirectUrl = 'https://giantgym.streamlit.app/?' + params.toString();
                        console.log('Presmerovávam na:', redirectUrl);
                        
                        // Presmerovať hlavnú stránku
                        window.top.location.href = redirectUrl;
                    }
                }
            } catch (e) {
                console.error('Chyba pri kontrole localStorage:', e);
            }
            
            // Pokračovať v kontrole
            if (checkCount < maxChecks) {
                setTimeout(checkForScanData, 1000);
            }
        }
        
        // Začať kontrolovať
        setTimeout(checkForScanData, 500);
    })();
    </script>
    <div style="display:none;">Polling active</div>
    """
    st.components.v1.html(polling_html, height=0)
    
    # Manuálny formulár ako záloha
    st.markdown("---")
    st.markdown("### ✍️ Manuálne prihlásenie")
    st.caption("Ak QR skener nefunguje, môžeš prihlásiť člena manuálne:")
    
    with st.form("manual_attendance_form"):
        manual_name = st.text_input("Meno a priezvisko", placeholder="Zadaj meno člena...")
        manual_membership = st.selectbox("Typ členstva", options=MEMBERSHIP_TYPES, index=1)
        manual_times_today = get_training_times_for_manual_form()
        next_t = get_next_training_time()
        manual_time_index = manual_times_today.index(next_t) if next_t in manual_times_today else 0
        manual_time = st.selectbox("Čas tréningu", options=manual_times_today, index=manual_time_index)
        manual_note = st.text_input("Poznámka", placeholder="Voliteľná poznámka")
        
        submitted = st.form_submit_button("✅ Prihlásiť", type="primary", use_container_width=True)
        
        if submitted:
            if manual_name.strip():
                result = add_attendance(worksheet, manual_name.strip(), manual_membership, manual_time, note=manual_note)
                if result is True:
                    st.success(f"✅ {manual_name} bol úspešne prihlásený!")
                    st.balloons()
                elif result == "duplicate":
                    st.warning(f"⚠️ {manual_name} je už prihlásený/á na tréning o {manual_time}. Nemôže sa prihlásiť dvakrát.")
                else:
                    st.error("❌ Chyba pri prihlasovaní.")
            else:
                st.warning("⚠️ Prosím, zadaj meno.")


def docs_view():
    """Pohľad pre dokumentáciu aplikácie - chránená heslom."""
    st.title("📚 Dokumentácia")
    
    # Kontrola prihlásenia
    if 'docs_authenticated' not in st.session_state:
        st.session_state.docs_authenticated = False
    
    if not st.session_state.docs_authenticated:
        st.markdown("### 🔐 Prístup k dokumentácii")
        st.info("Pre zobrazenie dokumentácie zadaj heslo.")
        
        password = st.text_input("Heslo", type="password", key="docs_password")
        
        if st.button("Prihlásiť sa", type="primary", use_container_width=True):
            if password == DOCS_PASSWORD:
                st.session_state.docs_authenticated = True
                st.rerun()
            else:
                st.error("❌ Nesprávne heslo")
        return
    
    # Tlačidlo na odhlásenie
    if st.button("🚪 Odhlásiť sa", key="docs_logout"):
        st.session_state.docs_authenticated = False
        st.rerun()
    
    st.markdown("---")
    
    # Dokumentácia
    st.markdown("""
    ## 🥊 Giant Gym - Aplikácia na evidenciu dochádzky
    
    Táto aplikácia slúži na evidenciu dochádzky členov na tréningy v Giant Gym.
    
    ---
    
    ### 📱 Ako funguje prihlasovanie
    
    1. **Člen naskenuje QR kód** - každý člen má svoju osobnú klubovú kartu s QR kódom
    2. **Automatické prihlásenie** - po naskenovaní sa člen automaticky prihlási na najbližší tréning
    3. **Údaje sa uložia** - dochádzka sa uloží do Google Sheets
    
    ---
    
    ### ⏰ Logika výberu času tréningu podľa dňa
    
    **Cez víkend (Sobota, Nedeľa):** iba tréning o **9:00**.
    
    **Cez týždeň (Pondelok–Piatok):** tréningy o 7:00, 15:30, 17:00, 18:30 (bez 9:00).
    
    | Aktuálny čas (Po–Pia) | Vybraný tréning |
    |----------------------|-----------------|
    | 00:00 - 07:59 | **7:00** (ranný) |
    | 08:00 - 16:29 | **15:30** (popoludňajší) |
    | 16:30 - 17:59 | **17:00** (popoludňajší) |
    | 18:00 - 23:59 | **18:30** (večerný) |
    
    Cez víkend sa vždy vyberie **9:00** bez ohľadu na hodinu.
    
    **Špeciálny tréning len v manuálnom prihlásení (Tréner):**  
    V **Utorok a Štvrtok** je v trénerskom manuálnom formulári (✍️ Manuálne prihlásenie) dostupný ešte tréning **17:30 - ženský tréning s Diankou**. Na tento tréning sa **nedá** prihlásiť cez QR kód ani cez formulár účastníka – iba tréner ho môže zapísať manuálne.
    
    ---
    
    ### 🚫 Prevencia duplicít
    
    Ten istý člen sa **nemôže prihlásiť 2x na rovnaký tréning** v ten istý deň. Ak sa člen pokúsi prihlásiť znova na ten istý čas, aplikácia zobrazí upozornenie a prihlásenie sa neuloží.
    
    ---
    
    ### 🎴 Klubové karty
    
    Každý člen si môže vygenerovať osobnú klubovú kartu:
    
    1. Choď na **Účastník** → **Vygenerovať klubovú kartu**
    2. Zadaj meno a typ členstva
    3. Stiahni kartu ako PNG obrázok
    4. Kartu môžeš:
       - Uložiť do galérie telefónu
       - Vytlačiť a nosiť so sebou
       - Nastaviť ako wallpaper pre rýchly prístup
    
    ---
    
    ### 📷 QR Scanner v gyme
    
    Pre hromadné skenovanie členov v gyme:
    
    **URL:** `https://giantgym.streamlit.app/?view=scanner`
    
    - Otvor túto URL na počítači s webkamerou
    - Členovia postupne skenujú svoje QR kódy
    - Po naskenovaní sa zobrazí potvrdenie a scanner je pripravený na ďalšieho člena
    
    ---
    
    ### 👨‍🏫 Trénerský prístup
    
    Tréner má prístup k:
    
    - **Zoznam prihlásených** - aktuálna dochádzka na dnešný deň
    - **Manuálne prihlásenie** - prihlásenie člena bez QR (v Ut a Št aj možnosť **17:30 - ženský tréning s Diankou**)
    - **Vymazanie dochádzky** - možnosť odstrániť nesprávne prihlásenia
    - **Štatistiky** - prehľad dochádzky za obdobie
    
    **Heslo pre trénera:** rovnaké ako pre dokumentáciu
    
    ---
    
    ### 📊 Štatistiky
    
    Dostupné štatistiky:
    
    - Celkový počet prihlásení
    - Prihlásenia podľa dňa
    - Prihlásenia podľa typu členstva
    - Prihlásenia podľa času tréningu
    - Export do CSV
    
    ---
    
    ### 🔗 URL parametre
    
    Aplikácia podporuje nasledovné URL parametre:
    
    | Parameter | Popis | Príklad |
    |-----------|-------|---------|
    | `view` | Pohľad aplikácie | `participant`, `trainer`, `scanner`, `statistics`, `docs` |
    | `name` | Meno člena | `Ján%20Novák` |
    | `membership` | Typ členstva | `Mesačné%20členstvo` |
    | `time` | Čas tréningu | `17:00` |
    | `auto` | Automatické prihlásenie | `1` |
    
    **Príklad kompletnej URL:**
    ```
    https://giantgym.streamlit.app/?view=participant&name=Ján%20Novák&membership=Mesačné%20členstvo&auto=1
    ```
    
    ---
    
    ### 🗄️ Google Sheets štruktúra
    
    Údaje sa ukladajú do Google Sheets s nasledovnými stĺpcami:
    
    | Stĺpec | Popis |
    |--------|-------|
    | Dátum | Dátum prihlásenia (DD.MM.YYYY) |
    | Čas | Čas tréningu |
    | Meno | Meno a priezvisko člena |
    | Typ členstva | Typ členstva |
    | Čas prihlásenia | Presný čas prihlásenia (HH:MM:SS) |
    
    ---
    
    ### ⚙️ Technické informácie
    
    - **Framework:** Streamlit
    - **Databáza:** Google Sheets
    - **QR kódy:** qrcode + PIL
    - **Časové pásmo:** Europe/Bratislava
    - **Hosting:** Streamlit Cloud
    
    ---
    
    ### 🆘 Riešenie problémov
    
    **Kamera nefunguje v scanneri:**
    - Povoľ prístup ku kamere v prehliadači
    - Použi Chrome alebo Safari
    - Skontroluj, či nie je kamera používaná inou aplikáciou
    
    **QR kód sa nedá naskenovať:**
    - Uisti sa, že QR kód je dobre osvetlený
    - Drž telefón stabilne
    - Skús priblížiť alebo oddialiť kameru
    
    **Prihlásenie sa neuložilo:**
    - Skontroluj internetové pripojenie
    - Počkaj na zelené potvrdenie
    - V prípade problémov použi manuálne prihlásenie v trénerskom view
    """)


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
        
        if st.button("📚 Dokumentácia", use_container_width=True):
            st.query_params["view"] = "docs"
            st.rerun()
        
        st.markdown("---")
        # Zobrazenie lokálneho dátumu
        today = get_local_time().date()
        st.markdown(f"📅 **{today.strftime('%d.%m.%Y')}**")
    
    # Zobrazenie správneho pohľadu
    if view == "trainer":
        trainer_view(worksheet)
    elif view == "statistics":
        statistics_view(client, spreadsheet_id)
    elif view == "wallet":
        wallet_pass_view()
    elif view == "scanner":
        scanner_view(worksheet)
    elif view == "docs":
        docs_view()
    else:
        participant_view(worksheet, query_params)


if __name__ == "__main__":
    main()
