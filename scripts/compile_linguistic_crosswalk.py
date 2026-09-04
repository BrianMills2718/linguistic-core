"""Compile one deterministic, non-promotional Plan 0147 crosswalk artifact."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from linguistic_core.linguistic_crosswalk_v1 import (  # noqa: E402
    append_reviewed_sumo_role_records_v1,
    bind_reviewed_sumo_roles_v1,
    compile_linguistic_crosswalk_v1,
)
from linguistic_core.linguistic_source_audit_v1 import LinguisticDonorLabelAuditV1  # noqa: E402
from linguistic_core.semantic_provenance import SemanticMappingRecord  # noqa: E402
from linguistic_core.sumo_governed_crosswalk_v1 import GovernedSumoCrosswalkV1  # noqa: E402


def _read(path: Path) -> bytes:
    """Read either a plain JSON input or a deterministic gzip JSON input."""

    return gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()


def _write_gzip(path: Path, payload: object) -> None:
    """Write canonical JSON with a deterministic gzip envelope."""

    encoded = json.dumps(
        payload,
        default=lambda item: item.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode() + b"\n"
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive:
            archive.write(encoded)


def main() -> int:
    """Build once from explicit, immutable inputs and refuse accidental replacement."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--mappings", type=Path, required=True)
    parser.add_argument("--governed-sumo", type=Path, required=True)
    parser.add_argument("--donor-database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix != ".gz":
        raise ValueError("crosswalk output must be a deterministic .gz artifact")
    if args.output.exists():
        raise FileExistsError(f"refusing to replace crosswalk artifact: {args.output}")
    audit = LinguisticDonorLabelAuditV1.model_validate_json(_read(args.audit))
    mappings = tuple(
        SemanticMappingRecord.model_validate_json(line)
        for line in _read(args.mappings).decode().splitlines()
    )
    governed = GovernedSumoCrosswalkV1.model_validate_json(_read(args.governed_sumo))
    reviewed = bind_reviewed_sumo_roles_v1(
        mappings, donor_database=args.donor_database, governed=governed
    )
    crosswalk = append_reviewed_sumo_role_records_v1(
        compile_linguistic_crosswalk_v1(mappings, audit), reviewed_roles=reviewed
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_gzip(args.output, crosswalk)
    print(crosswalk.content_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
