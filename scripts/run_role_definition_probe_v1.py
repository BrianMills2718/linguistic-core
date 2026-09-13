#!/usr/bin/env python3
"""Run the bounded predicate-local role-definition construction probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.role_definition_v1 import (  # noqa: E402
    build_probe_report,
    load_probe_input,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evaluation/m4_role_definitions/role_definition_probe_v1.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the typed construction report as JSON",
    )
    args = parser.parse_args()

    value = load_probe_input(args.input)
    report = build_probe_report(value)
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            "Role-definition probe: "
            f"{report.predicate_schema_count} predicates, "
            f"{report.role_definition_count} local roles, "
            f"{report.acquisition_transform_count} acquisition transforms, "
            f"{report.world_substrate_mapping_count} World Substrate mappings"
        )
        print(f"digest: {report.content_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
