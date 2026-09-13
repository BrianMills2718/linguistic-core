#!/usr/bin/env python3
"""Execute one declared consumer-profile projection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.consumer_projection_v1 import execute_consumer_projection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "evaluation/m4_role_definitions/analytic_core_profile_contract_v1.json",
    )
    parser.add_argument("--projection-id", required=True)
    parser.add_argument("--assertion-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = execute_consumer_projection(
        args.manifest,
        projection_id=args.projection_id,
        source_assertion_id=args.assertion_id,
    )
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"{report.projection_id}: {report.target_view}; "
            f"loss={report.loss_receipt.loss_classification}; "
            f"digest={report.content_sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())