import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="ISM PMI Heatmap", layout="wide")
st.title("🟢 ISM Manufacturing PMI® Industry Heatmap + History")
st.caption("Ultra-robust scraper • PR Newswire + ISM fallbacks • Historical trends")

# ====================== CONFIG ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

# ====================== SCRAPER (NOW BULLETPROOF) ======================
@st.cache_data(ttl=43200)  # 12 hours
def get_latest_report(force_refresh=False):
    # --- 1. Try PR Newswire list page (most reliable source) ---
    try:
        r = requests.get("https://www.prnewswire.com/news/institute-for-supply-management/", 
                        headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        # Regex to find the LATEST Manufacturing PMI report URL (appears first in HTML)
        url_match = re.search(
            r'https?://www\.prnewswire\.com/news-releases/manufacturing-pmi-at-\d+\.\d+%?[^"]*?ism-manufacturing-pmi-report-\d+\.html',
            r.text
        )
        if url_match:
            report_url = url_match.group(0)
            st.success("✅ Latest report found via PR Newswire")
            return fetch_report_content(report_url)
    except:
        pass

    # --- 2. Fallback: ISM official site ---
    try:
        r = requests.get("https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/",
                        headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("a", string=re.compile("Past Month Manufacturing Report", re.I))
        if link and link.get("href"):
            report_url = "https://www.ismworld.org" + link["href"] if not link["href"].startswith("http") else link["href"]
            st.info("✅ Using ISM official fallback")
            return fetch_report_content(report_url)
    except:
        pass

    # --- 3. Ultimate fallback: try known recent URL pattern (rarely needed) ---
    st.warning("⚠️ Using emergency fallback scraper...")
    # You can manually add the very latest URL here if needed for a few days
    known_latest = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(known_latest)

def fetch_report_content(url):
    """Download full report and extract all needed data"""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")

    # PMI
    pmi_match = re.search(r"Manufacturing PMI® (?:registered )?at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else None

    # Month/Year
    month_match = re.search(r"(\w+ \d{4}) ISM® Manufacturing", text)
    month_year = month_match.group(1) if month_match else "Latest Month"

    # Growth list - very forgiving regex
    growth_match = re.search(
        r"The (\d+) manufacturing industries reporting growth in \w+.*?listed in order.*?are: (.*?)\.(?=\s+The \d+ industries|\s+The three|\s*$)",
        text, re.DOTALL | re.IGNORECASE
    )
    growth_list = []
    if growth_match:
        raw = growth_match.group(2).replace(" and ", "; ")
        growth_list = [x.strip() for x in raw.split(";") if x.strip()]

    # Contraction list
    contr_match = re.search(
        r"The (\d+) industries reporting contraction .*? are: (.*?)\.",
        text, re.DOTALL | re.IGNORECASE
    )
    contr_list = []
    if contr_match:
        raw = contr_match.group(2).replace(" and ", "; ")
        contr_list = [x.strip() for x in raw.split(";") if x.strip()]

    return pmi, month_year, growth_list, contr_list, url

# ====================== LOAD HISTORICAL ======================
@st.cache_data
def load_historical():
    try:
        df = pd.read_csv("historical_data.csv")
        df["date"] = pd.to_datetime(df["date"])
        return df
    except:
        return pd.DataFrame(columns=["date", "pmi", "industry", "score"])

hist_df = load_historical()

# ====================== UI ======================
col1, col2 = st.columns([4, 1])
with col1:
    st.subheader("Latest ISM Manufacturing PMI® Report")
with col2:
    if st.button("🔄 Force Refresh", type="primary"):
        st.cache_data.clear()
        st.rerun()

pmi, month_year, growth, contraction, url = get_latest_report()

if pmi is not None:
    st.subheader(f"**{month_year}** — Manufacturing PMI® = **{pmi}%**")
    st.caption(f"[View full official release]({url})")

    # Compute scores exactly as you wanted
    scores = {ind: 0 for ind in INDUSTRIES}
    n_growth = len(growth)
    n_contr = len(contraction)
    
    for i, ind in enumerate(growth):
        if ind in scores:
            scores[ind] = n_growth - i
    for i, ind in enumerate(contraction):
        if ind in scores:
            scores[ind] = -(n_contr - i)

    current_df = pd.DataFrame({
        "Industry": list(scores.keys()),
        "Score": list(scores.values())
    }).sort_values("Score", ascending=False)

    # Beautiful heatmap styling
    def style_score(val):
        if val > 0:
            intensity = min(1, val / max(1, n_growth))
            return f"background-color: rgba(0, 200, 80, {intensity}); color: black; font-weight: bold"
        elif val < 0:
            intensity = min(1, abs(val) / max(1, n_contr))
            return f"background-color: rgba(255, 60, 60, {intensity}); color: white; font-weight: bold"
        return "background-color: #f0f2f6;"

    styled = current_df.style.map(style_score, subset=["Score"])\
                         .format({"Score": "{:+d}"})\
                         .set_properties(**{"text-align": "left"})

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ====================== HISTORICAL SECTION ======================
    st.divider()
    st.subheader("📈 Historical Score Trends & Color Changes")

    current_date = pd.to_datetime(month_year + " 1", format="%B %Y %d", errors="coerce")  # approximate day
    current_rows = [{"date": current_date, "pmi": pmi, "industry": ind, "score": sc} 
                   for ind, sc in scores.items()]
    current_hist = pd.DataFrame(current_rows)

    display_df = pd.concat([hist_df, current_hist]).drop_duplicates(subset=["date", "industry"])
    display_df = display_df.sort_values(["date", "score"], ascending=[False, False])

    # Heatmap of all months
    pivot = display_df.pivot(index="industry", columns="date", values="score").fillna(0)
    pivot = pivot.reindex(INDUSTRIES)

    fig_heat = px.imshow(
        pivot, labels=dict(x="Month", y="Industry", color="Score"),
        color_continuous_scale=["red", "white", "lime"],
        aspect="auto", text_auto=True
    )
    fig_heat.update_traces(texttemplate="%{z:+.0f}", textfont_size=10)
    st.plotly_chart(fig_heat, use_container_width=True)

    # Line chart for selected industries
    st.subheader("Score Evolution by Industry (track color changes over time)")
    selected_ind = st.multiselect("Select industries to track", INDUSTRIES,
                                default=["Chemical Products", "Transportation Equipment", 
                                        "Computer & Electronic Products", "Primary Metals"])
    if selected_ind:
        line_df = display_df[display_df["industry"].isin(selected_ind)]
        fig_line = px.line(line_df, x="date", y="score", color="industry", markers=True,
                          title="How industry rankings have shifted month-to-month")
        st.plotly_chart(fig_line, use_container_width=True)

    st.caption("✅ Green = growing (brighter = higher rank) | Red = contracting | White = unchanged\n"
               "Add new rows to historical_data.csv after each new report for perfect history.")

else:
    st.error("❌ Could not fetch the latest report from any source.")
    st.info("The scraper tried PR Newswire + ISM official site. This is very rare. Try the Force Refresh button in a few minutes.")

st.divider()
st.caption("Built with multiple fallbacks for maximum durability • Historical tracking included")
