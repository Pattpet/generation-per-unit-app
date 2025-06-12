import streamlit as st
from entsoe import EntsoePandasClient
import pandas as pd
import io
import datetime

# --- Konfigurace Stránky ---
st.set_page_config(
    page_title="Pavlova stahovačka",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ ENTSOE Data Downloader")
st.markdown("""
    **Pavle** vítej v aplikaci pro stahování dat z ENTSOE Transparency Platform API pro výrobu z jednotlivých bloků.
            """)

# --- Inicializace Session State pro uložení dat a stavu zpráv ---
# Toto zajistí, že data a stav zpráv přežijí reruny Streamlit aplikace.
if 'data_frame_display' not in st.session_state:
    st.session_state.data_frame_display = None
if 'data_frame_hourly_for_csv' not in st.session_state:
    st.session_state.data_frame_hourly_for_csv = None
if 'download_message_show' not in st.session_state:
    st.session_state.download_message_show = False

# --- Sidebar pro zadání API klíče a nastavení ---
with st.sidebar:
    # Získání API klíče ze Streamlit secrets
    if "entsoe_api_key" in st.secrets:
        api_key = st.secrets["entsoe_api_key"]
        #st.success("API klíč načten ze `secrets.toml`.") 
    else:
        st.error("API klíč nenalezen v `.streamlit/secrets.toml`.")
        st.info("Prosím, vytvořte nebo upravte soubor `.streamlit/secrets.toml` v kořenovém adresáři vašeho projektu a přidejte svůj klíč ve formátu: `entsoe_api_key = \"VÁŠ_API_KLÍČ_ZDE\"`.")
        st.stop() 

    # Inicializace ENTSOE klienta
    client = EntsoePandasClient(api_key=api_key)

    st.subheader("Výběr Časového Rozsahu")
    today = datetime.date.today()
    default_start_date = today - datetime.timedelta(days=7) 
    default_end_date = today - datetime.timedelta(days=1) 

    # Omezení date pickeru na dnešní datum jako maximální hodnotu
    start_date = st.date_input("Počáteční datum", default_start_date, max_value=today)
    end_date = st.date_input("Koncové datum", default_end_date, max_value=today)

    # Převod na Pandas Timestamp s časovou zónou pro ENTSOE API (Europe/Brussels = CET/CEST)
    start_dt = pd.Timestamp(start_date, tz='Europe/Brussels')
    # Pro End Date přidáváme 1 den, aby API vrátilo data až do konce vybraného dne
    end_dt = pd.Timestamp(end_date, tz='Europe/Brussels') + datetime.timedelta(days=1)


    if start_dt >= end_dt:
        st.error("Počáteční datum musí být před koncovým datem!")
        st.stop()

    st.subheader("Výběr Země / Bidding Zone")

    country_codes = {
        "Česká republika (CZ)": "CZ", 
        "Německo & Lucembursko (DE_LU)": "DE_LU", 
        "Slovensko (SK)": "SK", 
        "Polsko (PL)": "PL", 
        "Rakousko (AT)": "AT", 
        "Maďarsko (HU)": "HU", 
        "Francie (FR)": "FR", 
        "Itálie (IT)": "IT", 
        "Belgie (BE)": "BE",
        "Nizozemsko (NL)": "NL",
        "Švýcarsko (CH)": "CH",
    }
    
    selected_country_name = st.selectbox("Vyber zemi / Bidding Zone", list(country_codes.keys()))
    country_code_for_api = country_codes[selected_country_name]

    # --- Tlačítko pro stažení dat (iniciuje fetch API) ---
    st.subheader("Akce")
    download_data_button = st.button("Stáhnout data")

# --- Hlavní panel pro zobrazení dat ---

# Logika pro stahování a zpracování dat se spustí, když uživatel klikne na "Stáhnout data"
if download_data_button:
    # Resetuj zprávu o stažení CSV při novém stahování dat
    st.session_state.download_message_show = False
    
    st.subheader(f"Data o výrobě pro {selected_country_name}")
    data_frame = pd.DataFrame() 

    try:
        with st.spinner(f"Stahuji data o výrobě pro {selected_country_name} od {start_date} do {end_date}..."):
            data_frame = client.query_generation_per_plant(
                country_code=country_code_for_api, 
                start=start_dt, 
                end=end_dt, 
                psr_type=None, 
                include_eic=False
            )
            
            if data_frame.empty:
                st.warning("Pro vybrané parametry nebyla nalezena žádná data.")
                # Pokud nejsou data, vyčisti session state, aby se nezobrazovaly staré tabulky
                st.session_state.data_frame_display = None
                st.session_state.data_frame_hourly_for_csv = None
            else:
                #st.success("Data byla úspěšně stažena!")
                st.write(f"Nalezeno {len(data_frame)} záznamů v původním rozlišení (pravděpodobně 15minutové).")
                
                # --- Transformace sloupců pro MultiIndex s 2 úrovněmi ---
                if isinstance(data_frame.columns, pd.MultiIndex):
                    new_levels = [(col[0], col[1]) for col in data_frame.columns]
                    data_frame.columns = pd.MultiIndex.from_tuples(new_levels, names=['Název elektrárny', 'Typ paliva'])
                else:
                    st.warning("Sloupce nemají očekávaný MultiIndex formát. Nebudou transformovány.")

                # 2. Agregace dat do hodin pomocí mean
                data_frame_hourly = data_frame.resample('h').mean()
                #st.info("Data byla agregována na hodinové rozlišení (průměr hodnot za hodinu).")
                
                # Ulož originální hodinová data pro CSV stažení do session state
                st.session_state.data_frame_hourly_for_csv = data_frame_hourly
                
                # Připrav data pro zobrazení (formátování indexu) a ulož do session state
                data_frame_display = data_frame_hourly.copy()
                data_frame_display.index = data_frame_display.index.strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.data_frame_display = data_frame_display

    except Exception as e:
        st.error(f"Při stahování dat došlo k chybě: {e}")
        st.info("Zkontroluj prosím, zda je tvůj API klíč správný a zda jsou parametry (datum, země) platné pro daný dotaz a období.")
        st.markdown("[Dokumentace ENTSOE API](https://transparency.entsoe.eu/content/TransparencyPortalAPI/api-docs)")
        st.markdown("[Dokumentace knihovny `entsoe-py`](https://data-en.tso-e.eu/api-v1-swagger-ui/index.html?urls.primaryName=ENTSOE%20API%20v2#/Documentation)")
        # V případě chyby také vyčisti session state
        st.session_state.data_frame_display = None
        st.session_state.data_frame_hourly_for_csv = None
        st.session_state.download_message_show = False

# Podmíněné zobrazení tabulky a tlačítka pro stažení CSV
# Toto se spustí při každém rerunu, pokud jsou data v session_state
if st.session_state.data_frame_display is not None:
    st.write(f"Po hodinové agregaci: {len(st.session_state.data_frame_display)} záznamů. (Data jsou v časové zóně CET/CEST)")
    
    # Zobraz celou tabulku s nastavenou výškou
    st.dataframe(st.session_state.data_frame_display, height=700) 
    
    # Připrav CSV ke stažení - nyní s daty z session_state
    # Používáme data_frame_hourly_for_csv, aby se do CSV uložil DatetimeIndex
    csv_buffer = io.StringIO()
    st.session_state.data_frame_hourly_for_csv.to_csv(csv_buffer, index=True, encoding='utf-8-sig') 
    
    # Použijeme st.columns pro zobrazení tlačítka a zprávy vedle sebe
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        # st.download_button vrátí True, pokud byl kliknut
        download_button_clicked = st.download_button(
            label="Stáhnout hodinová data jako CSV",
            data=csv_buffer.getvalue(),
            file_name=f"entsoe_generation_hourly_{selected_country_name.replace(' ', '_').replace('&', '_').replace('(', '').replace(')', '')}_{start_date}_do_{end_date}.csv",
            mime="text/csv",
            key="download_csv_button" # Unikátní klíč pro tlačítko
        )
    
    with col2:
        # Zobraz zprávu "Staženo ✅" pouze pokud bylo tlačítko pro stažení CSV kliknuto
        if download_button_clicked:
            st.session_state.download_message_show = True # Nastav flag na True
        
        # Zobraz zprávu, pokud je flag nastaven
        if st.session_state.download_message_show:
            st.success("Data byla úspěšně stažena! ✅")