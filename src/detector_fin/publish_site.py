"""CLI: render the publication site into ``docs/``.

Usage::

    python -m detector_fin.publish_site

Loads ``config/site.yaml``, the publication locale, and the article fixtures,
then renders the full static site into ``docs/``. Idempotent: run it as often
as you like; committed output only changes when the inputs change.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .publish.generator import DEFAULT_OUTPUT_DIR, build_site


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m detector_fin.publish_site",
        description="Render the Detector_Fin publication site into docs/.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help="output directory for the generated site (default: docs)",
    )
    parser.add_argument("--site-config", default=None, help="path to site.yaml")
    parser.add_argument("--articles", default=None, help="article fixtures directory")
    parser.add_argument("--locale-dir", default=None, help="locale directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    written = build_site(
        Path(args.output),
        site_config_path=args.site_config,
        articles_dir=args.articles,
        locale_dir=args.locale_dir,
    )
    print(f"Rendered {len(written)} pages into {args.output}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
