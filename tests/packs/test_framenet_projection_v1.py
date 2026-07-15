"""Deterministic and fail-closed FrameNet projection tests for Plan 0147."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import zipfile

import pytest
from pydantic import ValidationError

from onto_canon6.packs.framenet_projection_v1 import (
    FrameNetProjectionError,
    FrameNetProjectionV1,
    compile_framenet_projection_v1,
    load_framenet_projection_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import (
    ArchiveSourceIdentityV1,
    DistributionMetadataEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
)


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "linguistic_sources" / "framenet"


def _fixture_members() -> dict[str, bytes]:
    return {
        f"framenet_v17/{path.relative_to(FIXTURE_ROOT).as_posix()}": path.read_bytes()
        for path in sorted(FIXTURE_ROOT.rglob("*.xml"))
    }


def _archive(
    tmp_path: Path,
    *,
    replacements: dict[str, bytes] | None = None,
    extras: dict[str, bytes] | None = None,
) -> Path:
    members = _fixture_members()
    members.update(replacements or {})
    members.update(extras or {})
    path = tmp_path / "framenet_v17.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member_name, payload in sorted(members.items()):
            member = zipfile.ZipInfo(member_name, date_time=(2020, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, payload)
    return path


def _manifest(archive: Path) -> LinguisticSourceManifestV1:
    source = LinguisticSourceSnapshotV1(
        source_key="framenet_17",
        family="framenet",
        release_label="1.7-fixture",
        official_url="https://example.invalid/framenet",
        availability="available",
        archive_identity=ArchiveSourceIdentityV1(
            archive_filename=archive.name,
            byte_count=archive.stat().st_size,
            sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            distribution_url="https://example.invalid/framenet_v17.zip",
        ),
        metadata_evidence=(
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
        ),
        license_disposition="verified_redistributable",
        storage_policy="external_cache",
        redistribution_allowed=True,
    )
    return LinguisticSourceManifestV1(sources=(source,))


def test_projection_is_complete_deterministic_and_round_trips(tmp_path: Path) -> None:
    archive = _archive(tmp_path)
    manifest = _manifest(archive)

    first = compile_framenet_projection_v1(manifest, source_archive=archive)
    second = compile_framenet_projection_v1(manifest, source_archive=archive)

    assert first == second
    assert first.frame_count == 2
    assert first.frame_element_count == 3
    assert first.lexical_unit_declaration_count == 3
    assert first.indexed_lexical_unit_count == 2
    assert first.frame_relation_count == 1
    assert first.frame_element_relation_count == 1
    quitting = next(frame for frame in first.frames if frame.name == "Quitting_a_place")
    departing = next(frame for frame in first.frames if frame.name == "Departing")
    assert [item.name for item in quitting.frame_elements] == ["Self_mover", "Source"]
    assert quitting.definition.startswith("\n<def-root>")
    assert quitting.definition.endswith("\n  ")
    assert [item.name for item in quitting.lexical_units] == ["quit.v", "withdraw.v"]
    assert [item.indexed_for_lookup for item in quitting.lexical_units] == [True, False]
    assert quitting.outgoing_relations[0].related_frame_name == "Departing"
    assert quitting.outgoing_relations[0].direction == "outgoing"
    assert quitting.outgoing_relations[0].containing_frame_role == "Child"
    assert quitting.outgoing_relations[0].related_frame_role == "Parent"
    assert quitting.outgoing_relations[0].frame_element_relations[0].sub_frame_element_name == (
        "Self_mover"
    )
    assert departing.incoming_relations[0].related_frame_name == "Quitting_a_place"
    assert departing.incoming_relations[0].direction == "incoming"

    projection_path = tmp_path / "projection.json.gz"
    projection_path.write_bytes(
        gzip.compress((first.model_dump_json() + "\n").encode("utf-8"), mtime=0)
    )
    assert load_framenet_projection_v1(projection_path) == first


def test_projection_rejects_count_preserving_frame_identity_drift(tmp_path: Path) -> None:
    member = "framenet_v17/frame/Quitting_a_place.xml"
    changed = _fixture_members()[member].replace(
        b'name="Quitting_a_place"', b'name="Wrong_frame_name"', 1
    )
    archive = _archive(tmp_path, replacements={member: changed})

    with pytest.raises(FrameNetProjectionError, match="index/content mismatch"):
        compile_framenet_projection_v1(_manifest(archive), source_archive=archive)


def test_projection_rejects_dangling_relation(tmp_path: Path) -> None:
    member = "framenet_v17/frRelation.xml"
    changed = _fixture_members()[member].replace(b'supID="200"', b'supID="999"', 1)
    archive = _archive(tmp_path, replacements={member: changed})

    with pytest.raises(FrameNetProjectionError, match="dangling FrameNet relation"):
        compile_framenet_projection_v1(_manifest(archive), source_archive=archive)


def test_projection_rejects_unindexed_frame_member(tmp_path: Path) -> None:
    extra = _fixture_members()["framenet_v17/frame/Departing.xml"].replace(
        b'ID="200" name="Departing"', b'ID="300" name="Extra"', 1
    )
    archive = _archive(
        tmp_path,
        extras={"framenet_v17/frame/Extra.xml": extra},
    )

    with pytest.raises(FrameNetProjectionError, match="index/member mismatch"):
        compile_framenet_projection_v1(_manifest(archive), source_archive=archive)


def test_projection_rejects_unknown_frame_element_core_type(tmp_path: Path) -> None:
    member = "framenet_v17/frame/Quitting_a_place.xml"
    changed = _fixture_members()[member].replace(b'coreType="Core"', b'coreType="Mystery"', 1)
    archive = _archive(tmp_path, replacements={member: changed})

    with pytest.raises(FrameNetProjectionError, match="unknown FrameNet core type"):
        compile_framenet_projection_v1(_manifest(archive), source_archive=archive)


def test_projection_model_rejects_corrupted_relation_endpoint(tmp_path: Path) -> None:
    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    payload["frames"][0]["outgoing_relations"][0]["related_frame_id"] = 999

    with pytest.raises(ValidationError, match="dangling endpoint"):
        FrameNetProjectionV1.model_validate(payload)
