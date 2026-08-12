# Module Graph

| Module | Status | Depends on | Exposes |
|---|---|---|---|
| Ingestion | in_progress | `config/`, `.env` | Source extractors and raw writes via `dbio` |
| Staging | in_progress | Ingestion, raw Delta tables | Normalized, deduplicated `staging_postings` |
| Warehouse | in_progress | Staging | Dimensions and fact tables |
| Marts | in_progress | Warehouse | Dashboard and export views |
| Export | in_progress | Marts | Excel tracker export and application updates |
| Exports | todo | Export | Generated workbook output |
| Dashboard | todo | Marts | Power BI or Tableau dashboard |
| Documentation | todo | All modules | Architecture, module graph, changelog, screenshots |
| Orchestration | in_progress | Ingestion, Staging, Warehouse, Marts | Manual pipeline entrypoint, run logging, cleanup |
| Configuration | todo | None | Non-secret company/source configuration |
| Tests | todo | Modules under test | Idempotency, edge-case, and parsing coverage |
