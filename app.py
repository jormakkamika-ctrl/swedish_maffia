import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime
import os

st.set_page_config(page_title="ISM PMI Tracker", layout="wide")

# ====================== CONFIG & CONSTANTS ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
HISTORICAL_FILE = "ism_history.csv"

# ====================== DATA PERSISTENCE ======================
def load_history():
    if os.path.exists(HISTORICAL_FILE):
        df = pd.read_csv(HISTORICAL_FILE)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame(columns=["date", "industry", "score"])

def save_to_history(df, report_date):
    existing_df = load_history()
    # Format current data for storage
    new_data = df.copy()
    new_data["date"] = pd.to_datetime(report_date)
    
    # Merge and remove duplicates (prevents double-saving same month)
    combined = pd.concat([existing_df, new_data]).drop_duplicates(subset=["date", "industry"], keep="last")
    combined.to_csv(HISTORICAL_FILE, index=False)

# ====================== ROBUST SCRAPER ======================
def fetch_report_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ")

        # 1. Extract PMI
        pmi_match = re.search(r"at (\d+\.\d+)%", text)
        pmi = float(pmi_match.group(1)) if pmi_match else 0.0

        # 2. Extract Month/Year
        month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}", text)
        month_year = month_match.group(0) if month_match else "Unknown"

        # 3. List Extraction Function
        def get_industry_list(pattern, source):
            match = re.search(pattern, source, re.DOTALL | re.IGNORECASE)
            if not match: return []
            items = match.group(1).replace(" and ", ", ")
            return [i.strip() for i in re.split(r'[;,]', items) if len(i.strip()) > 3]

        growth_pattern = r"industries reporting growth in .*? are: (.*?)\.(?= The| \w+ industries|$)"
        contr_pattern = r"industries reporting contraction in .*? are: (.*?)\.(?= The| \w+ industries|$)"

        growth_list = get_industry_list(growth_pattern, text)
        contr_list = get_industry_list(contr_pattern, text)

        return pmi, month_year, growth_list, contr_list, url
    except Exception as e:
        st.error(f"Scraping Error: {e}")
        return None, None, [], [], None

@st.cache_data(ttl=43200)
def get_latest_data():
    # Primary URL (Example: March 2026 fallback provided by you)
    url = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(url)

# ====================== MAIN UI ======================
st.title("🏭 ISM Manufacturing Industry Heatmap")
hist_df = load_history()

pmi, month_year, growth, contraction, report_url = get_latest_data()

if pmi:
    st.metric(label=f"Manufacturing PMI® ({month_year})", value=f"{pmi}%", delta=f"{pmi-50:.1f} vs Neutral")
    
    # --- DYNAMIC SCORING ---
    scores = {ind: 0 for ind in INDUSTRIES}
    
    # Growth scoring: Top of list = Max points
    n_growth = len(growth)
    for i, scraped_name in enumerate(growth):
        score_val = n_growth - i
        for official in INDUSTRIES:
            if official.lower() in scraped_name.lower():
                scores[official] = score_val

    # Contraction scoring: Top of list (worst) = Max negative points
    n_contr = len(contraction)
    for i, scraped_name in enumerate(contraction):
        score_val = -(n_contr - i)
        for official in INDUSTRIES:
            if official.lower() in scraped_name.lower():
                scores[official] = score_val

    current_df = pd.DataFrame({"industry": list(scores.keys()), "score": list(scores.values())})
    
    # Save automatically to history if it doesn't exist for this month
    save_to_history(current_df, month_year)

    # --- CURRENT HEATMAP DISPLAY ---
    st.subheader(f"Ranked Sector Performance: {month_year}")
    
    # Safety check for divisors to avoid division by zero
    max_g = max(n_growth, 1)
    max_c = max(n_contr, 1)

    def color_scale(val):
        if val > 0:
            # Scale alpha based on ranking (0.3 to 1.0)
            alpha = 0.3 + (val / max_g) * 0.7
            return f'background-color: rgba(0, 255, 0, {alpha:.2f}); color: black; font-weight: bold;'
        elif val < 0:
            # Scale alpha based on ranking (0.3 to 1.0)
            alpha = 0.3 + (abs(val) / max_c) * 0.7
            return f'background-color: rgba(255, 0, 0, {alpha:.2f}); color: white; font-weight: bold;'
        return 'background-color: #1e1e1e; color: #555;'

    # Use .map() instead of .applymap() for newer Pandas versions
    styled_df = current_df.sort_values("score", ascending=False).style.map(color_scale, subset=['score'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # --- HISTORICAL TREND HEATMAP ---
    st.divider()
    st.subheader("📈 6-Month Sector Momentum")
    
    full_hist = load_history()
    if not full_hist.empty:
        # Pivot for heatmap
        pivot = full_hist.pivot(index="industry", columns="date", values="score").fillna(0)
        # Sort industries by latest score
        pivot = pivot.sort_values(by=pivot.columns[-1], ascending=False)
        
        fig = px.imshow(
            pivot,
            labels=dict(x="Month", y="Industry", color="Score"),
            x=pivot.columns.strftime('%b %Y'),
            y=pivot.index,
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            text_auto=True,
            aspect="auto"
        )
        fig.update_layout(xaxis_title="", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No history found. Refresh to start collecting data.")

else:
    st.error("Failed to load report. Check your internet connection or URL.")

with st.sidebar:
    st.write(f"**Report Link:** [Source]({report_url})")
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
