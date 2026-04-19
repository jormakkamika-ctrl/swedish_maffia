import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import plotly.express as px
import numpy as np
import yfinance as yf
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

st.set_page_config(page_title="ISM Manufacturing Intelligence Hub", layout="wide")

# ====================== CONFIG ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ====================== ECONOMIC EXPOSURE ONTOLOGY ======================
class DriverName(str, Enum):
    DEMAND_MOMENTUM = "Demand Momentum"
    CAPEX_PRESSURE = "Capex & Capacity Pressure"
    INPUT_COST_INFLATION = "Input Cost Inflation"
    LABOR_TIGHTNESS = "Labor Market Tightness"
    INVENTORY_RESTOCKING = "Inventory Restocking Cycle"
    SECTOR_SPECIFIC_STRENGTH = "Sector-Specific End-Market Strength"

@dataclass(frozen=True)
class EconomicDriver:
    name: DriverName
    strength: float
    signals_used: List[str]
    description: str

def normalize_signal(value: float, mom_change: float, trend_months: int) -> float:
    if value is None:
        return 0.0
    level_score = (value - 50) / 50.0
    mom_score = max(min(mom_change / 5.0, 1.0), -1.0)
    trend_score = max(min(trend_months / 3.0, 1.0), 0.0)
    return max(min(level_score * (1 + mom_score) * trend_score, 1.0), -1.0)

def calculate_drivers(subcomponents: Dict) -> Dict[DriverName, EconomicDriver]:
    signals = {
        "new_orders": subcomponents.get("New Orders", {}),
        "backlog": subcomponents.get("Backlog of Orders", {}),
        "production": subcomponents.get("Production", {}),
        "employment": subcomponents.get("Employment", {}),
        "prices_paid": subcomponents.get("Prices", {}),
    }

    drivers: Dict[DriverName, EconomicDriver] = {}

    # Demand Momentum
    demand_strength = np.mean([
        normalize_signal(signals["new_orders"].get("current", 50), signals["new_orders"].get("change", 0), signals["new_orders"].get("trend", 0)),
        normalize_signal(signals["backlog"].get("current", 50), signals["backlog"].get("change", 0), signals["backlog"].get("trend", 0)),
    ])
    drivers[DriverName.DEMAND_MOMENTUM] = EconomicDriver(
        name=DriverName.DEMAND_MOMENTUM, strength=round(float(demand_strength), 2),
        signals_used=["New Orders", "Backlog of Orders"],
        description="Forward revenue visibility & sustained order flow"
    )

    # Capex & Capacity Pressure
    capex_strength = np.mean([
        normalize_signal(signals["backlog"].get("current", 50), signals["backlog"].get("change", 0), signals["backlog"].get("trend", 0)),
        normalize_signal(signals["production"].get("current", 50), signals["production"].get("change", 0), signals["production"].get("trend", 0)),
    ])
    drivers[DriverName.CAPEX_PRESSURE] = EconomicDriver(
        name=DriverName.CAPEX_PRESSURE, strength=round(float(capex_strength), 2),
        signals_used=["Backlog of Orders", "Production"],
        description="Capacity constraints → future capital spending"
    )

    # Input Cost Inflation
    drivers[DriverName.INPUT_COST_INFLATION] = EconomicDriver(
        name=DriverName.INPUT_COST_INFLATION,
        strength=round(normalize_signal(signals["prices_paid"].get("current", 50), signals["prices_paid"].get("change", 0), signals["prices_paid"].get("trend", 0)), 2),
        signals_used=["Prices Paid"],
        description="Input-cost pressure or pricing power"
    )

    # Labor Market Tightness
    drivers[DriverName.LABOR_TIGHTNESS] = EconomicDriver(
        name=DriverName.LABOR_TIGHTNESS,
        strength=round(normalize_signal(signals["employment"].get("current", 50), signals["employment"].get("change", 0), signals["employment"].get("trend", 0)), 2),
        signals_used=["Employment"],
        description="Hiring plans & wage pressure"
    )

    # Placeholders
    drivers[DriverName.INVENTORY_RESTOCKING] = EconomicDriver(name=DriverName.INVENTORY_RESTOCKING, strength=0.0, signals_used=["Inventories (future)"], description="Inventory drawdown → restocking")
    drivers[DriverName.SECTOR_SPECIFIC_STRENGTH] = EconomicDriver(name=DriverName.SECTOR_SPECIFIC_STRENGTH, strength=0.0, signals_used=["ISM Industry List"], description="Direct end-market momentum")

    return drivers

# ====================== PROFESSIONAL ECONOMIC EXPOSURE MAP ======================
# Expanded & comprehensive (covers ~70 common Yahoo industry strings)
INDUSTRY_EXPOSURE_MAP: Dict[str, Dict[DriverName, float]] = {
    # DEMAND MOMENTUM (New Orders / Backlog)
    "Auto Manufacturers": {DriverName.DEMAND_MOMENTUM: 0.92},
    "Auto Parts": {DriverName.DEMAND_MOMENTUM: 0.88},
    "Aerospace & Defense": {DriverName.DEMAND_MOMENTUM: 0.80},
    "Residential Construction": {DriverName.DEMAND_MOMENTUM: 0.85},
    "Consumer Electronics": {DriverName.DEMAND_MOMENTUM: 0.75},
    "Internet Retail": {DriverName.DEMAND_MOMENTUM: 0.60},
    "Specialty Retail": {DriverName.DEMAND_MOMENTUM: 0.55},
    "Railroads": {DriverName.DEMAND_MOMENTUM: 0.65},
    "Integrated Freight & Logistics": {DriverName.DEMAND_MOMENTUM: 0.60},
    "Lumber & Wood Production": {DriverName.DEMAND_MOMENTUM: 0.75},

    # CAPEX & CAPACITY PRESSURE
    "Specialty Industrial Machinery": {DriverName.CAPEX_PRESSURE: 0.92, DriverName.DEMAND_MOMENTUM: 0.78},
    "Farm & Heavy Construction Machinery": {DriverName.CAPEX_PRESSURE: 0.95, DriverName.DEMAND_MOMENTUM: 0.72},
    "Electrical Equipment & Parts": {DriverName.CAPEX_PRESSURE: 0.85, DriverName.DEMAND_MOMENTUM: 0.65},
    "Building Products & Equipment": {DriverName.CAPEX_PRESSURE: 0.80},
    "Engineering & Construction": {DriverName.CAPEX_PRESSURE: 0.88},
    "Semiconductor Equipment & Materials": {DriverName.CAPEX_PRESSURE: 0.95, DriverName.DEMAND_MOMENTUM: 0.82},
    "Industrial Distribution": {DriverName.CAPEX_PRESSURE: 0.70},

    # INPUT COST INFLATION (Prices Paid)
    "Steel": {DriverName.INPUT_COST_INFLATION: 0.88, DriverName.DEMAND_MOMENTUM: 0.75},
    "Aluminum": {DriverName.INPUT_COST_INFLATION: 0.85, DriverName.DEMAND_MOMENTUM: 0.70},
    "Copper": {DriverName.INPUT_COST_INFLATION: 0.90, DriverName.DEMAND_MOMENTUM: 0.78},
    "Other Industrial Metals & Mining": {DriverName.INPUT_COST_INFLATION: 0.87},
    "Chemicals": {DriverName.INPUT_COST_INFLATION: 0.82},
    "Specialty Chemicals": {DriverName.INPUT_COST_INFLATION: 0.78},
    "Building Materials": {DriverName.INPUT_COST_INFLATION: 0.75},
    "Paper & Paper Products": {DriverName.INPUT_COST_INFLATION: 0.70},
    "Oil & Gas Exploration & Production": {DriverName.INPUT_COST_INFLATION: 0.80},
    "Oil & Gas Refining & Marketing": {DriverName.INPUT_COST_INFLATION: 0.65},
    "Oil & Gas Equipment & Services": {DriverName.INPUT_COST_INFLATION: 0.72},
    "Packaging & Containers": {DriverName.INPUT_COST_INFLATION: 0.70},

    # SEMICONDUCTORS & TECH HARDWARE
    "Semiconductors": {DriverName.DEMAND_MOMENTUM: 0.85, DriverName.CAPEX_PRESSURE: 0.90},
    "Computer Hardware": {DriverName.DEMAND_MOMENTUM: 0.70, DriverName.CAPEX_PRESSURE: 0.60},
    "Electronic Components": {DriverName.DEMAND_MOMENTUM: 0.75},

    # LABOR MARKET TIGHTNESS (added where relevant)
    "Auto Manufacturers": {DriverName.LABOR_TIGHTNESS: 0.70},
    "Auto Parts": {DriverName.LABOR_TIGHTNESS: 0.68},
    "Specialty Industrial Machinery": {DriverName.LABOR_TIGHTNESS: 0.65},
    "Farm & Heavy Construction Machinery": {DriverName.LABOR_TIGHTNESS: 0.60},
    "Aerospace & Defense": {DriverName.LABOR_TIGHTNESS: 0.55},
}

# ====================== MANUAL OVERRIDES (high-conviction names) ======================
MANUAL_EXPOSURE_OVERRIDES: Dict[str, Dict[DriverName, float]] = {
    "CAT": {DriverName.CAPEX_PRESSURE: 0.95, DriverName.DEMAND_MOMENTUM: 0.80},
    "DE":  {DriverName.CAPEX_PRESSURE: 0.96, DriverName.DEMAND_MOMENTUM: 0.75},
    "NUE": {DriverName.INPUT_COST_INFLATION: 0.92, DriverName.DEMAND_MOMENTUM: 0.78},
    "FCX": {DriverName.INPUT_COST_INFLATION: 0.90, DriverName.DEMAND_MOMENTUM: 0.82},
    "NVDA": {DriverName.DEMAND_MOMENTUM: 0.88, DriverName.CAPEX_PRESSURE: 0.92},
    "TSLA": {DriverName.DEMAND_MOMENTUM: 0.90},
    "AMAT": {DriverName.CAPEX_PRESSURE: 0.94, DriverName.DEMAND_MOMENTUM: 0.80},
    "ETN": {DriverName.CAPEX_PRESSURE: 0.90},
    "PH":  {DriverName.CAPEX_PRESSURE: 0.88},
    # Add any other ticker you want to fine-tune here
}

# ====================== EXPLAIN SCORE (unchanged) ======================
def explain_score(row: pd.Series, drivers: Dict[DriverName, EconomicDriver]) -> str:
    reasons = []
    for driver_name in DriverName:
        exposure = row.get(driver_name.value, 0.0)
        if exposure > 0.3:
            strength = drivers[driver_name].strength
            if abs(strength) > 0.3:
                reasons.append(f"{strength:+.1f}×{exposure:.1f} {driver_name.value}")
    return " | ".join(reasons[:4]) or "Neutral exposure"

# ====================== FULL UPDATED TAG & SCORE FUNCTION ======================
def tag_and_score_stocks(stocks_df: pd.DataFrame, drivers: Dict[DriverName, EconomicDriver]) -> pd.DataFrame:
    """Apply industry mapping + manual ticker overrides, then compute ISM score."""
    if stocks_df.empty:
        return stocks_df

    exposure_matrix = []
    for _, row in stocks_df.iterrows():
        yahoo_ind = row.get("Yahoo Industry", "")
        ticker = row.get("Ticker", "")

        # 1. Start with industry-level mapping
        exposures = INDUSTRY_EXPOSURE_MAP.get(yahoo_ind, {}).copy()

        # 2. Apply manual ticker overrides (higher weight wins)
        if ticker in MANUAL_EXPOSURE_OVERRIDES:
            override = MANUAL_EXPOSURE_OVERRIDES[ticker]
            for d, weight in override.items():
                exposures[d] = max(exposures.get(d, 0.0), weight)

        # 3. Build vector aligned to DriverName order
        vector = [exposures.get(d, 0.0) for d in DriverName]
        exposure_matrix.append(vector)

    # Create exposure columns
    exposure_df = pd.DataFrame(exposure_matrix, columns=[d.value for d in DriverName], index=stocks_df.index)
    stocks_df = pd.concat([stocks_df, exposure_df], axis=1)

    # Compute final score
    driver_vector = np.array([drivers[d].strength for d in DriverName])
    stocks_df["ism_score"] = stocks_df[[d.value for d in DriverName]].dot(driver_vector).round(3)

    # Add explainability column
    stocks_df["why"] = stocks_df.apply(lambda r: explain_score(r, drivers), axis=1)

    return stocks_df.sort_values("ism_score", ascending=False)

# ====================== UTILS ======================
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name

NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}

def get_respondent_comments(text: str) -> list[str]:
    section_match = re.search(
        r"WHAT RESPONDENTS ARE SAYING\s*(.*?)(?=\s*(?:MANUFACTURING AT A GLANCE|The Institute for Supply Management®|©|ISM® Reports|Report Issued|$))",
        text, re.DOTALL | re.IGNORECASE
    )
    if not section_match:
        return []
    section = section_match.group(1).strip()
    bullet_pattern = r'(?:\*|\-)\s*["“](.+?)["”]\s*(?:\[\s*(.+?)\s*\])?'
    bullets = re.findall(bullet_pattern, section, re.DOTALL)
    comments = []
    for quote, industry in bullets:
        quote = quote.strip()
        if quote and len(quote) > 15:
            comment = f"• {quote}"
            if industry:
                comment += f" [{industry.strip()}]"
            comments.append(comment)
    return comments

# ====================== SUB-INDEX PARSER ======================
def parse_ism_subcomponents(text: str) -> dict:
    sub = {
        "New Orders": {"current": None, "change": None, "trend": None},
        "Production": {"current": None, "change": None, "trend": None},
        "Employment": {"current": None, "change": None, "trend": None},
        "Prices": {"current": None, "change": None, "trend": None},
        "Backlog of Orders": {"current": None, "change": None, "trend": None},
    }
    clean_text = re.sub(r'\s+', ' ', text)
    for key in sub.keys():
        row_pattern = rf"{re.escape(key)}\s+(\d+\.\d+)\s+[\d.]+\s+([+-]?\d+\.\d+)\s+(?:Growing|Contracting|Increasing|Decreasing|Slower|Faster|Unchanged)\s*(?:Growing|Contracting|Increasing|Decreasing|Slower|Faster|Unchanged)?\s*(\d+)"
        match = re.search(row_pattern, clean_text, re.IGNORECASE)
        if match:
            sub[key]["current"] = float(match.group(1))
            sub[key]["change"] = float(match.group(2))
            sub[key]["trend"] = int(match.group(3))
        else:
            fallback_pattern = rf"{re.escape(key)}\s+(\d+\.\d+)\s+[\d.]+\s+([+-]?\d+\.\d+).*?\s+(\d+)\s*(?:$|\s)"
            fb_match = re.search(fallback_pattern, clean_text, re.IGNORECASE)
            if fb_match:
                sub[key]["current"] = float(fb_match.group(1))
                sub[key]["change"] = float(fb_match.group(2))
                sub[key]["trend"] = int(fb_match.group(3))
    if sub["Prices"]["current"] is None:
        p_match = re.search(r"Prices\s+(\d+\.\d+)\s+[\d.]+\s+([+-]?\d+\.\d+).*?\s+(\d+)", clean_text, re.IGNORECASE)
        if p_match:
            sub["Prices"] = {"current": float(p_match.group(1)), "change": float(p_match.group(2)), "trend": int(p_match.group(3))}
    return sub

# ====================== TICKER LOADER (must come BEFORE the universe function) ======================
@st.cache_data(ttl=86400)
def get_all_nyse_nasdaq_tickers():
    """Ultra-robust ticker loader — uses requests + line split (no pandas NaN issues)."""
    try:
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        tickers = []
        for line in response.text.splitlines():
            t = line.strip()
            if t and not any(c in t for c in [".", "^", "/", "\\", " ", "\t"]):
                tickers.append(t)
        
        st.info(f"✅ Loaded {len(tickers):,} total US tickers (NASDAQ + NYSE + AMEX)")
        return sorted(tickers)
    except Exception as e:
        st.error(f"⚠️ Ticker list failed to load: {str(e)[:120]}")
        return []


# ====================== FULL STOCK UNIVERSE (now calls the function above) ======================
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_universe():
    """Single-ticker version — most reliable on Streamlit Cloud."""
    tickers_list = get_all_nyse_nasdaq_tickers()

    rows = []
    progress_bar = st.progress(0, text="Fetching full NYSE + NASDAQ universe (> $1B)... (this may take 4–6 min first time)")

    for idx, sym in enumerate(tickers_list):
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info

            industry = info.get("industry", "") or ""
            market_cap = info.get("marketCap") or info.get("enterpriseValue") or 0
            exchange = (info.get("exchange", "") or "").upper()
            company_name = info.get("longName") or info.get("shortName") or sym

            if market_cap > 1_000_000_000 and any(x in exchange for x in ["NYSE", "NYQ", "NMS", "NASD", "NASDAQ", "AMEX"]):
                rows.append({
                    "Ticker": sym,
                    "Company": company_name,
                    "Yahoo Industry": industry,
                    "Market Cap": market_cap,
                    "Exchange": exchange
                })
        except:
            continue

        # Update progress
        if idx % 50 == 0 or idx == len(tickers_list) - 1:
            progress = (idx + 1) / len(tickers_list)
            progress_bar.progress(progress, text=f"Found {len(rows):,} qualifying stocks so far...")

        time.sleep(0.35)   # polite delay to avoid rate limits

    progress_bar.empty()

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Market Cap", ascending=False)
        df["Market Cap"] = df["Market Cap"].apply(lambda x: f"${x/1_000_000_000:.1f}B")
        st.success(f"✅ Built universe with {len(df):,} stocks (Market Cap > $1B)")
    else:
        st.error("❌ No stocks found")

    return df

# ====================== SCRAPER ======================
def parse_report_text(text: str):
    pmi_match = re.search(r"at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else 50.0
    month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}", text)
    month_year = month_match.group(0) if month_match else "Unknown"

    def get_list(pattern, src):
        match = re.search(pattern, src, re.DOTALL | re.IGNORECASE)
        if not match: return []
        raw = match.group(1).replace(" and ", "; ")
        return [x.strip().strip('.') for x in raw.split(";") if len(x.strip()) > 3]
    growth_p = r"reporting growth in \w+.*?\s+are:(.*?)\.\s*The"
    contr_p = r"reporting contraction in \w+.*?\s+are:(.*?)\."
    growth = get_list(growth_p, text)
    contr = get_list(contr_p, text)

    comments = get_respondent_comments(text)
    subcomponents = parse_ism_subcomponents(text)

    return pmi, month_year, growth, contr, comments, subcomponents

@st.cache_data(ttl=86400)
def build_historical_dataset():
    all_data = []
    report_metadata = {}
    archive_url = "https://www.prnewswire.com/news/institute-for-supply-management/"
    try:
        r = requests.get(archive_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a['href'] for a in soup.find_all('a', href=True) if "manufacturing-pmi-report" in a['href'].lower()]
        for url in list(dict.fromkeys(links))[:8]:
            full_url = "https://www.prnewswire.com" + url if url.startswith('/') else url
            resp = requests.get(full_url, headers=HEADERS, timeout=10)
            raw_text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")
            pmi, m_year, growth, contr, comments, subcomponents = parse_report_text(raw_text)
            if m_year == "Unknown":
                continue
            date_obj = pd.to_datetime(m_year)
            report_metadata[date_obj] = {
                "comments": comments,
                "pmi": pmi,
                "subcomponents": subcomponents,
                "url": full_url
            }
            n_g, n_c = len(growth), len(contr)
            month_scores = {ind: 0 for ind in INDUSTRIES}
            for i, s in enumerate(growth):
                norm = normalize_name(s)
                if norm in NORM_TO_OFFICIAL:
                    month_scores[NORM_TO_OFFICIAL[norm]] = n_g - i
            for i, s in enumerate(contr):
                norm = normalize_name(s)
                if norm in NORM_TO_OFFICIAL:
                    month_scores[NORM_TO_OFFICIAL[norm]] = -(n_c - i)
            for ind, score in month_scores.items():
                all_data.append({
                    "date": date_obj,
                    "industry": ind,
                    "score": score,
                    "pmi": pmi,
                    "url": full_url
                })
    except Exception as e:
        st.error(f"Archive Fetch Error: {e}")
    return pd.DataFrame(all_data), report_metadata

# ====================== MAIN APP ======================
st.title("🏭 ISM Manufacturing Intelligence Hub")

with st.spinner("Rebuilding 6-month sector history from PR Newswire..."):
    df_master, report_metadata = build_historical_dataset()

if df_master.empty:
    st.error("No data found. Please check the scraper settings or the Source URL.")
    st.stop()

latest_date = df_master['date'].max()
current_df = df_master[df_master['date'] == latest_date].copy()
latest_meta = report_metadata.get(latest_date, {})
pmi_val = latest_meta.get("pmi", 50)
report_url = latest_meta.get("url", "#")
comments_list = latest_meta.get("comments", [])
subcomponents = latest_meta.get("subcomponents", {})

st.subheader(f"Current Report: {latest_date.strftime('%B %Y')}")

# === 1. HEADLINE MANUFACTURING PMI (restored as big prominent metric) ===
st.metric(
    label="**Manufacturing PMI**",
    value=f"{pmi_val:.1f}",
    delta=f"{'Above 50 (Expansion)' if pmi_val > 50 else 'Below 50 (Contraction)'}",
    delta_color="normal" if pmi_val > 50 else "inverse"
)

# === 2. SUB-INDICES ROW (unchanged — best-in-class) ===
metric_cols = st.columns(5)
keys = ["New Orders", "Production", "Employment", "Prices", "Backlog of Orders"]
labels = ["New Orders", "Production", "Employment", "Prices Paid", "Backlog of Orders"]
for i, (key, label) in enumerate(zip(keys, labels)):
    data = subcomponents.get(key, {})
    current = data.get("current")
    change = data.get("change")
    trend = data.get("trend")
    if current is not None:
        delta_str = f"{change:+.1f}/{trend}" if change is not None and trend is not None else None
        delta_color = "normal" if current > 50 else "inverse"
        with metric_cols[i]:
            st.metric(label=label, value=f"{current:.1f}", delta=delta_str, delta_color=delta_color)
    else:
        with metric_cols[i]:
            st.metric(label=label, value="N/A")

st.divider()

# === 3. INDUSTRY RANKINGS TABLE (restored exactly as before) ===
st.subheader("📊 Industry Rankings (Ordered by Growth)")
styled_df = (
    current_df[["industry", "score"]]
    .sort_values("score", ascending=False)
    .style.background_gradient(cmap="RdYlGn", subset=["score"], vmin=-13, vmax=13)
    .format({"score": "{:+d}"})
    .set_properties(**{"font-weight": "bold"})
)
st.dataframe(styled_df, use_container_width=True, hide_index=True)

st.divider()

# === 4. ECONOMIC DRIVER SIGNALS (placed exactly where you asked) ===
st.subheader("🔬 Economic Driver Signals (Professional Macro Translation)")
drivers = calculate_drivers(subcomponents)
driver_cols = st.columns(len(drivers))
for idx, (driver_name, driver) in enumerate(drivers.items()):
    with driver_cols[idx]:
        color = "normal" if driver.strength > 0 else "inverse"
        st.metric(
            label=driver.name,
            value=f"{driver.strength:+.2f}",
            delta=driver.description,
            delta_color=color
        )
        st.caption(" | ".join(driver.signals_used))

st.divider()

# ====================== ISM-LEVERAGED STOCK IDEAS ======================
st.subheader("🔥 ISM-Leveraged Stock Ideas")
st.caption("**Full NYSE + NASDAQ** • Market Cap > $1B • Scored by economic exposure")

if st.button("🚀 Generate Ranked Ideas (Full Universe)", type="primary", use_container_width=True):
    with st.spinner("Fetching full universe (~10k tickers) + applying macro scoring..."):
        stocks_df = get_full_stock_universe()
        if not stocks_df.empty:
            scored_df = tag_and_score_stocks(stocks_df, drivers)
            st.success(f"✅ Scored {len(scored_df)} stocks")
            display_cols = ["Ticker", "Company", "Yahoo Industry", "Market Cap", "ism_score", "why"]
            st.dataframe(
                scored_df.head(30)[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Market Cap": st.column_config.TextColumn("Market Cap"),
                    "Company": st.column_config.TextColumn("Company", width="medium"),
                    "why": st.column_config.TextColumn("Why this stock?", width="large"),
                    "ism_score": st.column_config.NumberColumn("ISM Score", format="%.2f"),
                }
            )
        else:
            st.error("❌ Could not fetch stock universe.")

# ====================== HISTORICAL BACKTEST ======================
st.subheader("📅 Historical Backtest (Test Past ISM Reports)")

if report_metadata:
    # Get sorted list of available historical dates
    historical_dates = sorted(report_metadata.keys(), reverse=True)
    date_options = [d.strftime('%B %Y') for d in historical_dates]
    
    selected_month_str = st.selectbox(
        "Select a past ISM report to backtest:",
        options=date_options,
        index=0  # default to most recent (current month)
    )
    
    # Map back to actual datetime object
    selected_date = next(d for d in historical_dates if d.strftime('%B %Y') == selected_month_str)
    
    if st.button(f"🔄 Re-run Scoring for {selected_month_str}", type="primary", use_container_width=True):
        with st.spinner(f"Re-calculating drivers + scoring for {selected_month_str}..."):
            # Get historical subcomponents
            hist_meta = report_metadata[selected_date]
            hist_subcomponents = hist_meta.get("subcomponents", {})
            
            # Re-compute drivers for that past month
            hist_drivers = calculate_drivers(hist_subcomponents)
            
            # Re-score the full stock universe with historical drivers
            stocks_df = get_full_stock_universe()  # uses cached universe
            if not stocks_df.empty:
                scored_hist = tag_and_score_stocks(stocks_df.copy(), hist_drivers)
                
                st.success(f"✅ Backtest complete for {selected_month_str} — Top ideas below")
                
                # Show the historical ranked table
                display_cols = ["Ticker", "Company", "Yahoo Industry", "Market Cap", "ism_score", "why"]
                st.dataframe(
                    scored_hist.head(30)[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Market Cap": st.column_config.TextColumn("Market Cap"),
                        "Company": st.column_config.TextColumn("Company", width="medium"),
                        "why": st.column_config.TextColumn("Why this stock scored high", width="large"),
                        "ism_score": st.column_config.NumberColumn("ISM Score", format="%.2f"),
                    }
                )
                
                # Quick driver snapshot for that month
                st.caption("Economic Driver Signals for this historical month:")
                driver_cols = st.columns(len(hist_drivers))
                for idx, (d_name, driver) in enumerate(hist_drivers.items()):
                    with driver_cols[idx]:
                        color = "normal" if driver.strength > 0 else "inverse"
                        st.metric(
                            label=d_name,
                            value=f"{driver.strength:+.2f}",
                            delta=driver.description,
                            delta_color=color
                        )
            else:
                st.error("No stock universe available for backtesting.")
else:
    st.info("No historical data available yet — run a Deep Refresh first.")

st.divider()

# ====================== RESPONDENT COMMENTS ======================
with st.expander("📢 WHAT RESPONDENTS ARE SAYING", expanded=False):
    if comments_list:
        st.markdown("\n\n".join(comments_list))
    else:
        st.info("No respondent comments available for this report.")

# ====================== REMAINING FEATURES ======================
st.subheader("📊 6-Month Sector Momentum")
pivot = df_master.pivot(index="industry", columns="date", values="score").fillna(0)
pivot = pivot.reindex(INDUSTRIES)
pivot.columns = pivot.columns.strftime('%b %Y')
fig = px.imshow(
    pivot,
    labels=dict(x="Report Month", y="Industry", color="Score"),
    color_continuous_scale="RdYlGn",
    color_continuous_midpoint=0,
    text_auto=True,
    aspect="auto"
)
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

# ====================== SIDEBAR ======================
with st.sidebar:
    st.image("https://www.ismworld.org/globalassets/pub/logos/ism_manufacturing_pmi_logo.png", width=200)
    st.write(f"**Current Source:** [PR Newswire]({report_url})")
    st.caption("**Sub-indices parser + Economic Exposure Ontology now live**")
    if st.button("Deep Refresh (Scrape Archive)"):
        st.cache_data.clear()
        st.rerun()
