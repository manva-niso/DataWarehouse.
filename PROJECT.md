# PROJECT.md - Project Config

## Name
Job Market Pulse

## One-line description
End-to-end data warehouse pipeline for multi-source job postings, Databricks (Delta) star-schema modeling, dashboard marts, and Excel export.

## Modules
| Module | Folder | Depends on | Exposes |
|---|---|---|---|
| Ingestion | `ingestion/` | `config/`, `.env` | Source extractors and raw writes via `dbio` |
| Staging | `staging/` | Ingestion, raw Delta tables | Normalized, deduplicated `staging_postings` |
| Warehouse | `warehouse/` | Staging | Dimensions and fact tables |
| Marts | `marts/` | Warehouse | Dashboard and export views |
| Export | `export/` | Marts | Excel tracker export and application updates |
| Exports | `exports/` | Export | Generated workbook output |
| Dashboard | `dashboard/` | Marts | Power BI or Tableau dashboard |
| Documentation | `docs/` | All modules | Architecture, module graph, changelog, screenshots |
| Orchestration | `orchestration/` | Ingestion, Staging, Warehouse, Marts | Manual pipeline entrypoint, run logging, cleanup |
| Configuration | `config/` | None | Non-secret company/source configuration |
| Tests | `tests/` | Modules under test | Idempotency, edge-case, and parsing coverage |

## Commands
- Install: `uv sync`
- Test: `uv run pytest`
- Lint: TBD
- Run: `uv run python -m orchestration.run_pipeline` (apply DDL first with `uv run python -m orchestration.apply_schema`)

## Model tiers
| Category | Request budget per 5 hours | Models | Permitted work |
|---|---:|---|---|
| Category 1 | 100-160 | `opencode-go/kimi-k3`, `opencode-go/grok-4.5`, `opencode-go/qwen3.8-max` | Architecture, planning, and orchestration only |
| Category 2 | 340-1,350 | `opencode-go/glm-5.2`, `opencode-go/glm-5.1`, `opencode-go/kimi-k2.7-code`, `opencode-go/kimi-k2.6`, `opencode-go/qwen3.7-max` | Critical debugging and final approval |
| Category 3 | 2,050-4,300 | `opencode-go/gpt-5.6-luna`, `opencode-go/mimo-v2.5-pro`, `opencode-go/minimax-m3`, `opencode-go/minimax-m2.7`, `opencode-go/qwen3.7-plus`, `opencode-go/qwen3.6-plus`, `opencode-go/deepseek-v4-pro`, `opencode-go/hy3` | Review, moderate changes, and non-critical fallback work |
| Category 4 | 30,000+ | `opencode-go/mimo-v2.5`, `opencode-go/deepseek-v4-flash` | Labour-intensive implementation, iteration, tests, and routine fixes |

## Architecture notes (optional)
- `AGENTS.md` is the authoritative product, schema, build-order, function-contract, edge-case, testing, and scope specification.
- Follow the AGENTS.md build order exactly. Complete the Adzuna vertical slice through dashboard/export before adding Greenhouse, Lever, or Rippling.
- Raw source tables are append-only Delta bronze tables. Staging uses replaceable SQL results; warehouse loads are upserts and must be idempotent.
- Dashboard and Excel export read marts only. No separate object store, dbt project, scheduler, frontend, ML, or forecasting work.
- Model routing is quota-based: scarce Category 1 models handle architecture, planning, and orchestration only; Category 2 handles constrained debugging and approval; Category 3 handles review and moderate work; high-volume Category 4 models handle labour-intensive and iterative implementation.
- `opencode-go/*` models require the user's OpenCode Go authentication outside this repository. No API keys belong in project files.

## Anything BOOTSTRAP.md should NOT do
- Do not implement ingestion, SQL, warehouse loads, marts, dashboard logic, exports, or tests during bootstrap.
- Do not skip the AGENTS.md build order or create later-stage source modules early.
- Do not add MCP servers, plugins, recurring skills, or broad tool permissions without a concrete module requirement.
- Do not write secrets, generated exports, or runtime cache contents to the repository.
- Stop after scaffolding and wait for the next implementation instruction.
