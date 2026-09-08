# Comprehensive Scaling Plan & Roadmap

This document outlines the strategic roadmap for scaling **Job Market Pulse** from a single-node data warehouse prototype into an enterprise-scale, high-throughput career intelligence platform.

---

## Architecture Evolution: Current vs. Scaled State

```
Current Architecture:
[Public ATS APIs] --> [Python Scripts] --> [Databricks Bronze] --> [Silver Staging] --> [Gold Marts] --> [Streamlit UI]

Target Scaled Architecture:
[50+ Job Boards] --> [Distributed Celery/Temporal Workers] --> [Kafka/Cloud PubSub]
                                                                     |
                                                                     v
                                                            [Databricks Lakehouse]
                                                            (Delta Liquid Clustering)
                                                                     |
                                  +----------------------------------+----------------------------------+
                                  |                                  |                                  |
                                  v                                  v                                  v
                         [Operational Cache]               [Vector Semantic Engine]            [BI & Analytics]
                           (Redis / DuckDB)                  (Databricks Mosaic AI)             (Power BI / Marts)
                                  |                                  |                                  |
                                  +----------------------------------+----------------------------------+
                                                                     |
                                                                     v
                                                    [Multi-Tenant FastAPI & Next.js/Streamlit]
                                                    [OAuth2 / Discord / Telegram Bot Alerts]
```

---

## 1. Ingestion Scaling (Crawling & Source Expansion)

### Current Limitations
- Sequential single-threaded execution for Greenhouse, Lever, and Rippling.
- Limited to 4 board connectors and static company lists in `companies.yaml`.

### Scale Roadmap
1. **Distributed Task Orchestration**:
   - Migrate crawler execution from synchronous loop to **Temporal** or **Celery + Redis**.
   - Decouple source scrapers into micro-workers that fetch boards in parallel.
2. **Connector Expansion**:
   - Add native extractors for:
     - **Workday** (Enterprise careers portals)
     - **SmartRecruiters** & **Jobvite**
     - **Ashby** (High-growth tech startups ATS)
     - **LinkedIn & Indeed Scraping Pipes** (via BrightData / ScraperAPI proxies).
3. **Smart Rate Limiting & Proxy Rotation**:
   - Implement exponential backoff, jitter, and automatic proxy rotation to prevent ATS 429 throttling.
4. **Change Data Capture (CDC)**:
   - Use MD5 payload hashing to discard unchanged job listings before warehouse ingestion, reducing bronze volume by 80%.

---

## 2. Warehouse & Storage Optimization (Databricks / Delta Lake)

### Current State
- Delta tables with 1,961 postings and ~2,000 raw payloads.
- Basic query indexing on `posting_id`.

### Scale Roadmap (1M+ Postings)
1. **Delta Lake Liquid Clustering**:
   - Enable Liquid Clustering on `fact_job_posting` and `job_posting_detail`:
     ```sql
     ALTER TABLE fact_job_posting CLUSTER BY (role_family, date_posted, source_id);
     ```
   - Automatically clusters data as it writes, eliminating the need for periodic manual `OPTIMIZE ... ZORDER`.
2. **Partitioning & Time-Travel Retention**:
   - Partition raw tables by `ingested_date`: `PARTITIONED BY (DATE(ingested_at))`.
   - Set automatic Delta retention policies:
     ```sql
     ALTER TABLE raw_greenhouse SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = 'interval 14 days');
     ```
3. **Materialized Aggregation Marts**:
   - Pre-compute heavy aggregates (`mart_posting_seasonality`, `mart_salary_summary`) as scheduled materialized Delta tables refreshed every 6 hours rather than dynamic runtime views.

---

## 3. AI, NLP & Semantic Matching Engine

### Current State
- Regex-based role family categorization and heuristic rule-based match scoring.
- Keyword and regex parsing for experience levels and fresher requirements.

### Scale Roadmap
1. **Vector Embeddings & Semantic Search**:
   - Compute sentence embeddings (using `text-embedding-3-small` or open-source `bge-large`) for every job description and store in Databricks Mosaic AI / pgvector.
   - Match candidates using cosine similarity between user resume text and job description embeddings.
2. **LLM-Powered Skill & Tech Stack Extraction**:
   - Run lightweight LLM batch jobs (e.g. `llama-3.1-8b` or `gemini-flash`) over raw job descriptions to extract:
     - Exact required tech stack (e.g. *Databricks Unity Catalog, dbt Core, Kafka Streaming*).
     - Visa sponsorship status (H-1B friendly vs. US Citizen only).
     - Exact interview rounds (take-home test, technical loop).
3. **Automated Skill Taxonomy Graph**:
   - Construct a graph connecting related skills (e.g. PySpark $\leftrightarrow$ Apache Spark $\leftrightarrow$ Databricks) so candidates with equivalent skills get full match credit.

---

## 4. Application Tier & Multi-User SaaS Scaling

### Current State
- Single-user Streamlit session using local storage and direct SQL queries.

### Scale Roadmap
1. **Query Caching & High-Performance Read Layer**:
   - Introduce **DuckDB** or **Redis** as a read-through cache for Streamlit.
   - Cache popular browse queries and filter lists in memory, reducing Databricks SQL warehouse DBU consumption by 90%.
2. **Multi-Tenant Authentication**:
   - Add Auth0 / Supabase OAuth2 (Google & GitHub login).
   - Migrate `user_profile`, `applications`, and `hidden_jobs` from single-user rows to a relational `user_id` foreign key schema.
3. **Automated Job Alerts & Webhooks**:
   - Daily automated match dispatch via **Telegram Bot**, **Discord Webhook**, or **Email Digest** (SendGrid) when new jobs matching the user's criteria are ingested.
4. **REST API Tier**:
   - Expose a high-performance **FastAPI** backend providing `/api/v1/jobs`, `/api/v1/matches`, and `/api/v1/trends` for external integrations and mobile applications.

---

## 5. Implementation Milestones

| Phase | Focus Area | Deliverables | Target Timeline |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Containerization & CI/CD** | Dockerfile, docker-compose, GitHub Actions workflow for automated test & build. | Completed |
| **Phase 2** | **Connector Expansion** | Ashby, SmartRecruiters, and Workday board connectors. | Next Sprint |
| **Phase 3** | **Performance & Caching** | Liquid Clustering, Redis caching layer, and materialized aggregate marts. | Sprint +2 |
| **Phase 4** | **Semantic AI Matching** | Mosaic AI embeddings, resume upload parser, and LLM tech-stack tagger. | Sprint +3 |
| **Phase 5** | **Multi-Tenant SaaS** | OAuth2 user authentication, custom email/Telegram alerts, and FastAPI tier. | Sprint +4 |
