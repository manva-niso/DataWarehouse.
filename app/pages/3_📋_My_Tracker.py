import sys
from pathlib import Path

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from datetime import date
import pandas as pd
import streamlit as st

from app.crud import add_note, delete_note, get_notes, mark_application, unmark_application
from dbio import query_rows
from export.export_tracker import export_tracker_to_excel

import sys
from pathlib import Path
import urllib.parse

# Ensure repository root is in sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "dbio").is_dir() and (_p / "app").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from datetime import date
import pandas as pd
import streamlit as st

from app.crud import add_note, delete_note, get_notes, unmark_application
from dbio import query_rows
from export.export_tracker import export_tracker_to_excel

st.set_page_config(page_title="Saved Opportunities - Job Market Pulse", page_icon="📋", layout="wide")

st.title("📋 Saved Opportunities & Research Notes")
st.caption("Review your bookmarked career opportunities, direct application links, and private research notes")

sql = """
SELECT
  a.posting_id,
  a.date_applied AS date_saved,
  a.updated_at,
  COALESCE(m.job_title, f.job_title, a.posting_id) AS job_title,
  COALESCE(m.company_name, c.company_name, 'Company') AS company_name,
  COALESCE(m.location, l.location_normalized, 'Location') AS location,
  COALESCE(m.role_family, f.role_family, 'OTHER') AS role_family,
  d.apply_url,
  d.posting_url,
  d.description
FROM applications a
LEFT JOIN mart_application_tracker m ON m.posting_id = a.posting_id
LEFT JOIN fact_job_posting f ON f.posting_id = a.posting_id
LEFT JOIN dim_company c ON c.company_id = f.company_id AND c.is_current = TRUE
LEFT JOIN dim_location l ON l.location_id = f.location_id
LEFT JOIN job_posting_detail d ON d.posting_id = a.posting_id
ORDER BY a.updated_at DESC, a.date_applied DESC
"""

try:
    saved_jobs = query_rows(sql)
except Exception:
    saved_jobs = []

# Metrics & Export Bar
top_c1, top_c2 = st.columns([3, 2])
with top_c1:
    st.metric("Total Bookmarked Opportunities", len(saved_jobs))

with top_c2:
    export_path = Path("exports") / "saved_opportunities.xlsx"
    if st.button("📥 Export Saved Opportunities to Excel", use_container_width=True):
        try:
            final_path = export_tracker_to_excel(str(export_path))
            with open(final_path, "rb") as f:
                st.download_button(
                    label="Click here to download Excel file",
                    data=f.read(),
                    file_name="saved_opportunities.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        except Exception as exc:
            st.error(f"Export error: {exc}")

st.markdown("---")

if not saved_jobs:
    st.info("You haven't bookmarked any jobs yet. Browse opportunities and click **⭐ Bookmark** on any job you'd like to save for review.")
else:
    for item in saved_jobs:
        pid = item["posting_id"]
        apply_url = item.get("apply_url")
        posting_url = item.get("posting_url")

        with st.container():
            c1, c2 = st.columns([3.5, 1.5])

            with c1:
                st.markdown(f"### {item.get('job_title') or pid} — **{item.get('company_name') or 'Company'}**")
                st.write(f"🏷️ `{item.get('role_family')}` | 📍 {item.get('location') or 'Location'} | 📅 Bookmarked: {item.get('date_saved')}")

            with c2:
                if apply_url:
                    st.link_button("🚀 Apply on Career Page", apply_url, type="primary")
                elif posting_url:
                    st.link_button("🚀 Apply on Career Page", posting_url, type="primary")
                else:
                    search_q = urllib.parse.quote(f"{item.get('company_name')} {item.get('job_title')} jobs")
                    st.link_button("🔍 Search Online", f"https://www.google.com/search?q={search_q}")

                if posting_url and posting_url != apply_url:
                    st.link_button("🔗 View Original Posting", posting_url)

                if st.button("🗑️ Remove Bookmark", key=f"rm_{pid}"):
                    try:
                        unmark_application(pid)
                        st.toast("Removed from bookmarks")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            # Notes section
            with st.expander(f"📝 View Description & Notes for {item.get('job_title') or pid}"):
                if item.get("description"):
                    st.markdown("#### Job Description Preview")
                    st.write(item["description"][:1000] + ("..." if len(item["description"]) > 1000 else ""))
                    st.markdown("---")

                st.markdown("#### Private Research Notes")
                notes = get_notes(pid)
                if notes:
                    for n in notes:
                        n_col1, n_col2 = st.columns([5, 1])
                        with n_col1:
                            st.caption(f"Added on {n['created_at']}")
                            st.write(n["note"])
                        with n_col2:
                            if st.button("Delete", key=f"del_n_{n['note_id']}"):
                                delete_note(n["note_id"])
                                st.rerun()
                        st.markdown("---")
                else:
                    st.caption("No notes recorded yet.")

                new_note = st.text_input("Add interview prep or research note", key=f"new_n_{pid}")
                if st.button("Save Note", key=f"save_n_{pid}"):
                    if new_note:
                        add_note(pid, new_note)
                        st.success("Note saved")
                        st.rerun()

            st.divider()

