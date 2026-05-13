import streamlit as st
st.set_page_config(
    page_title="Incident Intelligence Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.supabase_client import get_data
from utils.charts import (
    render_incidents_by_category,
    render_incidents_by_type,
    render_incidents_by_country,
    render_impact_distribution,
    render_timeline,
    render_wordcloud,
    render_source_breakdown
)
from utils.chatbot import chatbot_ui

TZ_MY = ZoneInfo("Asia/Kuala_Lumpur")   # GMT+8
def now_my(): return datetime.now(tz=TZ_MY)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Dark sidebar */
[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2130;
}
[data-testid="stSidebar"] * {
    color: #c9d1d9 !important;
}

/* Top header bar */
.dash-header {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.dash-title {
    font-size: 24px;
    font-weight: 600;
    color: #f0f6fc;
    letter-spacing: -0.3px;
}
.dash-subtitle {
    font-size: 13px;
    color: #8b949e;
    margin-top: 2px;
}
.dash-live {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #3fb950;
    font-family: 'IBM Plex Mono', monospace;
}
.live-dot {
    width: 8px; height: 8px;
    background: #3fb950;
    border-radius: 50%;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* KPI cards */
.kpi-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 18px 20px;
    text-align: center;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: #388bfd; }
.kpi-number {
    font-size: 36px;
    font-weight: 600;
    color: #f0f6fc;
    font-family: 'IBM Plex Mono', monospace;
    line-height: 1;
}
.kpi-label {
    font-size: 12px;
    color: #8b949e;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.kpi-delta {
    font-size: 12px;
    margin-top: 6px;
    font-family: 'IBM Plex Mono', monospace;
}
.kpi-up { color: #3fb950; }
.kpi-warn { color: #f78166; }

/* Section headers */
.section-header {
    font-size: 14px;
    font-weight: 500;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 24px 0 12px;
    border-bottom: 1px solid #21262d;
    padding-bottom: 8px;
}

/* Divider */
hr { border-color: #21262d !important; }

/* Streamlit overrides */
[data-testid="stMetric"] { background: transparent; }
.stPlotlyChart { border: 1px solid #21262d; border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar filters ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ Incident Intel")
    st.markdown("---")
    st.markdown("**Filters**")

    date_range = st.date_input(
        "Date range (GMT+8)",
        value=(now_my().date() - timedelta(days=90), now_my().date()),
        max_value=now_my().date()
    )

    category_filter = st.multiselect("Category", options=[], placeholder="All categories")
    country_filter  = st.multiselect("Country",  options=[], placeholder="All countries")
    impact_filter   = st.multiselect("Impact",   options=["Critical","High","Medium","Low"], placeholder="All impacts")

    st.markdown("---")
    auto_refresh = st.toggle("Auto-refresh (60s)", value=False)
    if auto_refresh:
        import time; time.sleep(60); st.rerun()

    st.markdown("---")
    st.markdown("<span style='font-size:11px;color:#484f58'>Data source: Supabase Postgres<br>Model: Claude claude-sonnet-4-20250514</span>", unsafe_allow_html=True)


# ── Load data ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def load_incidents():
    return get_data("incidents")   # table name in Supabase

with st.spinner("Loading incidents…"):
    df_raw = load_incidents()

if df_raw is None or df_raw.empty:
    st.error("⚠️ Could not load data from Supabase. Check your `.streamlit/secrets.toml` configuration.")
    st.stop()

df = df_raw.copy()
# Timestamps from Supabase are already converted to GMT+8 by supabase_client.py
# Just ensure the columns are datetime — no tz conversion needed here
for col in ("incident_date", "publication_date"):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_convert(TZ_MY)

# Apply sidebar filters — compare tz-aware timestamps with tz-aware bounds
if len(date_range) == 2:
    start = pd.Timestamp(date_range[0], tz=TZ_MY)
    end   = pd.Timestamp(date_range[1], tz=TZ_MY) + timedelta(days=1) - timedelta(seconds=1)
    if "incident_date" in df.columns:
        df = df[df["incident_date"].between(start, end, inclusive="both")]
if category_filter:
    df = df[df["category"].isin(category_filter)]
if country_filter:
    df = df[df["country"].isin(country_filter)]
if impact_filter:
    df = df[df["impact"].isin(impact_filter)]

# Update sidebar filter options from full data
with st.sidebar:
    # Re-render with real options (requires a workaround via session state)
    pass

# ── KPI metrics ──────────────────────────────────────────────────────────────
total_incidents   = len(df)
total_sources     = df["source"].nunique() if "source" in df.columns else 0
critical_count    = len(df[df["impact"] == "Critical"]) if "impact" in df.columns else 0
countries_affected = df["country"].nunique() if "country" in df.columns else 0
this_week = df[df["incident_date"] >= now_my() - timedelta(days=7)] if "incident_date" in df.columns else pd.DataFrame()
new_this_week = len(this_week)

st.markdown(f"""
<div class="dash-header">
  <div>
    <div class="dash-title">🛡️ Incident Intelligence Dashboard</div>
    <div class="dash-subtitle">Cybersecurity & Threat Monitoring · Real-time feed</div>
  </div>
  <div class="dash-live">
    <div class="live-dot"></div>
    LIVE · {now_my().strftime('%d %b %Y, %H:%M:%S')} GMT+8
  </div>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
cards = [
    (k1, total_incidents,    "Total Incidents",      f"+{new_this_week} this week", "up"),
    (k2, total_sources,      "Crawled Sources",      "Unique domains",              ""),
    (k3, critical_count,     "Critical Incidents",   "Needs attention",             "warn" if critical_count > 0 else ""),
    (k4, countries_affected, "Countries Affected",   "Unique nations",              ""),
    (k5, new_this_week,      "New This Week",         "Last 7 days",                "up"),
]
for col, val, label, delta, dtype in cards:
    delta_class = f"kpi-{dtype}" if dtype else "kpi-label"
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-number">{val:,}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-delta {delta_class}">{delta}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div class='section-header'>Incident Overview</div>", unsafe_allow_html=True)

# ── Row 1: Category + Incident Type ─────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    render_incidents_by_category(df)
with c2:
    render_incidents_by_type(df)

# ── Row 2: Timeline + Impact ─────────────────────────────────────────────────
st.markdown("<div class='section-header'>Trends & Impact</div>", unsafe_allow_html=True)
c3, c4 = st.columns([2, 1])
with c3:
    render_timeline(df)
with c4:
    render_impact_distribution(df)

# ── Row 3: Country map + Source breakdown ────────────────────────────────────
st.markdown("<div class='section-header'>Geography & Sources</div>", unsafe_allow_html=True)
c5, c6 = st.columns([2, 1])
with c5:
    render_incidents_by_country(df)
with c6:
    render_source_breakdown(df)

# ── Row 4: Word clouds ───────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Text Insights</div>", unsafe_allow_html=True)
w1, w2 = st.columns(2)
with w1:
    render_wordcloud(df, column="summary", title="Summary Keywords")
with w2:
    render_wordcloud(df, column="relevant_keywords", title="Relevant Keywords")

# ── Raw data expander ────────────────────────────────────────────────────────
with st.expander("📋 View raw incident data"):
    preferred = ["id","title","incident_date","category","incident_type","country","impact","source"]
    show_cols = [c for c in preferred if c in df.columns]
    if not show_cols:
        show_cols = list(df.columns)
    display_df = df[show_cols].copy()
    if "incident_date" in display_df.columns:
        display_df = display_df.sort_values("incident_date", ascending=False)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    with st.expander("🔍 Debug: actual column names from Supabase"):
        st.code(str(list(df.columns)))

# ── AI Chatbot ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>🤖 AI Analyst — Ask anything about the data</div>", unsafe_allow_html=True)
chatbot_ui(df)
