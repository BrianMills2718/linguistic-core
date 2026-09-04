"""Write one deterministic Plan 0147 crosswalk coverage receipt from explicit inputs."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from linguistic_core.framenet_projection_v1 import FrameNetProjectionV1  # noqa: E402
from linguistic_core.linguistic_crosswalk_coverage_v1 import (  # noqa: E402
    build_linguistic_crosswalk_coverage_v1,
)
from linguistic_core.linguistic_crosswalk_v1 import LinguisticCrosswalkV1  # noqa: E402
from linguistic_core.linguistic_source_audit_v1 import LinguisticDonorLabelAuditV1  # noqa: E402
from linguistic_core.linguistic_source_projection_v1 import PropBankProjectionV1  # noqa: E402
from linguistic_core.sumo_projection_v1 import SumoProjectionV1  # noqa: E402


def _read(path: Path) -> bytes:
    """Read either a plain JSON input or a deterministic gzip JSON input."""

    return gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()


def main() -> int:
    """Refuse replacement and write the complete source identity population report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--propbank", type=Path, required=True)
    parser.add_argument("--framenet", type=Path, required=True)
    parser.add_argument("--sumo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace crosswalk coverage report: {args.output}")
    report = build_linguistic_crosswalk_coverage_v1(
        LinguisticDonorLabelAuditV1.model_validate_json(_read(args.audit)),
        LinguisticCrosswalkV1.model_validate_json(_read(args.crosswalk)),
        PropBankProjectionV1.model_validate_json(_read(args.propbank)),
        FrameNetProjectionV1.model_validate_json(_read(args.framenet)),
        SumoProjectionV1.model_validate_json(_read(args.sumo)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(report.coverage_content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
