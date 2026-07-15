"""Inspect one exact installed linguistic bundle without donor or source caches.

The reader validates every package-owned input against the pack and linguistic
trace manifests. Exact FrameNet record identity remains separate from donor
candidate alignment status; this module never promotes a mapping or feeds trace
assets into runtime alias loading.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from onto_canon6.ontology_runtime.contracts import PackRef
from onto_canon6.packaged_assets import installed_ontology_packs_root
from onto_canon6.packs.framenet_projection_v1 import (
    FrameNetFrameRecordV1,
    FrameNetProjectionV1,
)
from onto_canon6.packs.linguistic_sources_v1 import LinguisticSourceManifestV1
from onto_canon6.packs.semantic_provenance import SemanticMappingRecord


class LinguisticBundleError(RuntimeError):
    """Raised when an exact installed bundle cannot be returned truthfully."""


class LinguisticTraceFileV1(BaseModel):
    """One package-owned trace file bound to its exact installed bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str = Field(min_length=1, description="Safe filename inside the exact pack.")
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete installed file."
    )

    @model_validator(mode="after")
    def _filename_is_safe(self) -> "LinguisticTraceFileV1":
        path = PurePosixPath(self.filename)
        if path.name != self.filename or self.filename in {".", ".."}:
            raise ValueError("trace filename must be one safe basename")
        return self


class LinguisticTraceManifestV1(BaseModel):
    """Strict producer manifest for separately hashed linguistic trace assets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-trace-manifest-v1"] = Field(
        default="linguistic-trace-manifest-v1", description="Manifest discriminator."
    )
    pack_ref: PackRef = Field(description="Exact installed pack owning the trace assets.")
    framenet_projection: LinguisticTraceFileV1 = Field(
        description="Complete deterministic FrameNet projection file."
    )
    framenet_projection_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized FrameNet projection content digest."
    )
    framenet_source_key: str = Field(min_length=1, description="Pinned FrameNet source key.")
    framenet_source_archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the external source archive."
    )
    framenet_source_archive_byte_count: int = Field(
        gt=0, description="Exact external source archive byte length."
    )
    framenet_distribution_url: str = Field(
        pattern=r"^https://", description="Maintained distribution URL bound by source metadata."
    )
    frame_count: int = Field(gt=0, description="Exact projected frame count.")
    frame_element_count: int = Field(ge=0, description="Exact projected FE count.")
    lexical_unit_declaration_count: int = Field(
        ge=0, description="All embedded lexical-unit declarations."
    )
    indexed_lexical_unit_count: int = Field(
        ge=0, description="Exact luIndex-selected lexical-unit count."
    )
    frame_relation_count: int = Field(ge=0, description="Exact frame-relation count.")
    frame_element_relation_count: int = Field(
        ge=0, description="Exact nested FE-relation count."
    )
    attribution: LinguisticTraceFileV1 = Field(
        description="Installed attribution and license notice."
    )
    license_id: Literal["CC-BY-3.0"] = Field(
        description="Reviewed license identifier for the retained FrameNet distribution."
    )
    license_url: Literal["https://creativecommons.org/licenses/by/3.0/"] = Field(
        description="Human-readable license terms URL."
    )
    raw_archive_packaged: Literal[False] = Field(
        default=False, description="The external raw archive must never be installed."
    )


class LinguisticBundleQueryV1(BaseModel):
    """Exact pack and canonical predicate requested by one bundle inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_ref: PackRef = Field(description="Explicit semver pack reference; latest is forbidden.")
    canonical_predicate_id: str = Field(
        pattern=r"^lc:[a-z0-9_]+$", description="Exact canonical linguistic predicate ID."
    )

    @model_validator(mode="after")
    def _pack_ref_is_exact(self) -> "LinguisticBundleQueryV1":
        if self.pack_ref.pack_id != "linguistic_core":
            raise ValueError("linguistic bundle V1 accepts only linguistic_core")
        parts = self.pack_ref.pack_version.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError("linguistic bundle requires an exact semantic version")
        return self


class CanonicalPredicateEntryV1(BaseModel):
    """Strict canonical predicate returned from the exact runtime pack asset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_id: str = Field(min_length=1, description="Canonical predicate ID.")
    family: str = Field(min_length=1, description="Runtime predicate family.")
    preferred_label: str = Field(min_length=1, description="Canonical preferred label.")
    description: str = Field(description="Canonical predicate description.")
    status: str = Field(min_length=1, description="Canonical predicate status.")


class CanonicalRoleEntryV1(BaseModel):
    """One ordered canonical role and its predicate cardinality."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: str = Field(min_length=1, description="Canonical role ID.")
    runtime_name: str = Field(min_length=1, description="Runtime role key.")
    preferred_label: str = Field(min_length=1, description="Canonical role label.")
    status: str = Field(min_length=1, description="Canonical role status.")
    required: bool = Field(description="Whether the predicate requires the role.")
    min_count: int = Field(ge=0, description="Minimum role cardinality.")
    max_count: int | None = Field(
        default=None, ge=0, description="Maximum cardinality, or null when unbounded."
    )

    @model_validator(mode="after")
    def _cardinality_is_consistent(self) -> "CanonicalRoleEntryV1":
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("canonical role maximum is below its minimum")
        if self.required != (self.min_count > 0):
            raise ValueError("canonical role required flag and minimum disagree")
        return self


AlignmentState = Literal["candidate", "verified", "rejected", "unresolved"]
SourceIdentityStatus = Literal["exact_source_record", "donor_only", "pending_projection"]


class LinguisticAlignmentRefV1(BaseModel):
    """One derived alignment ID with separate semantic and source-identity states."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alignment_id: str = Field(
        pattern=r"^lalign1_[0-9a-f]{24}$", description="System-derived stable alignment ID."
    )
    canonical_id: str = Field(min_length=1, description="Canonical object being aligned.")
    source_family: Literal["propbank", "framenet", "sumo"] = Field(
        description="External linguistic source family."
    )
    source_id: str = Field(min_length=1, description="Source or donor identifier.")
    relation: str = Field(min_length=1, description="Declared mapping relation.")
    state: AlignmentState = Field(description="Semantic alignment review state.")
    method: str = Field(min_length=1, description="Observed derivation method.")
    evidence_refs: tuple[str, ...] = Field(
        min_length=1, description="Nonempty evidence references supporting this record."
    )
    source_identity_status: SourceIdentityStatus = Field(
        description="Whether the source record itself has exact upstream identity."
    )
    verification_record_ref: str | None = Field(
        default=None, description="Independent review record required only for verified state."
    )

    @model_validator(mode="after")
    def _state_and_derived_id_are_consistent(self) -> "LinguisticAlignmentRefV1":
        expected = _alignment_id(
            canonical_id=self.canonical_id,
            source_family=self.source_family,
            source_id=self.source_id,
            relation=self.relation,
            state=self.state,
        )
        if self.alignment_id != expected:
            raise ValueError("linguistic alignment ID does not match its content")
        if (self.state == "verified") != (self.verification_record_ref is not None):
            raise ValueError("verified alignment requires an independent verification record")
        if self.source_family == "framenet" and self.state != "candidate":
            raise ValueError("FrameNet donor alignment must remain candidate in Slice 2B")
        return self


class FrameNetAlignedRecordV1(BaseModel):
    """Exact FrameNet frame paired with its independently typed alignment state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alignment: LinguisticAlignmentRefV1 = Field(description="Predicate-to-frame alignment.")
    frame: FrameNetFrameRecordV1 = Field(description="Exact source-native FrameNet record.")

    @model_validator(mode="after")
    def _alignment_matches_frame(self) -> "FrameNetAlignedRecordV1":
        if (
            self.alignment.source_family != "framenet"
            or self.alignment.source_id != self.frame.name
            or self.alignment.source_identity_status != "exact_source_record"
        ):
            raise ValueError("FrameNet alignment does not match its exact frame record")
        return self


class SumoBundleContextV1(BaseModel):
    """Honest pre-Slice-2C SUMO context without source-grounding claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["pending_source_projection"] = Field(
        default="pending_source_projection", description="SUMO Slice 2C is not yet complete."
    )
    source_grounded: Literal[False] = Field(
        default=False, description="Donor references are not exact current SUMO source records."
    )
    donor_refs: tuple[LinguisticAlignmentRefV1, ...] = Field(
        description="Bounded donor-only SUMO references for this predicate."
    )


class LinguisticBundleAssetDigestsV1(BaseModel):
    """Exact installed bytes consumed to produce one query response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_manifest_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed pack-manifest SHA-256."
    )
    trace_manifest_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed trace-manifest SHA-256."
    )
    predicate_types_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed predicate-types SHA-256."
    )
    role_types_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed role-types SHA-256."
    )
    predicate_role_edges_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed predicate-role-edges SHA-256."
    )
    semantic_mappings_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed semantic-mappings SHA-256."
    )
    framenet_projection_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed installed FrameNet projection SHA-256."
    )
    attribution_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Observed FrameNet attribution SHA-256."
    )


class LinguisticBundleV1(BaseModel):
    """One provenance-honest installed linguistic predicate bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-bundle-v1"] = Field(
        default="linguistic-bundle-v1", description="Bundle contract discriminator."
    )
    query: LinguisticBundleQueryV1 = Field(description="Exact query producing this bundle.")
    predicate: CanonicalPredicateEntryV1 = Field(description="Canonical predicate entry.")
    roles: tuple[CanonicalRoleEntryV1, ...] = Field(description="Roles in pack edge order.")
    propbank_refs: tuple[LinguisticAlignmentRefV1, ...] = Field(
        description="Donor PropBank references with honest alignment state."
    )
    framenet_records: tuple[FrameNetAlignedRecordV1, ...] = Field(
        description="Exact FrameNet records paired with candidate alignments."
    )
    sumo_context: SumoBundleContextV1 = Field(description="Bounded pre-Slice-2C SUMO context.")
    completeness: Literal["framenet_complete_sumo_pending"] = Field(
        default="framenet_complete_sumo_pending",
        description="FrameNet vertical path is complete; source-grounded SUMO is pending.",
    )
    trace_manifest: LinguisticTraceManifestV1 = Field(
        description="Exact installed trace contract supporting FrameNet records."
    )
    asset_digests: LinguisticBundleAssetDigestsV1 = Field(
        description="All installed asset bytes read for this response."
    )

    @model_validator(mode="after")
    def _bundle_reconciles(self) -> "LinguisticBundleV1":
        if self.query.canonical_predicate_id != self.predicate.predicate_id:
            raise ValueError("bundle predicate does not match query")
        if self.query.pack_ref != self.trace_manifest.pack_ref:
            raise ValueError("bundle query and trace manifest pack refs differ")
        role_ids = [role.role_id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("bundle canonical roles must be unique")
        for alignment in (
            *self.propbank_refs,
            *(record.alignment for record in self.framenet_records),
            *self.sumo_context.donor_refs,
        ):
            if alignment.canonical_id != self.predicate.predicate_id:
                raise ValueError("bundle alignment belongs to another canonical predicate")
        return self


class _PredicateRowV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    predicate_id: str
    family: str
    preferred_label: str
    description: str
    status: str


class _RoleRowV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    role_id: str
    runtime_name: str
    preferred_label: str
    status: str


class _PredicateRoleEdgeRowV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    predicate_id: str
    role_id: str
    required: bool
    min_count: int
    max_count: int | None


def _normalized_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _alignment_id(
    *,
    canonical_id: str,
    source_family: str,
    source_id: str,
    relation: str,
    state: str,
) -> str:
    digest = _normalized_sha256(
        {
            "canonical_id": canonical_id,
            "source_family": source_family,
            "source_id": source_id,
            "relation": relation,
            "state": state,
        }
    )
    return f"lalign1_{digest[:24]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LinguisticBundleError(f"LINGUISTIC_BUNDLE_ASSET_READ_ERROR filename={path.name}") from exc
    return digest.hexdigest()


def build_linguistic_trace_manifest_v1(
    *,
    pack_ref: PackRef,
    projection_path: Path,
    attribution_path: Path,
    source_manifest: LinguisticSourceManifestV1,
) -> LinguisticTraceManifestV1:
    """Build a strict trace manifest from completed package-owned assets."""

    projection = _load_projection_compatible(projection_path)
    source = next(
        (item for item in source_manifest.sources if item.source_key == projection.source_key),
        None,
    )
    if source is None or source.family != "framenet" or source.archive_identity is None:
        raise LinguisticBundleError("LINGUISTIC_TRACE_MISSING_FRAMENET_SOURCE_IDENTITY")
    archive = source.archive_identity
    license_ids = {
        item.license_id
        for item in source.metadata_evidence
        if item.evidence_scope == "license" and item.license_id is not None
    }
    if (
        archive.sha256 != projection.source_archive_sha256
        or archive.byte_count != projection.source_archive_byte_count
        or source.license_disposition != "verified_redistributable"
        or source.redistribution_allowed is not True
        or license_ids != {"CC-BY-3.0"}
    ):
        raise LinguisticBundleError("LINGUISTIC_TRACE_SOURCE_OR_LICENSE_MISMATCH")
    try:
        attribution_text = attribution_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LinguisticBundleError("LINGUISTIC_TRACE_INVALID_ATTRIBUTION") from exc
    if (
        "FrameNet 1.7" not in attribution_text
        or "CC-BY-3.0" not in attribution_text
        or "https://creativecommons.org/licenses/by/3.0/" not in attribution_text
        or archive.distribution_url not in attribution_text
    ):
        raise LinguisticBundleError("LINGUISTIC_TRACE_INVALID_ATTRIBUTION")
    return LinguisticTraceManifestV1(
        pack_ref=pack_ref,
        framenet_projection=LinguisticTraceFileV1(
            filename=projection_path.name,
            sha256=_sha256_file(projection_path),
        ),
        framenet_projection_content_sha256=projection.projection_content_sha256,
        framenet_source_key=projection.source_key,
        framenet_source_archive_sha256=projection.source_archive_sha256,
        framenet_source_archive_byte_count=projection.source_archive_byte_count,
        framenet_distribution_url=archive.distribution_url,
        frame_count=projection.frame_count,
        frame_element_count=projection.frame_element_count,
        lexical_unit_declaration_count=projection.lexical_unit_declaration_count,
        indexed_lexical_unit_count=projection.indexed_lexical_unit_count,
        frame_relation_count=projection.frame_relation_count,
        frame_element_relation_count=projection.frame_element_relation_count,
        attribution=LinguisticTraceFileV1(
            filename=attribution_path.name,
            sha256=_sha256_file(attribution_path),
        ),
        license_id="CC-BY-3.0",
        license_url="https://creativecommons.org/licenses/by/3.0/",
    )


def _load_projection_compatible(path: Path) -> FrameNetProjectionV1:
    try:
        payload = path.read_bytes()
        if path.suffix == ".gz":
            payload = gzip.decompress(payload)
        return FrameNetProjectionV1.model_validate_json(payload, extra="ignore")
    except (OSError, gzip.BadGzipFile, ValueError) as exc:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_FRAMENET_PROJECTION") from exc


def _load_jsonl_rows(path: Path, model: type[BaseModel]) -> tuple[BaseModel, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise LinguisticBundleError(f"LINGUISTIC_BUNDLE_INVALID_ASSET filename={path.name}") from exc
    rows: list[BaseModel] = []
    for line_number, line in enumerate(lines, 1):
        try:
            rows.append(model.model_validate_json(line))
        except ValueError as exc:
            raise LinguisticBundleError(
                f"LINGUISTIC_BUNDLE_INVALID_ASSET filename={path.name} line={line_number}"
            ) from exc
    return tuple(rows)


def _load_target_mappings(path: Path, canonical_id: str) -> tuple[SemanticMappingRecord, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_SEMANTIC_MAPPINGS") from exc
    selected: list[SemanticMappingRecord] = []
    for line_number, line in enumerate(lines, 1):
        try:
            untyped = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LinguisticBundleError(
                f"LINGUISTIC_BUNDLE_INVALID_SEMANTIC_MAPPINGS line={line_number}"
            ) from exc
        if not isinstance(untyped, dict) or untyped.get("canonical_id") != canonical_id:
            continue
        try:
            selected.append(SemanticMappingRecord.model_validate(untyped, extra="ignore"))
        except ValueError as exc:
            raise LinguisticBundleError(
                f"LINGUISTIC_BUNDLE_INVALID_SEMANTIC_MAPPINGS line={line_number}"
            ) from exc
    return tuple(selected)


def _alignment_from_mapping(
    mapping: SemanticMappingRecord,
    *,
    source_family: Literal["propbank", "framenet", "sumo"],
    state: AlignmentState,
    source_identity_status: SourceIdentityStatus,
) -> LinguisticAlignmentRefV1:
    return LinguisticAlignmentRefV1(
        alignment_id=_alignment_id(
            canonical_id=mapping.canonical_id,
            source_family=source_family,
            source_id=mapping.source_id,
            relation=mapping.relation,
            state=state,
        ),
        canonical_id=mapping.canonical_id,
        source_family=source_family,
        source_id=mapping.source_id,
        relation=mapping.relation,
        state=state,
        method=mapping.derivation_method,
        evidence_refs=(mapping.evidence_ref,),
        source_identity_status=source_identity_status,
    )


def _load_pack_manifest(pack_dir: Path, query: LinguisticBundleQueryV1) -> tuple[dict[str, str], str]:
    path = pack_dir / "manifest.yaml"
    manifest_sha256 = _sha256_file(path)
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_PACK_MANIFEST") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("pack"), dict):
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_PACK_MANIFEST")
    pack = manifest["pack"]
    if pack.get("id") != query.pack_ref.pack_id or pack.get("version") != query.pack_ref.pack_version:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_PACK_IDENTITY_MISMATCH")
    trace = manifest.get("linguistic_trace")
    if (
        not isinstance(trace, dict)
        or trace.get("schema_version") != "linguistic-trace-manifest-v1"
        or trace.get("manifest") != "linguistic_trace_manifest_v1.json"
    ):
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_TRACE_MANIFEST_UNDECLARED")
    build = manifest.get("build")
    hashes = build.get("artifact_sha256") if isinstance(build, dict) else None
    if not isinstance(hashes, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in hashes.items()
    ):
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_MISSING_ARTIFACT_HASHES")
    return hashes, manifest_sha256


def _verified_asset(pack_dir: Path, filename: str, declared_hashes: dict[str, str]) -> tuple[Path, str]:
    path = pack_dir / filename
    if not path.is_file():
        raise LinguisticBundleError(f"LINGUISTIC_BUNDLE_ASSET_MISSING filename={filename}")
    expected = declared_hashes.get(filename)
    observed = _sha256_file(path)
    if expected != observed:
        raise LinguisticBundleError(
            f"LINGUISTIC_BUNDLE_ASSET_HASH_MISMATCH filename={filename}"
        )
    return path, observed


def inspect_linguistic_bundle_at_root(
    query: LinguisticBundleQueryV1,
    *,
    packs_root: Path,
) -> LinguisticBundleV1:
    """Inspect an exact pack under an explicit package-assets root."""

    pack_dir = packs_root / query.pack_ref.pack_id / query.pack_ref.pack_version
    declared_hashes, pack_manifest_sha = _load_pack_manifest(pack_dir, query)
    trace_path, trace_sha = _verified_asset(
        pack_dir, "linguistic_trace_manifest_v1.json", declared_hashes
    )
    try:
        trace_manifest = LinguisticTraceManifestV1.model_validate_json(
            trace_path.read_bytes(), extra="ignore"
        )
    except (OSError, ValueError) as exc:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_TRACE_MANIFEST") from exc
    if trace_manifest.pack_ref != query.pack_ref:
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_TRACE_PACK_IDENTITY_MISMATCH")

    predicate_path, predicate_sha = _verified_asset(
        pack_dir, "predicate_types.jsonl", declared_hashes
    )
    role_path, role_sha = _verified_asset(pack_dir, "role_types.jsonl", declared_hashes)
    edge_path, edge_sha = _verified_asset(
        pack_dir, "predicate_role_edges.jsonl", declared_hashes
    )
    mapping_path, mapping_sha = _verified_asset(
        pack_dir, "semantic_mappings.jsonl", declared_hashes
    )
    projection_path, projection_sha = _verified_asset(
        pack_dir, trace_manifest.framenet_projection.filename, declared_hashes
    )
    attribution_path, attribution_sha = _verified_asset(
        pack_dir, trace_manifest.attribution.filename, declared_hashes
    )
    if (
        projection_sha != trace_manifest.framenet_projection.sha256
        or attribution_sha != trace_manifest.attribution.sha256
    ):
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_TRACE_ASSET_DIGEST_MISMATCH")
    projection = _load_projection_compatible(projection_path)
    if (
        projection.projection_content_sha256
        != trace_manifest.framenet_projection_content_sha256
        or projection.source_key != trace_manifest.framenet_source_key
        or projection.source_archive_sha256 != trace_manifest.framenet_source_archive_sha256
        or projection.source_archive_byte_count
        != trace_manifest.framenet_source_archive_byte_count
        or projection.frame_count != trace_manifest.frame_count
        or projection.frame_element_count != trace_manifest.frame_element_count
        or projection.lexical_unit_declaration_count
        != trace_manifest.lexical_unit_declaration_count
        or projection.indexed_lexical_unit_count
        != trace_manifest.indexed_lexical_unit_count
        or projection.frame_relation_count != trace_manifest.frame_relation_count
        or projection.frame_element_relation_count
        != trace_manifest.frame_element_relation_count
    ):
        raise LinguisticBundleError("LINGUISTIC_BUNDLE_PROJECTION_MANIFEST_MISMATCH")

    predicate_rows = _load_jsonl_rows(predicate_path, _PredicateRowV1)
    predicates = [
        row
        for row in predicate_rows
        if isinstance(row, _PredicateRowV1)
        and row.predicate_id == query.canonical_predicate_id
    ]
    if len(predicates) != 1:
        raise LinguisticBundleError(
            f"LINGUISTIC_BUNDLE_UNKNOWN_CANONICAL_ID identifier={query.canonical_predicate_id}"
        )
    predicate_row = predicates[0]
    predicate = CanonicalPredicateEntryV1.model_validate(predicate_row.model_dump())

    role_rows = _load_jsonl_rows(role_path, _RoleRowV1)
    roles_by_id = {
        row.role_id: row for row in role_rows if isinstance(row, _RoleRowV1)
    }
    edge_rows = _load_jsonl_rows(edge_path, _PredicateRoleEdgeRowV1)
    roles: list[CanonicalRoleEntryV1] = []
    for row in edge_rows:
        if not isinstance(row, _PredicateRoleEdgeRowV1) or row.predicate_id != predicate.predicate_id:
            continue
        role = roles_by_id.get(row.role_id)
        if role is None:
            raise LinguisticBundleError(f"LINGUISTIC_BUNDLE_DANGLING_ROLE role_id={row.role_id}")
        roles.append(
            CanonicalRoleEntryV1(
                **role.model_dump(),
                required=row.required,
                min_count=row.min_count,
                max_count=row.max_count,
            )
        )

    mappings = _load_target_mappings(mapping_path, predicate.predicate_id)
    propbank_refs = tuple(
        _alignment_from_mapping(
            mapping,
            source_family="propbank",
            state="candidate",
            source_identity_status="donor_only",
        )
        for mapping in mappings
        if mapping.source_key == "propbank_nltk"
    )
    frame_by_name = {frame.name: frame for frame in projection.frames}
    framenet_records: list[FrameNetAlignedRecordV1] = []
    for mapping in mappings:
        if mapping.source_key != "framenet_candidate":
            continue
        if mapping.relation != "candidate_alignment" or mapping.source_verified is not False:
            raise LinguisticBundleError("LINGUISTIC_BUNDLE_INVALID_FRAMENET_ALIGNMENT_STATE")
        frame = frame_by_name.get(mapping.source_id)
        if frame is None:
            raise LinguisticBundleError(
                f"LINGUISTIC_BUNDLE_DANGLING_FRAMENET_FRAME source_id={mapping.source_id}"
            )
        framenet_records.append(
            FrameNetAlignedRecordV1(
                alignment=_alignment_from_mapping(
                    mapping,
                    source_family="framenet",
                    state="candidate",
                    source_identity_status="exact_source_record",
                ),
                frame=frame,
            )
        )
    sumo_refs = tuple(
        _alignment_from_mapping(
            mapping,
            source_family="sumo",
            state="unresolved",
            source_identity_status="pending_projection",
        )
        for mapping in mappings
        if mapping.source_key == "onto_canon_sumo_plus"
    )
    return LinguisticBundleV1(
        query=query,
        predicate=predicate,
        roles=tuple(roles),
        propbank_refs=propbank_refs,
        framenet_records=tuple(framenet_records),
        sumo_context=SumoBundleContextV1(donor_refs=sumo_refs),
        trace_manifest=trace_manifest,
        asset_digests=LinguisticBundleAssetDigestsV1(
            pack_manifest_sha256=pack_manifest_sha,
            trace_manifest_sha256=trace_sha,
            predicate_types_sha256=predicate_sha,
            role_types_sha256=role_sha,
            predicate_role_edges_sha256=edge_sha,
            semantic_mappings_sha256=mapping_sha,
            framenet_projection_sha256=projection_sha,
            attribution_sha256=attribution_sha,
        ),
    )


def inspect_linguistic_bundle(query: LinguisticBundleQueryV1) -> LinguisticBundleV1:
    """Inspect one exact wheel-installed linguistic bundle."""

    return inspect_linguistic_bundle_at_root(
        query,
        packs_root=installed_ontology_packs_root(),
    )
