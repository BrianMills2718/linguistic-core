#!/usr/bin/env python3
"""Execute the bounded M4 acquisition mapping receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.contracts import PackRef  # noqa: E402
from linguistic_core.m4_acquisition_mapping_v1 import (  # noqa: E402
    build_report,
    load_jsonl,
    load_m3_evidence,
    render_report,
)
from linguistic_core.semantic_construction_v1 import (  # noqa: E402
    load_cases,
    load_exact_pack_closure,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="linguistic_core@0.3.3")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the typed candidate report as JSON after writing the Markdown report",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=ROOT / "evaluation/m4_acquisition_mapping/acquisition_mapping_cases_v1.json",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=ROOT / "evaluation/m4_acquisition_mapping/ACQUISITION_MAPPING_REPORT_V1.md",
    )
    args = parser.parse_args()
    pack_id, separator, pack_version = args.pack.partition("@")
    if not separator or not pack_id or not pack_version:
        parser.error("--pack must be an exact pack_id@semantic-version")
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    if selection.get("schema_version") != "m4-acquisition-mapping-case-selection.v1":
        parser.error("selection manifest schema mismatch")
    source_cases = (args.selection.parent / selection["source_cases"]).resolve()
    declared_ids = tuple(selection["case_ids"])
    if len(set(declared_ids)) != len(declared_ids):
        parser.error("selection manifest contains duplicate case IDs")
    all_cases = tuple(load_cases(source_cases))
    cases = tuple(case for case in all_cases if case.case_id in set(declared_ids))
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs", PackRef(pack_id=pack_id, pack_version=pack_version)
    )
    donor_asset = ROOT / "ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl"
    reconciliation_asset = ROOT / "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json"
    try:
        case_manifest = str(args.selection.relative_to(ROOT))
    except ValueError:
        case_manifest = str(args.selection)
    report = build_report(
        closure=closure,
        cases=cases,
        case_manifest=case_manifest,
        donor_mapping_asset=str(donor_asset.relative_to(ROOT)),
        predicate_relation_asset="ontology_packs/linguistic_core/0.3.3/predicate_relations.jsonl",
        role_correspondence_asset="ontology_packs/linguistic_core/0.3.3/role_correspondences.jsonl",
        donor_rows=load_jsonl(donor_asset),
        m3_evidence=load_m3_evidence(reconciliation_asset),
        m3_reconciliation_asset=str(reconciliation_asset.relative_to(ROOT)),
        manifest_case_ids=declared_ids,
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_report(report), encoding="utf-8")
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(f"M4 acquisition mapping: {report.passed} passed, {report.failed} failed")
        print(f"candidate mappings: {report.candidate_count}; digest: {report.content_sha256}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
