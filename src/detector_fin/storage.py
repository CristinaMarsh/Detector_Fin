"""Append-only parquet storage, partitioned by ``market_id`` / ``date``.

Milestone M1 storage layer. Design goals:

* **Append-only.** Every ``append`` writes a *new* part file; existing files are
  never mutated or overwritten. This gives us a point-in-time, audit-friendly
  history for free and matches the temporal-discipline requirements of the
  pipeline (section 3).
* **Partitioned** as ``<root>/<dataset>/market_id=<MID>/date=<YYYY-MM-DD>/``.
  Markets are isolated on disk exactly as they are at runtime.
* **Full-fidelity round-trip.** Records are pydantic models with nested
  structures (fragments, component maps, market stats). We persist the complete
  model JSON in a ``payload`` column and, alongside it, a handful of typed,
  flat columns (``market_id``, ``date``, ``record_key``, ``written_at``) for
  cheap filtering and partition pruning. Reading back parses ``payload`` so no
  information is lost to columnar flattening or schema evolution across parts.

The store is deliberately dependency-light: pyarrow for the parquet IO, no
external table/catalog service.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence, Type, TypeVar

import pyarrow as pa
import pyarrow.parquet as pq

from .schemas import StorageRecord

R = TypeVar("R", bound=StorageRecord)

_ARROW_SCHEMA = pa.schema(
    [
        ("market_id", pa.string()),
        ("date", pa.string()),  # ISO YYYY-MM-DD, matches partition value
        ("record_key", pa.string()),
        ("written_at", pa.timestamp("us", tz="UTC")),
        ("payload", pa.string()),  # full model JSON
    ]
)


def _partition_dir(root: Path, dataset: str, market_id: str, day: date) -> Path:
    return root / dataset / f"market_id={market_id}" / f"date={day.isoformat()}"


class ParquetStore:
    """A tiny append-only parquet store rooted at a directory."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # -- write ---------------------------------------------------------------

    def append(self, dataset: str, records: Sequence[R]) -> list[Path]:
        """Append ``records`` to ``dataset``. Returns the part files written.

        Records are grouped by their ``(market_id, date)`` partition key; each
        partition receives one new part file. Empty input is a no-op.
        """
        if not records:
            return []

        written_at = datetime.now(timezone.utc)
        grouped: dict[tuple[str, date], list[R]] = defaultdict(list)
        for rec in records:
            market_id, day = rec.partition_keys()
            grouped[(market_id, day)].append(rec)

        paths: list[Path] = []
        for (market_id, day), part in grouped.items():
            table = pa.table(
                {
                    "market_id": [market_id] * len(part),
                    "date": [day.isoformat()] * len(part),
                    "record_key": [r.record_key() for r in part],
                    "written_at": [written_at] * len(part),
                    "payload": [r.model_dump_json() for r in part],
                },
                schema=_ARROW_SCHEMA,
            )
            out_dir = _partition_dir(self.root, dataset, market_id, day)
            out_dir.mkdir(parents=True, exist_ok=True)
            # Unique, sortable-ish name; append-only so we never collide/clobber.
            fname = f"part-{written_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:12]}.parquet"
            path = out_dir / fname
            pq.write_table(table, path)
            paths.append(path)
        return paths

    # -- read ----------------------------------------------------------------

    def _iter_part_files(
        self,
        dataset: str,
        market_id: str | None,
        day: date | None,
    ) -> Iterable[Path]:
        base = self.root / dataset
        if not base.exists():
            return []
        if market_id is not None:
            market_dirs = [base / f"market_id={market_id}"]
        else:
            market_dirs = sorted(base.glob("market_id=*"))
        files: list[Path] = []
        for md in market_dirs:
            if not md.exists():
                continue
            if day is not None:
                date_dirs = [md / f"date={day.isoformat()}"]
            else:
                date_dirs = sorted(md.glob("date=*"))
            for dd in date_dirs:
                if dd.exists():
                    files.extend(sorted(dd.glob("*.parquet")))
        return files

    def read_table(
        self,
        dataset: str,
        market_id: str | None = None,
        day: date | None = None,
    ) -> pa.Table:
        """Read raw rows (index columns + ``payload``) as a pyarrow Table."""
        files = list(self._iter_part_files(dataset, market_id, day))
        if not files:
            return _ARROW_SCHEMA.empty_table()
        tables = [pq.read_table(f, schema=_ARROW_SCHEMA) for f in files]
        return pa.concat_tables(tables)

    def read(
        self,
        dataset: str,
        model_cls: Type[R],
        market_id: str | None = None,
        day: date | None = None,
    ) -> list[R]:
        """Read records back as validated model instances of ``model_cls``."""
        table = self.read_table(dataset, market_id=market_id, day=day)
        return [
            model_cls.model_validate_json(payload)
            for payload in table.column("payload").to_pylist()
        ]

    # -- introspection -------------------------------------------------------

    def markets(self, dataset: str) -> list[str]:
        base = self.root / dataset
        if not base.exists():
            return []
        return sorted(
            p.name.split("=", 1)[1] for p in base.glob("market_id=*") if p.is_dir()
        )

    def dates(self, dataset: str, market_id: str) -> list[date]:
        md = self.root / dataset / f"market_id={market_id}"
        if not md.exists():
            return []
        return sorted(
            date.fromisoformat(p.name.split("=", 1)[1])
            for p in md.glob("date=*")
            if p.is_dir()
        )


__all__ = ["ParquetStore"]
