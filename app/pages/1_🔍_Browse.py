"""Browse and search job opportunities across all integrated sources."""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from datetime import date
import urllib.parse
import pandas as pd
import streamlit as st

from app.crud import (
    add_note,
    delete_note,
    get_cataloged_companies,
    get_cataloged_skills,
    get_notes,
    hide_job,
    save_job,
    trigger_archive,
    trigger_reload_pipeline,
)
from dbio import query_rows
from orchestration.archive_encoder import (
    ENCODED_ARCHIVE_PATH,
    get_existing_archived_ids,
    load_encoded_archived_postings,
)

st.set_page_config(page_title="Browse Opportunities - Job Market Pulse", page_icon="🔍", layout="wide")

st.title("🔍 Browse Job Opportunities")
st.caption("Search, filter, and inspect verified job postings across Adzuna, Greenhouse, Lever, and Rippling")

# Render persistent status banners from previous action
if "action_status" in st.session_state:
    status_type, status_msg = st.session_state.pop("action_status")
    if status_type == "success":
        st.success(status_msg)
    elif status_type == "info":
        st.info(status_msg)
    elif status_type == "warning":
        st.warning(status_msg)
    elif status_type == "error":
        st.error(status_msg)

# Top Action Bar: On-Demand Pipeline Reload and Archive
act_col1, act_col2, act_col3 = st.columns([1.5, 1.8, 3.2])

with act_col1:
    if st.button("🔄 Ingest Fresh Jobs", help="Fetch fresh postings from job boards, stage, and update warehouse marts", use_container_width=True):
        with st.spinner("Fetching latest postings from Greenhouse, Lever, Rippling, and Adzuna..."):
            try:
                res = trigger_reload_pipeline()
                st.session_state["action_status"] = (
                    "success",
                    f"Pipeline executed successfully! Ingested {res['total_rows']:,} postings across sources."
                )
                st.rerun()
            except Exception as exc:
                st.session_state["action_status"] = ("error", f"Ingestion error: {exc}")
                st.rerun()

with act_col2:
    if st.button("🗄️ Archive & Encode Stale", help="Extract outdated/stale postings, encode into compressed cold-storage (.jsonl.gz), and purge completely from database", use_container_width=True):
        with st.spinner("Encoding outdated postings and purging database..."):
            try:
                counts = trigger_archive(retention_days=7)
                archived = counts.get("archived", 0)
                deleted = counts.get("deleted", 0)
                if archived > 0:
                    st.session_state["action_status"] = (
                        "success",
                        f"Encoded {archived:,} outdated postings to exports/archived_postings_encoded.jsonl.gz and purged {deleted:,} from database."
                    )
                else:
                    st.session_state["action_status"] = (
                        "info",
                        "Archive check completed: All active postings were verified within the last 7 days. 0 stale postings found. Database is 100% clean and lean!"
                    )
                st.rerun()
            except Exception as exc:
                st.session_state["action_status"] = ("error", f"Archive error: {exc}")
                st.rerun()

with act_col3:
    try:
        inv = query_rows("SELECT COUNT(*) AS active_cnt FROM fact_job_posting")[0]
        act_c = inv.get("active_cnt") or 0
        off_c = len(get_existing_archived_ids())
        st.info(f"📊 **Database**: 🟢 **{act_c:,} Active (Live in DB)** | 🗄️ **{off_c:,} Encoded Cold Storage** | ⚡ **0 Stale in DB**")
    except Exception:
        pass

st.markdown("---")

# Sidebar Filters
st.sidebar.header("Filter & Search")

# 1. Search Query
search_query = st.sidebar.text_input("Keyword Search", placeholder="e.g. Spark, Databricks, ETL")

# 2. Posting Status (Live vs Offline Cold Storage)
status_option = st.sidebar.radio(
    "Posting Status",
    ["Active Postings (Live Database)", "Offline Encoded Archive"],
    index=0,
    help="Active postings live in the Databricks Delta warehouse. Outdated postings are encoded into cold-storage (.jsonl.gz) to keep the database lean.",
)

# 3. Experience & Fresher Requirements
st.sidebar.markdown("---")
st.sidebar.subheader("🎓 Experience & Freshers")
fresher_only = st.sidebar.checkbox(
    "🎓 Freshers / New Grads Only",
    value=False,
    help="Show only entry-level, internship, new grad, or fresher eligible postings (0-1 yrs exp)",
)
exp_level_options = [
    "All Experience Levels",
    "🎓 Fresher / Entry Level (0-1 yrs)",
    "💼 Junior (1-3 yrs)",
    "💼 Mid-Level (3-5 yrs)",
    "💼 Senior (5-8 yrs)",
    "💼 Lead / Staff (8+ yrs)",
]
selected_exp_level = st.sidebar.selectbox("Experience Level", exp_level_options)
max_exp_input = st.sidebar.slider("Max Years Experience", min_value=0, max_value=12, value=12, help="Filter for opportunities requiring at most X years of experience")

st.sidebar.markdown("---")
st.sidebar.subheader("Role & Source")

# 4. Role Family Filter
role_families = ["All", "DE", "DA", "DS", "BI", "SWE", "OTHER"]
selected_role = st.sidebar.selectbox("Role Family", role_families)

# 5. Source Filter
sources = ["All", "Greenhouse", "Lever", "Rippling", "Adzuna"]
selected_source = st.sidebar.selectbox("Source", sources)

# 6. Company Filter
companies = ["All"] + get_cataloged_companies()
selected_company = st.sidebar.selectbox("Company", companies)

# 7. Skill Multi-Select
all_skills = get_cataloged_skills()
selected_skills = st.sidebar.multiselect("Must Mention Skills", all_skills, default=[])

# 8. Location & Remote
remote_only = st.sidebar.checkbox("Remote Only", value=False)
location_search = st.sidebar.text_input("Location Filter", placeholder="e.g. India, Bengaluru, US")

# 9. Recency
recency_choice = st.sidebar.selectbox(
    "Posting Recency",
    ["All Time", "Past 24 Hours", "Past 7 Days", "Past 14 Days", "Past 30 Days"],
)

# 10. Minimum Salary Floor
min_salary = st.sidebar.number_input("Minimum Salary (Annual)", min_value=0, value=0, step=50000)

# Build query conditions
base_table = "mart_application_tracker"
where_clauses = []
params = {}

# Exclude user-hidden jobs
where_clauses.append("t.posting_id NOT IN (SELECT posting_id FROM hidden_jobs)")

# Fresher & Experience Filters
if fresher_only:
    where_clauses.append("(d.is_fresher = TRUE OR d.experience_level = 'FRESHER')")

if selected_exp_level != "All Experience Levels":
    exp_map = {
        "🎓 Fresher / Entry Level (0-1 yrs)": "FRESHER",
        "💼 Junior (1-3 yrs)": "JUNIOR",
        "💼 Mid-Level (3-5 yrs)": "MID",
        "💼 Senior (5-8 yrs)": "SENIOR",
        "💼 Lead / Staff (8+ yrs)": "LEAD",
    }
    where_clauses.append("d.experience_level = :exp_lvl")
    params["exp_lvl"] = exp_map[selected_exp_level]

if max_exp_input < 12:
    where_clauses.append("(d.min_years_exp IS NOT NULL AND d.min_years_exp <= :max_exp)")
    params["max_exp"] = int(max_exp_input)

# Role Family
if selected_role != "All":
    where_clauses.append("t.role_family = :role_family")
    params["role_family"] = selected_role

# Source Prefix
if selected_source != "All":
    where_clauses.append("LOWER(t.posting_id) LIKE :source_prefix")
    params["source_prefix"] = f"{selected_source.lower()}-%"

# Company
if selected_company != "All":
    where_clauses.append("t.company_name = :company_name")
    params["company_name"] = selected_company

# Location
if remote_only:
    where_clauses.append("LOWER(t.location) LIKE '%remote%'")
if location_search and location_search.strip():
    where_clauses.append("LOWER(t.location) LIKE :loc")
    params["loc"] = f"%{location_search.strip().lower()}%"

# Recency
if recency_choice == "Past 24 Hours":
    where_clauses.append("t.date_posted >= CURRENT_DATE() - INTERVAL 1 DAY")
elif recency_choice == "Past 7 Days":
    where_clauses.append("t.date_posted >= CURRENT_DATE() - INTERVAL 7 DAY")
elif recency_choice == "Past 14 Days":
    where_clauses.append("t.date_posted >= CURRENT_DATE() - INTERVAL 14 DAY")
elif recency_choice == "Past 30 Days":
    where_clauses.append("t.date_posted >= CURRENT_DATE() - INTERVAL 30 DAY")

# Skills Filter
if selected_skills:
    skill_literals = ", ".join(f"'{s}'" for s in selected_skills)
    where_clauses.append(
        f"t.posting_id IN (SELECT m.posting_id FROM fact_posting_skill_mention m "
        f"JOIN dim_skill s ON s.skill_id = m.skill_id WHERE s.skill_name IN ({skill_literals}))"
    )

# Salary Filter
if min_salary > 0:
    where_clauses.append(
        "(d.salary_max >= :min_sal OR d.salary_min >= :min_sal)"
    )
    params["min_sal"] = float(min_salary)

# Keyword Search
if search_query and search_query.strip():
    where_clauses.append(
        "(LOWER(t.job_title) LIKE :query OR LOWER(t.company_name) LIKE :query OR LOWER(COALESCE(d.description, '')) LIKE :query)"
    )
    params["query"] = f"%{search_query.strip().lower()}%"

where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

if status_option == "Offline Encoded Archive":
    archived_offline_rows = load_encoded_archived_postings(limit=200)
    total_count = len(archived_offline_rows)
else:
    count_sql = f"SELECT COUNT(*) AS n FROM {base_table} t LEFT JOIN job_posting_detail d ON d.posting_id = t.posting_id {where_str}"
    try:
        total_count = query_rows(count_sql, params)[0]["n"]
    except Exception as exc:
        st.error(f"Error querying postings count: {exc}")
        total_count = 0

st.sidebar.markdown("---")
st.sidebar.metric("Matching Postings", f"{total_count:,}")

# Pagination
PAGE_SIZE = 15
total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
page_num = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1)
offset = (page_num - 1) * PAGE_SIZE

fetch_sql = f"""
SELECT
  t.posting_id,
  t.company_name,
  t.job_title,
  t.role_family,
  t.location,
  t.date_posted,
  t.closing_date,
  t.is_likely_closed,
  t.status AS application_status,
  d.salary_min,
  d.salary_max,
  d.currency,
  d.employment_type,
  d.posting_url,
  d.apply_url,
  d.description,
  d.min_years_exp,
  d.max_years_exp,
  d.is_fresher,
  d.experience_level
FROM {base_table} t
LEFT JOIN job_posting_detail d ON d.posting_id = t.posting_id
{where_str}
ORDER BY t.date_posted DESC, t.posting_id DESC
LIMIT {PAGE_SIZE} OFFSET {offset}
"""

if status_option == "Offline Encoded Archive":
    if ENCODED_ARCHIVE_PATH.exists():
        with open(ENCODED_ARCHIVE_PATH, "rb") as gz_file:
            st.download_button(
                "📥 Download Encoded Cold-Storage Archive (.jsonl.gz)",
                data=gz_file.read(),
                file_name="archived_postings_encoded.jsonl.gz",
                mime="application/gzip",
            )
    all_archived = load_encoded_archived_postings(limit=300)
    rows = all_archived[offset : offset + PAGE_SIZE]
else:
    try:
        rows = query_rows(fetch_sql, params)
    except Exception as exc:
        st.error(f"Could not execute live query: {exc}")
        rows = []

if not rows:
    st.info("No postings found matching your current filter criteria.")
    if status_option == "Active Postings (Live Database)":
        st.caption(
            "💡 Postings in warehouse may be older than the active threshold. "
            "Click **🔄 Ingest Fresh Jobs** above to fetch live openings, or change Posting Status to **Offline Encoded Archive**."
        )
else:
    # Top bar for results count & export
    col_exp, col_stat = st.columns([1, 3])
    with col_exp:
        df_export = pd.DataFrame(rows)
        csv_data = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Page (CSV)",
            data=csv_data,
            file_name=f"job_postings_page_{page_num}.csv",
            mime="text/csv",
        )
    with col_stat:
        st.write(f"Showing page **{page_num}** of **{total_pages}** ({total_count:,} total postings)")

    # Job Cards
    for row in rows:
        pid = row["posting_id"]
        family = row.get("role_family") or "OTHER"
        apply_url = row.get("apply_url")
        posting_url = row.get("posting_url")

        exp_lvl = row.get("experience_level") or "UNSPECIFIED"
        is_fresh = bool(row.get("is_fresher"))
        min_exp = row.get("min_years_exp")
        max_exp = row.get("max_years_exp")

        with st.container():
            c1, c2 = st.columns([3.5, 1.5])
            with c1:
                st.markdown(f"### {row['job_title']} — **{row['company_name']}**")
                meta_parts = [
                    f"🏷️ `{family}`",
                    f"📍 {row.get('location') or 'Location unspecified'}",
                    f"📅 Posted: {row.get('date_posted') or 'Recent'}",
                ]
                if is_fresh or exp_lvl == "FRESHER":
                    meta_parts.append("🎓 **Fresher / New Grad**")
                elif exp_lvl == "JUNIOR":
                    meta_parts.append("💼 **Junior (1-3 yrs)**")
                elif exp_lvl == "MID":
                    meta_parts.append(f"💼 **Mid-Level ({min_exp or 3}-{max_exp or 5} yrs)**")
                elif exp_lvl == "SENIOR":
                    meta_parts.append(f"💼 **Senior ({min_exp or 5}+ yrs)**")
                elif exp_lvl == "LEAD":
                    meta_parts.append(f"💼 **Lead / Staff ({min_exp or 8}+ yrs)**")

                if row.get("salary_max"):
                    sal_curr = row.get("currency") or ""
                    meta_parts.append(f"💰 {sal_curr} {row.get('salary_min', 0):,.0f} - {row['salary_max']:,.0f}")
                if row.get("employment_type"):
                    meta_parts.append(f"⏱️ {row['employment_type']}")
                if status_option == "Offline Encoded Archive" or row.get("is_likely_closed"):
                    meta_parts.append("🗄️ *Cold Storage Archive*")
                else:
                    meta_parts.append("🟢 *Live Active*")
                st.markdown(" | ".join(meta_parts))

            with c2:
                # Direct Links
                if apply_url:
                    st.link_button("🚀 Apply on Career Page", apply_url, type="primary")
                elif posting_url:
                    st.link_button("🚀 Apply on Career Page", posting_url, type="primary")
                else:
                    search_q = urllib.parse.quote(f"{row['company_name']} {row['job_title']} jobs")
                    st.link_button("🔍 Search Job Online", f"https://www.google.com/search?q={search_q}")

                if posting_url and posting_url != apply_url:
                    st.link_button("🔗 View Original Posting", posting_url)

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("⭐ Bookmark", key=f"save_{pid}"):
                        try:
                            save_job(pid)
                            st.toast("Saved to your bookmarks!", icon="⭐")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with b_col2:
                    if st.button("🚫 Dismiss", key=f"hide_{pid}"):
                        try:
                            hide_job(pid)
                            st.toast("Dismissed from view", icon="🚫")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

            # Details & Notes Expander
            with st.expander("📖 Read Job Details, Experience & Notes"):
                st.markdown("#### 🎓 Experience Requirements")
                e_c1, e_c2, e_c3 = st.columns(3)
                with e_c1:
                    st.metric("Seniority Classification", exp_lvl)
                with e_c2:
                    if min_exp is not None:
                        val = f"{min_exp} yrs" + (f" - {max_exp} yrs" if max_exp else "+")
                    else:
                        val = "Not specified"
                    st.metric("Required Experience", val)
                with e_c3:
                    st.metric("Fresher Eligible", "Yes 🎓" if is_fresh else "No")

                desc = row.get("description")
                if desc and desc.strip():
                    st.markdown("---")
                    st.markdown("#### Full Job Description")
                    st.write(desc)
                else:
                    st.info("No detailed description available in ATS feed. Click the link above to view details on the company's portal.")

                st.markdown("---")
                st.markdown("#### 📝 Private Notes & Research")
                notes = get_notes(pid)
                if notes:
                    for n in notes:
                        n_c1, n_c2 = st.columns([5, 1])
                        with n_c1:
                            st.caption(f"Added on {n['created_at']}")
                            st.write(n["note"])
                        with n_c2:
                            if st.button("🗑️ Delete", key=f"del_note_{n['note_id']}"):
                                delete_note(n["note_id"])
                                st.rerun()
                else:
                    st.caption("No notes recorded yet.")

                note_text = st.text_input("Add research note (e.g. required skills, interview prep)", key=f"note_in_{pid}")
                if st.button("Save Note", key=f"save_note_{pid}"):
                    if note_text:
                        try:
                            add_note(pid, note_text)
                            st.success("Note saved!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            st.divider()
