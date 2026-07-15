"""Compile the exact FrameNet archive into deterministic JSON or JSON.gz.

The command verifies the archive against the linguistic-source manifest, never
extracts source files, and refuses to overwrite an artifact without ``--force``.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from onto_canon6.packs.framenet_projection_v1 import (  # noqa: E402
    compile_framenet_projection_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)


def _atomic_write(path: Path, payload: bytes, *, force: bool) -> None:
    """Write a completed projection atomically with explicit overwrite consent."""

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
    """Build the agent-invocable FrameNet projection CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
    )
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Complete .json or .json.gz artifact.")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Compile a complete projection and print a compact JSON receipt."""

    args = build_parser().parse_args(argv)
    if args.force and args.output is None:
        raise ValueError("--force requires --output")
    if args.output is not None and not (
        args.output.name.endswith(".json") or args.output.name.endswith(".json.gz")
    ):
        raise ValueError("--output must end in .json or .json.gz")
    projection = compile_framenet_projection_v1(
        load_linguistic_source_manifest_v1(args.manifest),
        source_archive=args.source_archive,
    )
    output_sha256: str | None = None
    if args.output is not None:
        payload = (projection.model_dump_json(indent=2) + "\n").encode("utf-8")
        if args.output.name.endswith(".gz"):
            payload = gzip.compress(payload, mtime=0)
        _atomic_write(args.output, payload, force=args.force)
        output_sha256 = hashlib.sha256(payload).hexdigest()
    print(
        json.dumps(
            {
                "schema_version": projection.schema_version,
                "frame_count": projection.frame_count,
                "frame_element_count": projection.frame_element_count,
                "lexical_unit_declaration_count": projection.lexical_unit_declaration_count,
                "indexed_lexical_unit_count": projection.indexed_lexical_unit_count,
                "frame_relation_count": projection.frame_relation_count,
                "frame_element_relation_count": projection.frame_element_relation_count,
                "projection_content_sha256": projection.projection_content_sha256,
                "output_path": str(args.output) if args.output is not None else None,
                "output_sha256": output_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
