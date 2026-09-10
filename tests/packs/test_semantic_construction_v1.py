"""Focused tests for the M1 executable semantic-construction contract."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from linguistic_core.contracts import PackRef
from linguistic_core.semantic_construction_v1 import (
    ConstructionCaseV1,
    SemanticConstructionError,
    apply_mapping,
    evaluate_cases,
    load_cases,
    load_exact_pack_closure,
    render_report_markdown,
)

ROOT = Path(__file__).parents[2]
PACKS_ROOT = ROOT / "ontology_packs"
CASES = ROOT / "evaluation/semantic_construction/acquisition_cases_v1.json"


def _closure():
    return load_exact_pack_closure(
        PACKS_ROOT, PackRef(pack_id="linguistic_core", pack_version="0.3.3")
    )


def test_exact_declared_closure_and_acquisition_assertions_pass() -> None:
    closure = _closure()
    assert [member.pack_ref.pack_version for member in closure.members] == [
        "0.3.0",
        "0.3.1",
        "0.3.2",
        "0.3.3",
    ]
    report = evaluate_cases(load_cases(CASES), closure)
    assert report.failed == 0
    assert report.passed >= 10
    assert all(result.passed for result in report.cases)
    assert "Unsupported directions" in render_report_markdown(report)


def test_unrelated_installed_version_is_not_loaded(tmp_path: Path) -> None:
    copied = tmp_path / "packs"
    shutil.copytree(PACKS_ROOT / "linguistic_core", copied / "linguistic_core")
    rogue = copied / "linguistic_core" / "9.9.9"
    rogue.mkdir()
    (rogue / "manifest.yaml").write_text("not: a usable pack\n", encoding="utf-8")
    closure = load_exact_pack_closure(
        copied, PackRef(pack_id="linguistic_core", pack_version="0.3.3")
    )
    assert all(member.pack_ref.pack_version != "9.9.9" for member in closure.members)


def test_missing_declared_ancestor_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / "packs" / "linguistic_core"
    shutil.copytree(PACKS_ROOT / "linguistic_core" / "0.3.3", copied / "0.3.3")
    with pytest.raises(SemanticConstructionError, match="PACK_MANIFEST_UNAVAILABLE"):
        load_exact_pack_closure(
            tmp_path / "packs", PackRef(pack_id="linguistic_core", pack_version="0.3.3")
        )


def test_non_exact_version_selector_is_rejected() -> None:
    with pytest.raises(
        SemanticConstructionError, match="EXACT_SEMANTIC_VERSION_REQUIRED"
    ):
        load_exact_pack_closure(
            PACKS_ROOT, PackRef(pack_id="linguistic_core", pack_version="latest")
        )


def test_reverse_and_role_swap_operations_raise_visible_codes() -> None:
    cases = {case.case_id: case for case in load_cases(CASES)}
    with pytest.raises(
        SemanticConstructionError, match="MAPPING_DIRECTION_UNSUPPORTED"
    ):
        apply_mapping(cases["acquisition_to_purchase_rejected"], _closure())
    with pytest.raises(SemanticConstructionError, match="ROLE_FILLER_MISMATCH"):
        apply_mapping(cases["buyer_seller_swap_rejected"], _closure())


def test_unknown_operation_does_not_become_an_implicit_match() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))["cases"][0]
    payload["source"]["identity"]["predicate_id"] = "lc:sell_commerce_seller"
    payload["source"]["roles"] = {
        "lc.role.seller": "entity:acme",
        "lc.role.goods": "entity:beta",
    }
    payload["request"]["role_transforms"] = [
        {"source_role_id": "lc.role.seller", "target_role_id": "lc.role.recipient"},
        {"source_role_id": "lc.role.goods", "target_role_id": "lc.role.theme"},
    ]
    case = ConstructionCaseV1.model_validate_json(json.dumps(payload))
    with pytest.raises(
        SemanticConstructionError, match="PREDICATE_MAPPING_UNSUPPORTED"
    ):
        apply_mapping(case, _closure())
