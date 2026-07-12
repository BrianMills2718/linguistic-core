"""Plan 0140 Slice 1 tests for one-predicate semantic provenance closure.

The walking skeleton reads the real donor database, emits strict traceability
records for one predicate, and never changes the database or runtime pack.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from onto_canon6.packs.semantic_provenance import (
    PredicateProvenanceBundle,
    SemanticMappingRecord,
    SemanticSourceDescriptor,
    compile_predicate_provenance,
    render_provenance_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "sumo_plus.db"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "predicate_canon_provenance"
PREDICATE_ID = "abandon_leave_behind"


def _json_fixture(name: str) -> dict[str, object]:
    """Load one strict JSON fixture for contract validation."""

    return cast(
        dict[str, object],
        json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")),
    )


def _sha256(path: Path) -> str:
    """Return a byte-exact file checksum for read-only verification."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_approved_predicate_compiles_to_reviewed_fixture() -> None:
    """The approved predicate emits the exact reviewed Slice-1 contract (AC-1/2/6)."""

    actual = compile_predicate_provenance(DB_PATH, predicate_id=PREDICATE_ID)

    assert actual.model_dump(mode="json") == _json_fixture("approved_abandon_leave_behind.json")
    assert actual.donor_predicate.row_mapping_method_scope == "unknown"
    assert actual.donor_predicate.row_mapping_method_ref == "llm:gemini/gemini-2.5-flash"
    assert all(mapping.runtime_alias is False for mapping in actual.mappings)


@pytest.mark.parametrize(
    ("fixture_name", "model_type"),
    [
        ("fabricated_verified_version.json", SemanticSourceDescriptor),
        ("fabricated_verified_license.json", SemanticSourceDescriptor),
        ("donor_asserted_from_current_reference.json", SemanticSourceDescriptor),
        ("missing_mapping_evidence.json", SemanticMappingRecord),
        ("runtime_alias_true.json", SemanticMappingRecord),
        ("dangling_canonical_id.json", PredicateProvenanceBundle),
    ],
)
def test_negative_contract_fixtures_fail_loud(
    fixture_name: str,
    model_type: type[SemanticSourceDescriptor] | type[SemanticMappingRecord] | type[PredicateProvenanceBundle],
) -> None:
    """Both-sign controls reject fabricated certainty, weak evidence, aliases, and dangling IDs."""

    with pytest.raises(ValidationError):
        model_type.model_validate(_json_fixture(fixture_name))


@pytest.mark.parametrize(
    ("version_status", "license_status", "historical_evidence_kind"),
    [
        ("verified", "unknown", "none"),
        ("verified", "unknown", "current_reference_only"),
        ("donor_asserted", "unknown", "none"),
        ("donor_asserted", "unknown", "current_reference_only"),
        ("unknown", "verified", "none"),
        ("unknown", "verified", "current_reference_only"),
    ],
)
def test_certainty_requires_historical_evidence_cross_product(
    version_status: str,
    license_status: str,
    historical_evidence_kind: str,
) -> None:
    """Every known historical version/license state rejects non-historical evidence."""

    payload: dict[str, object] = {
        "source_key": "adversarial_source",
        "resource_name": "Adversarial source",
        "resource_version": "1.0" if version_status != "unknown" else None,
        "resource_version_status": version_status,
        "license_id": "MIT" if license_status == "verified" else None,
        "license_status": license_status,
        "artifact_sha256": None,
        "official_reference": (
            "https://example.com/current"
            if historical_evidence_kind == "current_reference_only"
            else None
        ),
        "official_reference_scope": (
            "current_reference_only"
            if historical_evidence_kind == "current_reference_only"
            else None
        ),
        "historical_evidence_kind": historical_evidence_kind,
        "evidence_ref": "adversarial non-historical evidence",
    }

    with pytest.raises(ValidationError):
        SemanticSourceDescriptor.model_validate(payload)


def test_shared_framenet_frame_is_traceability_not_alias() -> None:
    """One FrameNet candidate shared by multiple predicates cannot become an alias (AC-3)."""

    abandon_01 = compile_predicate_provenance(DB_PATH, predicate_id="abandon_leave_behind")
    abandon_02 = compile_predicate_provenance(DB_PATH, predicate_id="abandon_exchange")

    first_frames = {
        row.source_id
        for row in abandon_01.mappings
        if row.source_key == "framenet_candidate"
    }
    second_frames = {
        row.source_id
        for row in abandon_02.mappings
        if row.source_key == "framenet_candidate"
    }
    assert first_frames == second_frames == {"Quitting_a_place"}
    assert all(
        row.runtime_alias is False
        for bundle in (abandon_01, abandon_02)
        for row in bundle.mappings
        if row.source_key == "framenet_candidate"
    )
    frame_less = compile_predicate_provenance(
        DB_PATH,
        predicate_id="abandon_surrender_give",
    )
    assert "FrameNet mappings are" not in render_provenance_text(frame_less)


def test_frame_mapping_carries_approved_row_method_fields() -> None:
    """The mapping row itself exposes method and unknown scope as approved (AC-6)."""

    bundle = compile_predicate_provenance(DB_PATH, predicate_id=PREDICATE_ID)
    frame_mapping = next(
        row for row in bundle.mappings if row.source_key == "framenet_candidate"
    )

    assert frame_mapping.row_mapping_method_ref == "llm:gemini/gemini-2.5-flash"
    assert frame_mapping.row_mapping_method_scope == "unknown"
    assert "mapping_source" in frame_mapping.evidence_ref


def test_bundle_rejects_mapping_method_drift_from_donor_row() -> None:
    """A mapping cannot silently contradict its enclosing donor-row metadata."""

    payload = compile_predicate_provenance(DB_PATH, predicate_id=PREDICATE_ID).model_dump(
        mode="json"
    )
    frame_mapping = next(
        row for row in payload["mappings"] if row["source_key"] == "framenet_candidate"
    )
    frame_mapping["row_mapping_method_ref"] = "deterministic:invented"

    with pytest.raises(ValidationError):
        PredicateProvenanceBundle.model_validate(payload)


def test_mapping_kind_and_relation_cannot_be_conflated() -> None:
    """A role or type row cannot borrow a predicate mapping relation."""

    payload = _json_fixture("missing_mapping_evidence.json")
    payload["evidence_ref"] = "sqlite:role_slots"
    payload["canonical_kind"] = "entity_type"
    payload["relation"] = "positional_role"
    with pytest.raises(ValidationError):
        SemanticMappingRecord.model_validate(payload)


def test_noncanonical_db_does_not_inherit_canonical_donor_version(tmp_path: Path) -> None:
    """A different DB hash keeps the historical version unknown instead of laundering it."""

    db_path = tmp_path / "replacement.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE predicates (name TEXT PRIMARY KEY, propbank_sense_id TEXT, "
            "frame_id TEXT, source TEXT, mapping_confidence REAL, mapping_source TEXT)"
        )
        conn.execute(
            "CREATE TABLE role_slots (event_sense_id TEXT, named_label TEXT, "
            "arg_position TEXT, type_constraint TEXT, source TEXT)"
        )
        conn.execute(
            "INSERT INTO predicates VALUES ('test_event', 'test-01', NULL, "
            "'propbank:nltk', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO role_slots VALUES ('test_event', 'Agent', 'ARG0', "
            "'AutonomousAgent', 'propbank:nltk')"
        )
        conn.commit()
    finally:
        conn.close()

    bundle = compile_predicate_provenance(db_path, predicate_id="test_event")
    donor = next(source for source in bundle.sources if source.source_key == "onto_canon_sumo_plus")
    assert donor.resource_version is None
    assert donor.resource_version_status == "unknown"


def test_read_only_database_uri_quotes_reserved_path_characters(tmp_path: Path) -> None:
    """Valid filesystem paths containing SQLite URI delimiters open the intended database."""

    copied_db = tmp_path / "donor?copy#one.sqlite3"
    shutil.copy2(DB_PATH, copied_db)

    bundle = compile_predicate_provenance(copied_db, predicate_id=PREDICATE_ID)

    assert bundle.predicate_id == f"lc:{PREDICATE_ID}"
    donor = next(source for source in bundle.sources if source.source_key == "onto_canon_sumo_plus")
    assert donor.artifact_sha256 == _sha256(copied_db)


def test_inspector_is_agent_drivable_and_database_is_unchanged() -> None:
    """The CLI emits typed JSON while preserving the donor DB byte-for-byte (AC-7)."""

    before = _sha256(DB_PATH)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from onto_canon6.cli import main; raise SystemExit(main())",
            "inspect-canon-lineage",
            "--pack-id",
            "linguistic_core",
            "--pack-version",
            "0.3.0-candidate",
            "--sumo-db-path",
            str(DB_PATH),
            "--canonical-id",
            f"lc:{PREDICATE_ID}",
            "--output",
            "json",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        check=False,
        capture_output=True,
        text=True,
    )
    after = _sha256(DB_PATH)

    assert result.returncode == 0, result.stderr
    parsed = PredicateProvenanceBundle.model_validate_json(result.stdout)
    assert parsed.predicate_id == "lc:abandon_leave_behind"
    assert before == after


def test_inspector_unknown_predicate_fails_explicitly() -> None:
    """An unknown donor predicate is an explicit non-zero error, never an empty success."""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from onto_canon6.cli import main; raise SystemExit(main())",
            "inspect-canon-lineage",
            "--pack-id",
            "linguistic_core",
            "--pack-version",
            "0.3.0-candidate",
            "--sumo-db-path",
            str(DB_PATH),
            "--canonical-id",
            "lc:not_real",
            "--output",
            "json",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "CANON_LINEAGE_UNKNOWN_CANONICAL_ID" in result.stderr
    assert result.stdout == ""


def test_text_inspector_preserves_approved_claim_boundaries() -> None:
    """The real text renderer exposes every reviewed lineage and warning category."""

    bundle = compile_predicate_provenance(DB_PATH, predicate_id=PREDICATE_ID)
    rendered = render_provenance_text(bundle)
    required_fragments = (
        "kind: predicate_type",
        "lineage_status: mixed",
        "direct_build_input:",
        "sha256: 9a6da4825eb9e4f4d81d1263e5c2ee6847bb85a1b899727e6be929658e1da0f6",
        "upstream_version_status: donor_asserted",
        "license_status: unknown",
        "source_release: unknown",
        "source_verified: no",
        "row_mapping_method: llm:gemini/gemini-2.5-flash",
        "row_mapping_method_scope: unknown",
        "warnings:",
        "not independently verified",
        "cannot be attributed to a specific relationship",
        "not historical evidence",
    )
    for fragment in required_fragments:
        assert fragment in rendered
