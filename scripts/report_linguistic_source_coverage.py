"""Build a deterministic machine-consumed Plan 0147 source coverage report."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from linguistic_core.framenet_projection_v1 import FrameNetProjectionV1  # noqa: E402
from linguistic_core.linguistic_source_coverage_v1 import build_linguistic_source_coverage_v1  # noqa: E402
from linguistic_core.linguistic_source_projection_v1 import PropBankProjectionV1  # noqa: E402
from linguistic_core.linguistic_sources_v1 import LinguisticSourceVerificationReportV1  # noqa: E402
from linguistic_core.sumo_projection_v1 import SumoProjectionV1  # noqa: E402


def _read(path: Path) -> bytes:
    """Read plain JSON or deterministic gzip JSON without mutation."""

    return gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()


def main() -> int:
    """Refuse replacement and write one closed report from exact inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--propbank", type=Path, required=True)
    parser.add_argument("--framenet", type=Path, required=True)
    parser.add_argument("--sumo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace coverage report: {args.output}")
    coverage = build_linguistic_source_coverage_v1(
        LinguisticSourceVerificationReportV1.model_validate_json(_read(args.verification)),
        PropBankProjectionV1.model_validate_json(_read(args.propbank)),
        FrameNetProjectionV1.model_validate_json(_read(args.framenet)),
        SumoProjectionV1.model_validate_json(_read(args.sumo)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(coverage.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(coverage.coverage_content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
