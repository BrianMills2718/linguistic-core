#!/usr/bin/env python3
"""Execute and retain the M1 acquisition semantic-construction report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.contracts import PackRef
from linguistic_core.semantic_construction_v1 import (
    evaluate_cases,
    load_cases,
    load_exact_pack_closure,
    render_report_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="linguistic_core@0.3.3")
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "evaluation/semantic_construction/acquisition_cases_v1.json",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT
        / "evaluation/semantic_construction/acquisition_construction_report_v1.json",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=ROOT
        / "evaluation/semantic_construction/ACQUISITION_CONSTRUCTION_REPORT_V1.md",
    )
    args = parser.parse_args()
    pack_id, separator, pack_version = args.pack.partition("@")
    if not separator or not pack_id or not pack_version:
        parser.error("--pack must be an exact pack_id@semantic-version")
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs", PackRef(pack_id=pack_id, pack_version=pack_version)
    )
    report = evaluate_cases(load_cases(args.cases), closure)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_report_markdown(report), encoding="utf-8")
    print(f"semantic construction: {report.passed} passed, {report.failed} failed")
    print(
        "closure: "
        + " -> ".join(
            f"{member.pack_ref.pack_id}@{member.pack_ref.pack_version}"
            for member in report.pack_closure
        )
    )
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
