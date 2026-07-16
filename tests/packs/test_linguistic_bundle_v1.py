"""Installed pack-plus-adjunct linguistic bundle tests for Plan 0147 Slice 2B."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError
import yaml

from onto_canon6.ontology_runtime.contracts import PackRef
from onto_canon6.packs.linguistic_bundle_v1 import (
    build_linguistic_trace_manifest_v1,
    LinguisticAlignmentRefV1,
    LinguisticBundleV1,
    LinguisticBundleError,
    LinguisticBundleQueryV1,
    inspect_linguistic_bundle_at_roots,
)
from onto_canon6.packs.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    load_linguistic_source_manifest_v1,
)
from scripts.compile_linguistic_core_pack import validate_compiled_pack


REPO_ROOT = Path(__file__).parents[2]
PACKS_ROOT = REPO_ROOT / "ontology_packs"
TRACE_ADJUNCTS_ROOT = REPO_ROOT / "linguistic_trace_adjuncts"
PACK_DIR = PACKS_ROOT / "linguistic_core" / "0.3.0"
TRACE_DIR = TRACE_ADJUNCTS_ROOT / "linguistic_core" / "0.3.0"


def _query(canonical_id: str = "lc:abandon_leave_behind") -> LinguisticBundleQueryV1:
    return LinguisticBundleQueryV1(
        pack_ref=PackRef(pack_id="linguistic_core", pack_version="0.3.0"),
        canonical_predicate_id=canonical_id,
    )


def _copied_bundle_roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Copy the immutable pack and optional trace adjunct into separate roots."""

    packs_root = tmp_path / "ontology_packs"
    pack_dir = packs_root / "linguistic_core" / "0.3.0"
    shutil.copytree(PACK_DIR, pack_dir)
    trace_adjuncts_root = tmp_path / "linguistic_trace_adjuncts"
    trace_dir = trace_adjuncts_root / "linguistic_core" / "0.3.0"
    shutil.copytree(TRACE_DIR, trace_dir)
    return packs_root, trace_adjuncts_root, pack_dir, trace_dir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _alignment_id(
    *, canonical_id: str, source_family: str, source_id: str, relation: str, state: str
) -> str:
    payload = {
        "canonical_id": canonical_id,
        "source_family": source_family,
        "source_id": source_id,
        "relation": relation,
        "state": state,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"lalign1_{digest[:24]}"


def _update_pack_manifest_hash(pack_dir: Path, filename: str) -> None:
    manifest_path = pack_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["build"]["artifact_sha256"][filename] = _sha256(pack_dir / filename)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _retarget_trace_manifest(trace_dir: Path, pack_dir: Path) -> None:
    """Bind a copied adjunct to a deliberately rewritten test pack manifest."""

    trace_path = trace_dir / "linguistic_trace_manifest_v1.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["target_pack_manifest_sha256"] = _sha256(pack_dir / "manifest.yaml")
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")


def _inspect(
    query: LinguisticBundleQueryV1,
    *,
    packs_root: Path | None = None,
    trace_adjuncts_root: Path | None = None,
) -> LinguisticBundleV1:
    return inspect_linguistic_bundle_at_roots(
        query,
        packs_root=PACKS_ROOT if packs_root is None else packs_root,
        trace_adjuncts_root=(
            TRACE_ADJUNCTS_ROOT if trace_adjuncts_root is None else trace_adjuncts_root
        ),
    )


def test_concrete_bundle_separates_exact_frame_identity_from_candidate_alignment() -> None:
    bundle = _inspect(_query())

    assert bundle.predicate.predicate_id == "lc:abandon_leave_behind"
    assert [role.runtime_name for role in bundle.roles] == ["agent", "theme", "location"]
    assert [(item.source_id, item.state) for item in bundle.propbank_refs] == [
        ("abandon-01", "candidate")
    ]
    assert len(bundle.framenet_records) == 1
    aligned = bundle.framenet_records[0]
    assert aligned.alignment.source_id == "Quitting_a_place"
    assert aligned.alignment.state == "candidate"
    assert aligned.alignment.source_identity_status == "exact_source_record"
    assert aligned.frame.frame_id == 1644
    assert aligned.frame.source_ref.member_sha256 == (
        "bddc980e41cf6d3024453506fde44d6c625e63770f75036a38a3a02090dd0f67"
    )
    assert len(aligned.frame.frame_elements) == 26
    assert len(aligned.frame.lexical_units) == 21
    assert sum(item.indexed_for_lookup for item in aligned.frame.lexical_units) == 19
    assert any(
        relation.frame_relation_id == 2343
        and relation.relation_type_name == "ReFraming_Mapping"
        for relation in aligned.frame.outgoing_relations
    )
    assert bundle.sumo_context.status == "source_grounded_bounded"
    assert bundle.sumo_context.source_grounded is True
    assert [(item.source_id, item.state) for item in bundle.sumo_context.donor_refs] == [
        ("abandon_leave_behind", "unresolved")
    ]
    assert all(
        item.source_identity_status == "donor_only"
        for item in bundle.sumo_context.donor_refs
    )
    assert bundle.sumo_context.source_alignment is None
    published_sumo = bundle.sumo_context.published_context
    assert published_sumo is not None
    assert published_sumo.bounded_context.translocation_type_hierarchy == (
        "Translocation",
        "Motion",
        "Process",
        "Physical",
        "Entity",
    )
    assert published_sumo.bounded_context.case_roles == ("agent", "patient")
    assert "location" not in published_sumo.bounded_context.case_roles
    assert bundle.completeness == "framenet_complete_sumo_source_grounded_bounded"
    assert bundle.trace_manifest.raw_archive_packaged is False
    assert bundle.trace_manifest.raw_sumo_module_packaged is False
    assert bundle.trace_manifest.full_sumo_projection_packaged is False
    assert bundle.trace_manifest.target_pack_manifest_sha256 == _sha256(
        PACK_DIR / "manifest.yaml"
    )
    assert bundle.trace_manifest.framenet_source_archive_filename == "framenet_v17.zip"


def test_query_requires_exact_pack_version_and_known_canonical_id() -> None:
    with pytest.raises(ValidationError, match="exact semantic version"):
        LinguisticBundleQueryV1(
            pack_ref=PackRef(pack_id="linguistic_core", pack_version="latest"),
            canonical_predicate_id="lc:abandon_leave_behind",
        )

    with pytest.raises(LinguisticBundleError, match="UNKNOWN_CANONICAL_ID"):
        _inspect(_query("lc:not_present"))


def test_missing_and_changed_adjunct_projection_assets_fail_closed(tmp_path: Path) -> None:
    packs_root, trace_adjuncts_root, _pack_dir, trace_dir = _copied_bundle_roots(tmp_path)
    projection = trace_dir / "framenet_projection_v1.json.gz"
    projection.unlink()
    with pytest.raises(LinguisticBundleError, match="TRACE_ASSET_MISSING"):
        _inspect(
            _query(),
            packs_root=packs_root,
            trace_adjuncts_root=trace_adjuncts_root,
        )

    shutil.copy2(TRACE_DIR / "framenet_projection_v1.json.gz", projection)
    projection.write_bytes(projection.read_bytes() + b"substitution")
    with pytest.raises(LinguisticBundleError, match="TRACE_ASSET_HASH_MISMATCH"):
        _inspect(
            _query(),
            packs_root=packs_root,
            trace_adjuncts_root=trace_adjuncts_root,
        )


def test_missing_changed_or_retargeted_sumo_assets_fail_closed(tmp_path: Path) -> None:
    """Published SUMO context and attribution cannot be omitted or substituted."""

    packs_root, trace_adjuncts_root, _pack_dir, trace_dir = _copied_bundle_roots(tmp_path)
    context = trace_dir / "sumo_bounded_context_v1.json"
    context.unlink()
    with pytest.raises(LinguisticBundleError, match="TRACE_ASSET_MISSING"):
        _inspect(
            _query(), packs_root=packs_root, trace_adjuncts_root=trace_adjuncts_root
        )

    shutil.copy2(TRACE_DIR / "sumo_bounded_context_v1.json", context)
    payload = json.loads(context.read_text(encoding="utf-8"))
    payload["source_module_sha256"] = "0" * 64
    context.write_text(json.dumps(payload), encoding="utf-8")
    trace_path = trace_dir / "linguistic_trace_manifest_v1.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["sumo_context"]["sha256"] = _sha256(context)
    trace["sumo_source_module_sha256"] = "0" * 64
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(LinguisticBundleError, match="INVALID_SUMO_CONTEXT"):
        _inspect(
            _query(), packs_root=packs_root, trace_adjuncts_root=trace_adjuncts_root
        )


def test_trace_adjunct_rejects_same_identity_target_pack_substitution(tmp_path: Path) -> None:
    packs_root, trace_adjuncts_root, pack_dir, _trace_dir = _copied_bundle_roots(tmp_path)
    manifest_path = pack_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["pack"]["description"] += " Substituted after adjunct publication."
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(LinguisticBundleError, match="TRACE_TARGET_PACK_MISMATCH"):
        _inspect(
            _query(),
            packs_root=packs_root,
            trace_adjuncts_root=trace_adjuncts_root,
        )


def test_mapping_to_missing_frame_fails_after_explicit_test_rebinding(
    tmp_path: Path,
) -> None:
    packs_root, trace_adjuncts_root, pack_dir, trace_dir = _copied_bundle_roots(tmp_path)
    mappings_path = pack_dir / "semantic_mappings.jsonl"
    rows = [json.loads(line) for line in mappings_path.read_text(encoding="utf-8").splitlines()]
    target = next(
        row
        for row in rows
        if row.get("canonical_id") == "lc:abandon_leave_behind"
        and row.get("source_key") == "framenet_candidate"
    )
    target["source_id"] = "Missing_frame"
    mappings_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _update_pack_manifest_hash(pack_dir, mappings_path.name)
    _retarget_trace_manifest(trace_dir, pack_dir)

    with pytest.raises(LinguisticBundleError, match="DANGLING_FRAMENET_FRAME"):
        _inspect(
            _query(),
            packs_root=packs_root,
            trace_adjuncts_root=trace_adjuncts_root,
        )


def test_alignment_model_can_represent_independently_verified_framenet_record() -> None:
    alignment = LinguisticAlignmentRefV1(
        alignment_id=_alignment_id(
            canonical_id="lc:abandon_leave_behind",
            source_family="framenet",
            source_id="Quitting_a_place",
            relation="equivalent_to",
            state="verified",
        ),
        canonical_id="lc:abandon_leave_behind",
        source_family="framenet",
        source_id="Quitting_a_place",
        relation="equivalent_to",
        state="verified",
        method="independent_governed_review",
        evidence_refs=("review-evidence:framenet-1644",),
        source_identity_status="exact_source_record",
        verification_record_ref="verification-record:framenet-1644",
    )

    assert alignment.state == "verified"
    assert alignment.verification_record_ref == "verification-record:framenet-1644"


@pytest.mark.parametrize("bad_ref", ("", " ", " padded "))
def test_verified_alignment_rejects_empty_or_untrimmed_verification_ref(
    bad_ref: str,
) -> None:
    """A verified state requires a usable independent-record reference."""

    with pytest.raises(ValidationError):
        LinguisticAlignmentRefV1(
            alignment_id=_alignment_id(
                canonical_id="lc:abandon_leave_behind",
                source_family="framenet",
                source_id="Quitting_a_place",
                relation="equivalent_to",
                state="verified",
            ),
            canonical_id="lc:abandon_leave_behind",
            source_family="framenet",
            source_id="Quitting_a_place",
            relation="equivalent_to",
            state="verified",
            method="independent_governed_review",
            evidence_refs=("review-evidence:framenet-1644",),
            source_identity_status="exact_source_record",
            verification_record_ref=bad_ref,
        )


@pytest.mark.parametrize("bad_ref", ("", " ", " padded "))
def test_verified_alignment_rejects_empty_or_untrimmed_evidence_ref(
    bad_ref: str,
) -> None:
    """A nonempty evidence tuple cannot hide an unusable item."""

    with pytest.raises(ValidationError, match="evidence refs must be nonempty and trimmed"):
        LinguisticAlignmentRefV1(
            alignment_id=_alignment_id(
                canonical_id="lc:abandon_leave_behind",
                source_family="framenet",
                source_id="Quitting_a_place",
                relation="equivalent_to",
                state="verified",
            ),
            canonical_id="lc:abandon_leave_behind",
            source_family="framenet",
            source_id="Quitting_a_place",
            relation="equivalent_to",
            state="verified",
            method="independent_governed_review",
            evidence_refs=(bad_ref,),
            source_identity_status="exact_source_record",
            verification_record_ref="verification-record:framenet-1644",
        )


def test_donor_mapping_cannot_self_promote_after_coordinated_rehash(
    tmp_path: Path,
) -> None:
    packs_root, trace_adjuncts_root, pack_dir, trace_dir = _copied_bundle_roots(tmp_path)
    mappings_path = pack_dir / "semantic_mappings.jsonl"
    rows = [json.loads(line) for line in mappings_path.read_text(encoding="utf-8").splitlines()]
    target = next(
        row
        for row in rows
        if row.get("canonical_id") == "lc:abandon_leave_behind"
        and row.get("source_key") == "framenet_candidate"
    )
    target["source_verified"] = True
    mappings_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _update_pack_manifest_hash(pack_dir, mappings_path.name)
    _retarget_trace_manifest(trace_dir, pack_dir)

    with pytest.raises(LinguisticBundleError, match="INVALID_SEMANTIC_MAPPINGS"):
        _inspect(
            _query(),
            packs_root=packs_root,
            trace_adjuncts_root=trace_adjuncts_root,
        )


def test_reader_ignores_forward_additions_but_revalidates_v1_content(
    tmp_path: Path,
) -> None:
    packs_root, trace_adjuncts_root, pack_dir, trace_dir = _copied_bundle_roots(tmp_path)
    projection_path = trace_dir / "framenet_projection_v1.json.gz"
    projection = json.loads(gzip.decompress(projection_path.read_bytes()))
    projection["future_projection_field"] = {"version": 2}
    projection["frames"][0]["future_frame_field"] = "ignored by V1 reader"
    projection_path.write_bytes(
        gzip.compress((json.dumps(projection) + "\n").encode("utf-8"), mtime=0)
    )

    trace_path = trace_dir / "linguistic_trace_manifest_v1.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["future_trace_field"] = {"version": 2}
    trace["framenet_projection"]["sha256"] = _sha256(projection_path)
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

    manifest_path = pack_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["future_pack_manifest_field"] = "ignored by V1 reader"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    _retarget_trace_manifest(trace_dir, pack_dir)

    bundle = _inspect(
        _query(),
        packs_root=packs_root,
        trace_adjuncts_root=trace_adjuncts_root,
    )
    assert bundle.framenet_records[0].frame.name == "Quitting_a_place"


def test_trace_builder_binds_exact_pack_and_supplied_attribution_metadata() -> None:
    source_manifest = load_linguistic_source_manifest_v1(
        REPO_ROOT / "config" / "linguistic_sources_v1.yaml"
    )

    manifest = build_linguistic_trace_manifest_v1(
        pack_ref=_query().pack_ref,
        projection_path=TRACE_DIR / "framenet_projection_v1.json.gz",
        attribution_path=TRACE_DIR / "framenet_attribution.txt",
        target_pack_manifest_path=PACK_DIR / "manifest.yaml",
        source_manifest=source_manifest,
    )

    assert manifest.target_pack_manifest_sha256 == _sha256(PACK_DIR / "manifest.yaml")
    assert manifest.attribution_title == "FrameNet 1.7"
    assert manifest.attribution_author == "Collin F. Baker"
    assert manifest.attribution_uri == "http://framenet.icsi.berkeley.edu"


def test_trace_builder_rejects_source_identity_or_license_laundering() -> None:
    source_manifest = load_linguistic_source_manifest_v1(
        REPO_ROOT / "config" / "linguistic_sources_v1.yaml"
    )
    payload = source_manifest.model_dump(mode="python")
    frame_source = next(item for item in payload["sources"] if item["family"] == "framenet")
    frame_source["archive_identity"]["sha256"] = "0" * 64
    substituted_manifest = LinguisticSourceManifestV1.model_validate(payload)

    with pytest.raises(LinguisticBundleError, match="SOURCE_OR_LICENSE_MISMATCH"):
        build_linguistic_trace_manifest_v1(
            pack_ref=_query().pack_ref,
            projection_path=TRACE_DIR / "framenet_projection_v1.json.gz",
            attribution_path=TRACE_DIR / "framenet_attribution.txt",
            target_pack_manifest_path=PACK_DIR / "manifest.yaml",
            source_manifest=substituted_manifest,
        )


def test_trace_builder_rejects_coordinated_archive_filename_substitution(
    tmp_path: Path,
) -> None:
    """An internally consistent projection cannot rename the pinned source archive."""

    source_manifest = load_linguistic_source_manifest_v1(
        REPO_ROOT / "config" / "linguistic_sources_v1.yaml"
    )
    projection = json.loads(gzip.decompress((TRACE_DIR / "framenet_projection_v1.json.gz").read_bytes()))
    projection["source_archive_filename"] = "fabricated.zip"
    source_refs = [
        projection["frame_index_ref"],
        projection["lexical_unit_index_ref"],
        projection["relation_index_ref"],
    ]
    for frame in projection["frames"]:
        source_refs.append(frame["source_ref"])
        for direction in ("incoming_relations", "outgoing_relations"):
            source_refs.extend(relation["source_ref"] for relation in frame[direction])
    for source_ref in source_refs:
        source_ref["member_path"] = source_ref["member_path"].replace(
            "framenet_v17/", "fabricated/"
        )
    encoded_frames = json.dumps(
        projection["frames"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    projection["projection_content_sha256"] = hashlib.sha256(encoded_frames).hexdigest()
    substituted_projection = tmp_path / "framenet_projection_v1.json.gz"
    substituted_projection.write_bytes(
        gzip.compress((json.dumps(projection) + "\n").encode("utf-8"), mtime=0)
    )

    with pytest.raises(LinguisticBundleError, match="SOURCE_OR_LICENSE_MISMATCH"):
        build_linguistic_trace_manifest_v1(
            pack_ref=_query().pack_ref,
            projection_path=substituted_projection,
            attribution_path=TRACE_DIR / "framenet_attribution.txt",
            target_pack_manifest_path=PACK_DIR / "manifest.yaml",
            source_manifest=source_manifest,
        )


def test_committed_pack_remains_complete_without_adjunct_assets() -> None:
    validate_compiled_pack(PACK_DIR, require_provenance=True)

    trace_filenames = {path.name for path in TRACE_DIR.iterdir() if path.is_file()}
    pack_filenames = {path.name for path in PACK_DIR.iterdir() if path.is_file()}
    assert trace_filenames == {
        "framenet_attribution.txt",
        "framenet_projection_v1.json.gz",
        "linguistic_trace_manifest_v1.json",
        "sumo_attribution.txt",
        "sumo_bounded_context_v1.json",
    }
    assert trace_filenames.isdisjoint(pack_filenames)
