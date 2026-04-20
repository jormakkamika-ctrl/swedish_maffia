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

# ====================== NAICS MAPPING (exact ISM → NAICS) ======================
NAICS_MAPPING = {
    "Food, Beverage & Tobacco Products": "311, 312",
    "Textile Mills": "313",
    "Apparel, Leather & Allied Products": "315, 316",
    "Wood Products": "321",
    "Paper Products": "322",
    "Printing & Related Support Activities": "323",
    "Petroleum & Coal Products": "324",
    "Chemical Products": "325",
    "Plastics & Rubber Products": "326",
    "Nonmetallic Mineral Products": "327",
    "Primary Metals": "331",
    "Fabricated Metal Products": "332",
    "Machinery": "333",
    "Computer & Electronic Products": "334",
    "Electrical Equipment, Appliances & Components": "335",
    "Transportation Equipment": "336",
    "Furniture & Related Products": "337",
    "Miscellaneous Manufacturing": "339",
}

# ====================== PRIMARY ISM → YAHOO INDUSTRY MAPPING (broad but still primary) ======================
# Expanded to cover ~1,500 >$1B stocks dynamically when filtering the full universe
PRIMARY_ISM_MAPPING: Dict[str, List[str]] = {
    "Food, Beverage & Tobacco Products": ["Packaged Foods", "Beverages - Non-Alcoholic", "Tobacco", "Confectioners", "Farm Products"],
    "Textile Mills": ["Textile Manufacturing", "Apparel Manufacturing"],
    "Apparel, Leather & Allied Products": ["Apparel Manufacturing", "Footwear & Accessories"],
    "Wood Products": ["Lumber & Wood Production", "Building Materials", "Residential Construction"],
    "Paper Products": ["Paper & Forest Products", "Packaging & Containers"],
    "Printing & Related Support Activities": ["Packaging & Containers", "Specialty Industrial Machinery"],
    "Petroleum & Coal Products": ["Oil & Gas Refining & Marketing", "Oil & Gas Midstream"],
    "Chemical Products": ["Chemicals", "Specialty Chemicals"],
    "Plastics & Rubber Products": ["Packaging & Containers", "Rubber & Plastics"],
    "Nonmetallic Mineral Products": ["Building Materials", "Construction Materials"],
    "Primary Metals": ["Steel", "Aluminum", "Copper", "Other Industrial Metals & Mining"],
    "Fabricated Metal Products": ["Metal Fabrication", "Tools & Accessories"],
    "Machinery": ["Specialty Industrial Machinery", "Farm & Heavy Construction Machinery"],
    "Computer & Electronic Products": ["Semiconductors", "Electronic Components", "Computer Hardware"],
    "Electrical Equipment, Appliances & Components": ["Electrical Equipment & Parts", "Specialty Industrial Machinery"],
    "Transportation Equipment": ["Aerospace & Defense", "Auto Manufacturers", "Auto Parts"],
    "Furniture & Related Products": ["Furnishings, Fixtures & Appliances"],
    "Miscellaneous Manufacturing": ["Medical Instruments & Supplies", "Leisure"],
}

# ====================== ECONOMIC EXPOSURE ONTOLOGY (unchanged - for Tab 2) ======================
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

    demand_strength = np.mean([
        normalize_signal(signals["new_orders"].get("current", 50), signals["new_orders"].get("change", 0), signals["new_orders"].get("trend", 0)),
        normalize_signal(signals["backlog"].get("current", 50), signals["backlog"].get("change", 0), signals["backlog"].get("trend", 0)),
    ])
    drivers[DriverName.DEMAND_MOMENTUM] = EconomicDriver(
        name=DriverName.DEMAND_MOMENTUM, strength=round(float(demand_strength), 2),
        signals_used=["New Orders", "Backlog of Orders"],
        description="Forward revenue visibility & sustained order flow"
    )

    capex_strength = np.mean([
        normalize_signal(signals["backlog"].get("current", 50), signals["backlog"].get("change", 0), signals["backlog"].get("trend", 0)),
        normalize_signal(signals["production"].get("current", 50), signals["production"].get("change", 0), signals["production"].get("trend", 0)),
    ])
    drivers[DriverName.CAPEX_PRESSURE] = EconomicDriver(
        name=DriverName.CAPEX_PRESSURE, strength=round(float(capex_strength), 2),
        signals_used=["Backlog of Orders", "Production"],
        description="Capacity constraints → future capital spending"
    )

    drivers[DriverName.INPUT_COST_INFLATION] = EconomicDriver(
        name=DriverName.INPUT_COST_INFLATION,
        strength=round(normalize_signal(signals["prices_paid"].get("current", 50), signals["prices_paid"].get("change", 0), signals["prices_paid"].get("trend", 0)), 2),
        signals_used=["Prices Paid"],
        description="Input-cost pressure or pricing power"
    )

    drivers[DriverName.LABOR_TIGHTNESS] = EconomicDriver(
        name=DriverName.LABOR_TIGHTNESS,
        strength=round(normalize_signal(signals["employment"].get("current", 50), signals["employment"].get("change", 0), signals["employment"].get("trend", 0)), 2),
        signals_used=["Employment"],
        description="Hiring plans & wage pressure"
    )

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

# ====================== OFFICIAL TICKER LOADER (stolen from Bangkok app) ======================
@st.cache_data(ttl=86400)
def load_all_us_tickers():
    """Official NASDAQ + NYSE + AMEX lists — much cleaner than GitHub mirror."""
    try:
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        
        n_df = nasdaq[['Symbol', 'Security Name']].copy()
        o_df = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        
        full_df = pd.concat([n_df, o_df], ignore_index=True).drop_duplicates(subset='Symbol')
        
        # Filter obvious junk
        full_df = full_df[~full_df['Symbol'].str.contains(r'\$|\.|TEST|N/A', na=False)]
        
        st.info(f"✅ Loaded {len(full_df):,} official US tickers (NASDAQ + NYSE + AMEX)")
        return full_df
    except Exception as e:
        st.error(f"Failed to load official ticker list: {e}")
        return pd.DataFrame()


# ====================== FULL STOCK UNIVERSE (Hybrid — Best of Both Apps) ======================
@st.cache_data(ttl=86400, show_spinner=False)
def get_full_stock_universe(max_tickers: int = 6000, batch_size: int = 50):
    """Ultra-robust stock loader — survives Yahoo rate limits + bad tickers."""
    tickers_df = load_all_us_tickers()
    if tickers_df.empty:
        return pd.DataFrame()

    stock_symbols = tickers_df[~tickers_df['Security Name'].str.contains(
        'ETF|Trust|Fund|Invesco|iShares|Vanguard|WARRANT|RIGHTS|UNIT|WT', case=False, na=False
    )]['Symbol'].tolist()[:max_tickers]

    rows = []
    progress_bar = st.progress(0, text=f"Building ISM universe (> $1B) — scanning {len(stock_symbols):,} symbols...")

    for i in range(0, len(stock_symbols), batch_size):
        batch = stock_symbols[i:i + batch_size]
        
        for sym in batch:
            for attempt in range(3):  # retry up to 3 times per ticker
                try:
                    t = yf.Ticker(sym)
                    info = t.info or {}
                    fast_info = getattr(t, 'fast_info', {}) or {}

                    market_cap = (
                        info.get("marketCap") or info.get("market_cap") or
                        fast_info.get("marketCap") or fast_info.get("market_cap") or 0
                    )

                    if market_cap > 1_000_000_000:
                        company_name = info.get("longName") or info.get("shortName") or sym
                        industry = info.get("industry", "") or ""
                        exchange = str(info.get("exchange", "")).upper()

                        valid_exchanges = {"NYSE", "NYQ", "NMS", "NASD", "NASDAQ", "AMEX", "NASDAQGS", "NASDAQGM"}
                        
                        if any(kw in exchange for kw in valid_exchanges):
                            rows.append({
                                "Ticker": sym,
                                "Company": company_name,
                                "Yahoo Industry": industry,
                                "Market Cap": market_cap,
                                "Exchange": exchange,
                                "Security Name": tickers_df[tickers_df['Symbol'] == sym]['Security Name'].iloc[0] if sym in tickers_df['Symbol'].values else ""
                            })
                        break  # success → move to next ticker

                except Exception:
                    if attempt == 2:
                        break  # give up after 3 tries
                    time.sleep(1.5 ** attempt)  # backoff

        # Live progress + real "Found" count
        progress = min(1.0, (i + len(batch)) / len(stock_symbols))
        progress_bar.progress(progress, text=f"Processed {i+len(batch):,}/{len(stock_symbols):,} | Found {len(rows):,} valid stocks > $1B")

        time.sleep(2.0 + np.random.uniform(0.5, 1.5))  # aggressive but safe rate limit avoidance

    progress_bar.empty()

    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values("Market Cap", ascending=False).reset_index(drop=True)
        df["Market Cap"] = df["Market Cap"].apply(lambda x: f"${x/1_000_000_000:.1f}B")
        st.success(f"✅ Universe ready: **{len(df):,} stocks** (> $1B market cap)")
        return df
    else:
        st.error("❌ Could not fetch any valid stocks — try Deep Refresh or check connection.")
        return pd.DataFrame()

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
    """Robust scraper with retries + longer timeout + graceful fallback."""
    all_data = []
    report_metadata = {}
    
    archive_url = "https://www.prnewswire.com/news/institute-for-supply-management/"
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    for attempt in range(3):  # 3 attempts
        try:
            r = session.get(archive_url, timeout=30)  # increased from 15s
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Find all report links (updated pattern that works on current site)
            links = [a['href'] for a in soup.find_all('a', href=True) 
                    if any(x in a['href'].lower() for x in ["manufacturing-pmi", "ism-manufacturing", "report-on-business"])]
            
            # Deduplicate and take most recent 8
            links = list(dict.fromkeys(links))[:8]
            
            for url in links:
                full_url = "https://www.prnewswire.com" + url if url.startswith('/') else url
                try:
                    resp = session.get(full_url, timeout=25)
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
                    
                    # Build monthly industry scores
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
                except:
                    continue
                    
            break  # success on this attempt
            
        except Exception as e:
            if attempt == 2:  # last attempt
                st.warning(f"⚠️ Archive fetch failed after retries: {str(e)[:80]}... Using cached/current data only.")
            else:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
    
    df = pd.DataFrame(all_data)
    
    if df.empty:
        st.warning("⚠️ Could not fetch historical archive. Current report will still work. Try Deep Refresh later.")
        # Return empty but don't crash the app
        return pd.DataFrame(columns=["date", "industry", "score", "pmi", "url"]), {}
    
    st.success(f"✅ Loaded {len(df['date'].unique())} historical ISM reports")
    df = pd.DataFrame(all_data)
    df = df.drop_duplicates(subset=['date', 'industry'], keep='last').reset_index(drop=True)  # ← add this
    return df, report_metadata

# ====================== MAIN APP WITH TABS ======================
st.title("🏭 ISM Manufacturing Intelligence Hub")

with st.spinner("Rebuilding 6-month sector history..."):
    df_master, report_metadata = build_historical_dataset()

if df_master.empty:
    st.error("No data found.")
    st.stop()

latest_date = df_master['date'].max()
current_df = df_master[df_master['date'] == latest_date].copy()
latest_meta = report_metadata.get(latest_date, {})
pmi_val = latest_meta.get("pmi", 50)
report_url = latest_meta.get("url", "#")
comments_list = latest_meta.get("comments", [])
subcomponents = latest_meta.get("subcomponents", {})

tab1, tab2 = st.tabs(["🏭 Primary Effects", "🔬 Fund Manager Macro Scoring"])

# ====================== TAB 1: PRIMARY EFFECTS ======================
with tab1:
    st.subheader(f"Current Report: {latest_date.strftime('%B %Y')}")

    # Headline PMI + Sub-indices
    st.metric(
        label="**Manufacturing PMI**",
        value=f"{pmi_val:.1f}",
        delta=f"{'Above 50 (Expansion)' if pmi_val > 50 else 'Below 50 (Contraction)'}",
        delta_color="normal" if pmi_val > 50 else "inverse"
    )

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

    # Clickable Industry Rankings (single version)
    st.subheader("📊 Industry Rankings (Ordered by Growth) — Click to select")
    st.caption("Select one or more rows → then press the basket button")

    ranked_df = current_df[["industry", "score"]].sort_values("score", ascending=False).reset_index(drop=True)
    selected_rows = st.dataframe(
        ranked_df.style.background_gradient(cmap="RdYlGn", subset=["score"], vmin=-13, vmax=13)
        .format({"score": "{:+d}"})
        .set_properties(**{"font-weight": "bold"}),
        use_container_width=True,
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun"
    )

    st.divider()

    # NAICS Mapping — collapsed by default
    with st.expander("🔗 Official NAICS Mapping (ISM → Production Category)", expanded=False):
        naics_df = pd.DataFrame(list(NAICS_MAPPING.items()), columns=["ISM Industry", "NAICS Code(s)"])
        st.dataframe(naics_df, use_container_width=True, hide_index=True)

    st.divider()

    # Primary Effect Stock Baskets
    st.subheader("📦 Primary Effect Stock Baskets")
    st.caption("**Direct NAICS-mapped companies** • Only selected industries are processed")

    if st.button("🚀 Generate Primary Effect Baskets for Selected Industries", type="primary", use_container_width=True):
        stocks_df = get_full_stock_universe()
        if not stocks_df.empty:
            if len(selected_rows["selection"]["rows"]) > 0:
                selected_indices = selected_rows["selection"]["rows"]
                selected_industries = ranked_df.iloc[selected_indices]["industry"].tolist()
                st.success(f"✅ Filtering for {len(selected_industries)} selected industry(ies)")
            else:
                selected_industries = [ind for ind, score in zip(current_df["industry"], current_df["score"]) if score != 0]

            for industry in selected_industries:
                direction = "GROWTH" if current_df.loc[current_df['industry'] == industry, 'score'].iloc[0] > 0 else "CONTRACTION"
                color = "green" if direction == "GROWTH" else "red"

                yahoo_industries = PRIMARY_ISM_MAPPING.get(industry, [])
                if not yahoo_industries:
                    continue

                filtered = stocks_df[stocks_df["Yahoo Industry"].isin(yahoo_industries)].copy()
                filtered = filtered.sort_values("Market Cap", ascending=False).head(30)

                with st.expander(f"**{industry} — {direction}** ({len(filtered)} stocks)", expanded=True):
                    st.markdown(f"<span style='color:{color}'>**Primary Effect via NAICS {NAICS_MAPPING.get(industry, '—')}**</span>", unsafe_allow_html=True)
                    st.dataframe(
                        filtered[["Ticker", "Company", "Yahoo Industry", "Market Cap"]],
                        use_container_width=True,
                        hide_index=True
                    )

    # === Respondent Comments, 6-Month Momentum, Industry Score Evolution ===
    with st.expander("📢 WHAT RESPONDENTS ARE SAYING", expanded=False):
        if comments_list:
            st.markdown("\n\n".join(comments_list))
        else:
            st.info("No respondent comments available for this report.")

        st.subheader("📊 6-Month Sector Momentum")
    
    # Fixed: safely handle any duplicate (industry, date) rows
    pivot = df_master.pivot_table(
        index="industry", 
        columns="date", 
        values="score", 
        aggfunc="last"          # takes the latest value if duplicates exist
    ).fillna(0)
    
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
    st.plotly_chart(fig, use_container_width=True, key="momentum_chart")

    st.subheader("Industry Score Evolution")
    to_track = st.multiselect("Select industries to compare:", INDUSTRIES, 
                              default=["Transportation Equipment", "Chemical Products", "Computer & Electronic Products"])
    if to_track:
        line_df = df_master[df_master['industry'].isin(to_track)].sort_values('date')
        fig_line = px.line(line_df, x='date', y='score', color='industry', markers=True,
                           line_shape='spline', title="Relative Growth/Contraction Trends")
        st.plotly_chart(fig_line, use_container_width=True, key="evolution_chart")   # ← unique key

# ====================== TAB 2: FUND MANAGER MACRO SCORING (Secondary Effects) ======================
with tab2:
    st.subheader("🔬 Economic Driver Signals (Professional Macro Translation)")
    drivers = calculate_drivers(subcomponents)
    driver_cols = st.columns(len(drivers))
    for idx, (driver_name, driver) in enumerate(drivers.items()):
        with driver_cols[idx]:
            color = "normal" if driver.strength > 0 else "inverse"
            st.metric(label=driver.name, value=f"{driver.strength:+.2f}", delta=driver.description, delta_color=color)
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
        historical_dates = sorted(report_metadata.keys(), reverse=True)
        date_options = [d.strftime('%B %Y') for d in historical_dates]
       
        selected_month_str = st.selectbox(
            "Select a past ISM report to backtest:",
            options=date_options,
            index=0
        )
       
        selected_date = next(d for d in historical_dates if d.strftime('%B %Y') == selected_month_str)
       
        if st.button(f"🔄 Re-run Scoring for {selected_month_str}", type="primary", use_container_width=True):
            with st.spinner(f"Re-calculating drivers + scoring for {selected_month_str}..."):
                hist_meta = report_metadata[selected_date]
                hist_subcomponents = hist_meta.get("subcomponents", {})
                hist_drivers = calculate_drivers(hist_subcomponents)
               
                stocks_df = get_full_stock_universe()
                if not stocks_df.empty:
                    scored_hist = tag_and_score_stocks(stocks_df.copy(), hist_drivers)
                   
                    st.success(f"✅ Backtest complete for {selected_month_str} — Top ideas below")
                   
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

# ====================== SIDEBAR ======================
with st.sidebar:
    st.image("https://www.ismworld.org/globalassets/pub/logos/ism_manufacturing_pmi_logo.png", width=200)
    st.write(f"**Current Source:** [PR Newswire]({report_url})")
    st.caption("**Tab 1 = Primary Effects (NAICS direct)**\n**Tab 2 = Fund Manager Secondary / Macro Drivers**")
    if st.button("🔄 Deep Refresh (Scrape Archive)"):
        st.cache_data.clear()
        st.rerun()
