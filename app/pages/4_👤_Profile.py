"""Candidate Target Profile Settings for Match Engine."""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

import streamlit as st
from app.crud import get_cataloged_skills, get_profile, upsert_profile
from marts.refresh import refresh_mart_views

st.set_page_config(page_title="Target Profile - Job Market Pulse", page_icon="👤", layout="wide")

st.title("👤 Target Career Profile")
st.caption("Customize your target roles, skills, and preferences to automatically adjust matching scores")

all_skills = get_cataloged_skills()

# Fetch current profile
current = get_profile()

with st.form("profile_form"):
    st.subheader("1. Target Roles")
    all_roles = ["DE", "DA", "DS", "BI", "SWE", "OTHER"]
    default_roles = [r for r in current.get("target_roles", ["DE", "DA"]) if r in all_roles]
    selected_roles = st.multiselect("Target Role Families", all_roles, default=default_roles)

    st.subheader("2. Core Skills & Technologies")
    default_skills = [s for s in current.get("target_skills", ["SQL", "Python"]) if s in all_skills]
    selected_skills = st.multiselect("Key Skills to Match", all_skills, default=default_skills)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("3. Location Preferences")
        loc_str = st.text_input(
            "Preferred Locations (comma separated)",
            value=", ".join(current.get("preferred_locations", ["Remote", "India", "Bengaluru"])),
        )
        remote_pref = st.selectbox(
            "Remote Preference",
            ["ANY", "REMOTE_ONLY", "HYBRID", "ONSITE"],
            index=["ANY", "REMOTE_ONLY", "HYBRID", "ONSITE"].index(current.get("remote_preference", "ANY")),
        )

    with c2:
        st.subheader("4. Seniority & Compensation")
        seniority = st.selectbox(
            "Target Seniority Level",
            ["ENTRY", "MID", "SENIOR", "LEAD"],
            index=["ENTRY", "MID", "SENIOR", "LEAD"].index(current.get("seniority_level", "ENTRY")),
        )
        sal_col1, sal_col2 = st.columns(2)
        with sal_col1:
            min_salary = st.number_input("Minimum Desired Salary", value=float(current.get("min_salary", 0.0)), step=50000.0)
        with sal_col2:
            currency = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP"], index=0)

    st.markdown("---")
    submitted = st.form_submit_button("💾 Save Profile & Re-score Matches", use_container_width=True)

    if submitted:
        locs = [l.strip() for l in loc_str.split(",") if l.strip()]
        try:
            upsert_profile(
                target_roles=selected_roles,
                target_skills=selected_skills,
                preferred_locations=locs,
                remote_preference=remote_pref,
                min_salary=min_salary,
                currency=currency,
                seniority_level=seniority,
            )
            refresh_mart_views()
            st.success("✅ Profile updated successfully! Your match scores have been recalculated.")
        except Exception as exc:
            st.error(f"Error saving profile: {exc}")
