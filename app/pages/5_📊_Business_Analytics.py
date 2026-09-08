"""Business Analytics and Market Intelligence Dashboard."""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

import pandas as pd
import streamlit as st
from dbio import query_rows

st.set_page_config(page_title="Business Analytics - Job Market Pulse", page_icon="📊", layout="wide")

st.title("📊 Labor Market Business Intelligence")
st.caption("Aggregated analytics powered by Databricks SQL marts covering live and historical postings")

tab_role, tab_season, tab_sal, tab_quality, tab_funnel, tab_long = st.tabs([
    "👔 Role Market",
    "📅 Seasonality",
    "💰 Salary Summary",
    "🛡️ Source Quality",
    "📈 Funnel Analysis",
    "⏳ Longevity",
])

with tab_role:
    st.subheader("Role Family Distribution & Dynamics")
    try:
        data = query_rows("SELECT role_family, year_month, total_postings, avg_salary_min, avg_salary_max FROM mart_role_market ORDER BY total_postings DESC")
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            chart_data = df.groupby("role_family")["total_postings"].sum().reset_index()
            st.bar_chart(chart_data.set_index("role_family"))
        else:
            st.info("No data in mart_role_market.")
    except Exception as e:
        st.warning("Connect to warehouse to see live mart_role_market data.")

with tab_season:
    st.subheader("📅 Hiring Seasonality & Domain Release Patterns")
    st.caption("Longitudinal time-series analysis combining active and historical postings across all seasons and domains")

    try:
        data = query_rows("""
        SELECT
          role_family,
          domain_name,
          season,
          quarter,
          posting_year,
          month_of_year,
          month_name,
          year_month,
          source_id,
          posting_count,
          fresher_postings_count
        FROM mart_posting_seasonality
        ORDER BY year_month DESC, posting_count DESC
        """)

        if data:
            df = pd.DataFrame(data)

            # Executive Insights Callout
            season_agg = df.groupby("season")["posting_count"].sum().sort_values(ascending=False)
            top_season = season_agg.index[0] if not season_agg.empty else "N/A"
            top_season_pct = (season_agg.iloc[0] / season_agg.sum() * 100) if not season_agg.empty else 0

            month_agg = df.groupby("month_name")["posting_count"].sum().sort_values(ascending=False)
            top_month = month_agg.index[0] if not month_agg.empty else "N/A"

            fresher_season = df.groupby("season")["fresher_postings_count"].sum().sort_values(ascending=False)
            top_fresher_season = fresher_season.index[0] if not fresher_season.empty else "N/A"
            top_fresher_val = fresher_season.iloc[0] if not fresher_season.empty else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏆 Peak Release Season", top_season, f"{top_season_pct:.1f}% of all roles")
            c2.metric("📅 Peak Hiring Month", top_month)
            c3.metric("🎓 Peak Fresher Season", top_fresher_season, f"{top_fresher_val:,} new grad roles")
            c4.metric("📊 Total Cataloged Postings", f"{df['posting_count'].sum():,}")

            st.markdown("---")

            # Domain Slicer
            col_sel1, col_sel2 = st.columns([2, 2])
            with col_sel1:
                domain_list = ["All Domains"] + sorted(df["domain_name"].dropna().unique().tolist())
                chosen_domain = st.selectbox("🎯 Filter by Technical Domain / Role Category", domain_list)

            with col_sel2:
                year_list = ["All Years"] + sorted([str(y) for y in df["posting_year"].dropna().unique().tolist()], reverse=True)
                chosen_year = st.selectbox("📆 Filter by Year", year_list)

            filtered_df = df.copy()
            if chosen_domain != "All Domains":
                filtered_df = filtered_df[filtered_df["domain_name"] == chosen_domain]
            if chosen_year != "All Years":
                filtered_df = filtered_df[filtered_df["posting_year"] == int(chosen_year)]

            # Visualizations
            v_col1, v_col2 = st.columns(2)
            season_order = ["Winter", "Spring", "Summer", "Fall / Autumn"]

            with v_col1:
                st.markdown(f"#### 🌸 Seasonal Distribution: **{chosen_domain}**")
                s_counts = filtered_df.groupby("season")["posting_count"].sum().reindex(season_order).fillna(0)
                st.bar_chart(s_counts)

            with v_col2:
                st.markdown("#### 📆 Monthly Hiring Release Cadence")
                month_order = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ]
                m_counts = filtered_df.groupby("month_name")["posting_count"].sum().reindex(month_order).fillna(0)
                st.line_chart(m_counts)

            st.markdown("---")
            v_col3, v_col4 = st.columns(2)

            with v_col3:
                st.markdown("#### 🎓 Freshers & Internship Releases by Season")
                fresh_counts = filtered_df.groupby("season")["fresher_postings_count"].sum().reindex(season_order).fillna(0)
                st.bar_chart(fresh_counts)

            with v_col4:
                st.markdown("#### 🏢 Quarterly Release Waves (Q1 - Q4)")
                q_counts = filtered_df.groupby("quarter")["posting_count"].sum().reindex(["Q1", "Q2", "Q3", "Q4"]).fillna(0)
                st.bar_chart(q_counts)

            st.markdown("---")
            with st.expander("📋 Detailed Seasonality & Domain Data Table"):
                st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("No data in mart_posting_seasonality.")
    except Exception as e:
        st.warning(f"Connect to warehouse to see live mart_posting_seasonality data: {e}")

with tab_sal:
    st.subheader("Compensation Benchmarks by Role & Location")
    try:
        data = query_rows("SELECT role_family, location, currency, postings_with_salary, avg_salary_min, avg_salary_max FROM mart_salary_summary WHERE postings_with_salary > 0 ORDER BY avg_salary_max DESC")
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No salary data reported across integrated postings.")
    except Exception as e:
        st.warning("Connect to warehouse to see live mart_salary_summary data.")

with tab_quality:
    st.subheader("Source Data Quality & Completeness")
    try:
        data = query_rows("SELECT source_id, total_postings, distinct_companies, incomplete_percentage, earliest_posting_date, latest_posting_date FROM mart_source_quality")
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            st.bar_chart(df.set_index("source_id")["incomplete_percentage"])
        else:
            st.info("No data in mart_source_quality.")
    except Exception as e:
        st.warning("Connect to warehouse to see live mart_source_quality data.")

with tab_funnel:
    st.subheader("Application Conversion Funnel")
    try:
        data = query_rows("SELECT status, application_month, applications_count, percentage_of_month FROM mart_application_funnel ORDER BY application_month DESC")
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Start tracking applications to populate the conversion funnel.")
    except Exception as e:
        st.warning("Connect to warehouse to see live mart_application_funnel data.")

with tab_long:
    st.subheader("Posting Longevity & Lifecycle")
    try:
        data = query_rows("SELECT role_family, source_id, longevity_bracket, postings_count, avg_active_days, max_active_days FROM mart_posting_longevity ORDER BY postings_count DESC")
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No data in mart_posting_longevity.")
    except Exception as e:
        st.warning("Connect to warehouse to see live mart_posting_longevity data.")
