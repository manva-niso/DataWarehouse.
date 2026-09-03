# Job Market Pulse — ROADMAP (Phase 2)

> **Handoff document.** If you are an agent (or engineer) picking up this
> project, read this file first. It describes the exact current state, the
> approved future plan (Phases A–F), the locked-in decisions, and the
> verification commands for each phase.

---

## 1. Current State (verified 2026-08-13)

| Item | Value |
|---|---|
| Sources | Adzuna (50), Greenhouse/Figma+Stripe+Coinbase (892), Lever/leverdemo+palantir (697), Rippling/Gather (1) — all live |
| Raw payloads | 1,640 |
| Deduplicated postings | 1,602 |
| Tests | 58 passing (`uv run pytest`) |
| Warehouse | Databricks Free, Unity Catalog `workspace.default`, Delta Lake |
| Marts | `mart_application_tracker`, `mart_skill_demand_trend`, `mart_hiring_velocity`, `mart_company_activity` |
| Dashboard | spec + 4 matplotlib PNG previews in `docs/screenshots/`; no native `.pbix`/`.twbx` yet |
| Git tip | commit `fb5cf8c` (plus the roadmap-commit this file ships with) |

Complete history (architecture, every file, 12 solved errors, study order):
`docs/Job_Market_Pulse_to_read_reference_complete.md` (LOCAL ONLY, gitignored).

## 2. Step 0 — Housekeeping (DONE in the commit that ships this file)

- [x] Commit modified `AGENTS.md` (includes the Google-Workspace confirmation HARD RULE).
- [x] Commit regenerated `exports/application_tracker.xlsx`.
- [x] Remove stray `~` directory (its `.google-mcp` auth material was moved to
  `C:\Users\Asus\AppData\Local\Temp\opencode\google-mcp-backup\` — do not commit it).
- [x] Push.

## 3. Approved Plan Overview

```
4 source APIs → raw_* → staging (role classification) → warehouse
        → job_posting_detail (description, urls, salary)   [A]
        → applications (status lifecycle) + job_notes + hidden_jobs [A]
        → user_profile (DA/DE target profile)               [A]
        → archive retention (live facts stay lean)          [A2]
        → match engine → mart_job_match                     [B]
        → analytics marts (6 new)                           [D]
                    ↓                          ↓
            Streamlit live app              Power BI + Tableau
   browse/search/detail/CRUD/matches      full market analysis
                    ↓
            RAG assistant (later): "why does this job fit me?" [F]
```

---

## 4. Phase A — Data Model Extensions

### 4.1 `job_posting_detail` (new gold table)

`posting_id` (PK), `description` (plain text), `posting_url`, `apply_url`,
`salary_min`, `salary_max`, `currency`, `employment_type`, `last_seen_at`.

- Loaded via MERGE on `posting_id` (reappearing postings refresh detail).
- Keeps `fact_job_posting` lean (descriptions can be 20 KB+).
- Source of truth for search, detail page, matching, salary analytics, RAG.

Per-source field availability (verify live during build):

| Field | Adzuna | Greenhouse | Lever | Rippling |
|---|---|---|---|---|
| Description | ✅ | ✅ (HTML) | ✅ descriptionPlain | ✅ (role/company HTML) |
| Posting URL | ✅ | ✅ absolute_url | ✅ hostedUrl | ✅ url |
| Apply URL | ✅ redirect_url | ✅ absolute_url | ✅ applyUrl | ✅ url |
| Salary | ✅ min/max/currency | ❌ | ✅ salaryRange (some) | ⚠️ payRangeDetails (some) |
| Employment type | ✅ contract_type | ❌ | ✅ categories.commitment | ✅ employmentType |

### 4.2 `role_family` (new column)

- Computed in `staging/01_normalize_postings.sql` via RLIKE rules on title.
- Values: `DE`, `DA`, `DS`, `BI`, `SWE`, `OTHER` (SWE included per decision).
- Carried into `fact_job_posting` (schema change in `schema.sql` + `load_facts.sql`).
- Enables role-market analytics and profile matching at the fact level.

### 4.3 `applications` (enhanced)

Add columns: `status` (`SAVED / APPLIED / INTERVIEW / OFFER / REJECTED`),
`updated_at`. Existing rows default to `APPLIED`.

### 4.4 `job_notes` (new table)

`posting_id`, `note` (TEXT), `created_at`, `updated_at`.

### 4.5 `hidden_jobs` (new table)

`posting_id`, `hidden_at` — permanent dismiss; excluded from matches/browse.

### 4.6 `user_profile` (new table, editable in app)

Target roles (list), skills (list), preferred locations, remote flag, salary
expectation, seniority level. Seeded from `config/profile.yaml` (new file).
Single-row config table; re-scoring is instant after edits.

### 4.7 `dim_skill` expansion (25 → ~50)

Add: Looker, dbt, Redshift, Databricks, BigQuery, R, SAS, NumPy, DAX,
Power Query, A/B Testing, Data Visualization, Dashboarding, Orchestration,
CI/CD, Terraform, PostgreSQL, MySQL, MongoDB, NoSQL, REST, API, JSON,
Pipeline, MLflow, Snowflake (exists), Pandas (exists), Spark (exists), etc.

---

## 5. Phase A2 — Archive & Retention (DECIDED: archive-then-delete)

### Why

`fact_job_posting` becomes **live-only**. Postings that are past their date or
no longer on the source site are archived, then removed — saving storage —
while full history is preserved for analytics.

### Design

| Piece | Design |
|---|---|
| `fact_job_posting_archive` (new, append-only) | Full row snapshot + `archived_at` + `archive_reason` (`DATE_PASSED` / `NO_LONGER_SEEN`) |
| Archive rule (locked) | Archive+remove when `closing_date < today` OR `last_seen_at < today - 7 days` |
| Grace period (locked) | Immediate on `closing_date < today`; no extra grace day |
| `archive_stale_postings(retention_days=7) -> dict[str, int]` | New function in `orchestration/` (mirrors `cleanup_raw_tables`); idempotent; runs at end of `run_pipeline`; logs an `ARCHIVE` row in `pipeline_run_log` |
| Storage reclamation | `VACUUM fact_job_posting` (and optionally `raw_*`) as part of maintenance step (locked: automatic in maintenance command) |
| Tracker | `mart_application_tracker` unions live + archived rows **for postings you have tracked** — applied/interview history survives |
| Analytics marts | Seasonality/longevity/role-market read `live ∪ archive` |
| Matching | `mart_job_match` scores **live only** |
| Streamlit | Default filter "Live only"; **Archived** toggle (view-only) |
| Spec | AGENTS.md "never delete" edge case amended (see §9) |

### Conflict resolved

Old spec said "disappeared postings are never deleted". The new rule replaces
that for gold facts: **archive first, then delete from live**. Raw tables stay
append-only until `cleanup_raw_tables` retention runs.

---

## 6. Phase B — Matching Engine (rule-based first)

### Scoring formula (transparent, SQL-first)

```
match_score = 0.35×skill_match + 0.25×role_match + 0.15×location_match
            + 0.10×salary_match + 0.10×seniority_match + 0.05×recency
```

- `skill_match` = matched profile skills / profile skills (hard-skill bonus: SQL, Python, Spark, dbt)
- `role_match` = title RLIKE vs profile target role families
- `location_match` = profile location/remote vs posting location
- `salary_match` = posting range overlaps expectation (neutral when unknown)
- `seniority_match` = title seniority keywords vs profile level
- `recency` = newer postings score higher

### Outputs

- `mart_job_match`: one row per live posting × profile, score + per-factor breakdown.
- "New matches" feed = `match_score >= threshold` AND `first_seen_at` after last app view (`app_state` table).
- Threshold slider in the app; explainable in interviews ("why 82%").

RAG (Phase F) later adds LLM narrative on top of the same scores.

---

## 7. Phase C — Streamlit Live App (`app/`)

### Pages

| Page | Features |
|---|---|
| Browse | keyword search incl. description; filters; pagination; results count |
| Job Detail | full description, salary, Apply + Original links, skill badges, match score, source |
| My Matches | sorted by score, per-factor breakdown bars, threshold slider, "new since last visit" badges |
| My Tracker | status pipeline, click-to-advance, edit date, delete, notes |
| Profile | edit roles/skills/locations/salary → instant re-score |
| Business Analytics | read-only charts from analytics marts |
| Ask (RAG) | later, Phase F |

### Sorting / Filtering / Actions (approved matrix)

**Sort by:** date posted, match score, salary (where present), company A–Z, last seen.

**Filters:** role family, source, company, location, date range, salary min/max,
skills (multi-select), `is_likely_closed`, match-score threshold, live/archived toggle.

**Per-job actions:** open Apply URL, open Original posting, copy link, save
(`SAVED`), mark applied (pick date → `APPLIED`), advance status
(`INTERVIEW → OFFER → REJECTED`), unmark, add/edit/delete notes, hide
(`hidden_jobs`), compare 2–3 jobs side-by-side.

**Data actions:** export current filtered view → CSV/Excel (openpyxl), "Refresh now" (guarded).

### Implementation notes

- Reuses `dbio` (`query_rows` / `run_sql` / `insert_rows`) — no new DB layer.
- CRUD in `app/crud.py` (or `export/crud.py`): `save_job`, `mark_application(status, date)`,
  `unmark_application`, `add_note`, `update_note`, `delete_note`, `hide_job`,
  `upsert_profile` — all validated + tested.
- Secrets: `.env` (existing `load_dotenv` path) or `.streamlit/secrets.toml` (gitignored).
- Run: `uv run streamlit run app/Home.py`; add `streamlit` as dev dependency.
- Deployment decision: local first; Streamlit Community Cloud later (token in secrets).

---

## 8. Phase D — Business Analytics (6 new marts)

| Mart | Answers |
|---|---|
| `mart_role_market` | Postings per role family (DE/DA/DS/BI/SWE/OTHER) per month; top skills per family; salary by family |
| `mart_posting_seasonality` | Posting count by month-of-year + month × year matrix ("when are engineering jobs posted?") |
| `mart_salary_summary` | Avg/min/max salary by role family × location × source (where salary exists) |
| `mart_source_quality` | Rows per source, incomplete %, distinct companies, date coverage |
| `mart_application_funnel` | SAVED→APPLIED→INTERVIEW→OFFER→REJECTED counts over time |
| `mart_posting_longevity` | First-seen → last-seen days (how long postings stay live) |

All read `live ∪ archive` (history preserved). Seasonality includes a **source
slicer + coverage note** — Adzuna history spans 2017–2026, Rippling is thin;
without the slicer, source artifacts would be misread as market trends.

### Power BI report pages (user saves `.pbix` at desktop)

1. Overview (KPI cards, postings/month, by company)
2. Role Market (family trend, share donut, top skills)
3. Seasonality (month-of-year bar, month×year heatmap, YoY line)
4. Salary (avg by family/location, volume vs salary scatter)
5. Funnel (status funnel + trend)

### Tableau

- Decision (locked): **Tableau Desktop** (free trial, live Databricks connector)
  as primary; **Tableau Public** documented as the shareable-URL alternative
  (manual/extract refresh only — verify Databricks connector availability at build time).
- Same 6 marts; sheets + dashboard; screenshots to `docs/screenshots/`.

---

## 9. Phase E — RAG Assistant (later; needs LLM API key)

- Corpus: `job_posting_detail.description` (Phase A output).
- Embedding: chunk ~500 tokens → local vector store (FAISS/ChromaDB under `rag/`
  package; Databricks Free likely lacks vector search — verify).
- Streamlit "Ask" page: retrieve top-K by similarity + profile → LLM summarizes
  best matches "and why" with citations.
- Blocker: LLM API key (OpenAI/Anthropic/Gemini) — user has not provided one yet.
- Core pipeline stays clean: RAG is a separate package.

---

## 10. Locked Decisions (do not re-ask)

| Decision | Choice |
|---|---|
| Retention model | Archive-then-delete (never plain hard delete) |
| Unseen threshold | 7 days absent → archive |
| Closing-date rule | Archive immediately when `closing_date < today` (no grace) |
| VACUUM | Runs automatically in the maintenance step |
| Role families | DE, DA, DS, BI, SWE, OTHER (SWE included) |
| Tableau | Desktop primary, Public documented alternative |
| Matching | Rule-based SQL first, RAG narrative later |
| Skills | Expanded seed dictionary (~50), not NLP extraction |
| Deployment | Streamlit local first; cloud later |
| Matching app filter | Live postings only; archived view-only |

---

## 11. Verification Commands per Phase

```text
# Always
uv sync
uv run pytest

# Phase A (after schema + SQL changes)
uv run python -m orchestration.apply_schema
uv run python -m orchestration.run_pipeline
# verify: SELECT COUNT(*) FROM workspace.default.fact_job_posting
# verify: SELECT COUNT(*) FROM workspace.default.job_posting_detail

# Phase A2 (archive)
uv run python -c "from orchestration.run_pipeline import archive_stale_postings; print(archive_stale_postings(7))"
# verify: SELECT archive_reason, COUNT(*) FROM workspace.default.fact_job_posting_archive GROUP BY 1

# Phase B (matching)
uv run python -c "from marts.refresh import refresh_mart_views; refresh_mart_views()"
# verify: SELECT posting_id, match_score FROM workspace.default.mart_job_match ORDER BY match_score DESC LIMIT 10

# Phase C (app)
uv run streamlit run app/Home.py

# Phase D (marts + BI)
uv run python -c "from marts.refresh import refresh_mart_views; refresh_mart_views()"
uv run python dashboard/generate_screenshots.py

# Phase F (RAG) — only after LLM key
# (rag/ package instructions TBD at build time)
```

---

## 12. Docs the next agent should read

| Order | File | Purpose |
|---|---|---|
| 1 | `docs/ROADMAP.md` (this file) | Future plan + decisions |
| 2 | `AGENTS.md` | Engineering spec + contracts + archive rule |
| 3 | `README.md` | Overview + commands |
| 4 | `docs/Job_Market_Pulse_to_read_reference_complete.md` (local only) | Full history, 12 errors, study order |
| 5 | `PROJECT.md` | Technical guide + table catalogue |
| 6 | `docs/outputs-guide.md` | Consumption patterns (SQL/Python/Excel/BI) |
| 7 | `docs/integration-registry.md` + `docs/setup-checklist.md` | Credentials, endpoints, verification |