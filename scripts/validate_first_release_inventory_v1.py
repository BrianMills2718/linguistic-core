#!/usr/bin/env python3
"""Validate M2 and emit its deterministic matrix and retained reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.first_release_inventory_v1 import (
    load_and_validate_inventory,
    render_inventory_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT / "config/first_release_inventory_v1.yaml",
    )
    parser.add_argument(
        "--matrix-output",
        type=Path,
        default=ROOT / "evaluation/first_release_inventory/coverage_matrix_v1.json",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT
        / "evaluation/first_release_inventory/first_release_inventory_report_v1.json",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=ROOT
        / "evaluation/first_release_inventory/FIRST_RELEASE_INVENTORY_REPORT_V1.md",
    )
    args = parser.parse_args()
    inventory, report = load_and_validate_inventory(ROOT, args.inventory)
    for output in (args.matrix_output, args.json_output, args.markdown_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    matrix = {
        "schema_version": "linguistic-two-axis-coverage-matrix-v1",
        "inventory_id": inventory.inventory_id,
        "inventory_revision": inventory.revision,
        "cells": [item.model_dump(mode="json") for item in report.coverage_cells],
    }
    args.matrix_output.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    args.json_output.write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(
        render_inventory_markdown(inventory, report), encoding="utf-8"
    )
    print(
        f"first-release inventory: {report.selected_donor_count} donors, "
        f"{report.included_component_count} components, {report.included_field_count} fields, "
        f"{len(report.coverage_cells)} coverage cells"
    )
    print(f"publication_status={report.publication_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
