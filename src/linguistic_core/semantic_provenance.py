"""Compile inspectable Predicate Canon provenance from the donor database.

Plan 0140 keeps semantic traceability separate from runtime aliases. This
module implements the first walking skeleton for one predicate without writing
pack files or changing the progressive extraction backend.
"""

from __future__ import annotations

import hashlib
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator

ResourceVersionStatus = Literal["verified", "donor_asserted", "unknown"]
LicenseStatus = Literal["verified", "reference_only", "unknown"]
HistoricalEvidenceKind = Literal[
    "artifact_checksum",
    "donor_manifest",
    "current_reference_only",
    "none",
]
CanonicalKind = Literal["predicate_type", "role_slot", "entity_type", "hierarchy_edge"]
MappingRelation = Literal[
    "derived_from",
    "candidate_alignment",
    "typed_by",
    "positional_role",
    "subtype_of",
]
DerivationMethod = Literal[
    "direct_identifier",
    "donor_asserted",
    "deterministic",
    "llm",
    "unknown",
]
LineageStatus = Literal["donor_asserted", "unknown", "mixed"]

_PACK_CANDIDATE: Literal["linguistic_core@0.3.0-candidate"] = (
    "linguistic_core@0.3.0-candidate"
)
_SCHEMA_VERSION: Literal["predicate_canon_provenance.v1"] = "predicate_canon_provenance.v1"
_PROPBANK_REFERENCE = HttpUrl("https://github.com/propbank/propbank-frames")
_FRAMENET_REFERENCE = HttpUrl("https://berkeleyfn.framenetbr.ufjf.br/framenet_data")
_SUMO_REFERENCE = HttpUrl("https://www.ontologyportal.org/")
_CANONICAL_DONOR_SHA256 = "9a6da4825eb9e4f4d81d1263e5c2ee6847bb85a1b899727e6be929658e1da0f6"


class CanonProvenanceError(RuntimeError):
    """Raised when donor provenance cannot be compiled truthfully."""


class SemanticSourceDescriptor(BaseModel):
    """One semantic source or donor-artifact lineage descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1, description="Stable key referenced by semantic mappings.")
    resource_name: str = Field(min_length=1, description="Human-readable source or donor name.")
    resource_version: str | None = Field(
        description="Exact version when evidenced; null when historical version is unknown."
    )
    resource_version_status: ResourceVersionStatus = Field(
        description="Whether the version is verified, donor-asserted, or unknown."
    )
    license_id: str | None = Field(
        description="License identifier only when it applies to the evidenced historical source."
    )
    license_status: LicenseStatus = Field(
        description="Strength of the license claim for this historical lineage."
    )
    artifact_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Byte-exact source artifact checksum when a local artifact exists.",
    )
    official_reference: HttpUrl | None = Field(
        default=None,
        description="Official current resource page; not automatically historical evidence.",
    )
    official_reference_scope: Literal["current_reference_only", "historical_source"] | None = Field(
        default=None,
        description="Whether the official reference proves current availability or historical input.",
    )
    historical_evidence_kind: HistoricalEvidenceKind = Field(
        description="Evidence class supporting the historical version assertion."
    )
    evidence_ref: str = Field(min_length=1, description="Inspectable local evidence for this descriptor.")

    @model_validator(mode="after")
    def _version_and_license_claims_are_evidenced(self) -> "SemanticSourceDescriptor":
        """Reject current-reference laundering and internally inconsistent certainty."""

        historical_evidence = {"artifact_checksum", "donor_manifest"}
        if self.resource_version_status == "verified":
            raise ValueError(
                "predicate_canon_provenance.v1 has no trusted registry for verified versions"
            )
        if self.license_status == "verified":
            raise ValueError(
                "predicate_canon_provenance.v1 has no trusted registry for verified licenses"
            )
        if self.resource_version_status == "unknown" and self.resource_version is not None:
            raise ValueError("unknown resource version status requires resource_version=null")
        if self.resource_version_status in {"verified", "donor_asserted"} and self.resource_version is None:
            raise ValueError("known resource version status requires resource_version")
        if (
            self.resource_version_status in {"verified", "donor_asserted"}
            and self.historical_evidence_kind not in historical_evidence
        ):
            raise ValueError(
                "known historical version requires artifact or donor-manifest evidence"
            )
        if self.license_status == "unknown" and self.license_id is not None:
            raise ValueError("unknown license status requires license_id=null")
        if self.license_status == "reference_only" and (
            self.license_id is None
            or self.official_reference_scope != "current_reference_only"
            or self.historical_evidence_kind != "current_reference_only"
        ):
            raise ValueError(
                "reference-only license requires a current-reference-only source and license_id"
            )
        if self.official_reference is None and self.official_reference_scope is not None:
            raise ValueError("official_reference_scope requires official_reference")
        if self.official_reference_scope == "historical_source" and (
            self.historical_evidence_kind not in historical_evidence
        ):
            raise ValueError(
                "historical-source reference requires artifact or donor-manifest evidence"
            )
        if self.historical_evidence_kind == "current_reference_only" and (
            self.official_reference is None
            or self.official_reference_scope != "current_reference_only"
        ):
            raise ValueError(
                "current-reference-only evidence requires a current-reference-only official reference"
            )
        if self.historical_evidence_kind == "artifact_checksum" and self.artifact_sha256 is None:
            raise ValueError("artifact-checksum evidence requires artifact_sha256")
        if self.artifact_sha256 is not None and self.historical_evidence_kind not in historical_evidence:
            raise ValueError("artifact_sha256 requires artifact or donor-manifest evidence")
        _validate_known_source_identity(self)
        return self


class SemanticMappingRecord(BaseModel):
    """One traceability-only mapping from a canonical term to donor semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_id: str = Field(min_length=1, description="Canonical pack term or predicate-role slot ID.")
    canonical_kind: CanonicalKind = Field(description="Kind of canonical object being traced.")
    source_key: str = Field(min_length=1, description="Key of the source descriptor used by this row.")
    source_id: str = Field(min_length=1, description="Identifier as recorded by the donor source field.")
    relation: MappingRelation = Field(description="Declared semantic relationship to the source identifier.")
    derivation_method: DerivationMethod = Field(description="How this mapping relationship was obtained.")
    confidence_basis: str = Field(
        min_length=1,
        description="Evidence basis without laundering it into calibrated probability.",
    )
    row_mapping_method_ref: str | None = Field(
        default=None,
        description="Donor row mapping-method tag when relevant to this candidate mapping.",
    )
    row_mapping_method_scope: Literal["relation", "predicate_row", "unknown"] | None = Field(
        default=None,
        description="Proven semantic scope of the row method, or unknown when undocumented.",
    )
    row_mapping_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Uncalibrated donor row confidence when present on a candidate alignment.",
    )
    evidence_ref: str = Field(min_length=1, description="Exact donor field or artifact supporting the row.")
    source_verified: Literal[False] = Field(
        default=False,
        description="V1 has no trusted upstream verification registry; mappings remain unverified.",
    )
    runtime_alias: Literal[False] = Field(
        default=False,
        description="Traceability records are never runtime lookup aliases.",
    )

    @model_validator(mode="after")
    def _kind_matches_relation(self) -> "SemanticMappingRecord":
        """Keep predicate, role-slot, and type relations semantically distinct."""

        allowed_relations: dict[CanonicalKind, set[MappingRelation]] = {
            "predicate_type": {"derived_from", "candidate_alignment"},
            "role_slot": {"positional_role"},
            "entity_type": {"typed_by"},
            "hierarchy_edge": {"subtype_of"},
        }
        if self.relation not in allowed_relations[self.canonical_kind]:
            raise ValueError(
                f"{self.canonical_kind} cannot use semantic relation {self.relation}"
            )
        if (self.row_mapping_method_ref is None) != (self.row_mapping_method_scope is None):
            raise ValueError("row mapping method reference and scope must be supplied together")
        if self.row_mapping_method_ref is not None and self.relation != "candidate_alignment":
            raise ValueError("row mapping method metadata is valid only for candidate alignments")
        if self.row_mapping_confidence is not None and self.relation != "candidate_alignment":
            raise ValueError("row mapping confidence is valid only for candidate alignments")
        source_contracts: dict[str, dict[CanonicalKind, set[MappingRelation]]] = {
            "onto_canon_sumo_plus": {
                "predicate_type": {"derived_from"},
                "role_slot": {"positional_role"},
            },
            "propbank_nltk": {
                "predicate_type": {"derived_from"},
                "role_slot": {"positional_role"},
            },
            "framenet_candidate": {"predicate_type": {"candidate_alignment"}},
            "sumo_donor_types": {
                "entity_type": {"typed_by"},
                "hierarchy_edge": {"subtype_of"},
            },
        }
        source_contract = source_contracts.get(self.source_key)
        if source_contract is None:
            raise ValueError(f"unsupported semantic source key: {self.source_key}")
        expected_relations = source_contract.get(self.canonical_kind, set())
        if self.relation not in expected_relations:
            raise ValueError(
                f"source {self.source_key} cannot map {self.canonical_kind} via {self.relation}"
            )
        return self


class DonorPredicateMetadata(BaseModel):
    """Row-level donor metadata whose semantic scope may remain unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    donor_predicate_id: str = Field(min_length=1, description="Predicate primary key in the donor database.")
    donor_source: str = Field(min_length=1, description="Source label stored on the donor predicate row.")
    row_mapping_method_ref: str | None = Field(
        description="Donor row mapping-method tag, without attributing it to one semantic field."
    )
    row_mapping_method_scope: Literal["unknown"] | None = Field(
        description="Unknown until donor construction evidence identifies the governed relationship."
    )
    row_mapping_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Uncalibrated donor row confidence preserved as data, not probability.",
    )

    @model_validator(mode="after")
    def _method_fields_are_paired(self) -> "DonorPredicateMetadata":
        """Keep row method reference and its explicit unknown scope together."""

        if (self.row_mapping_method_ref is None) != (self.row_mapping_method_scope is None):
            raise ValueError("row mapping method reference and scope must be supplied together")
        return self


class PredicateProvenanceBundle(BaseModel):
    """Strict inspectable provenance bundle for one canonical predicate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["predicate_canon_provenance.v1"] = Field(
        description="Version of this traceability contract."
    )
    pack_candidate: Literal["linguistic_core@0.3.0-candidate"] = Field(
        description="Unpublished side-by-side pack target for Plan 0140."
    )
    kind: Literal["predicate_type"] = Field(
        description="Canonical object kind exposed explicitly on JSON and text surfaces."
    )
    lineage_status: LineageStatus = Field(
        description="Derived aggregate of source version-status claims."
    )
    predicate_id: str = Field(min_length=1, description="Canonical lc:-namespaced predicate ID.")
    role_ids: tuple[str, ...] = Field(description="Canonical role IDs declared by this predicate.")
    type_ids: tuple[str, ...] = Field(description="Canonical SUMO-derived filler type IDs.")
    donor_predicate: DonorPredicateMetadata = Field(description="Unmodified row-level donor metadata.")
    direct_build_input: SemanticSourceDescriptor = Field(
        description="Byte-bound donor artifact used directly to compile this lineage."
    )
    sources: tuple[SemanticSourceDescriptor, ...] = Field(
        min_length=1,
        description="All donor and semantic sources referenced by mappings.",
    )
    mappings: tuple[SemanticMappingRecord, ...] = Field(
        min_length=1,
        description="Traceability-only semantic mappings for this predicate slice.",
    )
    warnings: tuple[str, ...] = Field(
        description="Explicit claim-boundary warnings derived from present evidence."
    )

    @model_validator(mode="after")
    def _mappings_reference_owned_terms_and_sources(self) -> "PredicateProvenanceBundle":
        """Reject dangling canonical/source IDs and duplicate owned-term declarations."""

        if len(set(self.role_ids)) != len(self.role_ids):
            raise ValueError("role_ids must be unique")
        if len(set(self.type_ids)) != len(self.type_ids):
            raise ValueError("type_ids must be unique")
        source_keys = [source.source_key for source in self.sources]
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("source keys must be unique")
        if self.direct_build_input.source_key != "onto_canon_sumo_plus":
            raise ValueError("direct build input must be onto_canon_sumo_plus")
        matching_direct_sources = [
            source for source in self.sources if source.source_key == self.direct_build_input.source_key
        ]
        if matching_direct_sources != [self.direct_build_input]:
            raise ValueError("direct build input must exactly match its source descriptor")
        expected_lineage_status = _aggregate_lineage_status(self.sources)
        if self.lineage_status != expected_lineage_status:
            raise ValueError(
                f"lineage_status must be derived from sources: {expected_lineage_status}"
            )
        role_mapping_ids = {f"{self.predicate_id}:{role_id}" for role_id in self.role_ids}
        allowed_ids = {self.predicate_id, *self.type_ids, *role_mapping_ids}
        mapping_keys: set[tuple[str, str, str, str]] = set()
        mapped_canonical_ids: set[str] = set()
        for mapping in self.mappings:
            if mapping.canonical_id not in allowed_ids:
                raise ValueError(f"mapping references canonical ID outside bundle: {mapping.canonical_id}")
            if mapping.source_key not in source_keys:
                raise ValueError(f"mapping references unknown source key: {mapping.source_key}")
            if mapping.canonical_kind == "predicate_type" and mapping.canonical_id != self.predicate_id:
                raise ValueError("predicate mapping must reference bundle predicate_id")
            if mapping.canonical_kind == "entity_type" and mapping.canonical_id not in self.type_ids:
                raise ValueError("entity-type mapping must reference bundle type_ids")
            if mapping.canonical_kind == "role_slot" and mapping.canonical_id not in role_mapping_ids:
                raise ValueError("role-slot mapping must reference bundle role_ids")
            key = (
                mapping.canonical_id,
                mapping.source_key,
                mapping.source_id,
                mapping.relation,
            )
            if key in mapping_keys:
                raise ValueError(f"duplicate semantic mapping: {key}")
            mapping_keys.add(key)
            mapped_canonical_ids.add(mapping.canonical_id)
            if mapping.relation == "candidate_alignment":
                if mapping.row_mapping_method_ref != self.donor_predicate.row_mapping_method_ref:
                    raise ValueError(
                        "candidate mapping method must match donor predicate metadata"
                    )
                if mapping.row_mapping_method_scope != self.donor_predicate.row_mapping_method_scope:
                    raise ValueError(
                        "candidate mapping method scope must match donor predicate metadata"
                    )
                if mapping.row_mapping_confidence != self.donor_predicate.row_mapping_confidence:
                    raise ValueError(
                        "candidate mapping confidence must match donor predicate metadata"
                    )
        if allowed_ids - mapped_canonical_ids:
            raise ValueError(
                f"bundle terms missing semantic mappings: {sorted(allowed_ids - mapped_canonical_ids)}"
            )
        expected_warnings = _provenance_warnings(
            mappings=self.mappings,
            sources=self.sources,
            donor_predicate=self.donor_predicate,
        )
        if self.warnings != expected_warnings:
            raise ValueError("warnings must be derived exactly from bundle evidence")
        return self


class SemanticSourcesDocument(BaseModel):
    """Versioned source registry emitted beside one linguistic-core pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["predicate_canon_semantic_sources.v1"] = Field(
        description="Version of the pack-level semantic source registry."
    )
    pack_id: Literal["linguistic_core"] = Field(description="Owning ontology pack ID.")
    pack_version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
        description="Exact side-by-side pack version described by this registry.",
    )
    direct_build_input: SemanticSourceDescriptor = Field(
        description="Byte-bound donor artifact used directly by the compiler."
    )
    semantic_sources: tuple[SemanticSourceDescriptor, ...] = Field(
        min_length=3,
        description="Closed external semantic source descriptors referenced by mappings.",
    )

    @model_validator(mode="after")
    def _source_registry_is_complete(self) -> "SemanticSourcesDocument":
        """Require the exact reviewed V1 registry without duplicate source keys."""

        if self.direct_build_input.source_key != "onto_canon_sumo_plus":
            raise ValueError("direct build input must be onto_canon_sumo_plus")
        keys = [source.source_key for source in self.semantic_sources]
        if keys != ["framenet_candidate", "propbank_nltk", "sumo_donor_types"]:
            raise ValueError("semantic_sources must be sorted and complete for V1")
        return self


def compile_semantic_sources_document(
    db_path: Path,
    *,
    pack_version: str,
) -> SemanticSourcesDocument:
    """Compile the byte-bound, closed V1 source registry for one pack build."""

    return SemanticSourcesDocument(
        schema_version="predicate_canon_semantic_sources.v1",
        pack_id="linguistic_core",
        pack_version=pack_version,
        direct_build_input=_donor_source(_db_sha256(db_path)),
        semantic_sources=tuple(
            sorted(
                (_propbank_source(), _framenet_source(), _sumo_source()),
                key=lambda source: source.source_key,
            )
        ),
    )


def compile_predicate_provenance(db_path: Path, *, predicate_id: str) -> PredicateProvenanceBundle:
    """Compile one read-only provenance bundle from ``sumo_plus.db``.

    The function never writes the donor database or a runtime pack. Unknown
    historical versions and row-mapping scope remain explicit.
    """

    db_sha256 = _db_sha256(db_path)
    encoded_db_path = quote(db_path.resolve().as_posix(), safe="/")
    try:
        conn = sqlite3.connect(f"file:{encoded_db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise CanonProvenanceError(f"CANON_PROVENANCE_DB_ERROR detail={exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        predicate = conn.execute(
            "SELECT name, propbank_sense_id, frame_id, source, mapping_confidence, "
            "mapping_source FROM predicates WHERE name = ?",
            (predicate_id,),
        ).fetchone()
        if predicate is None:
            raise CanonProvenanceError(
                f"CANON_PROVENANCE_UNKNOWN_PREDICATE predicate_id={predicate_id}"
            )
        roles = conn.execute(
            "SELECT named_label, arg_position, type_constraint, source "
            "FROM role_slots WHERE event_sense_id = ? ORDER BY arg_position",
            (predicate_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise CanonProvenanceError(f"CANON_PROVENANCE_DB_ERROR detail={exc}") from exc
    finally:
        conn.close()

    donor_predicate_name = _required_db_token(predicate["name"], field="predicates.name")
    donor_source = _required_db_token(predicate["source"], field="predicates.source")
    normalized_roles = [
        (
            _required_db_token(role["named_label"], field="role_slots.named_label"),
            _required_db_token(role["arg_position"], field="role_slots.arg_position"),
            _required_db_token(role["source"], field="role_slots.source"),
            (
                _required_db_token(role["type_constraint"], field="role_slots.type_constraint")
                if role["type_constraint"] is not None
                else None
            ),
        )
        for role in roles
    ]
    canonical_predicate_id = f"lc:{donor_predicate_name}"
    role_ids = tuple(
        dict.fromkeys(_role_id(named_label) for named_label, _, _, _ in normalized_roles)
    )
    type_ids = tuple(
        dict.fromkeys(
            _sumo_type_id(type_constraint)
            for _, _, _, type_constraint in normalized_roles
            if type_constraint is not None
        )
    )

    direct_build_input = _donor_source(db_sha256)
    sources = [direct_build_input]
    mappings: list[SemanticMappingRecord] = [
        SemanticMappingRecord(
            canonical_id=canonical_predicate_id,
            canonical_kind="predicate_type",
            source_key="onto_canon_sumo_plus",
            source_id=donor_predicate_name,
            relation="derived_from",
            derivation_method="direct_identifier",
            confidence_basis="canonical predicate is compiled directly from the donor predicate row",
            evidence_ref=f"sqlite:predicates[name={predicate_id}].name",
        )
    ]
    mapping_method_ref = _optional_db_token(
        predicate["mapping_source"],
        field="predicates.mapping_source",
    )
    propbank_sense_id = _optional_db_token(
        predicate["propbank_sense_id"],
        field="predicates.propbank_sense_id",
    )
    if propbank_sense_id is not None:
        sources.append(_propbank_source())
        mappings.append(
            SemanticMappingRecord(
                canonical_id=canonical_predicate_id,
                canonical_kind="predicate_type",
                source_key="propbank_nltk",
                source_id=propbank_sense_id,
                relation="derived_from",
                derivation_method="direct_identifier",
                confidence_basis="donor predicate row stores the exact PropBank sense identifier",
                evidence_ref=f"sqlite:predicates[name={predicate_id}].propbank_sense_id",
            )
        )
    frame_id = _optional_db_token(predicate["frame_id"], field="predicates.frame_id")
    if frame_id is not None:
        sources.append(_framenet_source())
        mappings.append(
            SemanticMappingRecord(
                canonical_id=canonical_predicate_id,
                canonical_kind="predicate_type",
                source_key="framenet_candidate",
                source_id=frame_id,
                relation="candidate_alignment",
                derivation_method="donor_asserted",
                confidence_basis=(
                    "donor predicate row contains frame_id plus row mapping metadata; "
                    "upstream verification and the mapping-method semantic scope are absent"
                ),
                row_mapping_method_ref=mapping_method_ref,
                row_mapping_method_scope="unknown" if mapping_method_ref is not None else None,
                row_mapping_confidence=_optional_db_confidence(
                    predicate["mapping_confidence"],
                    field="predicates.mapping_confidence",
                ),
                evidence_ref=(
                    f"sqlite:predicates[name={predicate_id}]"
                    "{frame_id,mapping_confidence,mapping_source}"
                ),
            )
        )
    if any(type_constraint is not None for _, _, _, type_constraint in normalized_roles):
        sources.append(_sumo_source())

    for named_label, arg_position, role_source, type_constraint in normalized_roles:
        role_id = _role_id(named_label)
        mappings.append(
            SemanticMappingRecord(
                canonical_id=f"{canonical_predicate_id}:{role_id}",
                canonical_kind="role_slot",
                source_key="onto_canon_sumo_plus",
                source_id=f"{donor_predicate_name}:{arg_position}",
                relation="positional_role",
                derivation_method="direct_identifier",
                confidence_basis="canonical role slot is compiled directly from the donor role row",
                evidence_ref=(
                    f"sqlite:role_slots[event_sense_id={predicate_id},"
                    f"arg_position={arg_position}]"
                ),
            )
        )
        if propbank_sense_id is not None:
            mappings.append(
                SemanticMappingRecord(
                    canonical_id=f"{canonical_predicate_id}:{role_id}",
                    canonical_kind="role_slot",
                    source_key="propbank_nltk",
                    source_id=f"{propbank_sense_id}:{arg_position}",
                    relation="positional_role",
                    derivation_method="donor_asserted",
                    confidence_basis=(
                        f"donor role row source={role_source}; named label remains donor-derived"
                    ),
                    evidence_ref=(
                        f"sqlite:role_slots[event_sense_id={predicate_id},"
                        f"arg_position={arg_position}]"
                    ),
                )
            )
        if type_constraint is not None:
            type_name = type_constraint
            type_id = _sumo_type_id(type_name)
            if not any(
                mapping.canonical_kind == "entity_type" and mapping.canonical_id == type_id
                for mapping in mappings
            ):
                mappings.append(
                    SemanticMappingRecord(
                        canonical_id=type_id,
                        canonical_kind="entity_type",
                        source_key="sumo_donor_types",
                        source_id=type_name,
                        relation="typed_by",
                        derivation_method="donor_asserted",
                        confidence_basis="donor role type_constraint and locally owned SUMO hierarchy",
                        evidence_ref=(
                            f"sqlite:role_slots[event_sense_id={predicate_id},"
                            f"arg_position={arg_position}].type_constraint"
                        ),
                    )
                )

    donor_predicate = DonorPredicateMetadata(
        donor_predicate_id=donor_predicate_name,
        donor_source=donor_source,
        row_mapping_method_ref=mapping_method_ref,
        row_mapping_method_scope="unknown" if mapping_method_ref is not None else None,
        row_mapping_confidence=_optional_db_confidence(
            predicate["mapping_confidence"],
            field="predicates.mapping_confidence",
        ),
    )
    source_tuple = tuple(sources)
    mapping_tuple = tuple(mappings)
    lineage_status = _aggregate_lineage_status(source_tuple)
    try:
        return PredicateProvenanceBundle(
            schema_version=_SCHEMA_VERSION,
            pack_candidate=_PACK_CANDIDATE,
            kind="predicate_type",
            lineage_status=lineage_status,
            predicate_id=canonical_predicate_id,
            role_ids=role_ids,
            type_ids=type_ids,
            donor_predicate=donor_predicate,
            direct_build_input=direct_build_input,
            sources=source_tuple,
            mappings=mapping_tuple,
            warnings=_provenance_warnings(
                mappings=mapping_tuple,
                sources=source_tuple,
                donor_predicate=donor_predicate,
            ),
        )
    except ValidationError as exc:
        raise CanonProvenanceError(
            f"CANON_PROVENANCE_CONTRACT_ERROR predicate_id={predicate_id} detail={exc}"
        ) from exc


def render_provenance_text(bundle: PredicateProvenanceBundle) -> str:
    """Render the approved human-readable provenance contract without hiding unknowns."""

    donor = bundle.direct_build_input
    lines = [
        f"canonical_id: {bundle.predicate_id}",
        f"kind: {bundle.kind}",
        f"pack: {bundle.pack_candidate}",
        f"lineage_status: {bundle.lineage_status}",
        "",
        "direct_build_input:",
        f"  source: {donor.source_key}",
        f"  sha256: {donor.artifact_sha256 or 'unknown'}",
        f"  upstream_version_status: {donor.resource_version_status}",
        f"  upstream_version: {donor.resource_version or 'unknown'}",
        f"  license_status: {donor.license_status}",
        f"  license: {donor.license_id or 'unknown'}",
        "",
        "semantic_mappings:",
    ]
    source_by_key = {source.source_key: source for source in bundle.sources}
    for mapping in bundle.mappings:
        source = source_by_key[mapping.source_key]
        lines.append(
            f"  - {mapping.source_key}:{mapping.source_id} "
            f"({mapping.relation}; method={mapping.derivation_method}; runtime_alias=no)"
        )
        lines.append(f"    source_release: {source.resource_version or 'unknown'}")
        lines.append(f"    source_verified: {'yes' if source.resource_version_status == 'verified' else 'no'}")
        if mapping.row_mapping_method_ref is not None:
            lines.append(f"    row_mapping_method: {mapping.row_mapping_method_ref}")
            lines.append(
                f"    row_mapping_method_scope: {mapping.row_mapping_method_scope or 'unknown'}"
            )
    if bundle.warnings:
        lines.extend(["", "warnings:", *(f"  - {warning}" for warning in bundle.warnings)])
    return "\n".join(lines)


def _provenance_warnings(
    *,
    mappings: tuple[SemanticMappingRecord, ...],
    sources: tuple[SemanticSourceDescriptor, ...],
    donor_predicate: DonorPredicateMetadata,
) -> tuple[str, ...]:
    """Derive stable claim-boundary warnings from present typed evidence."""

    warnings: list[str] = []
    if any(mapping.source_key == "framenet_candidate" for mapping in mappings):
        warnings.append(
            "FrameNet mappings are donor-asserted candidate alignments, not independently verified."
        )
    if donor_predicate.row_mapping_method_scope == "unknown":
        warnings.append(
            "Row mapping tags with unknown scope cannot be attributed to a specific relationship."
        )
    if any(source.official_reference_scope == "current_reference_only" for source in sources):
        warnings.append(
            "Current official-resource metadata is reference-only, not historical evidence."
        )
    return tuple(warnings)


def _aggregate_lineage_status(
    sources: tuple[SemanticSourceDescriptor, ...],
) -> LineageStatus:
    """Return the only V1 aggregate statuses allowed by the source registry."""

    statuses = {source.resource_version_status for source in sources}
    if statuses == {"donor_asserted"}:
        return "donor_asserted"
    if statuses == {"unknown"}:
        return "unknown"
    return "mixed"


def _donor_source(db_sha256: str) -> SemanticSourceDescriptor:
    """Return the byte-bound descriptor for the locally owned donor artifact."""

    return SemanticSourceDescriptor(
        source_key="onto_canon_sumo_plus",
        resource_name="onto-canon predecessor Predicate Canon database",
        resource_version="2026-02-15" if db_sha256 == _CANONICAL_DONOR_SHA256 else None,
        resource_version_status=(
            "donor_asserted" if db_sha256 == _CANONICAL_DONOR_SHA256 else "unknown"
        ),
        license_id=None,
        license_status="unknown",
        artifact_sha256=db_sha256,
        official_reference=None,
        official_reference_scope=None,
        historical_evidence_kind="artifact_checksum",
        evidence_ref="data/PROVENANCE.md+data/sumo_plus.db",
    )


def _propbank_source() -> SemanticSourceDescriptor:
    """Return honest PropBank lineage with unknown historical release."""

    return _unknown_historical_source(
        source_key="propbank_nltk",
        resource_name="PropBank",
        official_reference=_PROPBANK_REFERENCE,
        evidence_ref="sqlite:predicates.source+propbank_sense_id",
    )


def _framenet_source() -> SemanticSourceDescriptor:
    """Return honest FrameNet candidate lineage with unknown historical release."""

    return _unknown_historical_source(
        source_key="framenet_candidate",
        resource_name="Berkeley FrameNet candidate alignment",
        official_reference=_FRAMENET_REFERENCE,
        evidence_ref="sqlite:predicates.frame_id",
    )


def _sumo_source() -> SemanticSourceDescriptor:
    """Return honest SUMO donor-type lineage with unknown historical release."""

    return _unknown_historical_source(
        source_key="sumo_donor_types",
        resource_name="SUMO lineage in donor type constraints",
        official_reference=_SUMO_REFERENCE,
        evidence_ref="sqlite:role_slots.type_constraint+type_hierarchy",
    )


def _unknown_historical_source(
    *,
    source_key: str,
    resource_name: str,
    official_reference: HttpUrl,
    evidence_ref: str,
) -> SemanticSourceDescriptor:
    """Build a descriptor that keeps current references separate from donor history."""

    return SemanticSourceDescriptor(
        source_key=source_key,
        resource_name=resource_name,
        resource_version=None,
        resource_version_status="unknown",
        license_id=None,
        license_status="unknown",
        artifact_sha256=None,
        official_reference=official_reference,
        official_reference_scope="current_reference_only",
        historical_evidence_kind="current_reference_only",
        evidence_ref=evidence_ref,
    )


def _validate_known_source_identity(source: SemanticSourceDescriptor) -> None:
    """Bind each closed V1 source key to its reviewed descriptor identity."""

    external_contracts: dict[str, tuple[str, HttpUrl, str]] = {
        "propbank_nltk": (
            "PropBank",
            _PROPBANK_REFERENCE,
            "sqlite:predicates.source+propbank_sense_id",
        ),
        "framenet_candidate": (
            "Berkeley FrameNet candidate alignment",
            _FRAMENET_REFERENCE,
            "sqlite:predicates.frame_id",
        ),
        "sumo_donor_types": (
            "SUMO lineage in donor type constraints",
            _SUMO_REFERENCE,
            "sqlite:role_slots.type_constraint+type_hierarchy",
        ),
    }
    if source.source_key == "onto_canon_sumo_plus":
        if (
            source.resource_name != "onto-canon predecessor Predicate Canon database"
            or source.license_status != "unknown"
            or source.official_reference is not None
            or source.historical_evidence_kind != "artifact_checksum"
            or source.evidence_ref != "data/PROVENANCE.md+data/sumo_plus.db"
        ):
            raise ValueError("onto_canon_sumo_plus descriptor identity mismatch")
        if source.resource_version_status == "donor_asserted" and (
            source.resource_version != "2026-02-15"
            or source.artifact_sha256 != _CANONICAL_DONOR_SHA256
        ):
            raise ValueError("canonical donor assertion requires its exact version and checksum")
        return
    contract = external_contracts.get(source.source_key)
    if contract is None:
        raise ValueError(f"unsupported semantic source key: {source.source_key}")
    resource_name, official_reference, evidence_ref = contract
    if (
        source.resource_name != resource_name
        or source.resource_version is not None
        or source.resource_version_status != "unknown"
        or source.license_id is not None
        or source.license_status != "unknown"
        or source.artifact_sha256 is not None
        or source.official_reference != official_reference
        or source.official_reference_scope != "current_reference_only"
        or source.historical_evidence_kind != "current_reference_only"
        or source.evidence_ref != evidence_ref
    ):
        raise ValueError(f"{source.source_key} descriptor identity mismatch")


def _role_id(named_label: str) -> str:
    """Return the existing linguistic-core role ID for a donor named label."""

    return f"lc.role.{named_label.lower()}"


def _sumo_type_id(type_name: str) -> str:
    """Return the existing linguistic-core type ID for a donor SUMO type."""

    return f"lc:sumo_type.{type_name}"


def _required_db_token(value: object, *, field: str) -> str:
    """Return one non-empty donor token or fail with field-level context."""

    if not isinstance(value, str) or not value.strip():
        raise CanonProvenanceError(f"CANON_PROVENANCE_INVALID_DONOR_FIELD field={field}")
    return value.strip()


def _db_sha256(db_path: Path) -> str:
    """Return a cached hash keyed by resolved path and exact filesystem state."""

    if not db_path.exists():
        raise CanonProvenanceError(f"CANON_PROVENANCE_DB_MISSING path={db_path}")
    if not db_path.is_file():
        raise CanonProvenanceError(f"CANON_PROVENANCE_DB_NOT_FILE path={db_path}")
    try:
        stat = db_path.stat()
        return _cached_file_sha256(
            str(db_path.resolve()),
            stat.st_size,
            stat.st_mtime_ns,
        )
    except OSError as exc:
        raise CanonProvenanceError(
            f"CANON_PROVENANCE_DB_READ_ERROR path={db_path} detail={exc}"
        ) from exc


@lru_cache(maxsize=8)
def _cached_file_sha256(resolved_path: str, size: int, mtime_ns: int) -> str:
    """Hash one immutable build input; size/mtime make cache invalidation explicit."""

    del size, mtime_ns
    try:
        return hashlib.sha256(Path(resolved_path).read_bytes()).hexdigest()
    except OSError as exc:
        raise CanonProvenanceError(
            f"CANON_PROVENANCE_DB_READ_ERROR path={resolved_path} detail={exc}"
        ) from exc


def _optional_db_token(value: object, *, field: str) -> str | None:
    """Return one optional donor token while rejecting malformed present values."""

    if value is None:
        return None
    return _required_db_token(value, field=field)


def _optional_db_confidence(value: object, *, field: str) -> float | None:
    """Return a finite donor confidence in [0, 1] or fail with typed context."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise CanonProvenanceError(f"CANON_PROVENANCE_INVALID_DONOR_FIELD field={field}")
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise CanonProvenanceError(
            f"CANON_PROVENANCE_INVALID_DONOR_FIELD field={field}"
        ) from exc
    if not 0.0 <= confidence <= 1.0:
        raise CanonProvenanceError(f"CANON_PROVENANCE_INVALID_DONOR_FIELD field={field}")
    return confidence
