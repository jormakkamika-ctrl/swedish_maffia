import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="ISM PMI Heatmap", layout="wide")
st.title("🟢 ISM Manufacturing PMI® Industry Heatmap + History")
st.caption("Latest data from PR Newswire • 18 official industries • Ranked scores + historical trends")

# ====================== CONFIG ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

# ====================== SCRAPER ======================
@st.cache_data(ttl=86400)  # 24h cache
def get_latest_report():
    # 1. Find latest Manufacturing PMI release on PR Newswire
    url = "https://www.prnewswire.com/news/institute-for-supply-management/"
    r = requests.get(url, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Find first link with "Manufacturing PMI® at"
    link = soup.find("a", href=True, string=re.compile(r"Manufacturing PMI® at", re.I))
    if not link:
        st.error("Could not find latest report. Try again later.")
        return None, None, None, None
    
    full_url = "https://www.prnewswire.com" + link["href"] if not link["href"].startswith("http") else link["href"]
    
    # 2. Fetch full release
    r = requests.get(full_url, timeout=15)
    text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")
    
    # Extract PMI
    pmi_match = re.search(r"Manufacturing PMI® at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else None
    
    # Extract month/year
    month_match = re.search(r"(\w+ \d{4}) ISM® Manufacturing", text)
    month_year = month_match.group(1) if month_match else "Unknown"
    
    # Growth list
    growth_match = re.search(r"The (\d+) manufacturing industries reporting growth in \w+ — listed in order — are: (.*?)\.(?=\s+The|\s*$)", text, re.DOTALL)
    growth_list = []
    if growth_match:
        raw = growth_match.group(2).replace(" and ", "; ")
        growth_list = [x.strip() for x in raw.split(";") if x.strip()]
    
    # Contraction list
    contr_match = re.search(r"The (\d+) industries reporting contraction .*? are: (.*?)\.", text, re.DOTALL)
    contr_list = []
    if contr_match:
        raw = contr_match.group(2).replace(" and ", "; ")
        contr_list = [x.strip() for x in raw.split(";") if x.strip()]
    
    return pmi, month_year, growth_list, contr_list, full_url

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
pmi, month_year, growth, contraction, url = get_latest_report()

if pmi:
    st.subheader(f"Latest: **{month_year}** — Manufacturing PMI® = **{pmi}%**")
    st.caption(f"[View full PR Newswire release]({url})")

    # Compute current scores
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
    
    # Color function
    def style_score(val):
        if val > 0:
            intensity = min(1, val / max(1, n_growth))
            return f"background-color: rgba(0, 200, 80, {intensity}); color: black; font-weight: bold"
        elif val < 0:
            intensity = min(1, abs(val) / max(1, n_contr))
            return f"background-color: rgba(255, 60, 60, {intensity}); color: white; font-weight: bold"
        return ""
    
    styled = current_df.style.map(style_score, subset=["Score"])\
                         .format({"Score": "{:+d}"})\
                         .set_properties(**{"text-align": "left"})
    
    st.subheader("Current Month Industry Ranking (Heatmap)")
    st.dataframe(styled, use_container_width=True, hide_index=True)
    
    # ====================== HISTORICAL ======================
    st.divider()
    st.subheader("Historical Score Trends (Color Changes Over Time)")
    
    # Add current month to historical for display
    current_date = pd.to_datetime(month_year)
    current_rows = []
    for ind, sc in scores.items():
        current_rows.append({"date": current_date, "pmi": pmi, "industry": ind, "score": sc})
    current_hist = pd.DataFrame(current_rows)
    
    display_df = pd.concat([hist_df, current_hist]).drop_duplicates(subset=["date", "industry"])
    display_df = display_df.sort_values(["date", "score"], ascending=[False, False])
    
    # Pivot for heatmap
    pivot = display_df.pivot(index="industry", columns="date", values="score").fillna(0)
    pivot = pivot.reindex(INDUSTRIES)  # consistent order
    
    # Plotly heatmap
    fig_heat = px.imshow(
        pivot,
        labels=dict(x="Month", y="Industry", color="Score"),
        color_continuous_scale=["red", "white", "lime"],
        aspect="auto",
        text_auto=True
    )
    fig_heat.update_traces(texttemplate="%{z:+.0f}", textfont_size=10)
    st.plotly_chart(fig_heat, use_container_width=True)
    
    # Line chart per industry (great for tracking color changes)
    st.subheader("Score Evolution by Industry")
    selected_ind = st.multiselect("Select industries to track", INDUSTRIES, default=["Chemical Products", "Transportation Equipment", "Computer & Electronic Products"])
    if selected_ind:
        line_df = display_df[display_df["industry"].isin(selected_ind)]
        fig_line = px.line(line_df, x="date", y="score", color="industry", markers=True,
                          title="How each industry's rank has changed over time")
        st.plotly_chart(fig_line, use_container_width=True)
    
    st.caption("✅ Green = growing (higher rank = brighter) | Red = contracting | White = unchanged\n"
               "Add new months to `historical_data.csv` whenever a fresh report drops!")

else:
    st.error("Could not fetch latest report. Please try refreshing.")

st.divider()
st.caption("Built for you • PR Newswire scraper • Fully automatic latest data • Historical tracking")
