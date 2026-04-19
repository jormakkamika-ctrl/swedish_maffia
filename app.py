import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="ISM PMI & Equity Intelligence", layout="wide")

# ====================== CONFIG & ROBUST MAPPING ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

# Robust mapping to yfinance 'industry' strings
ISM_TO_GICS_MAP = {
    "Transportation Equipment": ["Auto Manufacturers", "Aerospace & Defense", "Auto Parts"],
    "Computer & Electronic Products": ["Semiconductors", "Consumer Electronics", "Communication Equipment"],
    "Chemicals": ["Chemicals", "Specialty Chemicals", "Drug Manufacturers—General"],
    "Food, Beverage & Tobacco Products": ["Beverages—Non-Alcoholic", "Packaged Foods", "Tobacco"],
    "Primary Metals": ["Steel", "Other Precious Metals & Mining", "Aluminum"],
    "Machinery": ["Farm & Heavy Construction Machinery", "Specialty Industrial Machinery"],
    "Petroleum & Coal Products": ["Oil & Gas Refining & Marketing", "Oil & Gas Integrated"],
    "Electrical Equipment, Appliances & Components": ["Electrical Equipment & Parts"],
    "Furniture & Related Products": ["Furnishings, Fixtures & Appliances"],
    "Paper Products": ["Paper & Paper Products"]
}

# Base universe for scanning (S&P 100 + key industry leaders)
SCAN_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V", 
    "JNJ", "WMT", "PG", "MA", "UNH", "HD", "XOM", "CVX", "BAC", "PFE", "KO", "PEP",
    "COST", "ORCL", "AVGO", "ADBE", "CSCO", "CRM", "ACN", "ABT", "NKE", "LLY", "DIS",
    "UPS", "TXN", "DHR", "VZ", "NEE", "PM", "RTX", "HON", "LOW", "COP", "INTC", 
    "IBM", "CAT", "GS", "MS", "DE", "LMT", "GE", "AMAT", "BA", "AXP", "MDLZ", "TJX",
    "ADI", "ISRG", "GILD", "T", "VRTX", "EL", "AMGN", "MMC", "SBUX", "LRCX", "NOW",
    "BKNG", "REGN", "MDT", "PGR", "C", "ZTS", "MO", "SCHW", "PLD", "CB", "CI", 
    "SYK", "BSX", "MU", "PANW", "SNPS", "CDNS", "ETN", "WM", "ITW", "F", "GM", "X", 
    "NUE", "STLD", "FCX", "APD", "LIN", "SHW", "CTAS", "PH", "DOW", "DD"
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ====================== DATA ENGINE ======================

def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', '', name)
    return re.sub(r'\s+', ' ', name)

NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}

def parse_report_text(text):
    pmi_match = re.search(r"at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else 0.0
    month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}", text)
    month_year = month_match.group(0) if month_match else "Unknown"

    def get_list(pattern, src):
        match = re.search(pattern, src, re.DOTALL | re.IGNORECASE)
        if not match: return []
        raw = match.group(1).replace(" and ", "; ")
        return [x.strip().strip('.') for x in raw.split(";") if len(x.strip()) > 3]

    growth_p = r"reporting growth in \w+.*?\s+are:(.*?)\.\s*The"
    contr_p = r"reporting contraction in \w+.*?\s+are:(.*?)\."
    return pmi, month_year, get_list(growth_p, text), get_list(contr_p, text)

@st.cache_data(ttl=86400)
def build_historical_dataset():
    all_data = []
    archive_url = "https://www.prnewswire.com/news/institute-for-supply-management/"
    try:
        soup = BeautifulSoup(requests.get(archive_url, headers=HEADERS).text, "html.parser")
        links = [("https://www.prnewswire.com" + a['href'] if a['href'].startswith('/') else a['href']) 
                 for a in soup.find_all('a', href=True) if "manufacturing-pmi-report" in a['href'].lower()]
        
        for url in list(dict.fromkeys(links))[:8]:
            raw_text = BeautifulSoup(requests.get(url, headers=HEADERS).text, "html.parser").get_text(separator=" ")
            pmi, m_year, growth, contr = parse_report_text(raw_text)
            if m_year == "Unknown": continue
            n_g, n_c = len(growth), len(contr)
            month_scores = {ind: 0 for ind in INDUSTRIES}
            for i, s in enumerate(growth):
                norm = normalize_name(s)
                if norm in NORM_TO_OFFICIAL: month_scores[NORM_TO_OFFICIAL[norm]] = n_g - i
            for i, s in enumerate(contr):
                norm = normalize_name(s)
                if norm in NORM_TO_OFFICIAL: month_scores[NORM_TO_OFFICIAL[norm]] = -(n_c - i)
            for ind, score in month_scores.items():
                all_data.append({"date": pd.to_datetime(m_year), "industry": ind, "score": score, "pmi": pmi, "url": url})
    except: pass
    return pd.DataFrame(all_data)

def get_stocks_for_industries(gics_list):
    """Dynamically scans universe for matching industry and >$1B MC."""
    results = []
    if not gics_list: return pd.DataFrame()
    
    # We use batch download for speed
    tickers_data = yf.download(SCAN_UNIVERSE, period="1d", group_by='ticker', threads=True, progress=False)
    
    for t in SCAN_UNIVERSE:
        try:
            info = yf.Ticker(t).info
            mkt_cap = info.get('marketCap', 0)
            if info.get('industry') in gics_list and mkt_cap >= 1_000_000_000:
                results.append({
                    "Ticker": t,
                    "Company": info.get('shortName'),
                    "Industry": info.get('industry'),
                    "Price": f"${info.get('currentPrice', 0):.2f}",
                    "Market Cap": f"${mkt_cap/1e9:.1f}B",
                    "Forward P/E": f"{info.get('forwardPE', 0):.1f}",
                    "Div Yield": f"{info.get('dividendYield', 0)*100:.2f}%"
                })
        except: continue
    return pd.DataFrame(results)

# ====================== MAIN UI ======================

st.title("🏭 ISM Manufacturing & Equity Intelligence")

df_master = build_historical_dataset()

if not df_master.empty:
    latest_date = df_master['date'].max()
    current_df = df_master[df_master['date'] == latest_date].copy()
    
    # --- HEATMAP ---
    st.subheader(f"Historical Momentum & Diffusion")
    pivot = df_master.pivot(index="industry", columns="date", values="score").fillna(0).reindex(INDUSTRIES)
    pivot.columns = pivot.columns.strftime('%b %Y')
    fig = px.imshow(pivot, color_continuous_scale="RdYlGn", text_auto=True, aspect="auto")
    st.plotly_chart(fig, use_container_width=True)

    # --- INVESTMENT SCANNER ---
    st.divider()
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("Investment Filter")
        selected = st.selectbox("Select ISM Sector:", INDUSTRIES)
        score = current_df[current_df['industry'] == selected]['score'].iloc[0]
        st.write(f"Current ISM Score: **{score:+d}**")
        
        target_gics = ISM_TO_GICS_MAP.get(selected, [])
        if target_gics:
            st.write(f"Related GICS: {', '.join(target_gics)}")
            scan_btn = st.button(f"🔍 Scan for >$1B Cap Stocks")
        else:
            st.warning("No GICS mapping for this sector.")
            scan_btn = False

    with col_right:
        if scan_btn:
            with st.spinner(f"Analyzing {len(SCAN_UNIVERSE)} companies..."):
                stock_results = get_stocks_for_industries(target_gics)
                if not stock_results.empty:
                    st.dataframe(stock_results, use_container_width=True, hide_index=True)
                else:
                    st.info("No companies matching this industry found in the scanning universe.")

else:
    st.error("Archive not found. Please refresh.")
