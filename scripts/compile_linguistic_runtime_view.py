"""Compile a non-default sparse linguistic runtime view from a governed crosswalk."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1  # noqa: E402
from onto_canon6.packs.linguistic_runtime_view_v1 import compile_linguistic_runtime_view_v1  # noqa: E402


def main() -> int:
    """Compile once from an explicit crosswalk input."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = gzip.open(args.crosswalk, "rb").read() if args.crosswalk.suffix == ".gz" else args.crosswalk.read_bytes()
    receipt = compile_linguistic_runtime_view_v1(
        LinguisticCrosswalkV1.model_validate_json(data), output_dir=args.output
    )
    print(receipt.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
