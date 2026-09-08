"""Personalized Job Matching Feed backed by mart_job_match."""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from datetime import date
import streamlit as st

from app.crud import add_note, hide_job, mark_application, save_job
from dbio import query_rows

st.set_page_config(page_title="My Matches - Job Market Pulse", page_icon="🎯", layout="wide")

st.title("🎯 My Job Matches")
st.caption("Personalized recommendations scored against your target profile using multi-factor transparent rules")

# Controls
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    min_score = st.slider("Match Score Threshold (%)", min_value=30, max_value=95, value=45, step=5)
with c2:
    selected_role = st.selectbox("Role Filter", ["All", "DE", "DA", "BI", "DS", "SWE", "OTHER"])
with c3:
    status_filter = st.selectbox("Posting Status", ["All Matches", "Open / Active Only", "Closed / Stale Only"])
with c4:
    limit = st.selectbox("Show Top Matches", [20, 50, 100], index=0)

where_clauses = [f"match_score >= {min_score}"]
params = {}

if selected_role != "All":
    where_clauses.append("role_family = :role_family")
    params["role_family"] = selected_role

if status_filter == "Open / Active Only":
    where_clauses.append("is_likely_closed = FALSE")
elif status_filter == "Closed / Stale Only":
    where_clauses.append("is_likely_closed = TRUE")

where_str = f"WHERE {' AND '.join(where_clauses)}"

sql = f"""
SELECT
  posting_id,
  company_name,
  job_title,
  role_family,
  location,
  date_posted,
  salary_min,
  salary_max,
  currency,
  posting_url,
  apply_url,
  matched_skills,
  matched_skill_count,
  is_likely_closed,
  match_score,
  skill_match_score,
  role_match_score,
  location_match_score,
  salary_match_score,
  seniority_match_score,
  recency_score
FROM mart_job_match
{where_str}
ORDER BY match_score DESC, date_posted DESC
LIMIT {limit}
"""

try:
    matches = query_rows(sql, params)
except Exception as e:
    st.warning(f"Unable to retrieve live matches: {e}")
    matches = []

st.subheader(f"Ranked Matches ({len(matches)} found)")

if not matches:
    st.info("No job matches meet the selected threshold. Try lowering the threshold slider, adjusting the status filter, or updating your target profile.")
else:
    for job in matches:
        pid = job["posting_id"]
        score = float(job["match_score"] or 0)
        is_closed = job.get("is_likely_closed")

        with st.container():
            col_info, col_score, col_act = st.columns([3, 2, 1])

            with col_info:
                st.markdown(f"### {job['job_title']} — **{job['company_name']}**")
                status_tag = "⚠️ *Likely closed / stale*" if is_closed else "🟢 *Open / Active*"
                exp_lvl = job.get("experience_level") or "UNSPECIFIED"
                is_fresh = bool(job.get("is_fresher"))
                min_exp = job.get("min_years_exp")
                max_exp = job.get("max_years_exp")

                exp_badge = ""
                if is_fresh or exp_lvl == "FRESHER":
                    exp_badge = " | 🎓 **Fresher / New Grad**"
                elif exp_lvl == "JUNIOR":
                    exp_badge = " | 💼 **Junior (1-3 yrs)**"
                elif exp_lvl == "MID":
                    exp_badge = f" | 💼 **Mid ({min_exp or 3}-{max_exp or 5} yrs)**"
                elif exp_lvl == "SENIOR":
                    exp_badge = f" | 💼 **Senior ({min_exp or 5}+ yrs)**"
                elif exp_lvl == "LEAD":
                    exp_badge = f" | 💼 **Lead ({min_exp or 8}+ yrs)**"

                st.write(f"📍 **{job['location']}** | 🏷️ Family: **`{job['role_family']}`** | 📅 Posted: {job['date_posted'] or 'Recent'}{exp_badge} | {status_tag}")
                if job.get("matched_skills"):
                    skills = [s.strip() for s in job["matched_skills"].split(",") if s.strip()]
                    st.markdown("**Matched Skills:** " + " ".join([f"`{s}`" for s in skills[:8]]))

            with col_score:
                st.metric("Overall Match", f"{score:.1f}%")
                st.progress(min(1.0, max(0.0, score / 100.0)))
                with st.expander("Score Breakdown"):
                    st.caption(f"Skill Fit (35%): {job['skill_match_score']}%")
                    st.caption(f"Role Fit (25%): {job['role_match_score']}%")
                    st.caption(f"Location Fit (15%): {job['location_match_score']}%")
                    st.caption(f"Salary Fit (10%): {job['salary_match_score']}%")
                    st.caption(f"Seniority Fit (10%): {job['seniority_match_score']}%")
                    st.caption(f"Recency (5%): {job['recency_score']}%")

            with col_act:
                apply_url = job.get("apply_url")
                posting_url = job.get("posting_url")

                if apply_url:
                    st.link_button("🚀 Apply on Site", apply_url, type="primary")
                elif posting_url:
                    st.link_button("🚀 Apply on Site", posting_url, type="primary")

                if posting_url and posting_url != apply_url:
                    st.link_button("🔗 View Posting", posting_url)

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("⭐ Bookmark", key=f"m_save_{pid}"):
                        try:
                            save_job(pid)
                            st.toast("Saved to bookmarks!", icon="⭐")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with b_col2:
                    if st.button("🚫 Dismiss", key=f"m_hide_{pid}"):
                        try:
                            hide_job(pid)
                            st.toast("Dismissed", icon="🚫")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

            st.divider()

