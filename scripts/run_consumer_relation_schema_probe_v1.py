#!/usr/bin/env python3
"""Run the bounded consumer-owned relation-schema probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.role_definition_v1 import (  # noqa: E402
    build_consumer_relation_schema_probe_report,
    load_consumer_relation_schema_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evaluation/m4_role_definitions/world_substrate_relation_schema_v1.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_consumer_relation_schema_probe_report(
        load_consumer_relation_schema_probe(args.input)
    )
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"consumer relation schema: {report.relation_schema_id}; "
            f"roles={report.role_definition_count}; digest={report.content_sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
