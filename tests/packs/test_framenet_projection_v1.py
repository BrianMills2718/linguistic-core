"""Deterministic and fail-closed FrameNet projection tests for Plan 0147."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import cast
import zipfile

import pytest
from pydantic import ValidationError
import yaml

from scripts.compile_framenet_projection import main as compile_framenet_projection_main

from linguistic_core.framenet_projection_v1 import (
    FrameNetProjectionError,
    FrameNetProjectionV1,
    compile_framenet_projection_v1,
    load_framenet_projection_v1,
)
from linguistic_core.linguistic_bundle_v1 import LinguisticBundleError
from linguistic_core.linguistic_sources_v1 import (
    ArchiveSourceIdentityV1,
    DistributionMetadataEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
)


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "linguistic_sources" / "framenet"
REPO_ROOT = Path(__file__).parents[2]
COMMITTED_PROJECTION = (
    REPO_ROOT
    / "linguistic_trace_adjuncts"
    / "linguistic_core"
    / "0.3.0"
    / "framenet_projection_v1.json.gz"
)


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
                attribution_title="FrameNet 1.7",
                attribution_author="Fixture Author",
                attribution_uri="https://example.invalid/framenet",
            ),
        ),
        license_disposition="verified_redistributable",
        storage_policy="external_cache",
        redistribution_allowed=True,
    )
    return LinguisticSourceManifestV1(sources=(source,))


def _write_target_pack_manifest(path: Path) -> None:
    """Write the exact pack identity required by the trace-manifest builder."""

    path.write_text(
        yaml.safe_dump(
            {"pack": {"id": "linguistic_core", "version": "0.3.0"}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _valid_attribution_text() -> str:
    """Return all attribution evidence supplied by the fixture metadata."""

    return "\n".join(
        (
            "Title: FrameNet 1.7",
            "Original author: Fixture Author",
            "Source URI supplied by the distributor: https://example.invalid/framenet",
            "Distribution: https://example.invalid/framenet_v17.zip",
            "License: CC-BY-3.0",
            "https://creativecommons.org/licenses/by/3.0/",
            "",
        )
    )


def _rehash_projection_content(payload: dict[str, object]) -> None:
    """Recompute the existing self-hash after an adversarial content mutation."""

    frames = payload["frames"]
    encoded = json.dumps(frames, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["projection_content_sha256"] = hashlib.sha256(encoded).hexdigest()


def _frame_payload(payload: dict[str, object], name: str) -> dict[str, object]:
    """Return one mutable frame payload by exact source name."""

    frames = payload["frames"]
    assert isinstance(frames, (list, tuple))
    return cast(dict[str, object], next(frame for frame in frames if frame["name"] == name))


def _committed_projection_payload() -> dict[str, object]:
    """Load the real checked-in projection for count-preserving corruption controls."""

    return cast(dict[str, object], json.loads(gzip.decompress(COMMITTED_PROJECTION.read_bytes())))


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


def test_projection_model_rejects_rehashed_frame_source_ref_substitution(
    tmp_path: Path,
) -> None:
    """Self-rehashing cannot turn a fabricated member into an exact source record."""

    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    frame = _frame_payload(payload, "Quitting_a_place")
    frame["source_ref"] = {
        "source_key": "fabricated_source",
        "archive_sha256": "f" * 64,
        "member_path": "fabricated/frame.xml",
        "member_sha256": "1" * 64,
    }
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="source reference"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_binds_every_member_prefix_to_archive_filename(
    tmp_path: Path,
) -> None:
    """A coordinated member-prefix rewrite cannot retain the exact archive claim."""

    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    source_refs = [
        payload["frame_index_ref"],
        payload["lexical_unit_index_ref"],
        payload["relation_index_ref"],
    ]
    frames = cast(list[dict[str, object]], payload["frames"])
    for frame in frames:
        source_refs.append(frame["source_ref"])
        for direction in ("incoming_relations", "outgoing_relations"):
            relations = cast(list[dict[str, object]], frame[direction])
            source_refs.extend(relation["source_ref"] for relation in relations)
    for untyped_ref in source_refs:
        source_ref = cast(dict[str, object], untyped_ref)
        member_path = cast(str, source_ref["member_path"])
        source_ref["member_path"] = member_path.replace("framenet_v17/", "fabricated/")
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="source reference"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_relation_source_ref_substitution(
    tmp_path: Path,
) -> None:
    """Every mirrored relation remains bound to the exact relation-index member."""

    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    frame = _frame_payload(payload, "Quitting_a_place")
    outgoing = frame["outgoing_relations"]
    assert isinstance(outgoing, (list, tuple))
    relation = cast(dict[str, object], outgoing[0])
    source_ref = cast(dict[str, object], relation["source_ref"])
    source_ref["member_path"] = "fabricated/frRelation.xml"
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="relation source reference"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_incoming_relation_mirror_drift(
    tmp_path: Path,
) -> None:
    """Incoming mirrors cannot change relation metadata or FE endpoints."""

    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    frame = _frame_payload(payload, "Departing")
    incoming = frame["incoming_relations"]
    assert isinstance(incoming, (list, tuple))
    relation = cast(dict[str, object], incoming[0])
    relation["relation_type_name"] = "FABRICATED_RELATION_TYPE"
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="incoming relation mirror"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_incoming_fe_endpoint_drift(
    tmp_path: Path,
) -> None:
    """Incoming FE mirrors resolve against the declared sub/super frames."""

    archive = _archive(tmp_path)
    projection = compile_framenet_projection_v1(_manifest(archive), source_archive=archive)
    payload = projection.model_dump(mode="python")
    frame = _frame_payload(payload, "Departing")
    incoming = frame["incoming_relations"]
    assert isinstance(incoming, (list, tuple))
    relation = cast(dict[str, object], incoming[0])
    fe_relations = cast(tuple[dict[str, object], ...], relation["frame_element_relations"])
    fe_relations[0]["sub_frame_element_id"] = 999_999_999
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="dangling or drifted endpoint"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_global_relation_type_name_drift() -> None:
    """One mirrored edge cannot rename a relation type used by other exact edges."""

    payload = _committed_projection_payload()
    frames = cast(list[dict[str, object]], payload["frames"])
    containing_frame = next(
        frame
        for frame in frames
        if any(
            relation["relation_type_id"] == 1
            for relation in cast(list[dict[str, object]], frame["outgoing_relations"])
        )
    )
    outgoing = next(
        relation
        for relation in cast(
            list[dict[str, object]], containing_frame["outgoing_relations"]
        )
        if relation["relation_type_id"] == 1
    )
    related_frame = next(
        frame for frame in frames if frame["frame_id"] == outgoing["related_frame_id"]
    )
    incoming = next(
        relation
        for relation in cast(list[dict[str, object]], related_frame["incoming_relations"])
        if relation["frame_relation_id"] == outgoing["frame_relation_id"]
    )
    outgoing["relation_type_name"] = "FABRICATED_RELATION_TYPE"
    incoming["relation_type_name"] = "FABRICATED_RELATION_TYPE"
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="relation-type ID has conflicting metadata"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_global_frame_relation_id_duplicate() -> None:
    """Two otherwise closed mirrored edges cannot share one source relation ID."""

    payload = _committed_projection_payload()
    frames = cast(list[dict[str, object]], payload["frames"])
    outgoing_records = [
        (frame, relation)
        for frame in frames
        for relation in cast(list[dict[str, object]], frame["outgoing_relations"])
    ]
    first_frame, first = outgoing_records[0]
    second_frame, second = next(
        (frame, relation)
        for frame, relation in outgoing_records[1:]
        if (
            relation["relation_type_id"],
            frame["frame_id"],
            relation["related_frame_id"],
        )
        != (
            first["relation_type_id"],
            first_frame["frame_id"],
            first["related_frame_id"],
        )
    )
    second_target = next(
        frame for frame in frames if frame["frame_id"] == second["related_frame_id"]
    )
    second_incoming = next(
        relation
        for relation in cast(
            list[dict[str, object]], second_target["incoming_relations"]
        )
        if relation["frame_relation_id"] == second["frame_relation_id"]
        and relation["related_frame_id"] == second_frame["frame_id"]
    )
    second["frame_relation_id"] = first["frame_relation_id"]
    second_incoming["frame_relation_id"] = first["frame_relation_id"]
    def relation_key(relation: dict[str, object]) -> tuple[int, int, int]:
        return (
            cast(int, relation["relation_type_id"]),
            cast(int, relation["frame_relation_id"]),
            cast(int, relation["related_frame_id"]),
        )
    cast(list[dict[str, object]], second_frame["outgoing_relations"]).sort(
        key=relation_key
    )
    cast(list[dict[str, object]], second_target["incoming_relations"]).sort(
        key=relation_key
    )
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="frame-relation IDs must be globally unique"):
        FrameNetProjectionV1.model_validate(payload)


def test_projection_model_rejects_rehashed_global_semantic_type_name_drift() -> None:
    """One source reference cannot rename a semantic type shared by other FEs."""

    payload = _committed_projection_payload()
    frames = cast(list[dict[str, object]], payload["frames"])
    matching_types = [
        semantic_type
        for frame in frames
        for frame_element in cast(list[dict[str, object]], frame["frame_elements"])
        for semantic_type in cast(
            list[dict[str, object]], frame_element["semantic_types"]
        )
        if semantic_type["semantic_type_id"] == 182
    ]
    assert len(matching_types) > 1
    matching_types[0]["name"] = "FABRICATED_SEMANTIC_TYPE"
    _rehash_projection_content(payload)

    with pytest.raises(ValidationError, match="semantic-type ID has conflicting names"):
        FrameNetProjectionV1.model_validate(payload)


@pytest.mark.parametrize(
    ("left", "right"),
    (
        ("projection", "trace"),
        ("projection", "attribution"),
        ("projection", "target"),
        ("projection", "manifest"),
        ("projection", "source"),
        ("trace", "attribution"),
        ("trace", "target"),
        ("trace", "manifest"),
        ("trace", "source"),
        ("attribution", "target"),
        ("attribution", "manifest"),
        ("attribution", "source"),
        ("target", "manifest"),
        ("target", "source"),
        ("manifest", "source"),
    ),
)
def test_projection_cli_rejects_every_trace_path_collision_before_writing(
    tmp_path: Path,
    left: str,
    right: str,
) -> None:
    """All output and trace-input paths must be pairwise distinct under --force."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    paths = {
        "projection": tmp_path / "projection.json",
        "trace": tmp_path / "trace.json",
        "attribution": tmp_path / "attribution.json",
        "target": tmp_path / "target.json",
        "manifest": manifest_path,
        "source": archive,
    }
    paths["attribution"].write_text("sentinel attribution", encoding="utf-8")
    _write_target_pack_manifest(paths["target"])
    paths[right] = paths[left]
    before = {
        path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()
    }

    with pytest.raises(ValueError, match="distinct"):
        compile_framenet_projection_main(
            [
                "--manifest",
                str(paths["manifest"]),
                "--source-archive",
                str(paths["source"]),
                "--output",
                str(paths["projection"]),
                "--trace-manifest-output",
                str(paths["trace"]),
                "--attribution",
                str(paths["attribution"]),
                "--target-pack-manifest",
                str(paths["target"]),
                "--force",
            ]
        )
    after = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert after == before


@pytest.mark.parametrize("input_name", ("manifest", "source"))
def test_projection_only_cli_rejects_output_input_collision_before_reading(
    tmp_path: Path,
    input_name: str,
) -> None:
    """Projection-only mode cannot overwrite either required input under --force."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    inputs = {"manifest": manifest_path, "source": archive}
    before = {path: path.read_bytes() for path in inputs.values()}

    with pytest.raises(ValueError, match="inputs and outputs must be distinct"):
        compile_framenet_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-archive",
                str(archive),
                "--output",
                str(inputs[input_name]),
                "--force",
            ]
        )
    assert {path: path.read_bytes() for path in inputs.values()} == before


def test_projection_cli_requires_target_pack_manifest_for_trace(tmp_path: Path) -> None:
    """A trace adjunct cannot be built without its immutable target identity."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    attribution = tmp_path / "attribution.txt"
    attribution.write_text(_valid_attribution_text(), encoding="utf-8")
    projection_output = tmp_path / "projection.json.gz"
    trace_output = tmp_path / "trace.json"

    with pytest.raises(ValueError, match="--target-pack-manifest"):
        compile_framenet_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-archive",
                str(archive),
                "--output",
                str(projection_output),
                "--trace-manifest-output",
                str(trace_output),
                "--attribution",
                str(attribution),
            ]
        )
    assert not projection_output.exists()
    assert not trace_output.exists()


def test_projection_cli_preserves_atomic_single_output_behavior(tmp_path: Path) -> None:
    """Projection-only publication stays deterministic and refuses implicit overwrite."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "projection.json.gz"
    arguments = [
        "--manifest",
        str(manifest_path),
        "--source-archive",
        str(archive),
        "--output",
        str(output),
    ]

    assert compile_framenet_projection_main(arguments) == 0
    original = output.read_bytes()
    with pytest.raises(FileExistsError, match="--force"):
        compile_framenet_projection_main(arguments)
    assert output.read_bytes() == original
    assert compile_framenet_projection_main([*arguments, "--force"]) == 0
    assert output.read_bytes() == original
    assert not tuple(tmp_path.glob(".projection.json.gz.*"))


def test_projection_cli_trace_failure_leaves_no_partial_output(tmp_path: Path) -> None:
    """All trace prerequisites validate before either requested output is published."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    attribution = tmp_path / "attribution.txt"
    attribution.write_text("deliberately incomplete attribution", encoding="utf-8")
    target_pack_manifest = tmp_path / "manifest.yaml"
    _write_target_pack_manifest(target_pack_manifest)
    projection_output = tmp_path / "projection.json.gz"
    trace_output = tmp_path / "trace.json"

    with pytest.raises(LinguisticBundleError, match="INVALID_ATTRIBUTION"):
        compile_framenet_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-archive",
                str(archive),
                "--output",
                str(projection_output),
                "--trace-manifest-output",
                str(trace_output),
                "--attribution",
                str(attribution),
                "--target-pack-manifest",
                str(target_pack_manifest),
            ]
        )
    assert not projection_output.exists()
    assert not trace_output.exists()


def test_projection_cli_publishes_validated_projection_and_trace_together(
    tmp_path: Path,
) -> None:
    """A valid trace run publishes two mutually consistent completed payloads."""

    archive = _archive(tmp_path)
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(archive).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    attribution = tmp_path / "attribution.txt"
    attribution.write_text(_valid_attribution_text(), encoding="utf-8")
    target_pack_manifest = tmp_path / "manifest.yaml"
    _write_target_pack_manifest(target_pack_manifest)
    projection_output = tmp_path / "projection.json.gz"
    trace_output = tmp_path / "trace.json"

    assert (
        compile_framenet_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-archive",
                str(archive),
                "--output",
                str(projection_output),
                "--trace-manifest-output",
                str(trace_output),
                "--attribution",
                str(attribution),
                "--target-pack-manifest",
                str(target_pack_manifest),
            ]
        )
        == 0
    )

    projection = load_framenet_projection_v1(projection_output)
    trace = json.loads(trace_output.read_text(encoding="utf-8"))
    assert trace["framenet_projection"]["filename"] == projection_output.name
    assert trace["framenet_projection"]["sha256"] == hashlib.sha256(
        projection_output.read_bytes()
    ).hexdigest()
    assert trace["framenet_projection_content_sha256"] == (
        projection.projection_content_sha256
    )
    assert trace["target_pack_manifest_sha256"] == hashlib.sha256(
        target_pack_manifest.read_bytes()
    ).hexdigest()
