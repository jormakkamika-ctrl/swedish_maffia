import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="ISM PMI Heatmap", layout="wide")
st.title("🟢 ISM Manufacturing PMI® Industry Heatmap + History")
st.caption("Ultra-robust scraper • Exact ranked scoring (+13 to -3) • Green → Yellow → Red heatmap")

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ====================== SCRAPER (NOW EXTREMELY ROBUST) ======================
@st.cache_data(ttl=43200)
def get_latest_report():
    # 1. PR Newswire (primary - most reliable)
    try:
        r = requests.get("https://www.prnewswire.com/news/institute-for-supply-management/", 
                        headers=HEADERS, timeout=15)
        if r.ok:
            match = re.search(
                r'(https?://www\.prnewswire\.com/news-releases/manufacturing-pmi-at-\d+\.\d+.*?-ism-manufacturing-pmi-report-\d+\.html)',
                r.text
            )
            if match:
                return fetch_report_content(match.group(1))
    except:
        pass

    # 2. ISM official fallback
    try:
        r = requests.get("https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/",
                        headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("a", string=re.compile("Past Month Manufacturing Report", re.I))
        if link and link.get("href"):
            url = "https://www.ismworld.org" + link["href"] if not link["href"].startswith("http") else link["href"]
            return fetch_report_content(url)
    except:
        pass

    # 3. Emergency fallback - REAL March 2026 URL
    st.warning("⚠️ Using emergency fallback (real March 2026 report)")
    real_fallback = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(real_fallback)

def fetch_report_content(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")

    # PMI
    pmi_match = re.search(r"Manufacturing PMI® .*?at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else None

    # Month/Year
    month_match = re.search(r"(\w+ \d{4}) ISM® Manufacturing", text)
    month_year = month_match.group(1) if month_match else "Latest Month"

    # GROWTH LIST - tightened regex for exact phrasing
    growth_match = re.search(
        r"The (\d+) manufacturing industries reporting growth in \w+.*?listed in order.*?are: (.*?)\.(?=\s*The \d+ industries reporting contraction|\s*$)",
        text, re.DOTALL | re.IGNORECASE
    )
    growth_list = []
    if growth_match:
        raw = growth_match.group(2).replace(" and ", "; ")
        growth_list = [x.strip() for x in raw.split(";") if x.strip()]

    # CONTRACTION LIST
    contr_match = re.search(
        r"The (\d+) industries reporting contraction in \w+ are: (.*?)\.",
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

# ====================== MAIN APP ======================
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

    # === EXACT SCORING YOU ASKED FOR ===
    scores = {ind: 0 for ind in INDUSTRIES}
    n_growth = len(growth)
    n_contr = len(contraction)
    
    for i, ind in enumerate(growth):
        if ind in scores:
            scores[ind] = n_growth - i          # +13 (first) down to +1
    
    for i, ind in enumerate(contraction):
        if ind in scores:
            scores[ind] = -(n_contr - i)        # -3 (first contracting) down to -1

    current_df = pd.DataFrame({
        "Industry": list(scores.keys()),
        "Score": list(scores.values())
    }).sort_values("Score", ascending=False)

    # === PERFECT DIVERGING HEATMAP COLORS ===
    def style_score(val):
        if val > 0:
            intensity = val / max(13, n_growth)
            return f"background-color: rgba(0, 200, 80, {0.4 + 0.6*intensity}); color: black; font-weight: bold"
        elif val < 0:
            intensity = abs(val) / max(3, n_contr)
            return f"background-color: rgba(255, 70, 70, {0.4 + 0.6*intensity}); color: white; font-weight: bold"
        else:
            return "background-color: #fffacd; color: black;"  # bright yellow for unchanged

    styled = current_df.style.map(style_score, subset=["Score"])\
                         .format({"Score": "{:+d}"})\
                         .set_properties(**{"text-align": "left"})

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Debug panel (remove later if you want)
    with st.expander("🔍 Debug: Parsed growth / contraction lists"):
        st.write("**Growth (should be 13)**:", growth)
        st.write("**Contracting (should be 3)**:", contraction)

    # ====================== HISTORICAL ======================
    st.divider()
    st.subheader("📈 Historical Score Trends & Color Changes")

    current_date = pd.to_datetime(month_year + " 1", format="%B %Y %d", errors="coerce")
    current_rows = [{"date": current_date, "pmi": pmi, "industry": ind, "score": sc} 
                    for ind, sc in scores.items()]
    current_hist = pd.DataFrame(current_rows)

    display_df = pd.concat([hist_df, current_hist]).drop_duplicates(subset=["date", "industry"])
    display_df = display_df.sort_values(["date", "score"], ascending=[False, False])

    # Full history heatmap
    pivot = display_df.pivot(index="industry", columns="date", values="score").fillna(0)
    pivot = pivot.reindex(INDUSTRIES)
    fig_heat = px.imshow(
        pivot, labels=dict(x="Month", y="Industry", color="Score"),
        color_continuous_scale=["red", "yellow", "lime"],
        aspect="auto", text_auto=True
    )
    fig_heat.update_traces(texttemplate="%{z:+.0f}", textfont_size=10)
    st.plotly_chart(fig_heat, use_container_width=True)

    # Line chart
    st.subheader("Score Evolution by Industry")
    selected = st.multiselect("Select industries to track", INDUSTRIES, 
                             default=["Chemical Products", "Transportation Equipment", 
                                      "Computer & Electronic Products", "Primary Metals"])
    if selected:
        line_df = display_df[display_df["industry"].isin(selected)]
        fig_line = px.line(line_df, x="date", y="score", color="industry", markers=True,
                           title="How rankings change month-to-month")
        st.plotly_chart(fig_line, use_container_width=True)

    st.caption("✅ Bright green = strongest growth | Yellow = unchanged | Red = contracting")

else:
    st.error("Could not fetch report – try Force Refresh in a minute.")

st.divider()
st.caption("Fixed & polished for you • Exact scoring + proper colors • Historical tracking")
