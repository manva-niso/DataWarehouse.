"""Generate reproducible dashboard preview images from Databricks marts.

This is a preview generator for environments without a saved Power BI/Tableau
binary. It reads only mart views and writes PNGs under docs/screenshots/.
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dbio import query_rows  # noqa: E402

OUTPUT = ROOT / "docs" / "screenshots"
NAVY = "#10243e"
BLUE = "#2f80ed"
TEAL = "#20b2aa"
AMBER = "#f2a93b"
INK = "#172033"
MUTED = "#667085"
GRID = "#d9e2ec"


def _frame(title: str, subtitle: str):
    fig, ax = plt.subplots(figsize=(13, 7), facecolor="white")
    ax.set_facecolor("white")
    fig.text(0.06, 0.93, title, fontsize=24, fontweight="bold", color=NAVY)
    fig.text(0.06, 0.885, subtitle, fontsize=11, color=MUTED)
    return fig, ax


def _save(fig, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT / name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def skill_demand() -> None:
    rows = query_rows("SELECT * FROM mart_skill_demand_trend")
    totals: dict[str, int] = {}
    for row in rows:
        skill = row["skill_name"]
        totals[skill] = totals.get(skill, 0) + int(row["postings_mentioning_skill"] or 0)
    top = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:10]
    labels = [item[0] for item in reversed(top)]
    values = [item[1] for item in reversed(top)]
    fig, ax = _frame("Skill Demand", "Top skills by postings mentioning them | mart_skill_demand_trend")
    ax.barh(labels, values, color=BLUE, height=0.62)
    ax.set_xlabel("Postings mentioning skill", color=INK)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "skill-demand-trend.png")


def hiring_velocity() -> None:
    rows = query_rows("SELECT company_name, SUM(postings_posted) AS postings_posted FROM mart_hiring_velocity GROUP BY company_name ORDER BY postings_posted DESC LIMIT 12")
    rows = list(reversed(rows))
    labels = [row["company_name"] for row in rows]
    values = [int(row["postings_posted"] or 0) for row in rows]
    fig, ax = _frame("Hiring Velocity", "Top companies by posting volume | mart_hiring_velocity")
    ax.barh(labels, values, color=TEAL, height=0.62)
    ax.set_xlabel("Postings posted", color=INK)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "hiring-velocity.png")


def company_activity() -> None:
    rows = query_rows("SELECT company_name, active_postings, likely_closed_postings, total_postings FROM mart_company_activity ORDER BY total_postings DESC LIMIT 12")
    rows = list(reversed(rows))
    labels = [row["company_name"] for row in rows]
    active = [int(row["active_postings"] or 0) for row in rows]
    closed = [int(row["likely_closed_postings"] or 0) for row in rows]
    fig, ax = _frame("Company Activity", "Active versus likely closed postings | mart_company_activity")
    ax.barh(labels, active, color=BLUE, label="Active")
    ax.barh(labels, closed, left=active, color=AMBER, label="Likely closed")
    ax.set_xlabel("Postings", color=INK)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "company-activity.png")


def application_tracker() -> None:
    rows = query_rows("SELECT company_name, job_title, location, date_posted, closing_date, date_applied, is_likely_closed FROM mart_application_tracker ORDER BY date_posted DESC LIMIT 16")
    headers = ["Company", "Role", "Location", "Posted", "Closing", "Applied", "Closed?"]
    values = []
    for row in rows:
        values.append([
            str(row["company_name"] or ""),
            str(row["job_title"] or ""),
            str(row["location"] or ""),
            str(row["date_posted"] or ""),
            "Not specified" if row["closing_date"] is None else str(row["closing_date"]),
            "" if row["date_applied"] is None else str(row["date_applied"]),
            "Yes" if row["is_likely_closed"] else "No",
        ])
    fig, ax = _frame("Application Tracker", "Latest postings | mart_application_tracker")
    ax.axis("off")
    table = ax.table(cellText=values, colLabels=headers, loc="center", cellLoc="left", colLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.6)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if row == 0:
            cell.set_facecolor(NAVY)
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#f7f9fc" if row % 2 == 0 else "white")
            cell.set_text_props(color=INK)
    _save(fig, "application-tracker.png")


if __name__ == "__main__":
    skill_demand()
    hiring_velocity()
    company_activity()
    application_tracker()
    print(f"Generated dashboard previews in {OUTPUT}")
