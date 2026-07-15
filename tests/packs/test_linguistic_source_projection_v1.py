"""Deterministic source-repair and PropBank projection tests."""

from __future__ import annotations

import hashlib
import gzip
from pathlib import Path
import shutil
import subprocess

import pytest

from onto_canon6.packs.linguistic_source_projection_v1 import (
    LinguisticSourceRepairManifestV1,
    SourceProjectionError,
    SourceSyntaxRepairV1,
    compile_propbank_projection_v1,
    load_propbank_projection_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import (
    GitSourceIdentityV1,
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    compute_selected_payload_v1,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "linguistic_sources"


def _git(command: list[str], *, cwd: Path) -> str:
    return subprocess.run(
        ["git", *command], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _checkout(tmp_path: Path) -> tuple[Path, LinguisticSourceManifestV1]:
    checkout = tmp_path / "propbank"
    shutil.copytree(FIXTURES / "propbank", checkout)
    _git(["init", "--quiet"], cwd=checkout)
    _git(["config", "user.name", "Plan 0147 Fixture"], cwd=checkout)
    _git(["config", "user.email", "plan0147@example.invalid"], cwd=checkout)
    _git(["add", "."], cwd=checkout)
    _git(["commit", "--quiet", "-m", "fixture"], cwd=checkout)
    source = LinguisticSourceSnapshotV1(
        source_key="propbank",
        family="propbank",
        release_label="fixture",
        official_url="https://example.invalid/propbank",
        availability="available",
        git_identity=GitSourceIdentityV1(
            commit_sha=_git(["rev-parse", "HEAD"], cwd=checkout),
            tree_sha=_git(["rev-parse", "HEAD^{tree}"], cwd=checkout),
        ),
        selected_payload=compute_selected_payload_v1(
            checkout, selection_globs=("frames/*.xml",)
        ),
        license_disposition="verified_redistributable",
        license_evidence=(
            LicenseEvidenceV1.from_checkout_file(
                checkout, path="LICENSE", license_id="CC-BY-SA-4.0"
            ),
        ),
        storage_policy="external_cache",
        redistribution_allowed=True,
    )
    return checkout, LinguisticSourceManifestV1(sources=(source,))


def _repairs(checkout: Path) -> LinguisticSourceRepairManifestV1:
    malformed = checkout / "frames" / "malformed.xml"
    return LinguisticSourceRepairManifestV1(
        repairs=(
            SourceSyntaxRepairV1(
                repair_id="fixture_malformed_close_tag",
                source_key="propbank",
                relative_path="frames/malformed.xml",
                source_file_sha256=hashlib.sha256(malformed.read_bytes()).hexdigest(),
                old_fragment='<roleset id="broken.01"></predicate>',
                replacement_fragment='<roleset id="broken.01"></roleset></predicate>',
                reason="Close the roleset before the predicate.",
            ),
        )
    )


def test_projection_fails_closed_without_required_repair(tmp_path: Path) -> None:
    checkout, manifest = _checkout(tmp_path)

    with pytest.raises(SourceProjectionError, match="unrepaired PropBank XML"):
        compile_propbank_projection_v1(
            manifest,
            source_root=checkout,
            repair_manifest=LinguisticSourceRepairManifestV1(repairs=()),
        )


def test_exact_repair_compiles_roles_and_preserves_source_bytes(tmp_path: Path) -> None:
    checkout, manifest = _checkout(tmp_path)
    before = (checkout / "frames" / "malformed.xml").read_bytes()
    repairs = _repairs(checkout)

    first = compile_propbank_projection_v1(
        manifest, source_root=checkout, repair_manifest=repairs
    )
    second = compile_propbank_projection_v1(
        manifest, source_root=checkout, repair_manifest=repairs
    )

    assert first == second
    assert (checkout / "frames" / "malformed.xml").read_bytes() == before
    assert first.completeness == "complete_with_declared_syntax_repairs"
    assert first.source_file_count == 2
    assert first.parsed_file_count == 2
    assert tuple(record.roleset_id for record in first.rolesets) == (
        "audit.01",
        "broken.01",
    )
    audit = first.rolesets[0]
    assert tuple(role.number for role in audit.arguments) == ("0", "1")
    assert len(first.applied_repairs) == 1
    assert first.unrepaired_syntax_issues == ()
    assert first.identity_conflicts == ()

    artifact = tmp_path / "projection.json.gz"
    artifact.write_bytes(gzip.compress(first.model_dump_json().encode("utf-8"), mtime=0))
    assert load_propbank_projection_v1(artifact) == first


def test_repair_rejects_wrong_hash_and_nonunique_fragment(tmp_path: Path) -> None:
    checkout, manifest = _checkout(tmp_path)
    valid = _repairs(checkout).repairs[0]
    wrong_hash = valid.model_copy(update={"source_file_sha256": "0" * 64})
    with pytest.raises(SourceProjectionError, match="file SHA-256"):
        compile_propbank_projection_v1(
            manifest,
            source_root=checkout,
            repair_manifest=LinguisticSourceRepairManifestV1(repairs=(wrong_hash,)),
        )

    nonunique = valid.model_copy(
        update={"old_fragment": "frameset", "replacement_fragment": "frame-set"}
    )
    with pytest.raises(SourceProjectionError, match="exactly once"):
        compile_propbank_projection_v1(
            manifest,
            source_root=checkout,
            repair_manifest=LinguisticSourceRepairManifestV1(repairs=(nonunique,)),
        )
