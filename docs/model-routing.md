# Model Routing

The request budget is the primary routing signal. Models with the smallest
request pools are expensive or scarce and must be used least. High-volume
models handle the labour-intensive and iterative work.

| Category | Request budget per 5 hours | Assigned models | Allowed work |
|---|---:|---|---|
| Category 1 | 100-160 | `opencode-go/kimi-k3` (110), `opencode-go/grok-4.5` (120), `opencode-go/qwen3.8-max` (160) | Architecture, planning, and orchestration only |
| Category 2 | 340-1,350 | `opencode-go/glm-5.2` (880), `opencode-go/glm-5.1` (880), `opencode-go/kimi-k2.7-code` (1,350), `opencode-go/kimi-k2.6` (1,150), `opencode-go/qwen3.7-max` (340) | Critical debugging and final approval |
| Category 3 | 2,050-4,300 | `opencode-go/gpt-5.6-luna` (2,050), `opencode-go/mimo-v2.5-pro` (3,250), `opencode-go/minimax-m3` (3,200), `opencode-go/minimax-m2.7` (3,400), `opencode-go/qwen3.7-plus` (4,300), `opencode-go/qwen3.6-plus` (3,300), `opencode-go/deepseek-v4-pro` (3,450), `opencode-go/hy3` (4,300) | Review, moderate changes, and non-critical fallback work |
| Category 4 | 30,000+ | `opencode-go/mimo-v2.5` (30,100), `opencode-go/deepseek-v4-flash` (31,650) | Labour-intensive implementation, iteration, tests, and routine fixes |

## Operating rules
- Start with Category 1 only for architecture, planning, or orchestration. Never spend it on implementation, review, or routine debugging.
- Use Category 4 for the main implementation loop and the largest amount of code/test work.
- Use Category 3 for reviews and moderate changes when Category 4 is unnecessary.
- Use Category 2 only for critical debugging or final approval.
- `opencode-go/*` models require external OpenCode Go authentication. Never put provider keys in this repository.
- Prefer a fresh session per module and read only the relevant tracking document and module files.
