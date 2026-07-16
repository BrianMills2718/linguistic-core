"""Fail-closed tests for exact linguistic source snapshots."""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from onto_canon6.packs.linguistic_sources_v1 import (
    ArchiveSourceIdentityV1,
    DistributionMetadataEvidenceV1,
    GitSourceIdentityV1,
    LicenseDisposition,
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    SourceFamily,
    UnavailableSourceEvidenceV1,
    compute_selected_payload_v1,
    load_linguistic_source_manifest_v1,
    verify_linguistic_source_manifest_v1,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "linguistic_sources"


def _git(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *command], cwd=cwd, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _fixture_checkout(tmp_path: Path, source_key: str) -> tuple[Path, GitSourceIdentityV1]:
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


def _available_snapshot(
    *,
    source_key: str,
    family: SourceFamily,
    checkout: Path,
    identity: GitSourceIdentityV1,
    selection_globs: tuple[str, ...],
    license_paths: tuple[str, ...],
    license_disposition: LicenseDisposition,
) -> LinguisticSourceSnapshotV1:
    payload = compute_selected_payload_v1(checkout, selection_globs=selection_globs)
    evidence = tuple(
        LicenseEvidenceV1.from_checkout_file(
            checkout,
            path=path,
            license_id=(
                "CC-BY-SA-4.0" if license_disposition == "verified_redistributable" else None
            ),
        )
        for path in license_paths
    )
    return LinguisticSourceSnapshotV1(
        source_key=source_key,
        family=family,
        release_label="fixture",
        official_url=f"https://example.invalid/{source_key}",
        availability="available",
        git_identity=identity,
        selected_payload=payload,
        license_disposition=license_disposition,
        license_evidence=evidence,
        storage_policy="external_cache",
        redistribution_allowed=license_disposition == "verified_redistributable",
    )


def test_available_source_requires_exact_identity_payload_and_license() -> None:
    with pytest.raises(ValidationError, match="available source requires"):
        LinguisticSourceSnapshotV1(
            source_key="propbank",
            family="propbank",
            release_label="3.4",
            official_url="https://github.com/propbank/propbank-frames",
            availability="available",
            license_disposition="verified_redistributable",
            storage_policy="external_cache",
            redistribution_allowed=True,
        )


def test_archive_source_verifies_exact_bytes_and_rejects_substitution(tmp_path: Path) -> None:
    archive = tmp_path / "framenet_v17.zip"
    archive.write_bytes(b"exact retained FrameNet fixture")
    identity = ArchiveSourceIdentityV1(
        archive_filename=archive.name,
        byte_count=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        distribution_url="https://example.invalid/framenet_v17.zip",
    )
    metadata = (
        DistributionMetadataEvidenceV1(
            repository_url="https://example.invalid/metadata",
            revision_sha="1" * 40,
            path="index.xml",
            sha256="2" * 64,
            evidence_scope="archive_identity",
        ),
        DistributionMetadataEvidenceV1(
            repository_url="https://example.invalid/metadata",
            revision_sha="1" * 40,
            path="packages/corpora/framenet_v17.xml",
            sha256="3" * 64,
            evidence_scope="license",
            license_id="CC-BY-3.0",
            attribution_title="FrameNet 1.7",
            attribution_author="Fixture Author",
            attribution_uri="https://example.invalid/framenet",
        ),
    )
    source = LinguisticSourceSnapshotV1(
        source_key="framenet_17",
        family="framenet",
        release_label="1.7",
        official_url="https://example.invalid/framenet",
        availability="available",
        archive_identity=identity,
        metadata_evidence=metadata,
        license_disposition="verified_redistributable",
        storage_policy="external_cache",
        redistribution_allowed=True,
    )
    manifest = LinguisticSourceManifestV1(sources=(source,))

    verified = verify_linguistic_source_manifest_v1(
        manifest, source_roots={"framenet_17": archive}
    ).sources[0]
    assert verified.status == "verified"
    assert verified.archive_byte_count == identity.byte_count
    assert verified.archive_sha256 == identity.sha256

    wrong_name = archive.with_name("substituted-name.zip")
    archive.rename(wrong_name)
    with pytest.raises(ValueError, match="archive filename does not match"):
        verify_linguistic_source_manifest_v1(
            manifest, source_roots={"framenet_17": wrong_name}
        )
    wrong_name.rename(archive)

    archive.write_bytes(b"substituted")
    with pytest.raises(ValueError, match="archive bytes do not match"):
        verify_linguistic_source_manifest_v1(
            manifest, source_roots={"framenet_17": archive}
        )


def test_available_source_rejects_competing_git_and_archive_identities(
    tmp_path: Path,
) -> None:
    checkout, git_identity = _fixture_checkout(tmp_path, "propbank")
    git_source = _available_snapshot(
        source_key="propbank",
        family="propbank",
        checkout=checkout,
        identity=git_identity,
        selection_globs=("frames/*.xml",),
        license_paths=("LICENSE",),
        license_disposition="verified_redistributable",
    )
    payload = git_source.model_dump(mode="python")
    payload["archive_identity"] = {
        "archive_filename": "propbank.zip",
        "byte_count": 1,
        "sha256": "0" * 64,
        "distribution_url": "https://example.invalid/propbank.zip",
    }

    with pytest.raises(ValidationError, match="exactly one complete Git or archive identity"):
        LinguisticSourceSnapshotV1.model_validate(payload)


def test_unavailable_source_cannot_claim_payload_or_redistribution() -> None:
    evidence = UnavailableSourceEvidenceV1(
        observed_at=datetime.fromisoformat("2026-07-15T00:00:00+00:00"),
        evidence_url="https://berkeleyfn.framenetbr.ufjf.br/node/5574",
        reason="official request/download function temporarily unavailable",
    )
    source = LinguisticSourceSnapshotV1(
        source_key="framenet_17",
        family="framenet",
        release_label="1.7",
        official_url="https://berkeleyfn.framenetbr.ufjf.br/framenet_data",
        availability="temporarily_unavailable",
        unavailable_evidence=evidence,
        license_disposition="unknown",
        storage_policy="reference_only",
        redistribution_allowed=False,
    )
    manifest = LinguisticSourceManifestV1(sources=(source,))

    report = verify_linguistic_source_manifest_v1(manifest, source_roots={})

    assert report.sources[0].status == "unavailable"
    with pytest.raises(ValueError, match="must not receive a local source root"):
        verify_linguistic_source_manifest_v1(
            manifest, source_roots={"framenet_17": Path("unexpected")}
        )


def test_verifier_rejects_commit_and_content_substitution(tmp_path: Path) -> None:
    checkout, identity = _fixture_checkout(tmp_path, "propbank")
    source = _available_snapshot(
        source_key="propbank",
        family="propbank",
        checkout=checkout,
        identity=identity,
        selection_globs=("frames/*.xml",),
        license_paths=("LICENSE",),
        license_disposition="verified_redistributable",
    )
    manifest = LinguisticSourceManifestV1(sources=(source,))
    assert verify_linguistic_source_manifest_v1(
        manifest, source_roots={"propbank": checkout}
    ).sources[0].status == "verified"

    wrong_identity = identity.model_copy(update={"commit_sha": "0" * 40})
    wrong_source = source.model_copy(update={"git_identity": wrong_identity})
    with pytest.raises(ValueError, match="commit SHA"):
        verify_linguistic_source_manifest_v1(
            LinguisticSourceManifestV1(sources=(wrong_source,)),
            source_roots={"propbank": checkout},
        )

    (checkout / "frames" / "example.xml").write_text("substituted", encoding="utf-8")
    with pytest.raises(ValueError, match="selected payload"):
        verify_linguistic_source_manifest_v1(
            manifest, source_roots={"propbank": checkout}
        )


def test_mixed_license_source_cannot_enable_redistribution(tmp_path: Path) -> None:
    checkout, identity = _fixture_checkout(tmp_path, "sumo")
    source = _available_snapshot(
        source_key="sumo",
        family="sumo",
        checkout=checkout,
        identity=identity,
        selection_globs=("*.kif",),
        license_paths=("Merge.kif", "Mid-level-ontology.kif"),
        license_disposition="mixed_review_required",
    )

    with pytest.raises(ValidationError, match="redistribution requires"):
        source.model_copy(update={"redistribution_allowed": True}).model_validate(
            source.model_copy(update={"redistribution_allowed": True}).model_dump()
        )


def test_selected_payload_rejects_directory_symlink_escape(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "substituted.xml").write_text("outside", encoding="utf-8")
    (checkout / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes checkout root"):
        compute_selected_payload_v1(checkout, selection_globs=("linked/*.xml",))


def test_canonical_manifest_binds_available_framenet_archive() -> None:
    manifest = load_linguistic_source_manifest_v1(Path("config/linguistic_sources_v1.yaml"))

    assert tuple(source.family for source in manifest.sources) == (
        "propbank",
        "framenet",
        "sumo",
    )
    framenet = manifest.source_for("framenet_17")
    assert framenet.availability == "available"
    assert framenet.git_identity is None
    assert framenet.selected_payload is None
    assert framenet.archive_identity is not None
    assert framenet.archive_identity.byte_count == 99_207_152
    assert framenet.archive_identity.sha256 == (
        "22f6aad6fb799ba4dbed0440714e1118442ad7d7345351de37428581284f471c"
    )
    assert framenet.redistribution_allowed is True
    license_metadata = next(
        item for item in framenet.metadata_evidence if item.evidence_scope == "license"
    )
    assert license_metadata.attribution_title == "FrameNet 1.7"
    assert license_metadata.attribution_author == "Collin F. Baker"
    assert license_metadata.attribution_uri == "http://framenet.icsi.berkeley.edu"


def test_redistributable_framenet_archive_requires_complete_supplied_attribution(
    tmp_path: Path,
) -> None:
    """Exact license identity cannot omit supplied author/title/URI metadata."""

    archive = tmp_path / "framenet_v17.zip"
    archive.write_bytes(b"fixture")
    identity = ArchiveSourceIdentityV1(
        archive_filename=archive.name,
        byte_count=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        distribution_url="https://example.invalid/framenet_v17.zip",
    )
    metadata = (
        DistributionMetadataEvidenceV1(
            repository_url="https://example.invalid/metadata",
            revision_sha="1" * 40,
            path="index.xml",
            sha256="2" * 64,
            evidence_scope="archive_identity",
        ),
        DistributionMetadataEvidenceV1(
            repository_url="https://example.invalid/metadata",
            revision_sha="1" * 40,
            path="packages/corpora/framenet_v17.xml",
            sha256="3" * 64,
            evidence_scope="license",
            license_id="CC-BY-3.0",
        ),
    )

    with pytest.raises(ValidationError, match="FrameNet archive.*complete supplied attribution"):
        LinguisticSourceSnapshotV1(
            source_key="framenet_17",
            family="framenet",
            release_label="1.7",
            official_url="https://example.invalid/framenet",
            availability="available",
            archive_identity=identity,
            metadata_evidence=metadata,
            license_disposition="verified_redistributable",
            storage_policy="external_cache",
            redistribution_allowed=True,
        )
