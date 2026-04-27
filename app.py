import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import plotly.express as px
import numpy as np
import yfinance as yf
import json
import plotly.graph_objects as go
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

st.set_page_config(
    page_title="ISM Manufacturing Intelligence Hub",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "ISM Manufacturing Intelligence Hub — Professional Edition"}
)

# ====================== GLOBAL CSS INJECTION ======================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');

:root {
--bg-primary: #0d1117;
--bg-secondary: #161b22;
--bg-card: #1c2128;
--border-color: #30363d;
--accent-blue: #58a6ff;
--accent-green: #3fb950;
--accent-red: #f85149;
--accent-amber: #d29922;
--text-primary: #e6edf3;
--text-muted: #8b949e;
--font-mono: 'IBM Plex Mono', monospace;
--font-sans: 'IBM Plex Sans', sans-serif;
}

html, body, [class*="css"] {
font-family: var(--font-sans) !important;
}

.stApp {
background-color: #0d1117;
}

[data-testid="stSidebar"] {
background-color: #0d1117 !important;
border-right: 1px solid var(--border-color);
}

[data-testid="stSidebar"] .stMarkdown {
color: var(--text-muted);
font-size: 0.82rem;
}

div[data-testid="stMetric"] {
background: linear-gradient(135deg, #1c2128 0%, #161b22 100%);
border: 1px solid var(--border-color);
border-top: 2px solid var(--accent-blue);
border-radius: 8px;
padding: 18px 20px 14px;
transition: border-color 0.2s ease;
}

div[data-testid="stMetric"]:hover {
border-top-color: #79c0ff;
border-color: #444c56;
}

div[data-testid="stMetric"] > label {
color: var(--text-muted) !important;
font-size: 0.72rem !important;
font-weight: 600 !important;
text-transform: uppercase;
letter-spacing: 0.08em;
font-family: var(--font-mono) !important;
}

div[data-testid="stMetricValue"] {
color: var(--text-primary) !important;
font-family: var(--font-mono) !important;
font-size: 1.75rem !important;
font-weight: 600 !important;
}

div[data-testid="stMetricDelta"] {
font-size: 0.72rem !important;
font-family: var(--font-mono) !important;
}

.stTabs [data-baseweb="tab-list"] {
background-color: transparent;
border-bottom: 1px solid var(--border-color);
gap: 0px;
padding: 0;
}

.stTabs [data-baseweb="tab"] {
background-color: transparent;
border: none;
border-bottom: 2px solid transparent;
color: var(--text-muted);
font-family: var(--font-sans);
font-weight: 500;
font-size: 0.88rem;
padding: 12px 24px;
margin-right: 4px;
transition: color 0.2s ease, border-color 0.2s ease;
}

.stTabs [aria-selected="true"] {
background-color: transparent !important;
border-bottom: 2px solid var(--accent-blue) !important;
color: var(--accent-blue) !important;
font-weight: 600 !important;
}

.stTabs [data-baseweb="tab"]:hover {
color: var(--text-primary) !important;
background-color: rgba(88, 166, 255, 0.05) !important;
}

div[data-testid="stDataFrame"] {
border: 1px solid var(--border-color);
border-radius: 6px;
overflow: hidden;
}

.stButton > button[kind="primary"] {
background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
border: none;
color: white;
font-family: var(--font-sans);
font-weight: 600;
font-size: 0.85rem;
letter-spacing: 0.02em;
padding: 10px 24px;
border-radius: 6px;
transition: all 0.2s ease;
box-shadow: 0 2px 8px rgba(31, 111, 235, 0.3);
}

.stButton > button[kind="primary"]:hover {
transform: translateY(-1px);
box-shadow: 0 4px 16px rgba(31, 111, 235, 0.5);
}

.stButton > button:not([kind="primary"]) {
background-color: #21262d;
border: 1px solid var(--border-color);
color: var(--text-primary);
font-family: var(--font-sans);
font-weight: 500;
border-radius: 6px;
}

details[data-testid="stExpander"] {
background-color: var(--bg-card);
border: 1px solid var(--border-color);
border-radius: 6px;
padding: 4px;
}

details summary {
color: var(--text-primary) !important;
font-weight: 500;
font-size: 0.88rem;
}

hr {
border-color: var(--border-color) !important;
margin: 20px 0 !important;
}

div[data-testid="stAlert"] {
border-radius: 6px;
font-size: 0.83rem;
font-family: var(--font-mono);
}

.section-header {
font-family: 'IBM Plex Sans', sans-serif;
font-weight: 700;
font-size: 1.05rem;
color: #e6edf3;
padding: 10px 0 8px 14px;
border-left: 3px solid #58a6ff;
margin: 18px 0 12px;
letter-spacing: 0.01em;
}

.section-caption {
font-family: 'IBM Plex Mono', monospace;
font-size: 0.73rem;
color: #8b949e;
margin-top: -8px;
padding-left: 16px;
margin-bottom: 10px;
}

.pmi-banner {
border-radius: 8px;
padding: 14px 22px;
margin-bottom: 18px;
display: flex;
align-items: center;
gap: 18px;
font-family: 'IBM Plex Mono', monospace;
}

.pmi-expansion {
background: linear-gradient(135deg, rgba(63, 185, 80, 0.12), rgba(63, 185, 80, 0.04));
border: 1px solid rgba(63, 185, 80, 0.35);
border-left: 4px solid #3fb950;
}

.pmi-contraction {
background: linear-gradient(135deg, rgba(248, 81, 73, 0.12), rgba(248, 81, 73, 0.04));
border: 1px solid rgba(248, 81, 73, 0.35);
border-left: 4px solid #f85149;
}

div[data-testid="stSelectbox"] > div {
background-color: var(--bg-card) !important;
border-color: var(--border-color) !important;
border-radius: 6px;
}

div[data-testid="stMultiSelect"] > div {
background-color: var(--bg-card) !important;
border-color: var(--border-color) !important;
}

div[data-testid="stDownloadButton"] > button {
background-color: #21262d;
border: 1px solid var(--border-color);
color: #58a6ff;
font-weight: 600;
border-radius: 6px;
font-family: var(--font-sans);
font-size: 0.85rem;
}

div[data-testid="stCaptionContainer"] {
font-family: var(--font-mono) !important;
font-size: 0.73rem !important;
color: var(--text-muted) !important;
}
</style>
""", unsafe_allow_html=True)

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

PRIMARY_ISM_MAPPING: Dict[str, List[str]] = {
    "Food, Beverage & Tobacco Products": [
        "Packaged Foods", "Beverages - Non-Alcoholic", "Beverages - Brewers",
        "Tobacco", "Confectioners", "Farm Products"
    ],
    "Textile Mills": ["Textile Manufacturing"],
    "Apparel, Leather & Allied Products": ["Apparel Manufacturing", "Footwear & Accessories", "Apparel Retail"],
    "Wood Products": [
        "Lumber & Wood Production", "Building Materials", "Building Products & Equipment",
        "Home Improvement Retail"                                      # ← added
    ],
    "Paper Products": ["Paper & Forest Products", "Packaging & Containers"],
    "Printing & Related Support Activities": ["Packaging & Containers"],
    "Petroleum & Coal Products": ["Oil & Gas Refining & Marketing", "Oil & Gas Midstream", "Thermal Coal"],
    "Chemical Products": ["Chemicals", "Specialty Chemicals", "Agricultural Inputs"],
    "Plastics & Rubber Products": ["Rubber & Plastics", "Packaging & Containers"],
    "Nonmetallic Mineral Products": ["Building Materials", "Construction Materials"],
    "Primary Metals": [
        "Steel", "Aluminum", "Copper", "Other Industrial Metals & Mining",
        "Gold", "Other Precious Metals & Mining"
    ],
    "Fabricated Metal Products": ["Metal Fabrication", "Tools & Accessories"],
    "Machinery": [
        "Specialty Industrial Machinery", 
        "Farm & Heavy Construction Machinery", 
        "Pollution & Treatment Controls"
    ],
    "Computer & Electronic Products": [
        "Semiconductors", 
        "Electronic Components", 
        "Computer Hardware", 
        "Communication Equipment",
        "Semiconductor Equipment & Materials"
    ],
    "Electrical Equipment, Appliances & Components": ["Electrical Equipment & Parts"],
    "Transportation Equipment": ["Aerospace & Defense", "Auto Manufacturers", "Auto Parts", "Railroads"],
    "Furniture & Related Products": ["Home Furnishings & Fixtures", "Furnishings, Fixtures & Appliances"],
    "Miscellaneous Manufacturing": [
        "Medical Instruments & Supplies", 
        "Medical Devices", 
        "Leisure", 
        "Recreational Vehicles"
    ]
}

# ====================== PROFESSIONAL ETF MAPPINGS (Investment-Grade) ======================

# Tab 1: ISM Industry relevance (1-to-many weighted bridge)
GICS_TO_ISM_BRIDGE_V2: Dict[str, List[str]] = {
    "Technology":           ["Computer & Electronic Products"],
    "Industrials":          ["Machinery", "Fabricated Metal Products", "Transportation Equipment"],
    "Basic Materials":      ["Primary Metals", "Chemical Products", "Plastics & Rubber Products"],
    "Consumer Cyclical":    ["Apparel, Leather & Allied Products", "Furniture & Related Products"],
    "Consumer Defensive":   ["Food, Beverage & Tobacco Products"],
    "Energy":               ["Petroleum & Coal Products"],
    "Financial Services":   [],  # not directly ISM-mapped
    "Communication Services": [],
    "Real Estate":          [],
    "Healthcare":           [],
    "Utilities":            [],
}

# Tab 2: Economic Driver sensitivity matrix (sector → drivers)
SECTOR_DRIVER_MAPPING: Dict[str, Dict[str, float]] = {
    "Technology":           {"DEMAND_MOMENTUM": 0.85, "CAPEX_PRESSURE": 0.75},
    "Industrials":          {"CAPEX_PRESSURE": 0.90, "DEMAND_MOMENTUM": 0.75, "LABOR_TIGHTNESS": 0.65},
    "Basic Materials":      {"INPUT_COST_INFLATION": 0.90, "INVENTORY_RESTOCKING": 0.80},
    "Consumer Cyclical":    {"DEMAND_MOMENTUM": 0.88, "LABOR_TIGHTNESS": 0.70},
    "Consumer Defensive":   {"INPUT_COST_INFLATION": 0.55},
    "Energy":               {"INPUT_COST_INFLATION": 0.85, "CAPEX_PRESSURE": 0.60},
    "Financial Services":   {"SECTOR_SPECIFIC_STRENGTH": 0.90},
    "Communication Services": {"DEMAND_MOMENTUM": 0.65},
    "Real Estate":          {"CAPEX_PRESSURE": 0.55, "DEMAND_MOMENTUM": 0.50},
    "Healthcare":           {"DEMAND_MOMENTUM": 0.60},
    "Utilities":            {"INPUT_COST_INFLATION": 0.70},
}

# High-conviction thematic overrides (run BEFORE sector weighting)
THEME_OVERRIDES = {
    "Semiconductor": {"DEMAND_MOMENTUM": 0.92, "CAPEX_PRESSURE": 0.95},
    "AI":            {"DEMAND_MOMENTUM": 0.93, "CAPEX_PRESSURE": 0.88},
    "Clean Energy":  {"CAPEX_PRESSURE": 0.85, "DEMAND_MOMENTUM": 0.78},
    # Add more as you discover strong thematic ETFs
}

def get_etf_relevance_to_ism(ticker_row: pd.Series, target_ism: str, min_exposure: float = 0.20) -> float:
    """Weighted relevance of ETF to a specific ISM industry using actual sector weights."""
    try:
        weights = json.loads(ticker_row["Sector_Weights"])
        if not weights:
            return 0.0
    except:
        return 0.0

    total_relevance = 0.0
    for sector_name, weight_pct in weights.items():
        sector_key = sector_name.strip().title()
        if sector_key in GICS_TO_ISM_BRIDGE_V2:
            ism_list = GICS_TO_ISM_BRIDGE_V2[sector_key]
            if target_ism in ism_list:
                total_relevance += (weight_pct / 100.0)

    return total_relevance if total_relevance >= min_exposure else 0.0

# ====================== ECONOMIC DRIVER CLASSES ======================
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
        description="Capacity constraints -> future capital spending"
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

    drivers[DriverName.INVENTORY_RESTOCKING] = EconomicDriver(
        name=DriverName.INVENTORY_RESTOCKING, strength=0.0,
        signals_used=["Inventories (future)"], description="Inventory drawdown -> restocking"
    )
    drivers[DriverName.SECTOR_SPECIFIC_STRENGTH] = EconomicDriver(
        name=DriverName.SECTOR_SPECIFIC_STRENGTH, strength=0.0,
        signals_used=["ISM Industry List"], description="Direct end-market momentum"
    )
    return drivers

def apply_theme_override(ticker_row: pd.Series) -> Dict[str, float] | None:
    """High-precision thematic override — whole-word match only."""
    name = str(ticker_row.get("Security Name", "")) + " " + str(ticker_row.get("Company", ""))
    name_lower = name.lower()
    for theme, overrides in THEME_OVERRIDES.items():
        if theme.lower() in name_lower.split():   # avoids partial matches like "DEMAND"
            return overrides
    return None


def safe_parse_sector_weights(sector_weights_str) -> dict:
    """Reliable parser for Sector_Weights column loaded from pandas CSV."""
    if pd.isna(sector_weights_str) or not str(sector_weights_str).strip():
        return {}

    s = str(sector_weights_str).strip()

    # Remove outer quotes that pandas adds
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]

    # Fix double-escaped quotes ("" → ")
    s = s.replace('""', '"')

    try:
        weights = json.loads(s)
        return weights if isinstance(weights, dict) and weights else {}
    except json.JSONDecodeError:
        try:
            import ast
            parsed = ast.literal_eval(s)
            return parsed if isinstance(parsed, dict) and parsed else {}
        except:
            return {}


def calculate_etf_macro_score(ticker_row: pd.Series, drivers: Dict[DriverName, EconomicDriver]) -> dict:
    """Clean, final version — uses your existing SECTOR_DRIVER_MAPPING."""
    
    # 1. Thematic override (highest precision)
    theme_override = apply_theme_override(ticker_row)
    if theme_override:
        driver_vector = {d: 0.0 for d in DriverName}
        for driver_name, exposure in theme_override.items():
            if driver_name in driver_vector:
                driver_vector[driver_name] = exposure
        ism_score = sum(driver_vector[d] * drivers[d].strength for d in DriverName)
        return {
            **{d.value: round(driver_vector[d], 3) for d in DriverName},
            "ism_score": round(ism_score, 3),
            "conviction": round(ism_score * 0.9, 3),
            "why": f"Thematic override: {list(theme_override.keys())[0]}"
        }

    # 2. Sector-weighted scoring
    weights_str = str(ticker_row.get("Sector_Weights", "")).strip()
    if not weights_str or weights_str == "{}":
        return {"ism_score": 0.0, "conviction": 0.0, "why": "No sector weights data"}

    try:
        weights = json.loads(weights_str)
        if not isinstance(weights, dict) or not weights:
            return {"ism_score": 0.0, "conviction": 0.0, "why": "No sector weights data"}
    except:
        return {"ism_score": 0.0, "conviction": 0.0, "why": "JSON parse failed"}

    driver_vector = {d: 0.0 for d in DriverName}
    for sector_name, weight_pct in weights.items():
        sector_key = str(sector_name).strip().title()
        sector_exposures = SECTOR_DRIVER_MAPPING.get(sector_key, {})
        weight = float(weight_pct) / 100.0
        for driver_name, exposure_coeff in sector_exposures.items():
            if driver_name in driver_vector:
                driver_vector[driver_name] += weight * exposure_coeff

    ism_score = sum(driver_vector[d] * drivers[d].strength for d in DriverName)
    return {
        **{d.value: round(driver_vector[d], 3) for d in DriverName},
        "ism_score": round(ism_score, 3),
        "conviction": round(ism_score * 0.8, 3),
        "why": "Weighted sector exposure"
    }
# ====================== PROFESSIONAL ECONOMIC EXPOSURE MAP (Updated with Claude's best ideas) ======================
INDUSTRY_EXPOSURE_MAP: Dict[str, Dict[DriverName, float]] = {
    # DEMAND MOMENTUM
    "Auto Manufacturers": {DriverName.DEMAND_MOMENTUM: 0.92},
    "Auto Parts": {DriverName.DEMAND_MOMENTUM: 0.88},
    "Aerospace & Defense": {DriverName.DEMAND_MOMENTUM: 0.80},
    "Residential Construction": {DriverName.DEMAND_MOMENTUM: 0.85, DriverName.LABOR_TIGHTNESS: 0.75},
    "Consumer Electronics": {DriverName.DEMAND_MOMENTUM: 0.75},
    "Internet Retail": {DriverName.DEMAND_MOMENTUM: 0.55},
    "Specialty Retail": {DriverName.DEMAND_MOMENTUM: 0.50},
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

    # INPUT COST INFLATION
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
    "Semiconductors": {DriverName.DEMAND_MOMENTUM: 0.85, DriverName.CAPEX_PRESSURE: 0.90, DriverName.LABOR_TIGHTNESS: 0.70},
    "Computer Hardware": {DriverName.DEMAND_MOMENTUM: 0.70, DriverName.CAPEX_PRESSURE: 0.60},
    "Electronic Components": {DriverName.DEMAND_MOMENTUM: 0.75},

    # LABOR MARKET TIGHTNESS (expanded)
    "Auto Manufacturers": {DriverName.LABOR_TIGHTNESS: 0.70},
    "Auto Parts": {DriverName.LABOR_TIGHTNESS: 0.68},
    "Specialty Industrial Machinery": {DriverName.LABOR_TIGHTNESS: 0.65},
    "Farm & Heavy Construction Machinery": {DriverName.LABOR_TIGHTNESS: 0.60},
    "Aerospace & Defense": {DriverName.LABOR_TIGHTNESS: 0.55},
    "Residential Construction": {DriverName.LABOR_TIGHTNESS: 0.75},   # Claude's good suggestion

    # NEW / REFINED ENTRIES
    "Industrial Gases": {DriverName.INPUT_COST_INFLATION: 0.72, DriverName.CAPEX_PRESSURE: 0.68},
    "Water Utilities": {DriverName.CAPEX_PRESSURE: 0.60},            # mild positive capex
    "Utilities - Regulated": {DriverName.CAPEX_PRESSURE: 0.50, DriverName.DEMAND_MOMENTUM: -0.40},
    "Medical Devices": {DriverName.DEMAND_MOMENTUM: -0.15},          # softened per Claude
    "Pharmaceuticals": {DriverName.DEMAND_MOMENTUM: -0.20},          # softened
}

MANUAL_EXPOSURE_OVERRIDES: Dict[str, Dict[DriverName, float]] = {
    "CAT": {DriverName.CAPEX_PRESSURE: 0.95, DriverName.DEMAND_MOMENTUM: 0.80},
    "DE": {DriverName.CAPEX_PRESSURE: 0.96, DriverName.DEMAND_MOMENTUM: 0.75},
    "NUE": {DriverName.INPUT_COST_INFLATION: 0.92, DriverName.DEMAND_MOMENTUM: 0.78},
    "FCX": {DriverName.INPUT_COST_INFLATION: 0.90, DriverName.DEMAND_MOMENTUM: 0.82},
    "NVDA": {DriverName.DEMAND_MOMENTUM: 0.88, DriverName.CAPEX_PRESSURE: 0.92},
    "TSLA": {DriverName.DEMAND_MOMENTUM: 0.90},
    "AMAT": {DriverName.CAPEX_PRESSURE: 0.94, DriverName.DEMAND_MOMENTUM: 0.80},
    "ETN": {DriverName.CAPEX_PRESSURE: 0.90},
    "PH": {DriverName.CAPEX_PRESSURE: 0.88},
}

# ====================== HELPER FUNCTIONS ======================
def explain_score(row: pd.Series, drivers: Dict[DriverName, EconomicDriver]) -> str:
    reasons = []
    dominant_drivers = []
    
    for driver_name in DriverName:
        exposure = row.get(driver_name.value, 0.0)
        if exposure > 0.25:
            strength = drivers[driver_name].strength
            contribution = exposure * strength
            if abs(contribution) > 0.15:
                reasons.append(f"{strength:+.2f}×{exposure:.1f} {driver_name.value}")
                if contribution > 0.35:
                    dominant_drivers.append(driver_name.value)
    
    rationale = " | ".join(reasons[:4])
    if dominant_drivers:
        rationale = f"**{', '.join(dominant_drivers[:2])}** → " + rationale
    
    return rationale or "Low / neutral exposure"

def get_best_exposure(yahoo_ind: str) -> Dict[DriverName, float]:
    if not yahoo_ind or not isinstance(yahoo_ind, str):
        return {}
    clean_ind = yahoo_ind.strip()
    if clean_ind in INDUSTRY_EXPOSURE_MAP:
        return INDUSTRY_EXPOSURE_MAP[clean_ind].copy()
    for mapped_ind, exposure in INDUSTRY_EXPOSURE_MAP.items():
        if any(word.lower() in clean_ind.lower() for word in mapped_ind.split()):
            return exposure.copy()
        if any(word.lower() in mapped_ind.lower() for word in clean_ind.split()):
            return exposure.copy()
    return {}

def tag_and_score_stocks(stocks_df: pd.DataFrame, drivers: Dict[DriverName, EconomicDriver]) -> pd.DataFrame:
    if stocks_df.empty:
        return stocks_df

    # Build exposure matrix
    exposure_matrix = []
    for _, row in stocks_df.iterrows():
        yahoo_ind = row.get("Yahoo Industry", "")
        ticker = row.get("Ticker", "")
        exposures = get_best_exposure(yahoo_ind)
        if ticker in MANUAL_EXPOSURE_OVERRIDES:
            override = MANUAL_EXPOSURE_OVERRIDES[ticker]
            for d, weight in override.items():
                exposures[d] = max(exposures.get(d, 0.0), weight)
        vector = [exposures.get(d, 0.0) for d in DriverName]
        exposure_matrix.append(vector)

    exposure_df = pd.DataFrame(exposure_matrix, columns=[d.value for d in DriverName], index=stocks_df.index)
    stocks_df = pd.concat([stocks_df, exposure_df], axis=1)

    driver_vector = np.array([drivers[d].strength for d in DriverName])
    raw_score = stocks_df[[d.value for d in DriverName]].dot(driver_vector)

        # === BEST CONVICTION SCORE (professional, stable, real-world) ===
    new_orders_strength = drivers[DriverName.DEMAND_MOMENTUM].strength
    
    # Regime multiplier (still uses New Orders as the primary gauge)
    pmi_regime = 1.0
    if new_orders_strength > 0.4:
        pmi_regime = 1.25
    elif new_orders_strength > 0.2:
        pmi_regime = 1.10

    stocks_df["ism_score"] = (raw_score * pmi_regime).round(3)

    # Composite regime strength across all positive drivers
    positive_drivers = [max(0.0, d.strength) for d in drivers.values()]
    overall_regime_strength = np.mean(positive_drivers) if positive_drivers else 0.0
    
    # Conviction = ism_score boosted by overall regime strength (always readable)
    stocks_df["conviction"] = (stocks_df["ism_score"] * (0.65 + 0.35 * overall_regime_strength)).round(3)

    stocks_df["why"] = stocks_df.apply(lambda r: explain_score(r, drivers), axis=1)

    return stocks_df.sort_values("ism_score", ascending=False)

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

PLOTLY_THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(13,17,23,0)",
    plot_bgcolor="rgba(22,27,34,0.6)",
    font=dict(family="IBM Plex Mono, monospace", color="#8b949e", size=11),
    xaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
    yaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
)

def section_header(title: str, caption: str = ""):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-caption">{caption}</div>', unsafe_allow_html=True)

def show_stock_deep_dive(ticker: str):
    if not ticker:
        return
    with st.spinner(f"Loading {ticker}..."):
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")

        section_header(f"{ticker} — Deep Dive", info.get("longName", ""))

        if not hist.empty:
            macd, signal, histo = calculate_macd(hist)
            from plotly.subplots import make_subplots
            
            # 1. Ensure shared_xaxes is True
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                row_heights=[0.68, 0.32],
                subplot_titles=(f"{ticker} — 1Y Price", "MACD (12, 26, 9)")
            )

            # Price chart
            fig.add_trace(go.Scatter(
                x=hist.index, y=hist['Close'], name="Close",
                line=dict(color="#58a6ff", width=2),
                fill="tozeroy", fillcolor="rgba(88,166,255,0.06)"
            ), row=1, col=1)

            # MACD traces
            fig.add_trace(go.Scatter(x=hist.index, y=macd, name="MACD", line=dict(color="#f0883e", width=1.5)), row=2, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=signal, name="Signal", line=dict(color="#3fb950", width=1.5)), row=2, col=1)
            fig.add_trace(go.Bar(
                x=hist.index, y=histo, name="Histogram",
                marker_color=np.where(histo >= 0, "rgba(63,185,80,0.7)", "rgba(248,81,73,0.7)")
            ), row=2, col=1)

            # 2. UPDATED LAYOUT: Use 'x' hovermode and distance settings
            fig.update_layout(
                height=520,
                hovermode="x",           # Allows multi-subplot synchronization
                hoverdistance=-1,        # Ensures hover triggers across the entire width
                spikedistance=-1,        # Ensures spikes (lines) are always visible
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                **PLOTLY_THEME
            )

            # 3. UPDATED AXES: Switch to spikesnap="data"
            fig.update_xaxes(
                showspikes=True,
                spikecolor="rgba(255, 255, 255, 0.6)",
                spikethickness=1,
                spikedash="solid",
                spikesnap="data",        # CRITICAL: Snap to data to sync across both panels
                spikemode="across",      # Line spans the full height of the subplot
                matches='x',             # Syncs zooming/panning
                row=1, col=1
            )
            
            # Apply same settings to second x-axis
            fig.update_xaxes(
                showspikes=True,
                spikecolor="rgba(255, 255, 255, 0.6)",
                spikethickness=1,
                spikedash="solid",
                spikesnap="data",
                spikemode="across",
                row=2, col=1
            )

            fig.update_yaxes(title_text="Price ($)", row=1, col=1, tickprefix="$")
            fig.update_yaxes(title_text="MACD", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

        # ... (rest of the metrics table code remains the same)

        # === Metrics table (unchanged) ===
        price = info.get("currentPrice") or info.get("regularMarketPrice") or (hist['Close'].iloc[-1] if not hist.empty else None)
        mc = info.get("marketCap") or 0
        eps0 = info.get("trailingEps")
        eps1 = info.get("forwardEps")
        try:
            calendar = t.calendar
            eps2 = calendar['Forward EPS'].iloc[0] if not calendar.empty and 'Forward EPS' in calendar.columns else None
        except:
            eps2 = None

        pe0 = info.get("trailingPE") or (price / eps0 if eps0 and price else None)
        pe1 = info.get("forwardPE") or (price / eps1 if eps1 and price else None)
        eg1 = ((eps1 - eps0) / eps0 * 100) if eps0 and eps1 else None
        eg2 = ((eps2 - eps1) / eps1 * 100) if eps1 and eps2 else None
        peg1 = (pe1 / (eg1 / 100)) if pe1 and eg1 and eg1 != 0 else None
        peg2 = (pe1 / (eg2 / 100)) if pe1 and eg2 and eg2 != 0 else None
        rev_growth = info.get("revenueGrowth")
        rev_growth_pct = f"{rev_growth*100:.1f}%" if rev_growth is not None else "N/A"
        try:
            financials = t.financials
            revenue = financials.loc['Total Revenue'].iloc[0] if not financials.empty and 'Total Revenue' in financials.index else None
            rnd = financials.loc['Research And Development'].iloc[0] if not financials.empty and 'Research And Development' in financials.index else None
            rnd_pct_str = f"{(rnd / revenue * 100):.1f}%" if revenue and rnd else "N/A"
        except:
            rnd_pct_str = "N/A"

        col1, col2 = st.columns(2)
        with col1:
            left = pd.DataFrame({
                "Metric": ["Current Price", "Market Cap", "EPS FY0 (TTM)", "EPS FY1 (Est.)", "EPS FY2 (Est.)", "PE FY0", "PE FY1"],
                "Value": [
                    f"${price:.2f}" if price else "N/A",
                    f"${mc/1e9:.1f}B" if mc else "N/A",
                    f"{eps0:.2f}" if eps0 else "N/A",
                    f"{eps1:.2f}" if eps1 else "N/A",
                    f"{eps2:.2f}" if eps2 else "N/A",
                    f"{pe0:.1f}" if pe0 else "N/A",
                    f"{pe1:.1f}" if pe1 else "N/A"
                ]
            })
            st.dataframe(left, use_container_width=True, hide_index=True)

        with col2:
            right = pd.DataFrame({
                "Metric": ["EG F1 %", "EG F2 %", "PEG FY1", "PEG FY2", "Revenue Growth (YoY)", "R&D % of Revenue"],
                "Value": [
                    f"{eg1:.1f}%" if eg1 is not None else "N/A",
                    f"{eg2:.1f}%" if eg2 is not None else "N/A",
                    f"{peg1:.2f}" if peg1 else "N/A",
                    f"{peg2:.2f}" if peg2 else "N/A",
                    rev_growth_pct,
                    rnd_pct_str
                ]
            })
            st.dataframe(right, use_container_width=True, hide_index=True)

        st.caption(f"ISM Relevance: {ticker} | Industry: {info.get('industry', 'N/A')} | Sector: {info.get('sector', 'N/A')}")


def show_etf_deep_dive(ticker: str):
    """Full ETF deep dive: 1Y chart + MACD + metrics + interactive sector pie"""
    if not ticker:
        return
    with st.spinner(f"Loading {ticker}..."):
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")

        section_header(f"{ticker} — ETF Deep Dive", info.get("longName", ""))

        # === 1. PRICE CHART + MACD (identical style to stocks) ===
        if not hist.empty:
            macd, signal, histo = calculate_macd(hist)
            from plotly.subplots import make_subplots
            
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                row_heights=[0.68, 0.32],
                subplot_titles=(f"{ticker} — 1Y Price", "MACD (12, 26, 9)")
            )

            fig.add_trace(go.Scatter(
                x=hist.index, y=hist['Close'], name="Close",
                line=dict(color="#58a6ff", width=2),
                fill="tozeroy", fillcolor="rgba(88,166,255,0.06)"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=hist.index, y=macd, name="MACD", line=dict(color="#f0883e", width=1.5)), row=2, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=signal, name="Signal", line=dict(color="#3fb950", width=1.5)), row=2, col=1)
            fig.add_trace(go.Bar(
                x=hist.index, y=histo, name="Histogram",
                marker_color=np.where(histo >= 0, "rgba(63,185,80,0.7)", "rgba(248,81,73,0.7)")
            ), row=2, col=1)

            fig.update_layout(
                height=520,
                hovermode="x",
                **PLOTLY_THEME
            )
            fig.update_xaxes(showspikes=True, spikesnap="data", spikemode="across", matches='x', row=1, col=1)
            fig.update_xaxes(showspikes=True, spikesnap="data", spikemode="across", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No price history available for this ETF.")

        # === 2. METRICS TABLE + SECTOR PIE CHART ===
        col1, col2 = st.columns(2)
        aum = info.get("netAssets") or info.get("totalAssets") or info.get("marketCap") or 0

        with col1:
            left = pd.DataFrame({
                "Metric": ["AUM", "Category", "Expense Ratio", "1Y Return"],
                "Value": [
                    f"${aum/1e9:.1f}B" if aum else "N/A",
                    info.get("category", "N/A"),
                    f"{info.get('expenseRatio', 0)*100:.2f}%" if info.get('expenseRatio') else "N/A",
                    f"{((hist['Close'].iloc[-1]/hist['Close'].iloc[0])-1)*100:.1f}%" if not hist.empty and len(hist) > 1 else "N/A"
                ]
            })
            st.dataframe(left, use_container_width=True, hide_index=True)

        with col2:
            # Sector allocation pie chart
            sector_json = ""
            try:
                if hasattr(t, 'funds_data') and t.funds_data is not None:
                    sw = t.funds_data.sector_weightings
                    if sw is not None and not sw.empty:
                        sector_json = json.dumps({k: round(float(v)*100, 2) for k, v in sw.to_dict().items()})
            except:
                pass
            
            # Fallback to stored data in universe.csv
            if not sector_json:
                universe = get_full_universe()
                row = universe[universe["Ticker"] == ticker]
                if not row.empty and "Sector_Weights" in row.columns:
                    sector_json = row["Sector_Weights"].iloc[0]

            if sector_json and pd.notna(sector_json) and sector_json.strip():
                try:
                    weights = json.loads(sector_json)
                    if weights:
                        df_w = pd.DataFrame(list(weights.items()), columns=["Sector", "%"]).sort_values("%", ascending=False)
                        fig_pie = px.pie(df_w, names="Sector", values="%", title="Sector Allocation",
                                         color_discrete_sequence=px.colors.sequential.Blues_r)
                        fig_pie.update_traces(textinfo="percent+label")
                        fig_pie.update_layout(**PLOTLY_THEME, height=380)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("No sector breakdown available.")
                except:
                    st.info("No sector breakdown available.")
            else:
                st.info("No sector breakdown available.")

        st.caption(f"ISM Relevance: {info.get('category', 'N/A')} | Type: ETF")

# ====================== UTILS ======================
def normalize_name(name: str) -> str:
    name = name.lower().strip().replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', '', name)
    return re.sub(r'\s+', ' ', name)

NORM_TO_OFFICIAL = {normalize_name(ind): ind for ind in INDUSTRIES}
# ====================== ROBUST INDUSTRY LIST PARSER ======================
# ====================== ROBUST INDUSTRY LIST PARSER (HYBRID + DEBUG) ======================
def get_industry_lists(text: str) -> tuple[list[str], list[str]]:
    """Hybrid parser: sentence capture + position fallback. Works on scraped + clean text."""
    
    # === PRIMARY: Sentence-based capture (most reliable on clean lists) ===
    growth_match = re.search(
        r'reporting growth[^:]*?are:?\s*([^.]+?)\.',
        text, re.DOTALL | re.IGNORECASE
    )
    contr_match = re.search(
        r'reporting contraction[^:]*?are:?\s*([^.]+?)\.',
        text, re.DOTALL | re.IGNORECASE
    )
    
    growth_section = growth_match.group(1).strip() if growth_match else ""
    contr_section = contr_match.group(1).strip() if contr_match else ""
    
    print(f"DEBUG - Growth section captured: {len(growth_section)} chars")
    print(f"DEBUG - Contraction section captured: {len(contr_section)} chars")
    
    def extract_from_section(section_text: str) -> list[str]:
        if not section_text:
            return []
        found = []
        norm_section = normalize_name(section_text)
        for norm_ind, official in NORM_TO_OFFICIAL.items():
            if norm_ind in norm_section:
                pos = norm_section.find(norm_ind)
                found.append((official, pos))
        found.sort(key=lambda x: x[1])
        return [item[0] for item in found]
    
    growth = extract_from_section(growth_section)
    contraction = extract_from_section(contr_section)
    
    # === FALLBACK: Position-based (used if primary method found almost nothing) ===
    if len(growth) + len(contraction) < 10:  # less than half the industries → something went wrong
        print("WARNING: Primary capture weak → using position-based fallback")
        growth_start = text.lower().find("reporting growth")
        contr_start = text.lower().find("reporting contraction")
        
        found = []
        norm_text = normalize_name(text)
        for norm_ind, official in NORM_TO_OFFICIAL.items():
            pos = norm_text.find(norm_ind)
            if pos != -1:
                if growth_start != -1 and contr_start != -1:
                    if growth_start < pos < contr_start:
                        found.append((official, pos, "growth"))
                    elif pos > contr_start:
                        found.append((official, pos, "contraction"))
                else:
                    found.append((official, pos, "growth"))
        
        growth = [item[0] for item in sorted([x for x in found if x[2] == "growth"], key=lambda x: x[1])]
        contraction = [item[0] for item in sorted([x for x in found if x[2] == "contraction"], key=lambda x: x[1])]
    
    print(f"FINAL DEBUG Growth ({len(growth)}): {growth}")
    print(f"FINAL DEBUG Contraction ({len(contraction)}): {contraction}")
    
    return growth, contraction
    
def get_respondent_comments(text: str) -> list:
    patterns = [
        r"WHAT RESPONDENTS ARE SAYING\s*(.*?)(?=\s*(?:MANUFACTURING AT A GLANCE|The Institute for Supply Management|©|ISM® Reports|Report Issued|$))",
        r"RESPONDENTS ARE SAYING\s*(.*?)(?=\s*(?:MANUFACTURING AT A GLANCE|The Institute for Supply Management))",
        r"COMMENTS FROM RESPONDENTS\s*(.*?)(?=\s*(?:MANUFACTURING AT A GLANCE|$))",
    ]
    section = ""
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            section = match.group(1).strip()
            break
    if not section:
        return []
    bullet_pattern = r'(?:^|\n)[\s\u2022\-\*]+[\u201c\u201d"](.+?)[\u201c\u201d"]\s*(?:\[\s*(.+?)\s*\])?'
    bullets = re.findall(bullet_pattern, section, re.MULTILINE | re.DOTALL)
    comments = []
    for quote, industry in bullets:
        quote = quote.strip()
        if len(quote) > 15:
            comment = f"- {quote}"
            if industry and industry.strip():
                comment += f" [{industry.strip()}]"
            comments.append(comment)
    return comments

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
            sub[key] = {"current": float(match.group(1)), "change": float(match.group(2)), "trend": int(match.group(3))}
        else:
            fb_match = re.search(rf"{re.escape(key)}\s+(\d+\.\d+)\s+[\d.]+\s+([+-]?\d+\.\d+).*?\s+(\d+)\s*(?:$|\s)", clean_text, re.IGNORECASE)
            if fb_match:
                sub[key] = {"current": float(fb_match.group(1)), "change": float(fb_match.group(2)), "trend": int(fb_match.group(3))}
    if sub["Prices"]["current"] is None:
        p_match = re.search(r"Prices\s+(\d+\.\d+)\s+[\d.]+\s+([+-]?\d+\.\d+).*?\s+(\d+)", clean_text, re.IGNORECASE)
        if p_match:
            sub["Prices"] = {"current": float(p_match.group(1)), "change": float(p_match.group(2)), "trend": int(p_match.group(3))}
    return sub

# ====================== DATA LOADERS ======================
@st.cache_data(ttl=3600, show_spinner=False)  # shorter TTL to force refresh
def get_full_universe():
    csv_url = "https://raw.githubusercontent.com/jormakkamika-ctrl/swedish_maffia/main/universe.csv"
    try:
        df = pd.read_csv(csv_url)
        
        # Standardize Market Cap
        if "Size" in df.columns:
            df["Market Cap"] = df["Size"].apply(lambda x: f"${float(x)/1_000_000_000:.1f}B" if pd.notna(x) else "N/A")
        
        # === VERY AGGRESSIVE Sector_Weights cleaning ===
        if "Sector_Weights" in df.columns:
            def clean_weights(w):
                if pd.isna(w) or not str(w).strip():
                    return ""
                s = str(w).strip()
                # Remove outer quotes
                if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                    s = s[1:-1]
                # Fix doubled quotes
                s = s.replace('""', '"')
                # Remove any remaining junk
                s = s.strip()
                return s
            df["Sector_Weights"] = df["Sector_Weights"].apply(clean_weights)
        
        if "Type" not in df.columns:
            df["Type"] = "Stock"
        if "Category" not in df.columns:
            df["Category"] = ""
            
        return df
    except Exception as e:
        st.error(f"Could not load universe: {e}")
        return pd.DataFrame()

def parse_report_text(text: str):
    pmi_match = re.search(r"at (\d+\.\d+)%", text)
    pmi = float(pmi_match.group(1)) if pmi_match else 50.0
    month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}", text)
    month_year = month_match.group(0) if month_match else "Unknown"

    
        # === ROBUST INDUSTRY LIST EXTRACTION (POSITION-BASED) ===
    growth, contr = get_industry_lists(text)
    
    # DEBUG - you will see this in the "Process Log" after Deep Refresh
    print(f"DEBUG - Growth ({len(growth)}): {growth}")
    print(f"DEBUG - Contraction ({len(contr)}): {contr}")
    
    comments = get_respondent_comments(text)
    subcomponents = parse_ism_subcomponents(text)
    return pmi, month_year, growth, contr, comments, subcomponents

@st.cache_data(ttl=86400)
def build_historical_dataset():
    all_data = []
    report_metadata = {}
    archive_url = "https://www.prnewswire.com/news/institute-for-supply-management/"
    session = requests.Session()
    session.headers.update(HEADERS)
    log_messages = []

    for attempt in range(3):
        try:
            r = session.get(archive_url, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            links = [a['href'] for a in soup.find_all('a', href=True)
                     if any(x in a['href'].lower() for x in ["manufacturing-pmi", "ism-manufacturing", "report-on-business"])]
            links = list(dict.fromkeys(links))[:8]
            log_messages.append(f"Found {len(links)} report links.")

            for url in links:
                full_url = "https://www.prnewswire.com" + url if url.startswith('/') else url
                try:
                    resp = session.get(full_url, timeout=25)
                    raw_text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")
                    pmi, m_year, growth, contr, comments, subcomponents = parse_report_text(raw_text)
                    if m_year == "Unknown":
                        continue
                    date_obj = pd.to_datetime(m_year)
                    report_metadata[date_obj] = {"comments": comments, "pmi": pmi, "subcomponents": subcomponents, "url": full_url}
                    log_messages.append(f"Parsed: {m_year} | PMI={pmi}")
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
                        all_data.append({"date": date_obj, "industry": ind, "score": score, "pmi": pmi, "url": full_url})
                except Exception as e:
                    log_messages.append(f"Failed to parse {url}: {str(e)[:60]}")
                    continue
            break
        except Exception as e:
            log_messages.append(f"Attempt {attempt+1} failed: {str(e)[:80]}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    df = pd.DataFrame(all_data)
    if df.empty:
        return pd.DataFrame(columns=["date", "industry", "score", "pmi", "url"]), {}, log_messages
    df = df.drop_duplicates(subset=['date', 'industry'], keep='last').reset_index(drop=True)
    num_unique_dates = df['date'].nunique() if 'date' in df.columns and not df.empty else 0
    log_messages.append(f"Total records: {len(df)} across {num_unique_dates} reports.")
    return df, report_metadata, log_messages

# ====================== APP HEADER ======================
st.markdown("""
<div style="
display: flex;
align-items: center;
justify-content: space-between;
padding: 8px 0 20px;
border-bottom: 1px solid #30363d;
margin-bottom: 24px;
">
<div>
<h1 style="
font-family: 'IBM Plex Sans', sans-serif;
font-weight: 700;
font-size: 1.55rem;
color: #e6edf3;
margin: 0;
letter-spacing: -0.01em;
">ISM Manufacturing Intelligence Hub</h1>
<p style="
font-family: 'IBM Plex Mono', monospace;
font-size: 0.72rem;
color: #8b949e;
margin: 4px 0 0;
letter-spacing: 0.04em;
">ISM REPORT ON BUSINESS | SECTOR ANALYSIS | MACRO SCORING</p>
</div>
</div>
""", unsafe_allow_html=True)

# ====================== LOAD DATA ======================
with st.spinner("Building sector history from ISM archive..."):
    df_master, report_metadata, log_messages = build_historical_dataset()

if df_master.empty:
    st.error("No ISM data could be retrieved. Please try a Deep Refresh from the sidebar.")
    st.stop()

latest_date = df_master['date'].max()
current_df = df_master[df_master['date'] == latest_date].copy()
latest_meta = report_metadata.get(latest_date, {})
pmi_val = latest_meta.get("pmi", 50)
report_url = latest_meta.get("url", "#")
comments_list = latest_meta.get("comments", [])
subcomponents = latest_meta.get("subcomponents", {})

# ====================== TABS ======================
tab1, tab2 = st.tabs(["Primary Effects (ISM > Sectors > Stocks)", "Fund Manager Macro Scoring (Driver Analysis)"])

# ====================== TAB 1 ======================
with tab1:
    regime = "Expansion" if pmi_val >= 50 else "Contraction"
    regime_class = "pmi-expansion" if pmi_val >= 50 else "pmi-contraction"
    regime_color = "#3fb950" if pmi_val >= 50 else "#f85149"
    st.markdown(f"""
    <div class="pmi-banner {regime_class}">
    <div style="font-size:2rem; font-weight:700; color:{regime_color}; font-family:'IBM Plex Mono',monospace; line-height:1;">
    {pmi_val:.1f}
    </div>
    <div>
    <div style="font-size:0.68rem; color:#8b949e; font-family:'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:0.1em;">
    Headline PMI — {latest_date.strftime('%B %Y')}
    </div>
    <div style="font-size:0.9rem; font-weight:600; color:{regime_color}; font-family:'IBM Plex Sans',sans-serif; margin-top:2px;">
    Manufacturing {regime} &nbsp;|&nbsp; {"Above 50" if pmi_val >= 50 else "Below 50"} threshold
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    section_header("Sub-Index Command Center", "Key ISM sub-components | value / mom change / trend months")
    keys_order = ["New Orders", "Production", "Employment", "Prices", "Backlog of Orders"]
    labels_order = ["New Orders", "Production", "Employment", "Prices Paid", "Backlog of Orders"]
    metric_cols = st.columns(5)
    for i, (key, label) in enumerate(zip(keys_order, labels_order)):
        data = subcomponents.get(key, {})
        current = data.get("current")
        change = data.get("change")
        trend = data.get("trend")
        with metric_cols[i]:
            if current is not None:
                delta_str = f"{change:+.1f} | {trend}mo" if change is not None and trend is not None else None
                delta_color = "normal" if current >= 50 else "inverse"
                st.metric(label=label, value=f"{current:.1f}", delta=delta_str, delta_color=delta_color)
            else:
                st.metric(label=label, value="N/A")

    st.divider()

    section_header("Industry Rankings", "Ordered by current growth score | Select rows then generate baskets")

    ranked_df = current_df[["industry", "score"]].sort_values("score", ascending=False).reset_index(drop=True)
    selected_rows = st.dataframe(
        ranked_df.style
        .background_gradient(cmap="RdYlGn", subset=["score"], vmin=-13, vmax=13)
        .format({"score": "{:+d}"}),
        use_container_width=True,
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun"
    )

    st.divider()

    with st.expander("NAICS Mapping Reference (ISM Industry > Production Category)", expanded=False):
        naics_df = pd.DataFrame(list(NAICS_MAPPING.items()), columns=["ISM Industry", "NAICS Code(s)"])
        st.dataframe(naics_df, use_container_width=True, hide_index=True)

        st.divider()

    # ====================== GENERATE BASKETS (Stocks + ETFs) ======================
    if st.button("Generate Primary Effect Baskets for Selected Industries", type="primary", use_container_width=True):
        universe = get_full_universe()
        if universe.empty:
            st.error("Universe could not be loaded.")
        else:
            if len(selected_rows["selection"]["rows"]) > 0:
                selected_industries = ranked_df.iloc[selected_rows["selection"]["rows"]]["industry"].tolist()
            else:
                selected_industries = [ind for ind, score in zip(current_df["industry"], current_df["score"]) if score != 0]

            st.session_state.primary_baskets = {"stocks": {}, "etfs": {}}

            for industry in selected_industries:
                score_val = current_df.loc[current_df['industry'] == industry, 'score'].iloc[0]
                direction = "GROWTH" if score_val > 0 else "CONTRACTION"

                # STOCK BASKET
                yahoo_industries = PRIMARY_ISM_MAPPING.get(industry, [])
                stock_df = universe[(universe["Type"] == "Stock") & 
                                   (universe["Yahoo Industry"].isin(yahoo_industries))].copy()
                if not stock_df.empty:
                    stock_df = stock_df.sort_values("Market Cap", ascending=False)
                    st.session_state.primary_baskets["stocks"][industry] = {"df": stock_df, "direction": direction}

                # ETF BASKET - weighted by actual sector exposure
                etf_candidates = universe[universe["Type"] == "ETF"].copy()
                etf_df = pd.DataFrame()
                if not etf_candidates.empty:
                    etf_candidates["relevance"] = etf_candidates.apply(
                        lambda row: get_etf_relevance_to_ism(row, industry), axis=1
                    )
                    etf_df = etf_candidates[etf_candidates["relevance"] > 0].copy()
                    if not etf_df.empty:
                        etf_df = etf_df.sort_values("relevance", ascending=False)

                if not etf_df.empty:
                    etf_df = etf_df.drop(columns=["relevance"], errors="ignore")
                    st.session_state.primary_baskets["etfs"][industry] = {"df": etf_df, "direction": direction}

            st.success(f"Generated baskets for {len(selected_industries)} industries "
                       f"(stocks + weighted ETFs)")

    # ====================== DISPLAY BASKETS ======================
    if "primary_baskets" in st.session_state and (st.session_state.primary_baskets.get("stocks") or st.session_state.primary_baskets.get("etfs")):
        col_left, col_right = st.columns([2, 3])

        with col_left:
            section_header("Industry Baskets", "Stocks + ETFs | Click any row for deep dive")
            
            # STOCKS
            if st.session_state.primary_baskets.get("stocks"):
                st.subheader("Stocks")
                for industry, data in st.session_state.primary_baskets["stocks"].items():
                    direction_tag = data["direction"]
                    with st.expander(f"📌 {industry} [{direction_tag}] — Stocks", expanded=True):
                        df_display = data["df"][["Ticker", "Company", "Yahoo Industry", "Market Cap"]].copy()
                        df_display["Yahoo Finance"] = df_display["Ticker"].apply(
                            lambda t: f"https://finance.yahoo.com/quote/{t}"
                        )
                        selection = st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row",
                            column_config={
                                "Yahoo Finance": st.column_config.LinkColumn("Yahoo Finance", display_text="View")
                            }
                        )
                        if selection["selection"]["rows"]:
                            st.session_state.selected_ticker = df_display.iloc[selection["selection"]["rows"][0]]["Ticker"]
                            st.session_state.selected_type = "Stock"

            # ETFs
            if st.session_state.primary_baskets.get("etfs"):
                st.subheader("ETFs")
                for industry, data in st.session_state.primary_baskets["etfs"].items():
                    direction_tag = data["direction"]
                    with st.expander(f"📌 {industry} [{direction_tag}] — ETFs", expanded=True):
                        df_display = data["df"][["Ticker", "Company", "Category", "Market Cap"]].copy()
                        df_display["Yahoo Finance"] = df_display["Ticker"].apply(
                            lambda t: f"https://finance.yahoo.com/quote/{t}"
                        )
                        selection = st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row",
                            column_config={
                                "Yahoo Finance": st.column_config.LinkColumn("Yahoo Finance", display_text="View")
                            }
                        )
                        if selection["selection"]["rows"]:
                            st.session_state.selected_ticker = df_display.iloc[selection["selection"]["rows"][0]]["Ticker"]
                            st.session_state.selected_type = "ETF"

        with col_right:
            section_header("Selected Stock / ETF Analysis")
            ticker = st.session_state.get("selected_ticker")
            ticker_type = st.session_state.get("selected_type", "Stock")

            if ticker:
                if ticker_type == "ETF":
                    show_etf_deep_dive(ticker)
                else:
                    show_stock_deep_dive(ticker)
            else:
                st.markdown("""
                <div style="
                background: #161b22;
                border: 1px dashed #30363d;
                border-radius: 8px;
                padding: 48px 32px;
                text-align: center;
                color: #8b949e;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 0.82rem;
                ">
                Select a stock or ETF from the baskets on the left<br>to open the professional deep dive panel.
                </div>
                """, unsafe_allow_html=True)

    # ====================== RESPONDENT COMMENTS ======================
    with st.expander("Respondent Comments (What industry leaders are saying)", expanded=False):
        if comments_list:
            st.markdown(f"**Latest Report — {latest_date.strftime('%B %Y')}**")
            st.markdown("\n\n".join(comments_list))
            st.divider()
        else:
            st.info("No respondent comments parsed for this report.")

        st.subheader("Previous Months' Respondent Comments")
        historical_dates = sorted(report_metadata.keys(), reverse=True)[:6]
        for d in historical_dates[1:]:
            meta = report_metadata[d]
            old_comments = meta.get("comments", [])
            month_title = d.strftime('%B %Y')
            with st.expander(f"📅 {month_title} Comments ({len(old_comments)} quotes)"):
                if old_comments:
                    st.markdown("\n\n".join(old_comments))
                else:
                    st.info("No respondent comments available for this month.")

    st.divider()

    section_header("6-Month Sector Momentum", "Rolling ISM growth/contraction score by industry")
    pivot = df_master.pivot_table(
        index="industry", columns="date", values="score", aggfunc="last"
    ).fillna(0)
    pivot = pivot.reindex(INDUSTRIES)
    pivot.columns = pivot.columns.strftime('%b %Y')

    fig_heat = px.imshow(
        pivot,
        labels=dict(x="Report Month", y="Industry", color="Score"),
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        text_auto=True,
        aspect="auto"
    )
    fig_heat.update_layout(
        height=580,
        xaxis_title="",
        margin=dict(l=10, r=10, t=30, b=10),
        **PLOTLY_THEME
    )
    fig_heat.update_coloraxes(colorbar=dict(thickness=12, len=0.8))
    st.plotly_chart(fig_heat, use_container_width=True, key="momentum_chart")

    st.divider()

    section_header("Industry Score Evolution", "Track growth/contraction trends across reporting periods")
    to_track = st.multiselect(
        "Select industries to compare:",
        INDUSTRIES,
        default=["Transportation Equipment", "Chemical Products", "Computer & Electronic Products"]
    )
    if to_track:
        line_df = df_master[df_master['industry'].isin(to_track)].sort_values('date')
        fig_line = px.line(
            line_df, x='date', y='score', color='industry',
            markers=True, line_shape='spline',
        )
        fig_line.update_traces(line=dict(width=2))
        fig_line.update_layout(
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis_title="",
            yaxis_title="Score",
            margin=dict(l=10, r=10, t=50, b=10),
            **PLOTLY_THEME
        )
        fig_line.add_hline(y=0, line_dash="dot", line_color="#444c56", annotation_text="Neutral", annotation_font_color="#8b949e")
        st.plotly_chart(fig_line, use_container_width=True, key="evolution_chart")

# ====================== TAB 2 ======================
with tab2:
    drivers = calculate_drivers(subcomponents)

    section_header("Economic Driver Signal Strength", "ISM regime translation into investable macro drivers")

    driver_df = pd.DataFrame({
        "Driver": [d.value for d in drivers.keys()],
        "Strength": [d.strength for d in drivers.values()],
        "Description": [d.description for d in drivers.values()]
    })

    fig_drivers = px.bar(
        driver_df, x="Strength", y="Driver", orientation="h",
        text=driver_df["Strength"].apply(lambda x: f"{x:+.2f}"),
        color="Strength",
        color_continuous_scale=[[0, "#f85149"], [0.5, "#d29922"], [1, "#3fb950"]],
        color_continuous_midpoint=0,
    )
    fig_drivers.update_traces(textfont=dict(family="IBM Plex Mono", size=11), textposition="outside")
    fig_drivers.update_layout(height=320, coloraxis_showscale=False, margin=dict(l=10, r=40, t=20, b=10), **{k: v for k, v in PLOTLY_THEME.items() if k != "xaxis"})
    fig_drivers.update_layout(xaxis=dict(range=[-1.1, 1.1], zeroline=True, zerolinecolor="#444c56", zerolinewidth=1, gridcolor="#21262d", linecolor="#30363d"))
    st.plotly_chart(fig_drivers, use_container_width=True)

    st.divider()

    # Treemap
    section_header("Sector Signal Treemap", "Tile area = instrument count | Color = avg ISM score")
    if "scored_df_tab2" in st.session_state:
        scored_df = st.session_state.scored_df_tab2
        sector_for_treemap = (
            scored_df.groupby(["Type", "Yahoo Industry" if "Yahoo Industry" in scored_df.columns else "Category"])
            .agg(Avg_Score=("ism_score", "mean"), Count=("Ticker", "count"))
            .round(3)
            .reset_index()
        )
        if not sector_for_treemap.empty:
            fig_tree = px.treemap(
                sector_for_treemap,
                path=["Type", "Yahoo Industry" if "Yahoo Industry" in sector_for_treemap.columns else "Category"],
                values="Count",
                color="Avg_Score",
                color_continuous_scale=[[0, "#f85149"], [0.5, "#d29922"], [1, "#3fb950"]],
                color_continuous_midpoint=0,
            )
            fig_tree.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0), **PLOTLY_THEME)
            st.plotly_chart(fig_tree, use_container_width=True)

    st.divider()

    section_header("ISM-Leveraged Stock & ETF Ideas", "Full universe ranked by ISM driver alignment")

    # ====================== GENERATE RANKED IDEAS ======================
    if st.button("Generate Ranked Ideas (Full Universe Scoring)", type="primary", use_container_width=True):
        with st.spinner("Scoring full universe (stocks + ETFs)..."):
            universe = get_full_universe()
            if universe.empty:
                st.error("Universe could not be loaded.")
                st.stop()

            # Score stocks
            stocks_df = universe[universe["Type"] == "Stock"].copy()
            scored_stocks = tag_and_score_stocks(stocks_df, drivers) if not stocks_df.empty else pd.DataFrame()

            # Score ETFs
            etfs_df = universe[universe["Type"] == "ETF"].copy()
            scored_etfs = pd.DataFrame()
            if not etfs_df.empty:
                etf_rows = []
                for _, row in etfs_df.iterrows():
                    etf_score_data = calculate_etf_macro_score(row, drivers)
                    etf_rows.append({**row.to_dict(), **etf_score_data, "Type": "ETF"})
                scored_etfs = pd.DataFrame(etf_rows)

            # Combine
            scored_df = pd.concat([scored_stocks, scored_etfs], ignore_index=True)
            if not scored_df.empty:
                scored_df = scored_df.sort_values("conviction", ascending=False).reset_index(drop=True)

            st.session_state.scored_df_tab2 = scored_df
            st.success(f"Scored {len(scored_df):,} instruments ({len(scored_stocks)} stocks + {len(scored_etfs)} ETFs)")

    # ====================== DISPLAY RANKED LISTS + DEEP DIVE ======================
        col_left, col_right = st.columns([2, 3])

        with col_left:
            # Top Long Ideas (Stocks)
            section_header("📈 Top Long Ideas (Stocks)")
            top_stocks = scored_df[(scored_df["Type"] == "Stock") & (scored_df["ism_score"] > 0.05)].head(20)
            selection_long = st.dataframe(
                top_stocks[["Ticker", "Company", "ism_score", "conviction", "why"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # Short Candidates (Stocks)
            st.divider()
            section_header("📉 Short Candidates (Stocks)")
            short_stocks = scored_df[(scored_df["Type"] == "Stock") & (scored_df["ism_score"] < -0.05)].head(15)
            if short_stocks.empty:
                st.info("No strong short signals in current regime.")
            else:
                selection_short = st.dataframe(
                    short_stocks[["Ticker", "Company", "ism_score", "conviction", "why"]],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )

            # Top ETF Ideas
            st.divider()
            section_header("🏛 Top ETF Ideas")
            top_etfs = scored_df[(scored_df["Type"] == "ETF") & (scored_df["ism_score"] > 0.01)].head(15)  # lowered threshold
            if top_etfs.empty:
                st.info("No high-scoring ETFs yet. Try Deep Refresh.")
            else:
                selection_etf = st.dataframe(
                    top_etfs[["Ticker", "Company", "ism_score", "conviction", "why"]],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )

        with col_right:
            section_header("Selected Instrument Analysis")
            ticker = None
            ticker_type = None

            if selection_long["selection"]["rows"]:
                idx = selection_long["selection"]["rows"][0]
                ticker = top_stocks.iloc[idx]["Ticker"]
                ticker_type = "Stock"
            elif 'selection_short' in locals() and selection_short["selection"]["rows"]:
                idx = selection_short["selection"]["rows"][0]
                ticker = short_stocks.iloc[idx]["Ticker"]
                ticker_type = "Stock"
            elif 'selection_etf' in locals() and selection_etf["selection"]["rows"]:
                idx = selection_etf["selection"]["rows"][0]
                ticker = top_etfs.iloc[idx]["Ticker"]
                ticker_type = "ETF"

            if ticker:
                if ticker_type == "ETF":
                    show_etf_deep_dive(ticker)
                else:
                    show_stock_deep_dive(ticker)
            else:
                st.markdown("""
                <div style="background: #161b22; border: 1px dashed #30363d; border-radius: 8px; padding: 48px 32px; text-align: center; color: #8b949e; font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem;">
                Select any row from the lists on the left<br>to open the professional deep dive panel.
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        # Full table at the bottom (shows everything)
        st.dataframe(
            scored_df[["Ticker", "Company", "Type", "Yahoo Industry", "Category", "ism_score", "conviction", "why"]]
            .sort_values("conviction", ascending=False),
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Click the button above to generate the ranked universe.")

    # ====================== HISTORICAL BACKTEST ======================
    st.divider()
    section_header("Historical Backtest", "Re-run ISM scoring against any past report")
    if report_metadata:
        historical_dates = sorted(report_metadata.keys(), reverse=True)
        date_options = [d.strftime('%B %Y') for d in historical_dates]
        selected_month_str = st.selectbox("Select past ISM report:", options=date_options, index=0)
        selected_date = next(d for d in historical_dates if d.strftime('%B %Y') == selected_month_str)

        if st.button(f"Re-run Scoring for {selected_month_str}", type="primary", use_container_width=True):
            with st.spinner(f"Re-calculating for {selected_month_str}..."):
                hist_meta = report_metadata[selected_date]
                hist_drivers = calculate_drivers(hist_meta.get("subcomponents", {}))
                universe = get_full_universe()
                stocks_df = universe[universe["Type"] == "Stock"].copy()
                scored_hist = tag_and_score_stocks(stocks_df, hist_drivers) if not stocks_df.empty else pd.DataFrame()
                st.success(f"Backtest complete for {selected_month_str}")
                st.dataframe(
                    scored_hist.head(30)[["Ticker", "Company", "Yahoo Industry", "Market Cap", "ism_score", "why"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={"ism_score": st.column_config.ProgressColumn("Signal Strength", format="%.3f", min_value=-1.0, max_value=1.0)}
                )

# ====================== SIDEBAR ======================
with st.sidebar:
    st.markdown("""
    <div style="padding: 16px 0 8px;">
    <div style="
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    color: #58a6ff;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 10px;
    ">ISM Intelligence Hub</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        st.image("https://www.ismworld.org/globalassets/pub/logos/ism_manufacturing_pmi_logo.png", width=180)
    except:
        pass

    st.markdown("---")

    st.markdown(f"""
    <div style="font-family:'IBM Plex Sans',sans-serif; font-size:0.82rem; color:#e6edf3; margin-bottom:6px;">
    <strong>Report Period</strong><br>
    <span style="font-family:'IBM Plex Mono',monospace; color:#58a6ff; font-size:0.88rem;">
    {latest_date.strftime('%B %Y')}
    </span>
    </div>
    <div style="font-family:'IBM Plex Sans',sans-serif; font-size:0.82rem; color:#e6edf3; margin-bottom:6px;">
    <strong>Headline PMI</strong><br>
    <span style="font-family:'IBM Plex Mono',monospace; color:{'#3fb950' if pmi_val >= 50 else '#f85149'}; font-size:0.88rem;">
    {pmi_val:.1f} — {'Expansion' if pmi_val >= 50 else 'Contraction'}
    </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.7rem; color:#8b949e; line-height:1.8;">
    <strong style="color:#e6edf3;">Tab 1</strong> — Primary Effects<br>
    &nbsp;&nbsp;ISM > Sectors > Stock Baskets<br><br>
    <strong style="color:#e6edf3;">Tab 2</strong> — Macro Scoring<br>
    &nbsp;&nbsp;Driver Signals > Ranked Universe
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.write(f"**Source:** [PR Newswire]({report_url})")

    if st.button("Deep Refresh (Clear Cache + Re-scrape)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.expander("Process Log", expanded=False):
        if log_messages:
            for msg in log_messages:
                st.markdown(f"`{msg}`")
        else:
            st.caption("No log entries.")



