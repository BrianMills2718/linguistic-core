#!/usr/bin/env python3
"""Run the bounded relation-assertion/objectification probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.relation_assertion_v1 import (  # noqa: E402
    load_relation_assertion_bundle,
    validate_relation_assertion_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evaluation/m4_role_definitions/world_substrate_objectification_v1.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_relation_assertion_bundle(load_relation_assertion_bundle(args.input))
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"relation assertions: {report.assertion_count}; "
            f"nested fillers={report.relation_assertion_filler_count}; "
            f"digest={report.content_sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())