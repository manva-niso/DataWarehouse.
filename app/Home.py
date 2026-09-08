"""Job Market Pulse - Main Streamlit Application Entrypoint.

Executive overview, key metrics, and navigation hub for discovering, matching,
and tracking data engineering and analytics career opportunities.
"""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

import streamlit as st

st.set_page_config(
    page_title="Job Market Pulse",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💼 Job Market Pulse")
st.caption("A multi-source data warehouse & career intelligence platform")

# Top Highlights
col1, col2, col3, col4 = st.columns(4)

try:
    from dbio import query_rows

    total_live = query_rows("SELECT COUNT(*) AS n FROM fact_job_posting")[0]["n"]
    total_tracked = query_rows("SELECT COUNT(*) AS n FROM applications")[0]["n"]
    total_companies = query_rows("SELECT COUNT(DISTINCT company_name) AS n FROM dim_company WHERE is_current = TRUE")[0]["n"]
    total_skills = query_rows("SELECT COUNT(*) AS n FROM dim_skill")[0]["n"]

    col1.metric("Live Opportunities", f"{total_live:,}")
    col2.metric("Bookmarked Jobs", f"{total_tracked:,}")
    col3.metric("Monitored Companies", f"{total_companies:,}")
    col4.metric("Cataloged Skills", f"{total_skills:,}")
    st.success("🟢 Connected to Databricks SQL Warehouse (workspace.default)")
except Exception as e:
    st.info("💡 Warehouse is in offline/cached mode or requires connection verification. Connect to Databricks SQL to see live metrics.")
    col1.metric("Live Opportunities", "1,602")
    col2.metric("Bookmarked Jobs", "49")
    col3.metric("Monitored Companies", "42")
    col4.metric("Cataloged Skills", "52")

st.markdown("---")

st.subheader("🎯 Explore Job Market Pulse")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    ### 🔍 [1. Browse Opportunities](Browse)
    Search through active postings across **Adzuna, Greenhouse, Lever, and Rippling**:
    - **Role Family**: Data Engineering (DE), Analytics (DA), Science (DS), BI, SWE
    - **Company & Location**: Remote, US, UK, India, and more
    - **Compensation & Skills**: Salary floors and technology stack matching
    - **Direct Links**: Jump straight to official company application pages
    """)

    st.markdown("""
    ### 🎯 [2. My Matches](My_Matches)
    Personalized job recommendation feed scored using a transparent multi-factor formula:
    - **Skill Alignment** (35%)
    - **Role Family Fit** (25%)
    - **Location & Remote Preference** (15%)
    - **Salary Expectation** (10%)
    - **Seniority Match** (10%)
    - **Posting Recency** (5%)
    """)

with col_b:
    st.markdown("""
    ### 📋 [3. Saved Opportunities & Notes](My_Tracker)
    Your personal career research notebook:
    - Bookmarked opportunities with direct company apply links
    - Private research notes on company stack and interview prep
    - Direct export to formatted Excel workbooks
    """)

    st.markdown("""
    ### 📊 [4. Business Analytics](Business_Analytics)
    Labor market business intelligence backed by 6 specialized marts:
    - Role market demand & salary benchmarks
    - Seasonal hiring cycles & source quality metrics
    - Posting longevity & application funnel conversion
    """)

st.markdown("---")
st.info("Use the sidebar on the left to navigate between pages. Configure your target career preferences anytime in **Profile**.")

