# Architecture Decision Records

Each record has four parts: context, decision, alternatives considered, consequences. Each one has references for further reading.

| # | Decision | Status |
|---|---|---|
| [0001](0001-data-processing-stack.md) | Polars + DuckDB + Parquet; pandas only at the model boundary; uv | accepted |
| [0002](0002-scale-out-trigger.md) | When to move from a laptop to a cloud cluster | proposed (V2) |
| [0003](0003-dpe-source-remote-duckdb.md) | DPE source: ADEME's remote DuckDB | accepted |
| [0004](0004-dvf-dpe-matching-rules.md) | DVF × DPE matching rules | accepted |
| [0005](0005-dpe-coefficient-drift.md) | DPE coefficient changes: harmonise and monitor | accepted |
| [0006](0006-logging.md) | Logging | accepted |
| [0007](0007-pipeline-and-tracking.md) | Pipeline and tracking: DVC for how, MLflow for what, promotion gate | accepted |
| [0008](0008-drift-detector-design.md) | Drift detector: monitor the rule (implied coefficient), not only label PSI | accepted |
| [0009](0009-serving.md) | Serving: FastAPI for the model, Streamlit for people, IGN geocoding | accepted |
