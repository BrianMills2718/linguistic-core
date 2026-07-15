"""Installed-asset linguistic bundle contract tests for Plan 0147 Slice 2B."""

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
    LinguisticBundleError,
    LinguisticBundleQueryV1,
    inspect_linguistic_bundle_at_root,
)
from onto_canon6.packs.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    load_linguistic_source_manifest_v1,
)


REPO_ROOT = Path(__file__).parents[2]
PACKS_ROOT = REPO_ROOT / "ontology_packs"


def _query(canonical_id: str = "lc:abandon_leave_behind") -> LinguisticBundleQueryV1:
    return LinguisticBundleQueryV1(
        pack_ref=PackRef(pack_id="linguistic_core", pack_version="0.3.0"),
        canonical_predicate_id=canonical_id,
    )


def _copied_pack(tmp_path: Path) -> tuple[Path, Path]:
    packs_root = tmp_path / "ontology_packs"
    pack_dir = packs_root / "linguistic_core" / "0.3.0"
    shutil.copytree(PACKS_ROOT / "linguistic_core" / "0.3.0", pack_dir)
    return packs_root, pack_dir


def _update_manifest_hash(pack_dir: Path, filename: str) -> None:
    manifest_path = pack_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["build"]["artifact_sha256"][filename] = hashlib.sha256(
        (pack_dir / filename).read_bytes()
    ).hexdigest()
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_concrete_bundle_separates_exact_frame_identity_from_candidate_alignment() -> None:
    bundle = inspect_linguistic_bundle_at_root(_query(), packs_root=PACKS_ROOT)

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
    assert bundle.sumo_context.status == "pending_source_projection"
    assert bundle.sumo_context.source_grounded is False
    assert bundle.trace_manifest.raw_archive_packaged is False


def test_query_requires_exact_pack_version_and_known_canonical_id() -> None:
    with pytest.raises(ValidationError, match="exact semantic version"):
        LinguisticBundleQueryV1(
            pack_ref=PackRef(pack_id="linguistic_core", pack_version="latest"),
            canonical_predicate_id="lc:abandon_leave_behind",
        )

    with pytest.raises(LinguisticBundleError, match="UNKNOWN_CANONICAL_ID"):
        inspect_linguistic_bundle_at_root(_query("lc:not_present"), packs_root=PACKS_ROOT)


def test_missing_and_changed_projection_assets_fail_closed(tmp_path: Path) -> None:
    packs_root, pack_dir = _copied_pack(tmp_path)
    projection = pack_dir / "framenet_projection_v1.json.gz"
    projection.unlink()
    with pytest.raises(LinguisticBundleError, match="ASSET_MISSING"):
        inspect_linguistic_bundle_at_root(_query(), packs_root=packs_root)

    shutil.copy2(
        PACKS_ROOT / "linguistic_core" / "0.3.0" / "framenet_projection_v1.json.gz",
        projection,
    )
    projection.write_bytes(projection.read_bytes() + b"substitution")
    with pytest.raises(LinguisticBundleError, match="ASSET_HASH_MISMATCH"):
        inspect_linguistic_bundle_at_root(_query(), packs_root=packs_root)


def test_mapping_to_missing_frame_fails_even_when_attacker_rehashes_asset(
    tmp_path: Path,
) -> None:
    packs_root, pack_dir = _copied_pack(tmp_path)
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
    _update_manifest_hash(pack_dir, mappings_path.name)

    with pytest.raises(LinguisticBundleError, match="DANGLING_FRAMENET_FRAME"):
        inspect_linguistic_bundle_at_root(_query(), packs_root=packs_root)


def test_framenet_candidate_cannot_be_rehashed_as_verified() -> None:
    candidate = inspect_linguistic_bundle_at_root(
        _query(), packs_root=PACKS_ROOT
    ).framenet_records[0].alignment
    payload = candidate.model_dump(mode="python")
    payload["state"] = "verified"
    payload["verification_record_ref"] = "review:invented"
    identity_payload = {
        "canonical_id": payload["canonical_id"],
        "source_family": payload["source_family"],
        "source_id": payload["source_id"],
        "relation": payload["relation"],
        "state": payload["state"],
    }
    payload["alignment_id"] = "lalign1_" + hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]

    with pytest.raises(ValidationError, match="must remain candidate"):
        LinguisticAlignmentRefV1.model_validate(payload)


def test_installed_reader_ignores_forward_additions_but_revalidates_v1_content(
    tmp_path: Path,
) -> None:
    packs_root, pack_dir = _copied_pack(tmp_path)
    projection_path = pack_dir / "framenet_projection_v1.json.gz"
    projection = json.loads(gzip.decompress(projection_path.read_bytes()))
    projection["future_projection_field"] = {"version": 2}
    projection["frames"][0]["future_frame_field"] = "ignored by V1 reader"
    projection_path.write_bytes(
        gzip.compress((json.dumps(projection) + "\n").encode("utf-8"), mtime=0)
    )

    trace_path = pack_dir / "linguistic_trace_manifest_v1.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["future_trace_field"] = {"version": 2}
    trace["framenet_projection"]["sha256"] = hashlib.sha256(
        projection_path.read_bytes()
    ).hexdigest()
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

    manifest_path = pack_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["linguistic_trace"]["future_manifest_field"] = "ignored by V1 reader"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    _update_manifest_hash(pack_dir, projection_path.name)
    _update_manifest_hash(pack_dir, trace_path.name)

    bundle = inspect_linguistic_bundle_at_root(_query(), packs_root=packs_root)
    assert bundle.framenet_records[0].frame.name == "Quitting_a_place"


def test_trace_builder_rejects_source_identity_or_license_laundering() -> None:
    source_manifest = load_linguistic_source_manifest_v1(
        REPO_ROOT / "config" / "linguistic_sources_v1.yaml"
    )
    payload = source_manifest.model_dump(mode="python")
    frame_source = next(item for item in payload["sources"] if item["family"] == "framenet")
    frame_source["archive_identity"]["sha256"] = "0" * 64
    substituted_manifest = LinguisticSourceManifestV1.model_validate(payload)
    pack_dir = PACKS_ROOT / "linguistic_core" / "0.3.0"

    with pytest.raises(LinguisticBundleError, match="SOURCE_OR_LICENSE_MISMATCH"):
        build_linguistic_trace_manifest_v1(
            pack_ref=_query().pack_ref,
            projection_path=pack_dir / "framenet_projection_v1.json.gz",
            attribution_path=pack_dir / "framenet_attribution.txt",
            source_manifest=substituted_manifest,
        )
