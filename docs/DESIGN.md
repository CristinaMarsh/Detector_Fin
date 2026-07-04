# Detector_Fin — Design Contract v0.3

Purpose: daily equity risk assessment combining news flow, social
sentiment, and market statistics across multiple markets (US, China,
Korea initially). Output is a risk dossier per ticker, not a trading
signal. Human retains final judgment.

Pipeline: Fetcher -> Aggregator -> Judge (quant path + LLM path) -> Report.
The pipeline runs once per market per trading day at that market's own
decision time. Markets are isolated at runtime but share code and schemas.

## 0. Market abstraction (new in v0.2)

Every market is described by a `MarketConfig` (config/markets/*.yaml):

MarketConfig:
  market_id            # "US", "CN", "KR"
  timezone             # "America/New_York", "Asia/Shanghai", "Asia/Seoul"
  trading_calendar     # exchange_calendars id: XNYS, XSHG, XKRX
  decision_time_local  # pre-open, local tz; e.g. 08:30 CN, 08:00 KR, 08:30 US
  currency             # USD, CNY, KRW
  price_limit          # None for US; {main: 0.10, star_chinext: 0.20,
                       #   st: 0.05} for CN; {all: 0.30} for KR
  ticker_suffixes      # e.g. [".SS", ".SZ"] for CN, [".KS", ".KQ"] for KR
  sentiment_sources    # ordered list of adapter names valid for this market
  label_params         # per-market overrides for section 4 thresholds

Rules:
- All risk labels and returns are computed in local currency. No FX
  conversion inside the pipeline; cross-market comparison happens only
  at the evaluation layer via standardized (z-scored) quantities.
- Trading halts and suspensions (frequent in CN) produce explicit
  gap records in snapshots, never silently forward-filled prices.
- A limit-hit day (close at the price limit band) is itself recorded
  as an event and used as a label component (see 4).

### Universe registry (new in v0.2.2)

The instruments the pipeline tracks live in `config/universe.yaml`. Each entry:

Instrument:
  ticker           # local suffixed ticker, e.g. 600519.SS, 069500.KS, SPY
  name_en          # English display name
  market_id        # "US", "CN", "KR"
  instrument_type  # one of {equity, etf}
  price_limit_override  # optional; fractional daily band overriding the
                        #   market default for this instrument

Rules:
- `instrument_type` is a first-class field, not an after-the-fact tag. An ETF
  is not merely a labelled equity: beyond price volatility it carries NAV
  premium/discount and tracking-error risk dimensions, and its price-limit
  regime can differ from single stocks. CN ETFs carry a 10 percent daily price
  limit; cross-border (QDII) ETFs may differ, so per-instrument limit overrides
  are allowed in the universe entry via `price_limit_override`.

## 1. Agents and responsibilities

### 1.1 Fetcher
Collects raw items from pluggable sources and persists them append-only.
- Sources implement `SourceAdapter`:
  `fetch(market: MarketConfig, since: datetime) -> list[RawItem]`.
- Adapter roster by market (priority order):
  US: market_data (yfinance), stocktwits, reddit, rss_news, x_twitter(opt)
  CN: market_data (AkShare primary, yfinance .SS/.SZ fallback),
      eastmoney_guba (stock forum posts), xueqiu, rss_news_cn,
      x_twitter(opt, for globally followed names only)
  KR: market_data (pykrx primary, yfinance .KS/.KQ fallback),
      naver_finance_board, rss_news_kr, x_twitter(opt)
- Each RawItem carries a `lang` field (en, zh, ko). Fetcher does NO
  interpretation. Fidelity, language tag, and timestamps only.
- Scraper adapters (guba, xueqiu, naver) must respect robots.txt and
  rate limits, cache aggressively, and degrade gracefully to empty
  batches rather than crash the pipeline.

### 1.2 Aggregator
Transforms RawItem streams into per-ticker, per-day structured features.
- Deduplication (minhash or embedding similarity, language-aware),
  entity resolution (mention -> local ticker; handle CN company names,
  KR names, and cross-listings: ADR vs local line are DISTINCT tickers,
  linked via an `entity_id`), event classification (earnings, guidance,
  litigation, regulation, macro, rumor, suspension), sentiment scoring,
  volume and burst statistics.
- Sentiment scoring is per-language with pinned model versions:
  en: FinBERT (or LLM scorer), zh: Chinese FinBERT variant (or LLM
  scorer), ko: KR-FinBERT-SC (or LLM scorer). Raw scores are never
  compared across languages; only within-ticker rolling z-scores
  (window >= 60 trading days) enter the Judge. Model id and version
  are persisted per score.
- Output: `TickerDaySnapshot`. This is the ONLY input the Judge accepts.
- Sanitization boundary: strips URLs, instructions, and markup from any
  text fragment that survives into the snapshot. Fragments are stored
  in original language plus a machine translation to English for the
  human reviewer; both are marked untrusted.

### 1.3 Judge
Two independent paths over the same snapshot, outputs must be reconcilable.
- Quant path (deterministic): realized volatility state, drawdown,
  parametric and historical VaR/ES, sentiment z-score vs trailing
  window, news burst intensity, limit-hit and suspension flags,
  distance-to-limit for CN/KR. Produces `RiskScore` with component
  breakdown. All thresholds read from MarketConfig.label_params.
- LLM path: produces `EvidenceDossier` (structured JSON: claims, source
  counts, uncertainty notes, contrarian case). Works on the English
  translations plus structured features; never a buy/sell verdict.
- Human-in-the-loop: pipeline opens a GitHub Issue per flagged ticker
  containing both outputs. Human verdict recorded in the issue becomes
  labeled data for future calibration.

## 2. Schemas (authoritative, mirrored in src/detector_fin/schemas.py)

RawItem:
  id, source, market_id, lang, ticker_hints[], text, url, author_hash,
  event_time (UTC), observed_at (UTC), meta{}

MarketBar:
  ticker, market_id, instrument_type, date_local, open, high, low, close,
  volume, currency, source, observed_at (UTC)

TickerDaySnapshot:
  ticker, entity_id, market_id, instrument_type, date_local,
  n_items_by_source{}, sentiment_z, sentiment_model_version, burst_score,
  event_counts{},
  top_fragments[] (max 10; each an object {text_original, text_en,
    source_name, source_url}; text fields sanitized, max 280 chars),
  market{close, ret_1d, rv_20d, drawdown_60d, limit_hit: bool,
         suspended: bool, dist_to_upper_limit, dist_to_lower_limit}

RiskScore:
  ticker, market_id, instrument_type, date_local, score (0..1),
  components{}, method_version

EvidenceDossier:
  ticker, market_id, date_local, summary_claims[], supporting_counts{},
  uncertainty_notes[], contrarian_case, model_version, prompt_hash

## 3. Temporal discipline and provenance
- Each market runs at decision_time_local converted to UTC; features
  may only use data with observed_at strictly before that instant.
- Provenance rule: source_url values must propagate VERBATIM from
  RawItem.url through the aggregator into snapshots and any downstream
  dashboard payload. Backfilling URLs by search after the fact is
  forbidden; it would fabricate the provenance chain.
- Cross-market information flow is allowed and encouraged (e.g. US
  close information is legitimately available before CN/KR open) but
  must pass through observed_at filtering like everything else.
- Backtest labels are forward-looking per market calendar, computed
  later and stored separately from features.

## 4. Evaluation protocol
Risk judgment is framed as event prediction, evaluated per market
against baselines, then meta-analyzed across markets.
- Label L(t, k), per market calendar: 1 if within next k trading days
  the ticker experiences ANY of:
  (a) realized volatility above its trailing 95th percentile,
  (b) drawdown beyond threshold d,
  (c) absolute return jump > j sigma (US only; censored under limits),
  (d) a limit-hit day (CN, KR),
  (e) a trading suspension start (CN).
  Defaults: k = 5, d = 10 percent, j = 3; all overridable in
  MarketConfig.label_params. Sensitivity analysis over thresholds is
  part of the evaluation deliverable, not an afterthought.
- Metrics: AUC, Brier score, and skill score relative to a persistence
  baseline and a market-only baseline (quant path with no text
  features). The text pipeline earns its complexity only if it beats
  the market-only baseline out of sample, per market.
- Statistical comparison: Diebold-Mariano tests on loss differentials;
  walk-forward splits per market calendar, never random shuffles.
- Cross-market questions (secondary, publishable): does sentiment
  carry more incremental value in retail-dominated markets (CN, KR)
  than in the US? Does transfer of a judge calibrated on one market
  cold-start another? These mirror the cross-market framing used in
  the author's prior electricity market research.

## 5. Milestones (one PR each)
M1 schemas.py + MarketConfig loader + storage layer (parquet,
   append-only, partitioned by market_id/date) + tests
M2 fetcher: market_data adapters (yfinance US, AkShare CN, pykrx KR),
   covering both equities and ETFs (yfinance symbols, AkShare
   fund_etf_hist_em, pykrx ETF OHLCV endpoints) + universe registry
   + trading calendars + fixtures
M3 fetcher: sentiment adapters (stocktwits, eastmoney_guba,
   naver_finance_board) + fixtures
M4 aggregator: dedup, entity resolution, per-language sentiment
   scoring, snapshot builder
M5 judge/quant.py + per-market baselines + evaluation harness
M6 judge/llm.py + evidence dossier + GitHub Issue reporter
M7 GitHub Actions cron workflows (three schedules, one per market)
   + point-in-time data branch
M8 backtest report over pilot universe: 15 liquid US names, 15 CSI 300
   constituents (mix of main board and ChiNext/STAR), 10 KOSPI 200
   constituents
M10a publication layer: static site generator + sample content fixtures
    (this section 6). LLM writing layer is M10b.

## 6. Publication layer (new in v0.3)

The display layer is a generated publication site -- an editorial daily
covering market risk, in the style of an automated market-intelligence
journal -- rendered as static HTML into `docs/` and served by GitHub Pages.
M10a is the static site generator with fixture-authored sample content; the
LLM writing layer that authors articles from snapshots is M10b. The schema and
generator are designed for M10b now but M10b is not implemented here.

### 6.1 Article schema

Article:
  id             # stable slug, also the article page filename
  kind           # one of {morning_call, brief, weekly}
  market_id      # "US", "CN", "KR"
  ticker         # optional; present for single-name briefs
  date_local     # publication date, market-local
  lang           # e.g. "zh-Hant"
  headline
  dek            # standfirst / subtitle
  body_paragraphs[]
  sources[]      # {title, url}; url propagates VERBATIM per the section 3
                 #   provenance rule -- never backfilled by search
  model_version  # empty string for fixture-authored articles; MANDATORY and
  prompt_hash    #   non-empty once an article is LLM-written (M10b)

### 6.2 Site config

`config/site.yaml`:
  site_title
  locale         # UI locale key; default "zh-Hant"
  base_url
  disclaimer_key # key into the locale file for the research disclaimer

Simplified-Chinese source strings are converted to Traditional at build time
via OpenCC (optional `publish` extra). Fixture content is authored in
Traditional; the conversion is a normalisation step, never applied to URLs.

### 6.3 Rendering guardrails

- Internal schema tokens (e.g. observed_at, prompt_hash, model_version,
  text_original, sentiment_z, instrument_type) must NEVER appear in rendered
  HTML. The publication surfaces editorial prose and sources only.
- Every article page must display its sources as clickable links.
- Every generated page must carry the research disclaimer.
- No investment-advice wording anywhere. The site reports risk; it never
  recommends a trade. A disclaimer denying advice is required, not advice.
