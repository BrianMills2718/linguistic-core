"""Compile an exact SUMO checkout into deterministic JSON or JSON.gz.

The command verifies the Git source against the declared linguistic-source
manifest and refuses to replace an existing output unless ``--force`` is set.
It does not install, publish, or activate the derived projection.
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

from onto_canon6.packs.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)
from onto_canon6.packs.sumo_projection_v1 import (  # noqa: E402
    compile_sumo_projection_v1,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the agent-invocable external-source compiler interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
    )
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser


def _path_exists(path: Path) -> bool:
    """Treat dangling symlinks as occupied output paths."""

    return path.exists() or path.is_symlink()


def _write_atomic(path: Path, payload: bytes, *, force: bool) -> None:
    """Publish one completed artifact atomically without silent replacement."""

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
    """Compile the projection and print an identity/count receipt."""

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
    raw = (projection.model_dump_json() + "\n").encode("utf-8")
    if args.output is not None:
        payload = gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        _write_atomic(args.output, payload, force=args.force)
    receipt = {
        "source_commit_sha": projection.source_commit_sha,
        "source_tree_sha": projection.source_tree_sha,
        "selected_payload_sha256": projection.selected_payload_sha256,
        "projection_content_sha256": projection.projection_content_sha256,
        "module_count": len(projection.modules),
        "formula_count": projection.formula_count,
        "output": str(args.output) if args.output is not None else None,
        "published_or_activated": False,
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
