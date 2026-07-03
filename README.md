# Detector_Fin

Daily equity **risk assessment** combining news flow, social sentiment, and
market statistics across multiple markets (US, China, Korea initially). The
output is a *risk dossier* per ticker, not a trading signal — a human retains
final judgment.

Pipeline: **Fetcher → Aggregator → Judge (quant + LLM) → Report.** The pipeline
runs once per market per trading day at that market's own pre-open decision
time. Markets are isolated at runtime but share code and schemas.

See [`Design Contract v0.2`](#design-contract) for the full specification.

## Status

This repository is built milestone by milestone (one PR each):

| Milestone | Scope | State |
|-----------|-------|-------|
| **M1** | `schemas.py` + `MarketConfig` loader + storage layer + tests | ✅ this PR |
| M2 | Fetcher: market-data adapters (yfinance/AkShare/pykrx) + calendars | — |
| M3 | Fetcher: sentiment adapters (stocktwits, guba, naver) | — |
| M4 | Aggregator: dedup, entity resolution, sentiment, snapshot builder | — |
| M5 | Judge/quant + per-market baselines + evaluation harness | — |
| M6 | Judge/LLM + evidence dossier + GitHub Issue reporter | — |
| M7 | GitHub Actions cron workflows (one per market) | — |
| M8 | Backtest report over pilot universe | — |

## What's in M1

The **market abstraction** and the data spine everything else is built on.

### Market abstraction (`config/markets/*.yaml` → `MarketConfig`)

Every market is described entirely by config, so the same code runs each one:

```python
from detector_fin import load_market_config
from datetime import date

cn = load_market_config("CN")
cn.price_limit                       # {"main": 0.10, "star_chinext": 0.20, "st": 0.05}
cn.decision_datetime_utc(date(2026, 1, 5))   # 2026-01-05T00:30:00+00:00
cn.label_params.k                    # forward horizon for evaluation labels
```

Shipped markets: **US** (`XNYS`, no price limits), **CN** (`XSHG`, board-tiered
limits, suspensions), **KR** (`XKRX`, uniform 30% band). Timezones and trading
calendars are validated on load. `decision_datetime_utc` is the temporal cutoff
used to enforce point-in-time discipline (only data with `observed_at` strictly
before it may be used).

### Schemas (`detector_fin.schemas`)

Authoritative, mirrored from section 2 of the design contract:

- **`RawItem`** — a raw source observation (Fetcher output). Timestamps are
  validated as timezone-aware UTC instants.
- **`TickerDaySnapshot`** — per-ticker/per-day structured features; the **only**
  input the Judge accepts. Carries capped, sanitised, untrusted `top_fragments`
  (original + English) and a `MarketStats` block with limit/suspension flags.
- **`RiskScore`** — deterministic quant-path output (`0..1`, with component
  breakdown).
- **`EvidenceDossier`** — structured LLM-path output; never a buy/sell verdict.

Cross-cutting invariants enforced in code: UTC timestamps, upper-cased
`market_id`, `extra="forbid"`, fragment count/length caps, and score bounds.

### Storage (`detector_fin.storage.ParquetStore`)

Append-only parquet, partitioned on disk as
`<root>/<dataset>/market_id=<MID>/date=<YYYY-MM-DD>/part-*.parquet`.

- **Append-only:** every write creates a *new* part file; nothing is mutated or
  overwritten — a point-in-time history for free.
- **Full-fidelity round-trip:** records persist their complete model JSON plus
  flat index columns (`market_id`, `date`, `record_key`, `written_at`) for cheap
  partition pruning. Reads validate straight back into pydantic models, so
  nested structures (fragments, component maps) survive losslessly.

```python
from detector_fin import ParquetStore, TickerDaySnapshot

store = ParquetStore("data/")
store.append("snapshots", [snapshot, ...])
rows = store.read("snapshots", TickerDaySnapshot, market_id="CN")
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

Requires Python ≥ 3.11.

## Design Contract

The full v0.2 design contract (market abstraction, agents, schemas, temporal
discipline, evaluation protocol, milestones) governs this project. M1 implements
sections 0 and 2 and the storage requirements of M1; later milestones build on
this contract.
