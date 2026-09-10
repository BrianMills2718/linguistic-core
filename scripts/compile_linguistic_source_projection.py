"""Compile an exact source-native PropBank projection as JSON or JSON.gz.

The command never modifies captured source bytes. It emits a compact JSON
summary and optionally writes the complete typed projection atomically.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from linguistic_core.linguistic_source_projection_v1 import (
    compile_propbank_projection_v1,
    load_linguistic_source_repairs_v1,
)
from linguistic_core.linguistic_sources_v1 import (
    load_linguistic_source_manifest_v1,
)


def _atomic_write(path: Path, payload: bytes, *, force: bool) -> None:
    """Publish one projection atomically with explicit overwrite consent."""

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
    """Build the agent-invocable projection parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_sources_v1.yaml",
    )
    parser.add_argument(
        "--repairs",
        type=Path,
        default=_REPO_ROOT / "config" / "linguistic_source_repairs_v1.yaml",
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, help="Complete .json or .json.gz artifact."
    )
    parser.add_argument(
        "--reconciliation-output",
        type=Path,
        help="Compact deterministic JSON receipt for the exact example projection.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Emit diagnostic projection with visible unrepaired syntax issues.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Compile the projection and emit one compact JSON summary."""

    args = build_parser().parse_args(argv)
    if args.force and args.output is None and args.reconciliation_output is None:
        raise ValueError("--force requires --output or --reconciliation-output")
    if args.output is not None and not (
        args.output.name.endswith(".json") or args.output.name.endswith(".json.gz")
    ):
        raise ValueError("--output must end in .json or .json.gz")
    projection = compile_propbank_projection_v1(
        load_linguistic_source_manifest_v1(args.manifest),
        source_root=args.source_root,
        repair_manifest=load_linguistic_source_repairs_v1(args.repairs),
        require_complete=not args.allow_incomplete,
    )
    output_sha256: str | None = None
    if args.output is not None:
        payload = (projection.model_dump_json(indent=2) + "\n").encode("utf-8")
        if args.output.name.endswith(".gz"):
            payload = gzip.compress(payload, mtime=0)
        _atomic_write(args.output, payload, force=args.force)
        output_sha256 = hashlib.sha256(payload).hexdigest()
    examples = [
        (roleset, index, example)
        for roleset in projection.rolesets
        for index, example in enumerate(roleset.examples)
    ]
    acquisition_candidates = [
        (roleset, index, example)
        for roleset, index, example in examples
        if roleset.roleset_id == "buy.01"
        and example.relation is not None
        and {"ARG0", "ARG1", "ARG2"}
        <= {argument.argument_type for argument in example.arguments}
    ]
    if not acquisition_candidates:
        raise ValueError(
            "exact projection lacks an annotated buy.01 acquisition example"
        )
    acquisition_roleset, acquisition_index, acquisition_example = (
        acquisition_candidates[0]
    )
    reconciliation = {
        "schema_version": "propbank-example-reconciliation-v1",
        "source_key": projection.source_key,
        "source_commit_sha": projection.source_commit_sha,
        "source_tree_sha": projection.source_tree_sha,
        "selected_payload_sha256": projection.selected_payload_sha256,
        "completeness": projection.completeness,
        "source_file_count": projection.source_file_count,
        "parsed_file_count": projection.parsed_file_count,
        "roleset_count": len(projection.rolesets),
        "example_count": len(examples),
        "example_relation_count": sum(
            example.relation is not None for _, _, example in examples
        ),
        "example_argument_count": sum(
            len(example.arguments) for _, _, example in examples
        ),
        "example_amr_count": sum(example.amr is not None for _, _, example in examples),
        "example_note_count": sum(
            example.note is not None for _, _, example in examples
        ),
        "projection_content_sha256": projection.projection_content_sha256,
        "acquisition_example": {
            "roleset_id": acquisition_roleset.roleset_id,
            "source_relative_path": acquisition_roleset.source_relative_path,
            "example_index": acquisition_index,
            "record": acquisition_example.model_dump(mode="json"),
        },
    }
    if args.reconciliation_output is not None:
        _atomic_write(
            args.reconciliation_output,
            (json.dumps(reconciliation, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
            force=args.force,
        )
    summary = {
        "schema_version": projection.schema_version,
        "completeness": projection.completeness,
        "source_file_count": projection.source_file_count,
        "parsed_file_count": projection.parsed_file_count,
        "roleset_count": len(projection.rolesets),
        "argument_count": sum(len(record.arguments) for record in projection.rolesets),
        "example_count": reconciliation["example_count"],
        "example_argument_count": reconciliation["example_argument_count"],
        "applied_repair_count": len(projection.applied_repairs),
        "identity_conflict_count": len(projection.identity_conflicts),
        "unrepaired_syntax_issue_count": len(projection.unrepaired_syntax_issues),
        "projection_content_sha256": projection.projection_content_sha256,
        "output_path": str(args.output) if args.output is not None else None,
        "output_sha256": output_sha256,
        "reconciliation_output_path": (
            str(args.reconciliation_output)
            if args.reconciliation_output is not None
            else None
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
