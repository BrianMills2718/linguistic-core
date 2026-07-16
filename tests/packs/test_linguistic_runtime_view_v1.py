"""Proof that Plan 0147's sparse runtime successor cannot promote semantics."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from onto_canon6.ontology_runtime.loaders import clear_loader_caches, load_ontology_pack
from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from onto_canon6.packs.linguistic_runtime_view_v1 import (
    compile_linguistic_runtime_view_v1,
    validate_linguistic_runtime_view_v1,
)


def _crosswalk() -> LinguisticCrosswalkV1:
    """Load the committed exhaustive governed input."""

    path = Path(__file__).parents[2] / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz"
    return LinguisticCrosswalkV1.model_validate_json(gzip.open(path, "rb").read())


def test_sparse_view_loads_without_default_activation(tmp_path: Path) -> None:
    """A zero-eligible view is real, non-default, and has no aliases to leak."""

    output = tmp_path / "linguistic_core" / "0.4.0-rc1"
    receipt = compile_linguistic_runtime_view_v1(_crosswalk(), output_dir=output)
    assert receipt.eligible_record_count == 0
    assert receipt.default_activation is False
    assert validate_linguistic_runtime_view_v1(output) == receipt
    clear_loader_caches()
    loaded = load_ontology_pack("linguistic_core", "0.4.0-rc1", packs_root=tmp_path)
    assert not loaded.predicate_ids
    assert not loaded.role_ids
    assert not loaded.predicate_aliases


def test_sparse_view_rejects_row_and_hash_substitution(tmp_path: Path) -> None:
    """No caller can turn the sparse view into an unreviewed runtime assertion."""

    output = tmp_path / "linguistic_core" / "0.4.0-rc1"
    compile_linguistic_runtime_view_v1(_crosswalk(), output_dir=output)
    (output / "predicate_types.jsonl").write_text('{"predicate_id":"lc:forged"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="cannot emit runtime rows"):
        validate_linguistic_runtime_view_v1(output)
