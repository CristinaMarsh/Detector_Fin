# CLAUDE.md — Detector_Fin

Multi-agent equity risk assessment pipeline: fetch -> aggregate -> judge.
Read docs/DESIGN.md before writing any code. It is the binding contract.

## Language and style
- All code, comments, docstrings, commit messages, and identifiers in English only.
- Python 3.11+, type hints mandatory, pydantic v2 for all data schemas.
- Formatting: ruff format + ruff check must pass before any commit.
- No notebooks in main. Exploratory work goes to /notebooks and is gitignored.

## Architecture rules
- Three packages under src/detector_fin/: fetcher, aggregator, judge.
  They communicate ONLY through the pydantic schemas defined in
  src/detector_fin/schemas.py, which mirrors docs/DESIGN.md section 2.
  Never import fetcher internals from judge or vice versa.
- Sentiment sources are implementations of the SourceAdapter protocol.
  X/Twitter is one adapter among several, never a hard dependency.
- The judge has two paths: judge/quant.py (deterministic, rule and
  statistics based, fully unit-testable) and judge/llm.py (produces an
  evidence dossier as structured JSON for human review). The LLM path
  must never execute trades, write to external systems, or be given
  raw scraped text. It only sees aggregator output.

## Data discipline (non-negotiable)
- Every stored record carries observed_at (UTC, when we fetched it) and
  event_time (UTC, when it happened). Backtests may only condition on
  data with observed_at <= decision time. Point-in-time or it does not exist.
- LLM-generated scores are generated regressors: persist model version
  and prompt hash alongside every score. Never rescore historical text
  with a newer model and present it as historical signal.
- Raw fetched text is untrusted input (prompt injection risk). It is
  sanitized and reduced to controlled schemas in the aggregator before
  any LLM sees it.

## Secrets
- Never commit credentials. Use environment variables loaded from .env
  (gitignored). Keep .env.example updated. CI uses GitHub Actions secrets.

## Testing and delivery
- Every module ships with pytest unit tests; adapters get a recorded
  fixture (no live network calls in tests).
- One module per pull request. Small, reviewable diffs. Each PR
  description states which DESIGN.md section it implements.
- If a task conflicts with DESIGN.md, stop and open an issue instead of
  improvising.
