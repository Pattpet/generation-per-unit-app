import streamlit as st
from entsoe import EntsoePandasClient
import pandas as pd
import io
import datetime
import numpy as np
# Odebrány importy, které způsobovaly chybu nebo nebyly potřeba:
# from openpyxl import Workbook
# from openpyxl.utils.dataframe import dataframe_to_rows
# from openpyxl.styles import NumberFormat

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
if 'data_frame_display' not in st.session_state:
    st.session_state.data_frame_display = None
if 'data_frame_hourly_for_export' not in st.session_state:
    st.session_state.data_frame_hourly_for_export = None
if 'download_message_show_csv' not in st.session_state:
    st.session_state.download_message_show_csv = False
if 'download_message_show_xlsx' not in st.session_state:
    st.session_state.download_message_show_xlsx = False

# --- Sidebar pro zadání API klíče a nastavení ---
with st.sidebar:
    # Získání API klíče ze Streamlit secrets
    if "entsoe_api_key" in st.secrets:
        api_key = st.secrets["entsoe_api_key"]
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

    start_date = st.date_input("Počáteční datum", default_start_date, max_value=today)
    end_date = st.date_input("Koncové datum", default_end_date, max_value=today)

    start_dt = pd.Timestamp(start_date, tz='Europe/Brussels')
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

    st.subheader("Akce")
    download_data_button = st.button("Stáhnout data")

# --- Hlavní panel pro zobrazení dat ---
if download_data_button:
    st.session_state.download_message_show_csv = False
    st.session_state.download_message_show_xlsx = False

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
                st.session_state.data_frame_display = None
                st.session_state.data_frame_hourly_for_export = None
            else:
                st.write(f"Nalezeno {len(data_frame)} záznamů v původním rozlišení (pravděpodobně 15minutové).")

                # --- Transformace sloupců pro MultiIndex s 2 úrovněmi ---
                if isinstance(data_frame.columns, pd.MultiIndex):
                    if data_frame.columns.nlevels == 3: # Očekáváme 3 úrovně
                        # Vytvoříme nové úrovně z tuplů původního MultiIndexu, vezmeme jen první dvě
                        new_levels = [(col[0], col[1]) for col in data_frame.columns]
                        data_frame.columns = pd.MultiIndex.from_tuples(new_levels, names=['Název elektrárny', 'Typ paliva'])
                    else:
                        st.warning(f"Sloupce mají MultiIndex, ale počet úrovní ({data_frame.columns.nlevels}) není 3. Sloupce nebudou transformovány s explicitními názvy úrovní.")
                else:
                    st.warning("Sloupce nemají očekávaný MultiIndex formát. Nebudou transformovány.")

                # Agregace dat do hodin pomocí mean
                data_frame_hourly = data_frame.resample('h').mean()

                # Ulož hodinová data pro export do session state (DatetimeIndex se zachová)
                st.session_state.data_frame_hourly_for_export = data_frame_hourly

                # Připrav data pro zobrazení (formátování indexu pro Streamlit display)
                data_frame_display = data_frame_hourly.copy()
                data_frame_display.index = data_frame_display.index.strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.data_frame_display = data_frame_display

    except Exception as e:
        st.error(f"Při stahování dat došlo k chybě: {e}")
        st.info("Zkontroluj prosím, zda je tvůj API klíč správný a zda jsou parametry (datum, země) platné pro daný dotaz a období.")
        st.markdown("[Dokumentace ENTSOE API](https://transparency.entsoe.eu/content/TransparencyPortalAPI/api-docs)")
        st.markdown("[Dokumentace knihovny `entsoe-py`](https://data-en.tso-e.eu/api-v1-swagger-ui/index.html?urls.primaryName=ENTSOE%20API%20v2#/Documentation)")
        st.session_state.data_frame_display = None
        st.session_state.data_frame_hourly_for_export = None
        st.session_state.download_message_show_csv = False
        st.session_state.download_message_show_xlsx = False

# Podmíněné zobrazení tabulky a tlačítek pro stažení
if st.session_state.data_frame_display is not None:
    st.write(f"Po hodinové agregaci: {len(st.session_state.data_frame_display)} záznamů. (Data jsou v časové zóně CET/CEST)")

    st.dataframe(st.session_state.data_frame_display, height=700)

    # --- Příprava souborů ke stažení ---
    df_to_export = st.session_state.data_frame_hourly_for_export.copy() # Pracujeme na kopii

    # 1. Příprava CSV ke stažení (s desetinnou tečkou)
    csv_buffer = io.StringIO()
    df_to_export.to_csv(csv_buffer, index=True, encoding='utf-8-sig', decimal='.') # Změna na decimal='.'
    # encoding='utf-8-sig' je důležité pro správné zobrazení diakritiky v Excelu při otevření CSV

    # 2. Příprava XLSX ke stažení (jako skutečné číslo, Excel si poradí s tečkou/čárkou dle nastavení)
    excel_buffer = io.BytesIO()

    # PŘEVOD INDEXU NA TIMEZONE-NAIVE PŘED EXPORTEM DO EXCELU
    if df_to_export.index.tz is not None:
        df_to_export.index = df_to_export.index.tz_localize(None)

    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, index=True, sheet_name='Data')

        # V této verzi NEBUDEME ručně nastavovat number_format,
        # necháme Excel, aby si s formátováním čísel poradil sám
        # podle regionálního nastavení uživatele.
        # Takto budou hodnoty zapsány jako čistá čísla.
        # Workbook a sheet objekty zde nejsou potřeba, pokud neaplikujeme vlastní styly
        # workbook = writer.book
        # sheet = writer.sheets['Data']
        # for row_idx, row in enumerate(sheet.iter_rows()):
        #    for col_idx, cell in enumerate(row):
        #        if row_idx > 0 and col_idx > 0:
        #            if isinstance(cell.value, (int, float, np.number)):
        #                cell.number_format = '# ##0,00' # Tuto řádku jsme odstranili!


    excel_buffer.seek(0) # Resetuj pozici bufferu na začátek

    # --- Tlačítka pro stažení a zprávy ---
    col1, col2, col3 = st.columns([0.25, 0.25, 0.5])

    with col1:
        download_csv_clicked = st.download_button(
            label="Stáhnout jako CSV",
            data=csv_buffer.getvalue(),
            file_name=f"entsoe_generation_hourly_{selected_country_name.replace(' ', '_').replace('&', '_').replace('(', '').replace(')', '')}_{start_date}_do_{end_date}.csv",
            mime="text/csv",
            key="download_csv_button"
        )
        if download_csv_clicked:
            st.session_state.download_message_show_csv = True
            st.session_state.download_message_show_xlsx = False

    with col2:
        download_xlsx_clicked = st.download_button(
            label="Stáhnout jako XLSX",
            data=excel_buffer.getvalue(),
            file_name=f"entsoe_generation_hourly_{selected_country_name.replace(' ', '_').replace('&', '_').replace('(', '').replace(')', '')}_{start_date}_do_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_xlsx_button"
        )
        if download_xlsx_clicked:
            st.session_state.download_message_show_xlsx = True
            st.session_state.download_message_show_csv = False

    with col3:
        if st.session_state.download_message_show_csv:
            st.success("CSV soubor byl úspěšně připraven ke stažení! ✅ (Čísla s desetinnou tečkou)")
        elif st.session_state.download_message_show_xlsx:
            st.success("XLSX soubor byl úspěšně připraven ke stažení! ✅ (Čísla jsou uložena jako číselné hodnoty. Formát zobrazení desetinných míst závisí na nastavení vašeho Excelu.)")