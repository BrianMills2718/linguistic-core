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
from onto_canon6.ontology_runtime.contracts import PackRef  # noqa: E402
from onto_canon6.packs.linguistic_bundle_v1 import (  # noqa: E402
    build_linguistic_trace_manifest_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)


def _path_exists(path: Path) -> bool:
    """Treat dangling symlinks as occupied output paths."""

    return path.exists() or path.is_symlink()


def _atomic_write_many(
    outputs: tuple[tuple[Path, bytes], ...],
    *,
    force: bool,
) -> None:
    """Stage every completed payload before publishing the output set.

    A filesystem cannot replace two names in one operation, so forced
    replacements are first retained under private sibling names. If any
    publication fails, the function restores every prior output and removes
    every newly published output before surfacing the error.
    """

    for path, _payload in outputs:
        if _path_exists(path) and not force:
            raise FileExistsError(f"output already exists; pass --force to replace: {path}")
        if path.is_dir():
            raise IsADirectoryError(f"output path is a directory: {path}")

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    published: set[Path] = set()
    try:
        for path, payload in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=path.parent,
                prefix=f".{path.name}.stage-",
                delete=False,
            ) as handle:
                staged[path] = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

        # Repeat the no-overwrite check after potentially slow staging so a
        # newly occupied output is never deliberately replaced without force.
        if not force:
            for path, _payload in outputs:
                if _path_exists(path):
                    raise FileExistsError(
                        f"output already exists; pass --force to replace: {path}"
                    )

        if force:
            for path, _payload in outputs:
                if not _path_exists(path):
                    continue
                with tempfile.NamedTemporaryFile(
                    dir=path.parent,
                    prefix=f".{path.name}.backup-",
                    delete=False,
                ) as handle:
                    backup = Path(handle.name)
                backup.unlink()
                os.replace(path, backup)
                backups[path] = backup

        for path, _payload in outputs:
            os.replace(staged[path], path)
            published.add(path)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for path, _payload in reversed(outputs):
            try:
                prior_output = backups.get(path)
                if prior_output is not None and _path_exists(prior_output):
                    os.replace(prior_output, path)
                elif path in published:
                    path.unlink(missing_ok=True)
            except OSError as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                "atomic output rollback failed: " + "; ".join(rollback_errors)
            ) from exc
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, payload: bytes, *, force: bool) -> None:
    """Preserve the atomic single-output behavior through the set publisher."""

    _atomic_write_many(((path, payload),), force=force)


def _validate_paths_are_distinct(
    named_paths: tuple[tuple[str, Path], ...],
) -> None:
    """Reject lexical, symlink, and existing-hardlink collisions before reads."""

    seen: list[tuple[str, Path, Path]] = []
    for label, path in named_paths:
        resolved = path.resolve(strict=False)
        for previous_label, previous_path, previous_resolved in seen:
            same_existing_file = False
            if _path_exists(path) and _path_exists(previous_path):
                try:
                    same_existing_file = path.samefile(previous_path)
                except OSError:
                    same_existing_file = False
            if resolved == previous_resolved or same_existing_file:
                raise ValueError(
                    "FrameNet compiler inputs and outputs must be distinct; "
                    f"{previous_label} collides with {label}"
                )
        seen.append((label, path, resolved))


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
    parser.add_argument(
        "--trace-manifest-output",
        type=Path,
        help="Optional linguistic_trace_manifest_v1.json written beside --output.",
    )
    parser.add_argument(
        "--attribution",
        type=Path,
        help="Existing attribution file required with --trace-manifest-output.",
    )
    parser.add_argument(
        "--target-pack-manifest",
        type=Path,
        help="Exact immutable pack manifest required with --trace-manifest-output.",
    )
    parser.add_argument("--pack-id", default="linguistic_core")
    parser.add_argument("--pack-version", default="0.3.0")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Compile a complete projection and print a compact JSON receipt."""

    args = build_parser().parse_args(argv)
    if args.force and args.output is None:
        raise ValueError("--force requires --output")
    if args.trace_manifest_output is not None and (
        args.output is None
        or args.attribution is None
        or args.target_pack_manifest is None
    ):
        raise ValueError(
            "--trace-manifest-output requires --output, --attribution, and "
            "--target-pack-manifest"
        )
    if args.output is not None:
        named_paths = [
            ("source manifest", args.manifest),
            ("source archive", args.source_archive),
            ("projection output", args.output),
        ]
        if args.trace_manifest_output is not None:
            named_paths.extend(
                (
                    ("trace output", args.trace_manifest_output),
                    ("attribution", args.attribution),
                    ("target pack manifest", args.target_pack_manifest),
                )
            )
        _validate_paths_are_distinct(tuple(named_paths))
    if args.output is not None and not (
        args.output.name.endswith(".json") or args.output.name.endswith(".json.gz")
    ):
        raise ValueError("--output must end in .json or .json.gz")
    source_manifest = load_linguistic_source_manifest_v1(args.manifest)
    projection = compile_framenet_projection_v1(
        source_manifest,
        source_archive=args.source_archive,
    )
    output_sha256: str | None = None
    projection_payload: bytes | None = None
    if args.output is not None:
        payload = (projection.model_dump_json(indent=2) + "\n").encode("utf-8")
        if args.output.name.endswith(".gz"):
            payload = gzip.compress(payload, mtime=0)
        projection_payload = payload
        output_sha256 = hashlib.sha256(payload).hexdigest()
    trace_manifest_sha256: str | None = None
    trace_payload: bytes | None = None
    if args.trace_manifest_output is not None:
        assert projection_payload is not None
        # The trace builder validates completed projection bytes and records the
        # projection basename. A private directory lets it inspect the exact
        # payload without publishing the requested output prematurely.
        with tempfile.TemporaryDirectory(prefix="framenet-projection-") as directory:
            staged_projection = Path(directory) / args.output.name
            staged_projection.write_bytes(projection_payload)
            trace_manifest = build_linguistic_trace_manifest_v1(
                pack_ref=PackRef(pack_id=args.pack_id, pack_version=args.pack_version),
                projection_path=staged_projection,
                attribution_path=args.attribution,
                target_pack_manifest_path=args.target_pack_manifest,
                source_manifest=source_manifest,
            )
        trace_payload = (trace_manifest.model_dump_json(indent=2) + "\n").encode("utf-8")
        trace_manifest_sha256 = hashlib.sha256(trace_payload).hexdigest()
    if args.output is not None:
        assert projection_payload is not None
        outputs = [(args.output, projection_payload)]
        if args.trace_manifest_output is not None:
            assert trace_payload is not None
            outputs.append((args.trace_manifest_output, trace_payload))
        if len(outputs) == 1:
            _atomic_write(args.output, projection_payload, force=args.force)
        else:
            _atomic_write_many(tuple(outputs), force=args.force)
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
                "trace_manifest_path": (
                    str(args.trace_manifest_output)
                    if args.trace_manifest_output is not None
                    else None
                ),
                "trace_manifest_sha256": trace_manifest_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
