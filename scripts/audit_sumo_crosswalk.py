"""Audit all donor SUMO candidates against one exact source checkout.

The command compiles the pinned SUMO checkout, reads the donor SQLite database
immutably, and optionally writes a deterministic JSON or JSON.gz report. It
does not review, publish, install, activate, or promote any candidate mapping.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile


_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from linguistic_core.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)
from linguistic_core.sumo_crosswalk_audit_v1 import (  # noqa: E402
    audit_sumo_crosswalk_v1,
)
from linguistic_core.sumo_projection_v1 import (  # noqa: E402
    compile_sumo_projection_v1,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the agent-invocable read-only reconciliation interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
    )
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument(
        "--donor-db", type=Path, default=_REPO_ROOT / "data" / "sumo_plus.db"
    )
    parser.add_argument("--constraint-module", default="Merge.kif")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser


def _path_exists(path: Path) -> bool:
    """Treat dangling symlinks as occupied output paths."""

    return path.exists() or path.is_symlink()


def _write_atomic(path: Path, payload: bytes, *, force: bool) -> None:
    """Publish one completed report atomically without silent replacement."""

    if _path_exists(path) and not force:
        raise FileExistsError(f"output already exists; pass --force to replace: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.stage-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if _path_exists(path) and not force:
            raise FileExistsError(f"output already exists; pass --force to replace: {path}")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Run the audit and print a compact, non-promotional receipt."""

    args = build_parser().parse_args(argv)
    if args.force and args.output is None:
        raise ValueError("--force requires --output")
    if args.output is not None and not (
        args.output.name.endswith(".json") or args.output.name.endswith(".json.gz")
    ):
        raise ValueError("--output must end in .json or .json.gz")
    manifest = load_linguistic_source_manifest_v1(args.manifest)
    projection = compile_sumo_projection_v1(
        manifest, source_checkout=args.source_checkout
    )
    report = audit_sumo_crosswalk_v1(
        args.donor_db,
        projection=projection,
        constraint_module=args.constraint_module,
    )
    raw = (report.model_dump_json() + "\n").encode("utf-8")
    if args.output is not None:
        payload = gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        _write_atomic(args.output, payload, force=args.force)
    receipt = {
        "constraint_module": report.constraint_module,
        "constraint_rule": report.constraint_rule,
        "donor_db_sha256": report.donor_db_sha256,
        "output": str(args.output) if args.output is not None else None,
        "published_or_activated": False,
        "report_content_sha256": report.report_content_sha256,
        "review_authority": report.review_authority,
        "sumo_commit_sha": report.sumo_commit_sha,
        "sumo_projection_content_sha256": report.sumo_projection_content_sha256,
        "summary": report.summary.model_dump(mode="json"),
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
