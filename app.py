HTML<FILE filename="app.py" size="12485 bytes">
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime
import yfinance as yf

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

# IMPROVED: More accurate & complete Yahoo Finance industry strings (exact matches from yfinance.info['industry'])
# This fixes the empty results — especially for Petroleum & Coal Products (now includes "Oil & Gas Integrated")
ISM_TO_YAHOO_INDUSTRIES = {
    "Transportation Equipment": ["Aerospace & Defense", "Auto Manufacturers", "Auto Parts", "Railroads"],
    "Computer & Electronic Products": ["Semiconductors", "Computer Hardware", "Electronic Components", 
                                      "Communication Equipment", "Semiconductor Equipment & Materials"],
    "Chemical Products": ["Chemicals", "Specialty Chemicals"],
    "Food, Beverage & Tobacco Products": ["Packaged Foods", "Beverages - Non-Alcoholic", "Beverages - Brewers", 
                                         "Tobacco", "Confectioners"],
    "Primary Metals": ["Steel", "Aluminum", "Copper", "Other Industrial Metals & Mining"],
    "Machinery": ["Specialty Industrial Machinery", "Farm & Heavy Construction Machinery", "Tools & Accessories"],
    "Furniture & Related Products": ["Furnishings, Fixtures & Appliances"],
    "Petroleum & Coal Products": [
        "Oil & Gas Integrated",                  # ← XOM, CVX, etc.
        "Oil & Gas Exploration & Production",    # ← COP, EOG, etc.
        "Oil & Gas Refining & Marketing",        # ← PSX, MPC, VLO, etc.
        "Oil & Gas Midstream",                   # ← pipelines
        "Oil & Gas Equipment & Services"         # ← SLB, BKR, etc.
    ],
    "Electrical Equipment, Appliances & Components": ["Electrical Equipment & Parts"],
    "Apparel, Leather & Allied Products": ["Textile Manufacturing", "Footwear & Accessories", "Apparel Manufacturing"],
    "Wood Products": ["Lumber & Wood Production"],
    "Paper Products": ["Paper & Paper Products"],
    "Plastics & Rubber Products": ["Specialty Chemicals"],
    "Nonmetallic Mineral Products": ["Building Materials"],
    "Fabricated Metal Products": ["Metal Fabrication"],
    "Textile Mills": ["Textile Manufacturing"],
    "Printing & Related Support Activities": ["Specialty Business Services"],
    "Miscellaneous Manufacturing": ["Conglomerates", "Specialty Industrial Machinery"],
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


def get_respondent_comments(text: str) -> list[str]:
    section_match = re.search(
        r"WHAT RESPONDENTS ARE SAYING\s*(.*?)(?=\s*(?:MANUFACTURING AT A GLANCE|The Institute for Supply Management®|©|ISM® Reports|Report Issued|$))",
        text,
        re.DOTALL | re.IGNORECASE
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
                industry = industry.strip()
                comment += f" [{industry}]"
            comments.append(comment)

    if not comments:
        raw_bullets = re.split(r'\s*(?:\*|\-)\s*["“]?', section)
        for line in raw_bullets:
            line = line.strip().strip('"“”')
            if line and len(line) > 20:
                comments.append(f"• {line}")

    return comments


# ====================== STOCK FETCHER ======================
@st.cache_data(ttl=86400)
def get_sp500_tickers():
    """Return list of current S&P 500 tickers."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        return df["Symbol"].tolist() if (df := tables[0]) is not None else []
    except Exception:
        return ["AAPL", "MSFT", "GOOGL", "XOM", "CVX"]  # fallback with some energy names


@st.cache_data(ttl=3600)
def fetch_stocks_in_industries(selected_industries: tuple):
    """
    Fetch stocks matching the selected Yahoo industries.
    Now uses FLEXIBLE matching + correct industry strings.
    """
    if not selected_industries:
        return pd.DataFrame()

    tickers_list = get_sp500_tickers()
    if len(tickers_list) < 10:
        return pd.DataFrame()

    tickers_obj = yf.Tickers(" ".join(tickers_list))

    rows = []
    for sym in tickers_list:
        try:
            info = tickers_obj.tickers[sym].info

            industry = info.get("industry", "") or ""
            market_cap = info.get("marketCap") or info.get("enterpriseValue") or 0
            exchange = info.get("exchange", "").upper()
            company_name = info.get("longName") or info.get("shortName") or sym

            # FLEXIBLE MATCHING (handles minor variations)
            industry_match = any(
                y.lower() in industry.lower() or industry.lower() in y.lower()
                for y in selected_industries
            )

            if (
                industry_match
                and market_cap > 1_000_000_000
                and exchange in ["NYSE", "NYQ", "NMS", "NASD", "NASDAQ"]
            ):
                rows.append({
                    "Ticker": sym,
                    "Company": company_name,
                    "Yahoo Industry": industry,
                    "Market Cap": market_cap,
                    "Exchange": exchange
                })
        except:
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Market Cap", ascending=False)
        df["Market Cap"] = df["Market Cap"].apply(lambda x: f"${x/1_000_000_000:.1f}B")
    return df


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

    comments = get_respondent_comments(text)

    return pmi, month_year, get_list(growth_p, text), get_list(contr_p, text), comments


@st.cache_data(ttl=86400)
def build_historical_dataset():
    all_data = []
    report_metadata = {}
    
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
            pmi, m_year, growth, contr, comments = parse_report_text(raw_text)
            
            if m_year == "Unknown":
                continue
            
            date_obj = pd.to_datetime(m_year)
            
            report_metadata[date_obj] = {
                "comments": comments,
                "pmi": pmi,
                "url": url
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
                    "url": url
                })
    except Exception as e:
        st.error(f"Archive Fetch Error: {e}")

    return pd.DataFrame(all_data), report_metadata


# ====================== MAIN APP ======================
st.title("🏭 ISM Manufacturing Intelligence Hub")

with st.spinner("Rebuilding 6-month sector history from PR Newswire..."):
    df_master, report_metadata = build_historical_dataset()

if not df_master.empty:
    latest_date = df_master['date'].max()
    current_df = df_master[df_master['date'] == latest_date].copy()
    
    latest_meta = report_metadata.get(latest_date, {})
    pmi_val = latest_meta.get("pmi", current_df['pmi'].iloc[0])
    report_url = latest_meta.get("url", current_df['url'].iloc[0])
    comments_list = latest_meta.get("comments", [])

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
        selected_sector = st.selectbox("Select ISM Sector for Yahoo Mapping:", INDUSTRIES)
        
        related_yahoo = ISM_TO_YAHOO_INDUSTRIES.get(selected_sector, ["No direct Yahoo Finance mapping found"])
        
        st.info(f"**ISM Sector:** {selected_sector}\n\n**Maps to Yahoo Finance Industries:**\n" + "\n".join([f"- {y}" for y in related_yahoo]))
        
        score_now = current_df[current_df['industry'] == selected_sector]['score'].iloc[0]
        status = "🟢 Growing" if score_now > 0 else "🔴 Contracting" if score_now < 0 else "🟡 Neutral"
        st.write(f"Current Status: **{status}** ({score_now:+d})")

        st.write("**Select Yahoo Industries to Analyze**")
        selected_yahoo_industries = st.multiselect(
            "Tick the ones you want to explore:",
            options=related_yahoo,
            default=related_yahoo[:2] if len(related_yahoo) > 1 else related_yahoo,
            key="yahoo_select"
        )

    st.divider()
    with st.expander("📢 WHAT RESPONDENTS ARE SAYING", expanded=False):
        if comments_list:
            st.markdown("\n\n".join(comments_list))
        else:
            st.info("No respondent comments available for this report.")

    # === STOCKS SECTION ===
    st.subheader("📊 Stocks in Selected Yahoo Industries")
    st.caption("Filtered to NYSE/Nasdaq companies with Market Cap > $1 Billion (S&P 500 universe)")

    if st.button("🔍 Fetch Stocks (> $1B Market Cap)", type="primary", use_container_width=True):
        if selected_yahoo_industries:
            with st.spinner("Fetching latest stock data from Yahoo Finance..."):
                stocks_df = fetch_stocks_in_industries(tuple(selected_yahoo_industries))
                
                if not stocks_df.empty:
                    st.success(f"✅ Found {len(stocks_df)} qualifying stocks")
                    st.dataframe(
                        stocks_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Market Cap": st.column_config.TextColumn("Market Cap"),
                            "Company": st.column_config.TextColumn("Company", width="medium")
                        }
                    )
                else:
                    st.warning("No stocks found matching your selection in the current universe.")
        else:
            st.warning("Please select at least one Yahoo Finance industry above.")

    # --- HISTORICAL TREND HEATMAP ---
    st.subheader("📈 6-Month Sector Momentum")
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

    # --- SECTOR TRACKER (LINE CHART) ---
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
    st.caption("**Note:** Stock lookup uses S&P 500 universe (fast & reliable). Full NYSE/Nasdaq >$1B can be added later.")
    if st.button("Deep Refresh (Scrape Archive)"):
        st.cache_data.clear()
        st.rerun()

