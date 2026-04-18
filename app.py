import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import os
from datetime import datetime

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

# ====================== NAME NORMALIZATION ======================
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name

NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}

# ====================== DATA PERSISTENCE ======================
def load_history():
    if os.path.exists(HISTORICAL_FILE):
        df = pd.read_csv(HISTORICAL_FILE)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame(columns=["date", "industry", "score"])

def save_to_history(df, report_date):
    existing_df = load_history()
    new_data = df.copy()
    new_data["date"] = pd.to_datetime(report_date)
    combined = pd.concat([existing_df, new_data]).drop_duplicates(subset=["date", "industry"], keep="last")
    combined.to_csv(HISTORICAL_FILE, index=False)
    return combined

# ====================== SCRAPER ======================
def fetch_report_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")

        pmi_match = re.search(r"Manufacturing PMI® .*?at (\d+\.\d+)%", text)
        pmi = float(pmi_match.group(1)) if pmi_match else 0.0

        month_match = re.search(r"(\w+ \d{4}) ISM® Manufacturing", text)
        month_year = month_match.group(1) if month_match else "Unknown"

        # Growth list
        growth_block = re.search(r"listed in order — are:(.*?)\. The", text, re.DOTALL | re.IGNORECASE)
        growth_list = []
        if growth_block:
            raw = growth_block.group(1).replace(" and ", "; ")
            growth_list = [x.strip() for x in raw.split(";") if x.strip()]

        # Contraction list
        contr_block = re.search(r"contraction in \w+ are:(.*?)\.", text, re.DOTALL | re.IGNORECASE)
        contraction_list = []
        if contr_block:
            raw = contr_block.group(1).replace(" and ", "; ")
            contraction_list = [x.strip() for x in raw.split(";") if x.strip()]

        return pmi, month_year, growth_list, contraction_list, url
    except Exception:
        return None, None, [], [], None

@st.cache_data(ttl=43200)
def get_latest_data():
    url = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(url)

# ====================== MAIN APP ======================
st.title("🏭 ISM Manufacturing Industry Heatmap")

hist_df = load_history()
pmi, month_year, growth, contraction, report_url = get_latest_data()

if pmi:
    # ====================== SCORING ======================
    scores = {ind: 0 for ind in INDUSTRIES}
    n_growth = len(growth)
    n_contr = len(contraction)

    for i, scraped in enumerate(growth):
        norm = normalize_name(scraped)
        if norm in NORM_TO_OFFICIAL:
            official = NORM_TO_OFFICIAL[norm]
            scores[official] = n_growth - i

    for i, scraped in enumerate(contraction):
        norm = normalize_name(scraped)
        if norm in NORM_TO_OFFICIAL:
            official = NORM_TO_OFFICIAL[norm]
            scores[official] = -(n_contr - i)

    current_df = pd.DataFrame({"industry": list(scores.keys()), "score": list(scores.values())})

    saved_df = save_to_history(current_df, month_year)

    # ====================== CURRENT MONTH TABLE ======================
    st.subheader(f"Ranked Sector Performance: {month_year} (PMI® {pmi}%)")

    styled_df = (
        current_df
        .sort_values("score", ascending=False)
        .style.background_gradient(
            cmap="RdYlGn",
            subset=["score"],
            vmin=-max(abs(current_df["score"].max()), abs(current_df["score"].min()), 1),
            vmax=max(abs(current_df["score"].max()), abs(current_df["score"].min()), 1)
        )
        .format({"score": "{:+d}"})
        .set_properties(**{"text-align": "left", "font-weight": "bold"})
    )
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # ====================== DOWNLOAD BUTTON ======================
    st.caption("💾 Historical data is saved automatically in this app.")
    csv_data = saved_df.to_csv(index=False)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.download_button(
            label="📥 Download ism_history.csv",
            data=csv_data,
            file_name="ism_history.csv",
            mime="text/csv",
        )
    with col2:
        st.info("To keep history forever:\n"
                "1. Click the button above\n"
                "2. Go to your GitHub repo → replace `ism_history.csv`\n"
                "3. Commit the change (once per month)")

    # ====================== HISTORICAL HEATMAP (FIXED ORDER) ======================
    st.divider()
    st.subheader("📈 6-Month Sector Momentum (Fixed Sector Order)")

    full_hist = load_history()
    if not full_hist.empty:
        pivot = full_hist.pivot(index="industry", columns="date", values="score").fillna(0)
        pivot = pivot.reindex(INDUSTRIES)                    # ← sectors stay in fixed order
        pivot.columns = pivot.columns.strftime('%b %Y')

        fig = px.imshow(
            pivot,
            labels=dict(x="Month", y="Industry", color="Score"),
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            text_auto=True,
            aspect="auto"
        )
        fig.update_layout(xaxis_title="", yaxis_title="", height=650)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No history yet — the next report will start collecting data.")

else:
    st.error("Failed to load report.")

with st.sidebar:
    st.write(f"**Report Link:** [Source]({report_url})")
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
