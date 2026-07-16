"""Emit the fail-closed Plan 0147 linguistic quality-harness receipt."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import sys

import yaml

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1  # noqa: E402
from onto_canon6.packs.linguistic_quality_harness_v1 import (  # noqa: E402
    run_blocked_linguistic_quality_harness_v1,
)
from onto_canon6.packs.linguistic_runtime_view_v1 import LinguisticRuntimeViewReceiptV1  # noqa: E402


def main() -> int:
    """Write once from explicit governed inputs, never invoke a provider or fallback."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace quality receipt: {args.output}")
    crosswalk_data = gzip.open(args.crosswalk, "rb").read() if args.crosswalk.suffix == ".gz" else args.crosswalk.read_bytes()
    manifest = yaml.safe_load(args.runtime_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("build"), dict):
        raise ValueError("runtime manifest requires a build object")
    receipt = run_blocked_linguistic_quality_harness_v1(
        LinguisticCrosswalkV1.model_validate_json(crosswalk_data),
        LinguisticRuntimeViewReceiptV1.model_validate(manifest["build"].get("runtime_view_receipt")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(receipt.content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
