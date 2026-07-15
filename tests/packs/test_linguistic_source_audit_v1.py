"""Read-only donor-label comparison tests for Plan 0147."""

from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
import subprocess

from onto_canon6.packs.linguistic_source_audit_v1 import (
    audit_linguistic_donor_labels_v1,
    normalize_propbank_donor_id_v1,
    normalize_sumo_donor_id_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import (
    GitSourceIdentityV1,
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    UnavailableSourceEvidenceV1,
    compute_selected_payload_v1,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "linguistic_sources"


def _git(command: list[str], *, cwd: Path) -> str:
    return subprocess.run(
        ["git", *command], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _checkout(tmp_path: Path, source_key: str) -> tuple[Path, GitSourceIdentityV1]:
    checkout = tmp_path / source_key
    shutil.copytree(FIXTURES / source_key, checkout)
    _git(["init", "--quiet"], cwd=checkout)
    _git(["config", "user.name", "Plan 0147 Fixture"], cwd=checkout)
    _git(["config", "user.email", "plan0147@example.invalid"], cwd=checkout)
    _git(["add", "."], cwd=checkout)
    _git(["commit", "--quiet", "-m", "fixture"], cwd=checkout)
    return checkout, GitSourceIdentityV1(
        commit_sha=_git(["rev-parse", "HEAD"], cwd=checkout),
        tree_sha=_git(["rev-parse", "HEAD^{tree}"], cwd=checkout),
    )


def _manifest(
    propbank: Path,
    propbank_identity: GitSourceIdentityV1,
    sumo: Path,
    sumo_identity: GitSourceIdentityV1,
) -> LinguisticSourceManifestV1:
    return LinguisticSourceManifestV1(
        sources=(
            LinguisticSourceSnapshotV1(
                source_key="propbank",
                family="propbank",
                release_label="fixture",
                official_url="https://example.invalid/propbank",
                availability="available",
                git_identity=propbank_identity,
                selected_payload=compute_selected_payload_v1(
                    propbank, selection_globs=("frames/*.xml",)
                ),
                license_disposition="verified_redistributable",
                license_evidence=(
                    LicenseEvidenceV1.from_checkout_file(
                        propbank, path="LICENSE", license_id="CC-BY-SA-4.0"
                    ),
                ),
                storage_policy="external_cache",
                redistribution_allowed=True,
            ),
            LinguisticSourceSnapshotV1(
                source_key="framenet",
                family="framenet",
                release_label="1.7",
                official_url="https://example.invalid/framenet",
                availability="temporarily_unavailable",
                unavailable_evidence=UnavailableSourceEvidenceV1.model_validate(
                    {
                        "observed_at": "2026-07-15T00:00:00Z",
                        "evidence_url": "https://example.invalid/unavailable",
                        "reason": "fixture unavailable",
                    }
                ),
                license_disposition="unknown",
                storage_policy="reference_only",
                redistribution_allowed=False,
            ),
            LinguisticSourceSnapshotV1(
                source_key="sumo",
                family="sumo",
                release_label="fixture",
                official_url="https://example.invalid/sumo",
                availability="available",
                git_identity=sumo_identity,
                selected_payload=compute_selected_payload_v1(
                    sumo, selection_globs=("*.kif",)
                ),
                license_disposition="mixed_review_required",
                license_evidence=(
                    LicenseEvidenceV1.from_checkout_file(sumo, path="Merge.kif"),
                    LicenseEvidenceV1.from_checkout_file(
                        sumo, path="Mid-level-ontology.kif"
                    ),
                ),
                storage_policy="external_cache",
                redistribution_allowed=False,
            ),
        )
    )


def _donor_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE predicates (
          name TEXT PRIMARY KEY,
          propbank_sense_id TEXT,
          frame_id TEXT,
          process_type TEXT,
          source TEXT
        );
        CREATE TABLE frames (id TEXT PRIMARY KEY, name TEXT, source TEXT);
        CREATE TABLE types (id TEXT PRIMARY KEY, source TEXT);
        INSERT INTO predicates VALUES
          ('audit', 'audit-01', 'Becoming_aware', 'Process', 'propbank:nltk'),
          ('broken', 'broken-01', NULL, NULL, 'propbank:nltk'),
          ('fake', 'fake-01', NULL, NULL, 'propbank:nltk'),
          ('missing', 'missing-01', NULL, 'MissingType', 'propbank:nltk'),
          ('invalid', 'not_a_sense', NULL, NULL, 'propbank:nltk');
        INSERT INTO frames VALUES
          ('Becoming_aware', 'Becoming aware', 'framenet:v17');
        INSERT INTO types VALUES
          ('Process', 'sumo:Merge.kif'),
          ('MissingType', 'sumo:Merge.kif');
        """
    )
    connection.commit()
    connection.close()


def test_propbank_normalization_preserves_hyphenated_lemma() -> None:
    assert normalize_propbank_donor_id_v1("take-over-01") == "take-over.01"
    assert normalize_propbank_donor_id_v1("not_a_sense") is None
    assert normalize_sumo_donor_id_v1("IntentionalProcess") == "IntentionalProcess"
    assert normalize_sumo_donor_id_v1("(DeadFn") is None


def test_audit_classifies_every_donor_id_without_mutating_db(tmp_path: Path) -> None:
    propbank, propbank_identity = _checkout(tmp_path, "propbank")
    sumo, sumo_identity = _checkout(tmp_path, "sumo")
    database = tmp_path / "donor.db"
    _donor_db(database)
    before = database.read_bytes()

    report = audit_linguistic_donor_labels_v1(
        database,
        manifest=_manifest(propbank, propbank_identity, sumo, sumo_identity),
        source_roots={"propbank": propbank, "sumo": sumo},
    )

    assert database.read_bytes() == before
    by_family = report.summary_by_family()
    assert by_family["propbank"].model_dump() == {
        "family": "propbank",
        "donor_identifier_count": 5,
        "matched_count": 2,
        "missing_count": 2,
        "invalid_count": 1,
        "unavailable_count": 0,
    }
    assert by_family["framenet"].unavailable_count == 1
    assert by_family["sumo"].matched_count == 1
    assert by_family["sumo"].missing_count == 1
    assert len(report.comparisons) == 8
    assert len(report.source_syntax_issues) == 1
    assert report.source_syntax_issues[0].relative_path == "frames/malformed.xml"
