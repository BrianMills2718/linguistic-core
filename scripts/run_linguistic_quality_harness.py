"""Emit the fail-closed Plan 0147 linguistic quality-harness receipt."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import sys

import yaml

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1  # noqa: E402
from onto_canon6.packs.linguistic_quality_harness_v1 import (  # noqa: E402
    build_linguistic_quality_preregistration_v1,
    run_blocked_linguistic_quality_harness_v1,
)
from onto_canon6.packs.linguistic_runtime_view_v1 import LinguisticRuntimeViewReceiptV1  # noqa: E402


def main() -> int:
    """Write once from explicit governed inputs, never invoke a provider or fallback."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preregistration-output", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--plan0141-observation-commit")
    parser.add_argument("--plan0141-plan-blob-sha")
    parser.add_argument("--plan0141-plan-content-sha256")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace quality receipt: {args.output}")
    if args.preregistration_output is not None and args.preregistration_output.exists():
        raise FileExistsError(
            f"refusing to replace quality preregistration: {args.preregistration_output}"
        )
    if args.preregistration_output == args.output:
        raise ValueError("quality receipt and preregistration require distinct outputs")
    preregistration_values = (
        args.baseline_manifest,
        args.plan0141_observation_commit,
        args.plan0141_plan_blob_sha,
        args.plan0141_plan_content_sha256,
    )
    if args.preregistration_output is not None and any(
        value is None for value in preregistration_values
    ):
        raise ValueError("preregistration output requires baseline and exact Plan 0141 pins")
    if args.preregistration_output is None and any(
        value is not None for value in preregistration_values
    ):
        raise ValueError("Plan 0141 preregistration pins require --preregistration-output")
    crosswalk_data = (
        gzip.open(args.crosswalk, "rb").read()
        if args.crosswalk.suffix == ".gz"
        else args.crosswalk.read_bytes()
    )
    manifest = yaml.safe_load(args.runtime_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("build"), dict):
        raise ValueError("runtime manifest requires a build object")
    runtime_view = LinguisticRuntimeViewReceiptV1.model_validate(
        manifest["build"].get("runtime_view_receipt")
    )
    receipt = run_blocked_linguistic_quality_harness_v1(
        LinguisticCrosswalkV1.model_validate_json(crosswalk_data),
        runtime_view,
    )
    preregistration = None
    if args.preregistration_output is not None:
        assert args.baseline_manifest is not None
        assert args.plan0141_observation_commit is not None
        assert args.plan0141_plan_blob_sha is not None
        assert args.plan0141_plan_content_sha256 is not None
        baseline_sha256 = hashlib.sha256(args.baseline_manifest.read_bytes()).hexdigest()
        preregistration = build_linguistic_quality_preregistration_v1(
            runtime_view,
            baseline_manifest_sha256=baseline_sha256,
            plan0141_observation_commit=args.plan0141_observation_commit,
            plan0141_plan_blob_sha=args.plan0141_plan_blob_sha,
            plan0141_plan_content_sha256=args.plan0141_plan_content_sha256,
        )
    # Materialize only after every input and requested artifact validates. This
    # prevents a bad optional preregistration from leaving a valid-looking
    # standalone receipt behind.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.preregistration_output is not None:
        args.preregistration_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(receipt.content_sha256)
    if args.preregistration_output is not None and preregistration is not None:
        args.preregistration_output.write_text(
            preregistration.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        print(preregistration.content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
