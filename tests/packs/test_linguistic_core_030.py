"""Plan 0140 Slice A tests for reproducible linguistic_core@0.3.0.

The successor pack is a side-by-side, byte-stable build whose nine runtime
artifacts remain exactly equal to immutable 0.2.0. Provenance assets are hashed
and traceability-only; the runtime alias loader remains unchanged.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import TypedDict

import pytest
import yaml

from onto_canon6.ontology_runtime import (  # type: ignore[import-untyped]
    clear_loader_caches,
    load_ontology_pack,
)
from onto_canon6.packs.role_slots_lookup import RoleSlotsError  # type: ignore[import-untyped]
from scripts.compile_linguistic_core_pack import (
    CompileStats,
    LinguisticCoreCompileError,
    compile_pack,
    validate_compiled_pack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "sumo_plus.db"
BASELINE_PACK = REPO_ROOT / "ontology_packs" / "linguistic_core" / "0.2.0"
BUILD_TIMESTAMP = "2026-07-12T19:00:00Z"
RUNTIME_FILES = (
    "aliases.jsonl",
    "constraints.jsonl",
    "entity_types.jsonl",
    "hierarchy_edges.jsonl",
    "predicate_role_edges.jsonl",
    "predicate_types.jsonl",
    "role_types.jsonl",
    "source_mappings.jsonl",
    "value_types.jsonl",
)


class CompiledPair(TypedDict):
    """Two independently compiled candidate directories plus build statistics."""

    first_root: Path
    first: Path
    second: Path
    stats: CompileStats


def _sha256(path: Path) -> str:
    """Return the digest of exact artifact bytes."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, object]]:
    """Load one JSONL artifact as typed-enough test rows."""

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def compiled_pair(tmp_path_factory: pytest.TempPathFactory) -> CompiledPair:
    """Build the full candidate twice from identical declared inputs."""

    root = tmp_path_factory.mktemp("linguistic-core-030")
    first_root = root / "first"
    second_root = root / "second"
    first = first_root / "linguistic_core" / "0.3.0"
    second = second_root / "linguistic_core" / "0.3.0"
    stats = compile_pack(
        DB_PATH,
        first,
        pack_version="0.3.0",
        build_timestamp=BUILD_TIMESTAMP,
    )
    compile_pack(
        DB_PATH,
        second,
        pack_version="0.3.0",
        build_timestamp=BUILD_TIMESTAMP,
    )
    return {"first_root": first_root, "first": first, "second": second, "stats": stats}


def test_two_full_builds_are_byte_identical(compiled_pair: CompiledPair) -> None:
    """Identical DB/version/timestamp inputs produce identical complete directories."""

    first = compiled_pair["first"]
    second = compiled_pair["second"]
    assert {path.name for path in first.iterdir()} == {path.name for path in second.iterdir()}
    assert {
        path.name: _sha256(path) for path in first.iterdir()
    } == {path.name: _sha256(path) for path in second.iterdir()}


def test_declared_timestamp_changes_only_manifest(
    compiled_pair: CompiledPair,
    tmp_path: Path,
) -> None:
    """Changing declared build time cannot perturb semantic artifact bytes."""

    changed = tmp_path / "linguistic_core" / "0.3.0"
    compile_pack(
        DB_PATH,
        changed,
        pack_version="0.3.0",
        build_timestamp="2026-07-12T19:00:01Z",
    )
    baseline = compiled_pair["first"]
    for filename in {
        *RUNTIME_FILES,
        "predicate_canon_index.jsonl",
        "semantic_sources.yaml",
        "semantic_mappings.jsonl",
    }:
        assert (changed / filename).read_bytes() == (baseline / filename).read_bytes()
    assert (changed / "manifest.yaml").read_bytes() != (baseline / "manifest.yaml").read_bytes()


def test_successor_runtime_bytes_equal_immutable_020(compiled_pair: CompiledPair) -> None:
    """The successor adds provenance without changing any runtime semantic byte."""

    candidate = compiled_pair["first"]
    for filename in RUNTIME_FILES:
        assert (candidate / filename).read_bytes() == (BASELINE_PACK / filename).read_bytes()


def test_full_inventory_counts_and_provenance_reconcile(compiled_pair: CompiledPair) -> None:
    """Every declared donor/source/hierarchy category has exhaustive trace rows."""

    candidate = compiled_pair["first"]
    stats = compiled_pair["stats"]
    assert stats == {
        "predicate_count": 4669,
        "role_slot_count": 11890,
        "role_type_count": 903,
        "entity_type_count": 555,
        "hierarchy_edge_count": 689,
        "predicate_role_edge_count": 11890,
        "constraint_count": 11620,
        "source_mapping_count": 16546,
        "semantic_mapping_count": 46150,
        "canon_index_count": 4669,
        "blank_named_label_count": 0,
    }
    rows = _jsonl(candidate / "semantic_mappings.jsonl")
    by_source: dict[str, int] = {}
    for row in rows:
        source_key = str(row["source_key"])
        by_source[source_key] = by_source.get(source_key, 0) + 1
        assert row["runtime_alias"] is False
        assert row["source_verified"] is False
    assert by_source == {
        "framenet_candidate": 2263,
        "onto_canon_sumo_plus": 16559,
        "propbank_nltk": 16546,
        "sumo_donor_types": 10782,
    }
    hierarchy_rows = [row for row in rows if row["canonical_kind"] == "hierarchy_edge"]
    assert len(hierarchy_rows) == 689
    assert all(row["relation"] == "subtype_of" for row in hierarchy_rows)


def test_manifest_hashes_cover_exact_nonmanifest_inventory(compiled_pair: CompiledPair) -> None:
    """The manifest binds every exact emitted semantic/runtime artifact byte."""

    candidate = compiled_pair["first"]
    manifest = yaml.safe_load((candidate / "manifest.yaml").read_text(encoding="utf-8"))
    hashes = manifest["build"]["artifact_sha256"]
    assert set(hashes) == {path.name for path in candidate.iterdir()} - {"manifest.yaml"}
    assert hashes == {filename: _sha256(candidate / filename) for filename in hashes}
    assert set(manifest["content"].values()) == set(RUNTIME_FILES)
    assert manifest["provenance"] == {
        "schema_version": "predicate_canon_provenance_assets.v1",
        "semantic_sources": "semantic_sources.yaml",
        "semantic_mappings": "semantic_mappings.jsonl",
        "predicate_canon_index": "predicate_canon_index.jsonl",
    }


def test_provenance_assets_never_enter_runtime_alias_loader(compiled_pair: CompiledPair) -> None:
    """Loading 0.3.0 preserves the exact 0.2.0 runtime alias views."""

    clear_loader_caches()
    candidate = load_ontology_pack(
        "linguistic_core",
        "0.3.0",
        packs_root=compiled_pair["first_root"],
    )
    baseline = load_ontology_pack("linguistic_core", "0.2.0")
    assert candidate.predicate_aliases == baseline.predicate_aliases
    assert candidate.role_aliases == baseline.role_aliases
    assert "Quitting_a_place" not in candidate.predicate_aliases


@pytest.mark.parametrize("mutation", ["missing", "corrupt", "unexpected"])
def test_artifact_adequacy_failures_are_explicit(
    compiled_pair: CompiledPair,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Missing, corrupt, and undeclared assets cannot validate as a complete pack."""

    candidate = tmp_path / "candidate"
    shutil.copytree(compiled_pair["first"], candidate)
    if mutation == "missing":
        (candidate / "semantic_sources.yaml").unlink()
    elif mutation == "corrupt":
        with (candidate / "semantic_mappings.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{}\n")
    else:
        (candidate / "undeclared.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(LinguisticCoreCompileError):
        validate_compiled_pack(candidate, require_provenance=True)


def test_unsupported_provenance_schema_fails_even_with_matching_hash(
    compiled_pair: CompiledPair,
    tmp_path: Path,
) -> None:
    """A self-consistent hash cannot authorize an unsupported source schema."""

    candidate = tmp_path / "candidate"
    shutil.copytree(compiled_pair["first"], candidate)
    source_path = candidate / "semantic_sources.yaml"
    sources = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    sources["schema_version"] = "predicate_canon_semantic_sources.v999"
    source_path.write_text(yaml.safe_dump(sources, sort_keys=False), encoding="utf-8")
    manifest_path = candidate / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["build"]["artifact_sha256"]["semantic_sources.yaml"] = _sha256(source_path)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(LinguisticCoreCompileError, match="invalid semantic source registry"):
        validate_compiled_pack(candidate, require_provenance=True)


@pytest.mark.parametrize(
    "mutation", ["pack_version", "direct_input_hash", "coordinated_pack_rewrite"]
)
def test_source_registry_identity_drift_fails_even_with_matching_hash(
    compiled_pair: CompiledPair,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Rehashed provenance cannot disagree with its pack or direct donor identity."""

    candidate = tmp_path / mutation / "0.3.0"
    shutil.copytree(compiled_pair["first"], candidate)
    source_path = candidate / "semantic_sources.yaml"
    sources = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    manifest_path = candidate / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if mutation == "pack_version":
        sources["pack_version"] = "9.9.9"
        expected = "pack identity mismatch"
    elif mutation == "coordinated_pack_rewrite":
        sources["pack_version"] = "9.9.9"
        manifest["pack"]["id"] = "wrong_pack"
        manifest["pack"]["version"] = "9.9.9"
        expected = "pack identity mismatch"
    else:
        sources["direct_build_input"]["artifact_sha256"] = "0" * 64
        expected = "invalid semantic source registry"
    source_path.write_text(yaml.safe_dump(sources, sort_keys=False), encoding="utf-8")
    manifest["build"]["artifact_sha256"]["semantic_sources.yaml"] = _sha256(source_path)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(LinguisticCoreCompileError, match=expected):
        validate_compiled_pack(candidate, require_provenance=True)


@pytest.mark.parametrize(
    ("source_key", "canonical_kind", "expected"),
    [
        ("propbank_nltk", "predicate_type", "PropBank semantic provenance"),
        ("sumo_donor_types", "hierarchy_edge", "hierarchy provenance"),
        ("framenet_candidate", "predicate_type", "FrameNet candidate provenance"),
        ("sumo_donor_types", "entity_type", "SUMO entity provenance"),
        ("onto_canon_sumo_plus", "role_slot", "direct donor provenance"),
    ],
)
def test_self_consistent_mapping_deletion_fails_cross_artifact_coverage(
    compiled_pair: CompiledPair,
    tmp_path: Path,
    source_key: str,
    canonical_kind: str,
    expected: str,
) -> None:
    """Rehashing a truncated mapping file cannot self-certify incomplete provenance."""

    candidate = tmp_path / source_key / canonical_kind / "0.3.0"
    shutil.copytree(compiled_pair["first"], candidate)
    mapping_path = candidate / "semantic_mappings.jsonl"
    rows = _jsonl(mapping_path)
    remove_index = next(
        index
        for index, row in enumerate(rows)
        if row["source_key"] == source_key
        and row["canonical_kind"] == canonical_kind
    )
    rows.pop(remove_index)
    mapping_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    manifest_path = candidate / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["build"]["artifact_sha256"]["semantic_mappings.jsonl"] = _sha256(
        mapping_path
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(LinguisticCoreCompileError, match=expected):
        validate_compiled_pack(candidate, require_provenance=True)


@pytest.mark.parametrize(
    ("source_key", "canonical_kind"),
    [
        ("framenet_candidate", "predicate_type"),
        ("sumo_donor_types", "entity_type"),
        ("onto_canon_sumo_plus", "role_slot"),
    ],
)
def test_self_consistent_source_id_fabrication_fails_release_digest(
    compiled_pair: CompiledPair,
    tmp_path: Path,
    source_key: str,
    canonical_kind: str,
) -> None:
    """Complete counts plus a rewritten manifest cannot authorize false lineage."""

    candidate = tmp_path / source_key / canonical_kind / "0.3.0"
    shutil.copytree(compiled_pair["first"], candidate)
    mapping_path = candidate / "semantic_mappings.jsonl"
    rows = _jsonl(mapping_path)
    row = next(
        item
        for item in rows
        if item["source_key"] == source_key and item["canonical_kind"] == canonical_kind
    )
    row["source_id"] = "fabricated_source_identifier"
    mapping_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows),
        encoding="utf-8",
    )
    manifest_path = candidate / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["build"]["artifact_sha256"]["semantic_mappings.jsonl"] = _sha256(
        mapping_path
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(LinguisticCoreCompileError, match="independently anchored digest"):
        validate_compiled_pack(candidate, require_provenance=True)


def test_existing_target_and_invalid_build_identity_fail_before_write(tmp_path: Path) -> None:
    """Unsafe target/version/timestamp inputs fail loud without partial publication."""

    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(LinguisticCoreCompileError, match="already exists"):
        compile_pack(
            DB_PATH,
            target,
            pack_version="0.3.0",
            build_timestamp=BUILD_TIMESTAMP,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"
    with pytest.raises(LinguisticCoreCompileError, match="invalid pack version"):
        compile_pack(DB_PATH, tmp_path / "bad-version", pack_version="candidate")
    with pytest.raises(LinguisticCoreCompileError, match="require --build-timestamp"):
        compile_pack(DB_PATH, tmp_path / "missing-time", pack_version="0.3.0")
    with pytest.raises(LinguisticCoreCompileError, match="RFC3339 UTC"):
        compile_pack(
            DB_PATH,
            tmp_path / "bad-time",
            pack_version="0.3.0",
            build_timestamp="not-a-time",
        )


def test_missing_donor_leaves_no_partial_output(tmp_path: Path) -> None:
    """Build adequacy failure occurs before any candidate directory is published."""

    output = tmp_path / "linguistic_core" / "0.3.0"
    with pytest.raises(RoleSlotsError, match="not found"):
        compile_pack(
            tmp_path / "missing.sqlite3",
            output,
            pack_version="0.3.0",
            build_timestamp=BUILD_TIMESTAMP,
        )
    assert not output.exists()


def test_legacy_compiler_reproduces_committed_020_exactly(tmp_path: Path) -> None:
    """The versioned compiler retains exact byte reproduction of immutable 0.2.0."""

    reproduced = tmp_path / "linguistic_core" / "0.2.0"
    compile_pack(DB_PATH, reproduced, pack_version="0.2.0")
    assert {path.name for path in reproduced.iterdir()} == {
        path.name for path in BASELINE_PACK.iterdir()
    }
    assert {
        path.name: _sha256(path) for path in reproduced.iterdir()
    } == {path.name: _sha256(path) for path in BASELINE_PACK.iterdir()}
