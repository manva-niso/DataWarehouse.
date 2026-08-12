# Architecture

## Decisions
- Build order, schema, function signatures, critical edge cases, testing priorities, and out-of-scope rules are defined in the project engineering specification.
- The first deliverable is one complete Adzuna vertical slice: raw table, staging, warehouse, first mart, Excel export, and dashboard connection.
- Databricks (Unity Catalog, catalog `workspace`, schema `default`) is the only storage system. Delta tables in one catalog/schema serve as raw (append-only), staging, and gold; the `dbio/` package wraps `databricks-sql-connector` for all Python access.
- Marts are the only source for dashboard and Excel presentation layers.
- Cross-source deduplication uses normalized company, title, and location; exact-title collisions remain a documented false-positive risk.
- External credentials, system actions, and cross-module contracts are tracked in `docs/integration-registry.md`; execution order is tracked in `docs/setup-checklist.md`.
