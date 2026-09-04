"""Read-only SUMO donor reconciliation tests for Plan 0147 Slice 3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from pydantic import ValidationError

from linguistic_core.linguistic_sources_v1 import (
    GitSourceIdentityV1,
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    compute_selected_payload_v1,
)
from linguistic_core.sumo_crosswalk_audit_v1 import (
    SumoCrosswalkAuditError,
    SumoCrosswalkAuditV1,
    SumoPredicateCandidateV1,
    SumoRoleCandidateV1,
    audit_sumo_crosswalk_v1,
    load_sumo_crosswalk_audit_v1,
)
from linguistic_core.sumo_projection_v1 import (
    SumoProjectionV1,
    compile_sumo_projection_v1,
)


def _git(checkout: Path, *args: str) -> str:
    """Run one local Git operation for the clean-room source fixture."""

    completed = subprocess.run(
        ["git", *args], cwd=checkout, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _source_fixture(tmp_path: Path) -> tuple[Path, LinguisticSourceManifestV1]:
    """Create one exact Git SUMO source plus its strict manifest."""

    checkout = tmp_path / "sumo"
    checkout.mkdir()
    _git(checkout, "init", "--initial-branch=main")
    _git(checkout, "config", "user.email", "fixture@example.invalid")
    _git(checkout, "config", "user.name", "SUMO fixture")
    (checkout / "LICENSE").write_text("fixture evidence\n", encoding="utf-8")
    (checkout / "Merge.kif").write_text(
        """(instance Entity Class)
(instance Physical Class)
(instance Process Class)
(instance Leaving Class)
(instance Object Class)
(instance AutonomousAgent Class)
(subclass Physical Entity)
(subclass Process Physical)
(subclass Leaving Process)
(subclass Object Physical)
(subclass AutonomousAgent Object)
(instance Relation Class)
(instance CaseRole Class)
(subclass CaseRole Relation)
(instance agent CaseRole)
(instance patient CaseRole)
(instance manner CaseRole)
(instance processRole CaseRole)
(instance ordinaryRelation Relation)
(domain agent 1 Process)
(domain agent 2 AutonomousAgent)
(domain patient 1 Process)
(domain patient 2 Entity)
(domain processRole 1 Process)
(domain processRole 2 Process)
""",
        encoding="utf-8",
    )
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-m", "fixture")
    source = LinguisticSourceSnapshotV1(
        source_key="sumo_root_kif",
        family="sumo",
        release_label="fixture",
        official_url="https://example.invalid/sumo",
        availability="available",
        git_identity=GitSourceIdentityV1(
            commit_sha=_git(checkout, "rev-parse", "HEAD"),
            tree_sha=_git(checkout, "rev-parse", "HEAD^{tree}"),
        ),
        selected_payload=compute_selected_payload_v1(
            checkout, selection_globs=("*.kif",)
        ),
        license_disposition="mixed_review_required",
        license_evidence=(
            LicenseEvidenceV1.from_checkout_file(
                checkout, path="LICENSE", evidence_scope="repository"
            ),
        ),
        storage_policy="external_cache",
        redistribution_allowed=False,
    )
    manifest = LinguisticSourceManifestV1(sources=(source,))
    return checkout, manifest


def _projection(tmp_path: Path) -> SumoProjectionV1:
    """Compile a strict synthetic SUMO projection through the real boundary."""

    checkout, manifest = _source_fixture(tmp_path)
    return compile_sumo_projection_v1(manifest, source_checkout=checkout)


def _database(path: Path) -> None:
    """Create representative donor candidates covering every classification."""

    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE predicates (
          name TEXT PRIMARY KEY,
          propbank_sense_id TEXT,
          process_type TEXT,
          lemma TEXT,
          sense_num INTEGER,
          description TEXT,
          frame_id TEXT,
          source TEXT,
          mapping_confidence REAL,
          mapping_source TEXT,
          is_static BOOLEAN DEFAULT 0
        );
        CREATE TABLE role_slots (
          event_sense_id TEXT NOT NULL REFERENCES predicates(name),
          named_label TEXT NOT NULL,
          arg_position TEXT NOT NULL,
          abstract_role TEXT,
          type_constraint TEXT,
          required INTEGER DEFAULT 0,
          source TEXT NOT NULL,
          PRIMARY KEY (event_sense_id, named_label)
        );
        INSERT INTO predicates VALUES
          ('abandon_leave_behind', 'abandon-01', 'Leaving', 'abandon', 1,
           'leave behind', 'Quitting_a_place', 'propbank:nltk', 0.9,
           'llm:fixture', 0),
          ('missing_process', 'missing-01', 'MissingProcess', 'missing', 1,
           'missing process', NULL, 'propbank:nltk', 0.2, 'llm:fixture', 0),
          ('unmapped_process', 'unmapped-01', NULL, 'unmapped', 1,
           'no process mapping', NULL, 'propbank:nltk', NULL, NULL, 0);
        INSERT INTO role_slots VALUES
          ('abandon_leave_behind', 'Agent', 'ARG0', 'agent',
           'AutonomousAgent', 0, 'propbank:nltk'),
          ('abandon_leave_behind', 'Theme', 'ARG1', 'patient',
           'Entity', 0, 'propbank:nltk'),
          ('abandon_leave_behind', 'Location', 'ARG2', NULL,
           'Object', 0, 'propbank:nltk'),
          ('missing_process', 'Mismatch', 'ARG0', 'patient',
           'Object', 0, 'propbank:nltk'),
          ('missing_process', 'Supertype', 'ARG0A', 'agent',
           'Object', 0, 'propbank:nltk'),
          ('missing_process', 'Incomparable', 'ARG0B', 'processRole',
           'Object', 0, 'propbank:nltk'),
          ('missing_process', 'Absent', 'ARG1', 'manner',
           'Entity', 0, 'propbank:nltk'),
          ('missing_process', 'Missing', 'ARG2', 'missingRole',
           'MissingType', 0, 'propbank:nltk'),
          ('unmapped_process', 'NonCase', 'ARG0', 'ordinaryRelation',
           NULL, 0, 'propbank:nltk');
        """
    )
    connection.commit()
    connection.close()


def _by_predicate(
    report: SumoCrosswalkAuditV1, predicate_id: str
) -> SumoPredicateCandidateV1:
    return next(item for item in report.predicates if item.donor_predicate_id == predicate_id)


def _by_role(
    report: SumoCrosswalkAuditV1, predicate_id: str, label: str
) -> SumoRoleCandidateV1:
    return next(
        item
        for item in report.roles
        if item.donor_predicate_id == predicate_id and item.named_label == label
    )


def test_audit_is_exhaustive_read_only_and_keeps_candidates_unreviewed(
    tmp_path: Path,
) -> None:
    projection = _projection(tmp_path)
    database = tmp_path / "donor.db"
    _database(database)
    before = database.read_bytes()

    first = audit_sumo_crosswalk_v1(database, projection=projection)
    second = audit_sumo_crosswalk_v1(database, projection=projection)

    assert first == second
    assert database.read_bytes() == before
    assert first.donor_db_sha256 == hashlib.sha256(before).hexdigest()
    assert first.constraint_module == "Merge.kif"
    assert len(first.predicates) == 3
    assert len(first.roles) == 9
    assert {item.review_state for item in first.predicates} == {"candidate_unreviewed"}
    assert {item.review_state for item in first.roles} == {"candidate_unreviewed"}

    abandon = _by_predicate(first, "abandon_leave_behind")
    assert abandon.canonical_predicate_id == "lc:abandon_leave_behind"
    assert abandon.process_type_status == "exact_current_source"
    assert abandon.mapping_method_ref == "llm:fixture"
    assert abandon.mapping_method_scope == "unknown"
    assert abandon.mapping_confidence == 0.9

    agent = _by_role(first, "abandon_leave_behind", "Agent")
    patient = _by_role(first, "abandon_leave_behind", "Theme")
    location = _by_role(first, "abandon_leave_behind", "Location")
    assert (agent.role_status, agent.type_status, agent.constraint_status) == (
        "exact_case_role",
        "exact_current_source",
        "direct_match",
    )
    assert (patient.role_status, patient.type_status, patient.constraint_status) == (
        "exact_case_role",
        "exact_current_source",
        "direct_match",
    )
    assert location.abstract_role is None
    assert location.role_status == "unmapped"
    assert location.type_status == "exact_current_source"
    assert location.constraint_status == "not_applicable"
    assert location.observed_constraint_types == ()

    assert _by_role(first, "missing_process", "Mismatch").constraint_status == (
        "compatible_donor_subtype"
    )
    assert _by_role(first, "missing_process", "Supertype").constraint_status == (
        "incompatible_donor_supertype"
    )
    assert _by_role(first, "missing_process", "Incomparable").constraint_status == (
        "incomparable_types"
    )
    assert _by_role(first, "missing_process", "Absent").constraint_status == (
        "no_direct_constraint"
    )
    missing = _by_role(first, "missing_process", "Missing")
    assert missing.role_status == "missing_current_source"
    assert missing.type_status == "missing_current_source"
    non_case = _by_role(first, "unmapped_process", "NonCase")
    assert non_case.role_status == "exact_non_case_relation"
    assert non_case.constraint_status == "not_applicable"


def test_report_rejects_row_omission_status_corruption_and_promotion(
    tmp_path: Path,
) -> None:
    database = tmp_path / "donor.db"
    _database(database)
    report = audit_sumo_crosswalk_v1(database, projection=_projection(tmp_path))

    omitted = report.model_dump(mode="python")
    omitted["roles"] = omitted["roles"][:-1]
    with pytest.raises(ValidationError, match="summary"):
        SumoCrosswalkAuditV1.model_validate(omitted)

    changed = report.model_dump(mode="python")
    changed["roles"][0]["constraint_status"] = "no_direct_constraint"
    with pytest.raises(ValidationError):
        SumoCrosswalkAuditV1.model_validate(changed)

    content_changed = report.model_dump(mode="python")
    content_changed["predicates"][0]["frame_id"] = "substituted"
    with pytest.raises(ValidationError, match="content SHA-256"):
        SumoCrosswalkAuditV1.model_validate(content_changed)

    promoted = report.model_dump(mode="python")
    promoted["predicates"][0]["review_state"] = "verified"
    with pytest.raises(ValidationError):
        SumoCrosswalkAuditV1.model_validate(promoted)


def test_audit_rejects_missing_schema_and_unknown_constraint_module(
    tmp_path: Path,
) -> None:
    database = tmp_path / "donor.db"
    sqlite3.connect(database).execute("CREATE TABLE predicates (name TEXT)").connection.close()
    projection = _projection(tmp_path)

    with pytest.raises(SumoCrosswalkAuditError, match="donor schema"):
        audit_sumo_crosswalk_v1(database, projection=projection)

    valid_database = tmp_path / "valid.db"
    _database(valid_database)
    with pytest.raises(SumoCrosswalkAuditError, match="constraint module"):
        audit_sumo_crosswalk_v1(
            valid_database,
            projection=projection,
            constraint_module="Missing.kif",
        )


def test_cli_writes_deterministic_strict_report_and_refuses_replacement(
    tmp_path: Path,
) -> None:
    checkout, manifest = _source_fixture(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    database = tmp_path / "donor.db"
    _database(database)
    output = tmp_path / "audit.json.gz"
    command = [
        sys.executable,
        "scripts/audit_sumo_crosswalk.py",
        "--manifest",
        str(manifest_path),
        "--source-checkout",
        str(checkout),
        "--donor-db",
        str(database),
        "--output",
        str(output),
    ]

    first = subprocess.run(command, check=True, capture_output=True, text=True)
    receipt = json.loads(first.stdout)
    assert receipt["review_authority"] == "none_audit_only"
    assert receipt["published_or_activated"] is False
    report = load_sumo_crosswalk_audit_v1(output)
    first_bytes = output.read_bytes()
    assert receipt["report_content_sha256"] == report.report_content_sha256

    refused = subprocess.run(command, capture_output=True, text=True)
    assert refused.returncode != 0
    assert "output already exists" in refused.stderr
    assert output.read_bytes() == first_bytes

    subprocess.run([*command, "--force"], check=True, capture_output=True, text=True)
    assert output.read_bytes() == first_bytes
