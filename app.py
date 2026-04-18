import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import os

st.set_page_config(page_title="ISM PMI Heatmap", layout="wide")

# ====================== CONFIG ======================
INDUSTRIES = [
    "Food, Beverage & Tobacco Products", "Textile Mills", "Apparel, Leather & Allied Products",
    "Wood Products", "Paper Products", "Printing & Related Support Activities",
    "Petroleum & Coal Products", "Chemical Products", "Plastics & Rubber Products",
    "Nonmetallic Mineral Products", "Primary Metals", "Fabricated Metal Products",
    "Machinery", "Computer & Electronic Products", "Electrical Equipment, Appliances & Components",
    "Transportation Equipment", "Furniture & Related Products", "Miscellaneous Manufacturing"
]

HEADERS = {"User-Agent": "Mozilla/5.0"}
HISTORICAL_FILE = "ism_history.csv"

# ====================== PERSISTENCE ======================
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

# ====================== ROBUST SCRAPER ======================
def fetch_report_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        # Using separator=" " prevents words from sticking together when HTML tags are removed
        text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")

        pmi_match = re.search(r"at (\d+\.\d+)%", text)
        pmi = float(pmi_match.group(1)) if pmi_match else 0.0

        month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}", text)
        month_year = month_match.group(0) if month_match else "Unknown Month"

        def get_clean_list(pattern, source):
            match = re.search(pattern, source, re.DOTALL | re.IGNORECASE)
            if not match: return []
            raw = match.group(1)
            # 1. Standardize separators
            raw = raw.replace(" and ", "; ").replace(", ", "; ")
            # 2. Split and clean each item aggressively
            items = []
            for i in raw.split(";"):
                clean = i.strip().strip(".")
                # Remove leading 'and ' if it survived the replace
                clean = re.sub(r'^and\s+', '', clean, flags=re.IGNORECASE)
                if len(clean) > 3:
                    items.append(clean)
            return items

        # Regex uses \u2014 to handle the long em-dash often used in PR Newswire
        growth_p = r"listed in order\s*[\u2014-]\s*are:(.*?)\.\s*The"
        contr_p = r"reporting contraction in \w+ are:(.*?)\."

        return pmi, month_year, get_clean_list(growth_p, text), get_clean_list(contr_p, text), url
    except:
        return None, None, [], [], None

@st.cache_data(ttl=43200)
def get_report():
    # March 2026 Fallback URL
    url = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(url)

# ====================== MAIN APP ======================
st.title("🏭 ISM Manufacturing Industry Heatmap")

pmi, month_year, growth, contraction, url = get_report()

if pmi:
    st.subheader(f"PMI: {pmi}% | {month_year}")
    
    # --- GAP-PROOF SCORING LOGIC ---
    scores = {ind: 0 for ind in INDUSTRIES}
    matched_set = set()

    # 1. Score Growth
    n_g = len(growth)
    for i, scraped_name in enumerate(growth):
        score_val = n_g - i
        s_clean = scraped_name.lower()
        for official in INDUSTRIES:
            if (official.lower() in s_clean or s_clean in official.lower()) and official not in matched_set:
                scores[official] = score_val
                matched_set.add(official)
                break

    # 2. Score Contraction
    n_c = len(contraction)
    for i, scraped_name in enumerate(contraction):
        score_val = -(n_c - i)
        s_clean = scraped_name.lower()
        for official in INDUSTRIES:
            if (official.lower() in s_clean or s_clean in official.lower()) and official not in matched_set:
                scores[official] = score_val
                matched_set.add(official)
                break

    current_df = pd.DataFrame({"industry": list(scores.keys()), "score": list(scores.values())})
    save_to_history(current_df, month_year)

    # --- DISPLAY ---
    def style_fn(val):
        if val > 0:
            alpha = 0.3 + (val / max(n_g, 1)) * 0.7
            return f'background-color: rgba(0, 200, 80, {alpha:.2f}); color: black; font-weight: bold'
        if val < 0:
            alpha = 0.3 + (abs(val) / max(n_c, 1)) * 0.7
            return f'background-color: rgba(255, 70, 70, {alpha:.2f}); color: white; font-weight: bold'
        return 'color: #555;'

    st.dataframe(
        current_df.sort_values("score", ascending=False).style.map(style_fn, subset=['score']),
        use_container_width=True, hide_index=True
    )

    # --- HISTORICAL HEATMAP ---
    st.divider()
    st.subheader("📈 Historical Trends")
    hist_df = load_history()
    if not hist_df.empty:
        pivot = hist_df.pivot(index="industry", columns="date", values="score").fillna(0)
        # Sort by latest month performance
        pivot = pivot.sort_values(by=pivot.columns[-1], ascending=False)
        fig = px.imshow(
            pivot,
            x=pivot.columns.strftime('%b %Y'),
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            text_auto=True, aspect="auto"
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔍 Debug Scraper Lists"):
        st.write(f"Growth ({len(growth)}): {growth}")
        st.write(f"Contraction ({len(contraction)}): {contraction}")
else:
    st.error("Could not fetch report data.")
