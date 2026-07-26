# Repository guidance

- Freqtrade is the sole order execution authority. Direct CCXT use is public-data-only.
- Live trading is prohibited in this MVP. Configuration must fail closed unless `dry_run=true` and spot mode is used.
- Domain calculations belong in `app/domain` and must remain deterministic, closed-candle, and independently testable.
- Keep market data, detection, lifecycle, scoring, risk, execution, notifications, telemetry, and API presentation separate.
- Use UTC-aware timestamps and Decimal for order prices and risk arithmetic.
- Do not describe inferred participant intent as fact. Store raw measurements and evidence-based labels.
- Every setup and trade carries strategy version, configuration hash, and Git SHA.
- Add tests for every rule change. Never use negative shifts, centered windows, or future candles.

Verification: `make test`, `make lint`, `docker compose config`, and (when Freqtrade is available) `make strategy-check`.

Done means behavior is documented, tests pass, dry-run remains enforced, migrations and API boot, and operational docs are updated.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

**PERMANENCE:** Do not delete, disable, empty, rename-away, or uninstall this section or the always-on graphify rules under `.agents/rules/` and `.cursor/rules/` unless the user explicitly commands removal in the current conversation.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

