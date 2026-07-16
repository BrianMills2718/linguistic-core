"""Compile the reviewed bounded SUMO publication profile from explicit inputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from onto_canon6.packs.linguistic_sources_v1 import (  # noqa: E402
    load_linguistic_source_manifest_v1,
)
from onto_canon6.packs.sumo_projection_v1 import compile_sumo_projection_v1  # noqa: E402
from onto_canon6.packs.sumo_publication_v1 import (  # noqa: E402
    compile_sumo_publication_v1,
    load_sumo_module_publication_config_v1,
)


def _write_new(path: Path, payload: str) -> None:
    """Write one new artifact without silently replacing reviewed evidence."""

    if path.exists():
        raise FileExistsError(f"refusing to replace SUMO publication artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Compile exact source, review, context, and attribution artifacts."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--publication-config", type=Path, required=True)
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--context-output", type=Path, required=True)
    parser.add_argument("--attribution-output", type=Path, required=True)
    args = parser.parse_args(argv)
    projection = compile_sumo_projection_v1(
        load_linguistic_source_manifest_v1(args.source_manifest),
        source_checkout=args.source_checkout,
    )
    review, context, attribution = compile_sumo_publication_v1(
        projection,
        source_checkout=args.source_checkout,
        config=load_sumo_module_publication_config_v1(args.publication_config),
    )
    outputs = (args.review_output, args.context_output, args.attribution_output)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to replace SUMO publication artifacts: {existing}")
    _write_new(args.review_output, review.model_dump_json(indent=2) + "\n")
    _write_new(args.context_output, context.model_dump_json(indent=2) + "\n")
    _write_new(args.attribution_output, attribution)
    print(review.review_content_sha256)
    print(context.content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
