"""Verify exact external linguistic source checkouts against the curated manifest.

This command is offline: it never clones, downloads, mutates, or promotes a
source. Supply one ``SOURCE_KEY=PATH`` checkout or archive for every available
source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from onto_canon6.packs.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
    verify_linguistic_source_manifest_v1,
)


def _source_roots(values: list[str]) -> dict[str, Path]:
    """Parse unique ``SOURCE_KEY=PATH`` arguments without guessing keys."""

    roots: dict[str, Path] = {}
    for value in values:
        source_key, separator, raw_path = value.partition("=")
        if not separator or not source_key or not raw_path:
            raise ValueError("--source-root values must use SOURCE_KEY=PATH")
        if source_key in roots:
            raise ValueError(f"duplicate --source-root key: {source_key}")
        roots[source_key] = Path(raw_path)
    return roots


def build_parser() -> argparse.ArgumentParser:
    """Build the agent-invocable CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
        help="Strict source manifest YAML (default: config/linguistic_sources_v1.yaml).",
    )
    parser.add_argument(
        "--source-root",
        action="append",
        default=[],
        metavar="SOURCE_KEY=PATH",
        help="Local exact checkout or archive for an available source; repeat per source.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Verify the complete manifest and emit one JSON report."""

    args = build_parser().parse_args(argv)
    manifest = load_linguistic_source_manifest_v1(args.manifest)
    report = verify_linguistic_source_manifest_v1(
        manifest, source_roots=_source_roots(args.source_root)
    )
    print(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
