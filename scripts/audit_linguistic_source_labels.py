"""Compare donor source labels with exact current linguistic source checkouts.

The command is read-only with respect to sources and the donor database. It
prints a compact JSON summary; ``--output`` optionally writes exhaustive
per-identifier dispositions without flooding agent context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from linguistic_core.linguistic_source_audit_v1 import (  # noqa: E402
    audit_linguistic_donor_labels_v1,
)
from linguistic_core.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)


def _source_roots(values: list[str]) -> dict[str, Path]:
    """Parse unique ``SOURCE_KEY=PATH`` arguments."""

    roots: dict[str, Path] = {}
    for value in values:
        source_key, separator, raw_path = value.partition("=")
        if not separator or not source_key or not raw_path:
            raise ValueError("--source-root values must use SOURCE_KEY=PATH")
        if source_key in roots:
            raise ValueError(f"duplicate --source-root key: {source_key}")
        roots[source_key] = Path(raw_path)
    return roots


def _write_report(path: Path, payload: bytes, *, force: bool) -> None:
    """Publish one exhaustive report atomically with explicit overwrite consent."""

    if path.exists() and not force:
        raise FileExistsError(f"output already exists; pass --force to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    """Build the agent-invocable audit parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
    )
    parser.add_argument(
        "--donor-db", type=Path, default=_REPO_ROOT / "data" / "sumo_plus.db"
    )
    parser.add_argument(
        "--source-root", action="append", default=[], metavar="SOURCE_KEY=PATH"
    )
    parser.add_argument(
        "--output", type=Path, help="Optional exhaustive JSON report output path."
    )
    parser.add_argument(
        "--force", action="store_true", help="Replace an existing --output atomically."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the exact read-only audit and emit a compact JSON readout."""

    args = build_parser().parse_args(argv)
    if args.force and args.output is None:
        raise ValueError("--force requires --output")
    manifest = load_linguistic_source_manifest_v1(args.manifest)
    report = audit_linguistic_donor_labels_v1(
        args.donor_db,
        manifest=manifest,
        source_roots=_source_roots(args.source_root),
    )
    output_sha256: str | None = None
    if args.output is not None:
        payload = (report.model_dump_json(indent=2) + "\n").encode("utf-8")
        _write_report(args.output, payload, force=args.force)
        output_sha256 = hashlib.sha256(payload).hexdigest()
    summary = {
        "schema_version": report.schema_version,
        "donor_db_sha256": report.donor_db_sha256,
        "manifest_semantic_sha256": report.manifest_semantic_sha256,
        "summaries": [item.model_dump(mode="json") for item in report.summaries],
        "comparison_count": len(report.comparisons),
        "source_syntax_issue_count": len(report.source_syntax_issues),
        "source_syntax_issues": [
            item.model_dump(mode="json") for item in report.source_syntax_issues[:20]
        ],
        "output_path": str(args.output) if args.output is not None else None,
        "output_sha256": output_sha256,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
