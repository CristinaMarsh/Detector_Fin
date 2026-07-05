# Detector_Fin

**Live site: https://cristinamarsh.github.io/Detector_Fin/** — the generated
publication site, served by GitHub Pages from `main` `/docs`.

Daily equity **risk assessment** combining news flow, social sentiment, and
market statistics across multiple markets (US, China, Korea initially). The
output is a *risk dossier* per ticker, not a trading signal — a human retains
final judgment.

Pipeline: **Fetcher → Aggregator → Judge (quant + LLM) → Report.** The pipeline
runs once per market per trading day at that market's own pre-open decision
time. Markets are isolated at runtime but share code and schemas.

See [`Design Contract v0.3`](#design-contract) for the full specification.

## Status

This repository is built milestone by milestone (one PR each):

| Milestone | Scope | State |
|-----------|-------|-------|
| **M1** | `schemas.py` + `MarketConfig` loader + storage layer + tests | ✅ merged |
| **M2** | Fetcher: market-data adapters (yfinance/AkShare/pykrx), equities **and ETFs**, + universe registry + calendars | ✅ merged |
| **M3a** | Fetcher: disclosure adapters (SEC EDGAR / cninfo / DART) + universe `ids` map | ✅ this PR |
| M3b | Fetcher: sentiment adapters (stocktwits, guba, naver) | — |
| M4 | Aggregator: dedup, entity resolution, sentiment, snapshot builder | — |
| M5 | Judge/quant + per-market baselines + evaluation harness | — |
| M6 | Judge/LLM + evidence dossier + GitHub Issue reporter | — |
| M7 | GitHub Actions cron workflows (one per market) | — |
| M8 | Backtest report over pilot universe | — |
| **M10a** | Publication layer: static site generator + sample content fixtures | ✅ this PR |
| M10b | Publication layer: LLM writing layer (articles from snapshots) | — |

## Viewing the site

The display layer is a generated **publication site** under [`docs/`](docs/):
`index.html` is the editorial front page, with market-desk pages, individual
article pages under `docs/articles/`, and an about page. The original data panel
is preserved unchanged at `docs/panel.html` and linked from every page footer.

- **GitHub Pages.** Served from the `docs` folder on `main` at
  **https://cristinamarsh.github.io/Detector_Fin/** once Pages is enabled:
  *Settings → Pages → Source: Deploy from a branch → Branch: `main`, Folder:
  `/docs` → Save.* Allow a minute or two after the first save.
- **Mainland-China mirror.** For more reliable access from mainland China, a
  [Tencent EdgeOne Pages](https://edgeone.ai/products/pages) site can be bound
  to this repository with the output directory set to `docs`.
- **Local preview.** No build step for viewing — serve the folder directly:

  ```bash
  python -m http.server --directory docs 8000
  # then open http://localhost:8000/
  ```

### Regenerating the site (M10a)

The site is rendered from article fixtures by a Jinja2 generator. The output is
committed, so it is live immediately after merge; regenerate after changing
fixtures or templates:

```bash
pip install -e ".[publish]"        # optional: OpenCC (Simplified → Traditional)
python -m detector_fin.publish_site
```

- **Content**: Traditional-Chinese fixtures in `data/sample_articles/` (one
  morning call per market plus per-ticker briefs), each citing resolvable
  exchange/public source pages whose URLs propagate verbatim.
- **Config & i18n**: `config/site.yaml` and `docs/i18n/zh-Hant.json`.
- **Guardrails**: internal schema tokens never appear in rendered HTML, every
  page carries the research disclaimer, and every article shows its sources as
  clickable links. Rendering is idempotent. The LLM writing layer is **M10b**.

## What's in M2

The **market-data fetcher**: real daily OHLCV bars for all three markets,
covering equities **and ETFs**.

- **Universe registry** (`config/universe.yaml` → `Instrument`): every tracked
  instrument with a first-class `instrument_type` (`equity` | `etf`) and an
  optional `price_limit_override` (CN ETFs sit at a 10% band; cross-border QDII
  ETFs may differ).
- **`MarketBar`** schema: one daily OHLCV bar in local currency, stamped with a
  UTC `observed_at` and filtered to valid exchange sessions.
- **Adapters** (`detector_fin.fetcher.market_data`): `YFinanceAdapter` (US),
  `AkshareAdapter` (CN, `fund_etf_hist_em` for ETFs), `PykrxAdapter` (KR, ETF
  OHLCV endpoints). Each strips/derives the local ticker suffix and lazily
  imports its client, so the core install needs none of them.
- **CLI**:

  ```bash
  pip install -e ".[fetch]"          # installs yfinance / akshare / pykrx
  python -m detector_fin.fetch_bars --market CN --since 2026-06-01
  ```

  Loads the universe, runs the market's adapter, and appends `MarketBar`
  records to the `bars` dataset of the `ParquetStore`.

Tests use recorded fixtures only — no live network calls.

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

The full [v0.2.2 design contract](docs/DESIGN.md) (market abstraction, universe
registry, agents, schemas, temporal discipline and provenance, evaluation
protocol, milestones) governs this project. M1 implements the storage spine and
schemas; M2 adds the universe registry and market-data fetcher (sections 0, 1.1,
and 2). Later milestones build on this contract.
