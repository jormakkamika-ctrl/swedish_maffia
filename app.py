import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime
import os
import git
import shutil

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

# ====================== NAME NORMALIZATION (FIXES SKIPPING) ======================
def normalize_name(name: str) -> str:
    """Normalise for reliable matching"""
    name = name.lower().strip()
    name = name.replace("&", "and")          # & → and
    name = re.sub(r'[^a-z0-9\s]', '', name)  # remove all punctuation
    name = re.sub(r'\s+', ' ', name)         # collapse spaces
    return name

# Lookup dict: normalized → original official name
NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}


# ====================== PERSISTENT GIT HISTORY (ROBUST) ======================
def push_to_github():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["GITHUB_REPO"]
        
        # Clone only if needed
        if not os.path.exists(".git"):
            clone_url = f"https://{token}@github.com/{repo_name}.git"
            git.Repo.clone_from(clone_url, ".", depth=1)
        
        repo = git.Repo(".")
        
        # Stage the CSV
        repo.index.add([HISTORICAL_FILE])
        
        if repo.is_dirty(untracked_files=True):
            commit_message = f"Update ISM history - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            repo.index.commit(commit_message)
            origin = repo.remote()
            origin.push()
            st.toast("✅ History saved to GitHub!", icon="✅")
            return True
        return False
    except Exception as e:
        st.toast(f"⚠️ GitHub save skipped (non-critical): {str(e)[:100]}", icon="⚠️")
        return False
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
    push_to_github()

# ====================== ROBUST SCRAPER ======================
def fetch_report_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ")

        # PMI + Month
        pmi_match = re.search(r"Manufacturing PMI® .*?at (\d+\.\d+)%", text)
        pmi = float(pmi_match.group(1)) if pmi_match else 0.0

        month_match = re.search(r"(\w+ \d{4}) ISM® Manufacturing", text)
        month_year = month_match.group(1) if month_match else "Unknown"

        # === GROWTH LIST (robust split) ===
        growth_block = re.search(r"listed in order — are:(.*?)\. The", text, re.DOTALL | re.IGNORECASE)
        growth_list = []
        if growth_block:
            raw = growth_block.group(1).replace(" and ", "; ")
            items = [x.strip() for x in raw.split(";") if x.strip()]
            growth_list = [x for x in items if len(x) > 3]

        # === CONTRACTION LIST ===
        contr_block = re.search(r"contraction in \w+ are:(.*?)\.", text, re.DOTALL | re.IGNORECASE)
        contraction_list = []
        if contr_block:
            raw = contr_block.group(1).replace(" and ", "; ")
            items = [x.strip() for x in raw.split(";") if x.strip()]
            contraction_list = [x for x in items if len(x) > 3]

        return pmi, month_year, growth_list, contraction_list, url

    except Exception:
        return None, None, [], [], None

@st.cache_data(ttl=43200)
def get_latest_data():
    # You can keep your fallback URL or change to the real latest one
    url = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-52-7-march-2026-ism-manufacturing-pmi-report-302730721.html"
    return fetch_report_content(url)

# ====================== MAIN UI ======================
st.title("🏭 ISM Manufacturing Industry Heatmap")

hist_df = load_history()
pmi, month_year, growth, contraction, report_url = get_latest_data()

if pmi:
    # ====================== EXACT SCORING (NO MORE SKIPPING) ======================
    scores = {ind: 0 for ind in INDUSTRIES}
    n_growth = len(growth)
    n_contr = len(contraction)

    # Growth: +13 → +1
    for i, scraped in enumerate(growth):
        norm = normalize_name(scraped)
        if norm in NORM_TO_OFFICIAL:
            official = NORM_TO_OFFICIAL[norm]
            scores[official] = n_growth - i

    # Contraction: -3 → -1
    for i, scraped in enumerate(contraction):
        norm = normalize_name(scraped)
        if norm in NORM_TO_OFFICIAL:
            official = NORM_TO_OFFICIAL[norm]
            scores[official] = -(n_contr - i)

    current_df = pd.DataFrame({"industry": list(scores.keys()), "score": list(scores.values())})

    # Auto-save to history
    save_to_history(current_df, month_year)

    # ====================== DISPLAY ======================
        # ====================== DISPLAY ======================
    st.subheader(f"Ranked Sector Performance: {month_year} (PMI® {pmi}%)")

    # === NEW: Perfect diverging colors matching your historical heatmap ===
    max_abs = max(abs(current_df["score"].max()), abs(current_df["score"].min()), 1)
    
    styled_df = (
        current_df
        .sort_values("score", ascending=False)
        .style.background_gradient(
            cmap="RdYlGn",          # ← same as your historical chart
            subset=["score"],
            vmin=-max_abs,          # force symmetric scale around zero
            vmax=max_abs
        )
        .format({"score": "{:+d}"})
        .set_properties(**{
            "text-align": "left",
            "font-weight": "bold"
        })
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Debug (remove when happy)
    with st.expander("🔍 Debug: Parsed lists & scores"):
        st.write("**Growth list**:", growth)
        st.write("**Contraction list**:", contraction)

        # ====================== HISTORICAL ======================
    st.divider()
    st.subheader("📈 6-Month Sector Momentum (Fixed Sector Order)")

    full_hist = load_history()
    if not full_hist.empty:
        # Create pivot
        pivot = full_hist.pivot(index="industry", columns="date", values="score").fillna(0)
        
        # === KEY FIX: Keep sectors in FIXED order (never moves) ===
        pivot = pivot.reindex(INDUSTRIES)          # ← this locks the row order
        
        # Optional: rename columns to short month names (cleaner)
        pivot.columns = pivot.columns.strftime('%b %Y')
        
        fig = px.imshow(
            pivot,
            labels=dict(x="Month", y="Industry", color="Score"),
            color_continuous_scale="RdYlGn",      # same beautiful green-yellow-red
            color_continuous_midpoint=0,
            text_auto=True,                       # shows the actual score number
            aspect="auto"
        )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No history yet — refresh after the next ISM report drops.")

else:
    st.error("Failed to load report.")

with st.sidebar:
    st.write(f"**Report Link:** [Source]({report_url})")
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
