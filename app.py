import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="ISM PMI Intelligence", layout="wide")

# ====================== CONFIG & MAPPING ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

# Robust direct ticker mapping (NYSE + Nasdaq, all > $1B cap)
ISM_TO_TICKERS = {
    "Transportation Equipment": ["F", "GM", "TSLA", "HON", "RTX", "LMT", "BA", "NOC", "GD", "UNP", "DE", "CAT", "PCAR"],
    "Computer & Electronic Products": ["AAPL", "MSFT", "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MU", "AMAT", "TXN", "ADI"],
    "Chemical Products": ["DOW", "DD", "LYB", "ECL", "PPG", "SHW", "APD", "LIN", "CF", "MOS", "EMN"],
    "Food, Beverage & Tobacco Products": ["KO", "PEP", "MDLZ", "KHC", "GIS", "STZ", "MNST", "ADM", "TSN", "KDP", "PM", "MO"],
    "Primary Metals": ["NUE", "X", "CLF", "STLD", "RS", "ATI", "AA", "SCCO"],
    "Machinery": ["CAT", "DE", "ETN", "HON", "CMI", "IR", "ROP", "AME", "DOV", "PH"],
    "Furniture & Related Products": ["MHK", "TPX", "LZB", "LEG"],
    "Petroleum & Coal Products": ["XOM", "CVX", "PSX", "MPC", "VLO", "HFC", "OXY"],
    "Electrical Equipment, Appliances & Components": ["GE", "EMR", "ETN", "PH", "ROK", "AMT", "HON"],
    "Textile Mills": ["NWL", "UFI"],
    "Paper Products": ["IP", "PKG", "AVY", "SEE"],
    "Plastics & Rubber Products": ["GT", "CCK", "AVY"],
    "Nonmetallic Mineral Products": ["VMC", "MLM", "EXP", "CX", "SUM"],
    "Fabricated Metal Products": ["EMR", "PH", "ITW", "FAST"],
    "Miscellaneous Manufacturing": ["MMM", "GE", "HON", "ITW"],
    "Apparel, Leather & Allied Products": ["NKE", "VFC", "PVH", "HBI", "LEVI", "COLM"],
    "Printing & Related Support Activities": ["RRD", "DLX"]
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ====================== UTILS ======================
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name

NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}

# ====================== SCRAPER ENGINE ======================
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
        r = requests.get(archive_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        links = []
        for a in soup.find_all('a', href=True):
            if "manufacturing-pmi-report" in a['href'].lower():
                full_url = "https://www.prnewswire.com" + a['href'] if a['href'].startswith('/') else a['href']
                links.append(full_url)
        
        for url in list(dict.fromkeys(links))[:8]:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            raw_text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")
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
                all_data.append({
                    "date": pd.to_datetime(m_year), 
                    "industry": ind, 
                    "score": score, 
                    "pmi": pmi,
                    "url": url
                })
    except Exception as e:
        st.error(f"Archive Fetch Error: {e}")

    return pd.DataFrame(all_data)

# ====================== LIVE STOCK LOOKUP ======================
@st.cache_data(ttl=3600)
def get_stocks_for_industry(industry: str):
    tickers = ISM_TO_TICKERS.get(industry, [])
    if not tickers:
        return pd.DataFrame()
    
    data = yf.Tickers(" ".join(tickers))
    rows = []
    for t in tickers:
        try:
            info = data.tickers[t].info
            market_cap = info.get("marketCap") or info.get("enterpriseValue") or 0
            if market_cap > 1_000_000_000:
                rows.append({
                    "Ticker": t,
                    "Company": info.get("longName", t),
                    "Market Cap": f"${market_cap/1e9:.1f}B",
                    "Price": round(info.get("currentPrice") or info.get("regularMarketPrice") or 0, 2),
                    "% Change": round(info.get("regularMarketChangePercent") or 0, 2),
                    "Yahoo Link": f"https://finance.yahoo.com/quote/{t}"
                })
        except:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Market Cap", ascending=False)
    return df

# ====================== MAIN APP ======================
st.title("🏭 ISM Manufacturing Intelligence Hub")

with st.spinner("Rebuilding 6-month sector history from PR Newswire..."):
    df_master = build_historical_dataset()

if not df_master.empty:
    latest_date = df_master['date'].max()
    current_df = df_master[df_master['date'] == latest_date].copy()
    pmi_val = current_df['pmi'].iloc[0]
    report_url = current_df['url'].iloc[0]

    st.subheader(f"Current Report: {latest_date.strftime('%B %Y')}")
    st.metric("Manufacturing PMI®", f"{pmi_val}%", delta=f"{round(pmi_val-50, 1)} vs 50.0 Neutral")

    col_table, col_info = st.columns([2, 1])
    
    with col_table:
        st.write("**Industry Rankings (Ordered by Growth)**")
        styled_df = (
            current_df[["industry", "score"]]
            .sort_values("score", ascending=False)
            .style.background_gradient(cmap="RdYlGn", subset=["score"], vmin=-13, vmax=13)
            .format({"score": "{:+d}"})
            .set_properties(**{"font-weight": "bold"})
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

    with col_info:
        st.write("**Investment Context**")
        selected_sector = st.selectbox("Select Sector for Stock List:", INDUSTRIES)
        
        score_now = current_df[current_df['industry'] == selected_sector]['score'].iloc[0]
        status = "🟢 Growing" if score_now > 0 else "🔴 Contracting" if score_now < 0 else "🟡 Neutral"
        st.write(f"Current Status: **{status}** ({score_now:+d})")

    # ====================== LIVE STOCKS SECTION ======================
    st.divider()
    st.subheader(f"📋 Stocks in **{selected_sector}** (> $1B market cap)")

    stock_df = get_stocks_for_industry(selected_sector)
    
    if not stock_df.empty:
        st.success(f"Found {len(stock_df)} large-cap stocks")
        st.dataframe(
            stock_df.style.format({"% Change": "{:+.2f}%"}),
            use_container_width=True,
            hide_index=True
        )
        st.caption("💡 Click any Ticker link to open Yahoo Finance")
    else:
        st.info("No stocks found for this sector yet (mapping can be expanded).")

    # Historical sections (your original)
    st.divider()
    st.subheader("📈 6-Month Sector Momentum")
    pivot = df_master.pivot(index="industry", columns="date", values="score").fillna(0)
    pivot = pivot.reindex(INDUSTRIES)
    pivot.columns = pivot.columns.strftime('%b %Y')
    fig = px.imshow(pivot, labels=dict(x="Report Month", y="Industry", color="Score"),
                    color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                    text_auto=True, aspect="auto")
    fig.update_layout(height=600, xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Industry Score Evolution")
    to_track = st.multiselect("Select industries to compare:", INDUSTRIES, 
                              default=["Transportation Equipment", "Chemical Products", "Computer & Electronic Products"])
    if to_track:
        line_df = df_master[df_master['industry'].isin(to_track)].sort_values('date')
        fig_line = px.line(line_df, x='date', y='score', color='industry', markers=True,
                           line_shape='spline', title="Relative Growth/Contraction Trends")
        st.plotly_chart(fig_line, use_container_width=True)

else:
    st.error("No data found. Please check the scraper settings or the Source URL.")

with st.sidebar:
    st.image("https://www.ismworld.org/globalassets/pub/logos/ism_manufacturing_pmi_logo.png", width=200)
    st.write(f"**Current Source:** [PR Newswire]({report_url if 'report_url' in locals() else '#'})")
    if st.button("Deep Refresh (Scrape Archive)"):
        st.cache_data.clear()
        st.rerun()

