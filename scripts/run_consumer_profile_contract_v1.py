#!/usr/bin/env python3
"""Validate one versioned consumer profile contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.consumer_profile_v1 import validate_consumer_profile_contract  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "evaluation/m4_role_definitions/analytic_core_profile_contract_v1.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_consumer_profile_contract(args.manifest)
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"consumer profile {report.profile_id}@{report.profile_version}: "
            f"schemas={report.relation_schema_count}; projections={report.projection_count}; "
            f"digest={report.content_sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())