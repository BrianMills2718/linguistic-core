#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.contracts import PackRef
from linguistic_core.m4_acquisition_mapping_v1 import load_jsonl, load_m3_evidence
from linguistic_core.m4_acquisition_mapping_v2 import build_report, render_report
from linguistic_core.role_definition_v1 import load_probe_input
from linguistic_core.semantic_construction_v1 import load_cases, load_exact_pack_closure

SELECTION = ROOT / "evaluation/m4_acquisition_mapping/acquisition_mapping_cases_v1.json"
CASES = ROOT / "evaluation/semantic_construction/acquisition_cases_v1.json"
DONOR = ROOT / "ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl"
RECONCILIATION = ROOT / "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json"
ROLE_DEFINITIONS = ROOT / "evaluation/m4_role_definitions/role_definition_probe_v1.json"
OUTPUT = ROOT / "evaluation/m4_acquisition_mapping/ACQUISITION_MAPPING_REPORT_V2.md"


def main() -> int:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    declared_ids = tuple(selection["case_ids"])
    cases = tuple(
        case for case in load_cases(CASES) if case.case_id in set(declared_ids)
    )
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs", PackRef(pack_id="linguistic_core", pack_version="0.3.3")
    )
    report = build_report(
        closure=closure,
        cases=cases,
        case_manifest=str(SELECTION.relative_to(ROOT)),
        donor_mapping_asset=str(DONOR.relative_to(ROOT)),
        predicate_relation_asset="ontology_packs/linguistic_core/0.3.3/predicate_relations.jsonl",
        role_correspondence_asset="ontology_packs/linguistic_core/0.3.3/role_correspondences.jsonl",
        donor_rows=load_jsonl(DONOR),
        m3_evidence=load_m3_evidence(RECONCILIATION),
        m3_reconciliation_asset=str(RECONCILIATION.relative_to(ROOT)),
        manifest_case_ids=declared_ids,
        role_definition_asset=str(ROLE_DEFINITIONS.relative_to(ROOT)),
        role_definition_input=load_probe_input(ROLE_DEFINITIONS),
        role_definition_asset_sha256=hashlib.sha256(ROLE_DEFINITIONS.read_bytes()).hexdigest(),
    )
    OUTPUT.write_text(render_report(report), encoding="utf-8")
    if "--json" in sys.argv:
        print(report.model_dump_json(indent=2))
    else:
        print(f"M4 acquisition mapping v2: {report.base_report.passed} passed, {report.base_report.failed} failed")
        print(f"digest: {report.content_sha256}")
    return 0 if report.base_report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
