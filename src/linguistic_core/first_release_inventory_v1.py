"""Finite first-release inventory and two-axis coverage contract.

The inventory selects source components and fields; it does not ingest donor
bytes, authorize publication, or claim that selected coverage has been audited.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.contracts import PackRef
from linguistic_core.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    load_linguistic_source_manifest_v1,
)

CONSTRUCTION_AXES = (
    "verbal_predicates",
    "nominal_references",
    "adjectival_state_predication",
    "light_verb_constructions",
    "alternations_converses",
    "negation_modality_aspect",
    "quantities_comparisons",
    "temporal_scope",
    "generic_kind_claims",
    "nested_attributed_claims",
)

DOMAIN_AXES = (
    "physical_spatial",
    "time_change",
    "agents_organizations",
    "possession_transfer",
    "social_legal",
    "information_communication",
    "cognition_argument",
    "measurement",
)

CoverageStatus = Literal[
    "selected_unmeasured",
    "contract_only",
    "explicit_gap",
    "out_of_scope_first_release",
]


class InventoryError(RuntimeError):
    """Raised when the M2 inventory is incomplete, inconsistent, or drifted."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRefV1(_Model):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _safe_path(self) -> EvidenceRefV1:
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("evidence path must be repository-relative")
        return self


class RightsDispositionV1(_Model):
    license_disposition: Literal[
        "verified_redistributable", "mixed_review_required", "unknown"
    ]
    license_ids: tuple[str, ...]
    redistribution_allowed: bool
    release_condition: str = Field(min_length=1)
    evidence: tuple[EvidenceRefV1, ...] = Field(min_length=1)


class FieldSelectionV1(_Model):
    field: str = Field(pattern=r"^[a-z0-9_.]+$")
    disposition: Literal["include", "exclude"]
    implementation_state: Literal["retained", "not_yet_retained", "not_applicable"]
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _state_matches_disposition(self) -> FieldSelectionV1:
        if (
            self.disposition == "include"
            and self.implementation_state == "not_applicable"
        ):
            raise ValueError("included fields require a real implementation state")
        if (
            self.disposition == "exclude"
            and self.implementation_state != "not_applicable"
        ):
            raise ValueError("excluded fields must be not_applicable")
        return self


class StructuredCountV1(_Model):
    unit: str = Field(pattern=r"^[a-z0-9_]+$")
    selected: int = Field(ge=0)
    available: int = Field(ge=0)
    selected_field: str = Field(pattern=r"^[a-z0-9_]+$")
    available_field: str = Field(pattern=r"^[a-z0-9_]+$")
    evidence: EvidenceRefV1

    @model_validator(mode="after")
    def _selected_does_not_exceed_available(self) -> StructuredCountV1:
        if self.selected > self.available:
            raise ValueError("selected component count cannot exceed available count")
        return self


class ComponentSelectionV1(_Model):
    component_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    selector: str = Field(min_length=1)
    disposition: Literal["include", "exclude"]
    rights_scope: str = Field(min_length=1)
    count: StructuredCountV1
    fields: tuple[FieldSelectionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _fields_are_unique(self) -> ComponentSelectionV1:
        names = [item.field for item in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("component field names must be unique")
        if self.disposition == "include" and not any(
            item.disposition == "include" for item in self.fields
        ):
            raise ValueError("included component requires at least one included field")
        return self


class DonorSelectionV1(_Model):
    source_key: str = Field(pattern=r"^[a-z0-9_]+$")
    family: Literal["propbank", "framenet", "sumo"]
    release_label: str = Field(min_length=1)
    identity: str = Field(min_length=1)
    rights: RightsDispositionV1
    components: tuple[ComponentSelectionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _components_are_unique(self) -> DonorSelectionV1:
        ids = [item.component_id for item in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("donor component ids must be unique")
        if not any(item.disposition == "include" for item in self.components):
            raise ValueError("selected donor requires an included component")
        return self


class ExcludedCandidateV1(_Model):
    candidate_key: str = Field(pattern=r"^[a-z0-9_]+$")
    family: str = Field(min_length=1)
    disposition: Literal[
        "deferred_not_selected",
        "deferred_internal_only",
        "excluded_no_permission",
    ]
    version_status: Literal["not_pinned_not_selected"]
    reason: str = Field(min_length=1)


class CoverageCellRuleV1(_Model):
    status: CoverageStatus
    source_keys: tuple[str, ...] = ()
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def _sources_match_status(self) -> CoverageCellRuleV1:
        if self.status == "selected_unmeasured" and not self.source_keys:
            raise ValueError(
                "selected_unmeasured coverage requires selected source keys"
            )
        if self.status != "selected_unmeasured" and self.source_keys:
            raise ValueError("only selected_unmeasured coverage may cite source keys")
        return self


class CoverageRuleV1(_Model):
    construction: Literal[*CONSTRUCTION_AXES]
    default: CoverageCellRuleV1
    domain_overrides: dict[Literal[*DOMAIN_AXES], CoverageCellRuleV1] = Field(
        default_factory=dict
    )


class FirstReleaseInventoryV1(_Model):
    schema_version: Literal["linguistic-first-release-inventory-v1"]
    inventory_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    revision: str = Field(min_length=1)
    target_pack: PackRef
    publication_status: Literal["not_authorized"]
    source_manifest: EvidenceRefV1
    target_pack_manifest: EvidenceRefV1
    supporting_evidence: tuple[EvidenceRefV1, ...] = Field(min_length=1)
    selected_donors: tuple[DonorSelectionV1, ...] = Field(min_length=1)
    excluded_candidates: tuple[ExcludedCandidateV1, ...]
    coverage_rules: tuple[CoverageRuleV1, ...]

    @model_validator(mode="after")
    def _inventory_is_finite(self) -> FirstReleaseInventoryV1:
        selected = [item.source_key for item in self.selected_donors]
        if len(selected) != len(set(selected)):
            raise ValueError("selected donor keys must be unique")
        excluded = [item.candidate_key for item in self.excluded_candidates]
        if len(excluded) != len(set(excluded)):
            raise ValueError("excluded candidate keys must be unique")
        if set(selected) & set(excluded):
            raise ValueError("one source cannot be both selected and excluded")
        constructions = [item.construction for item in self.coverage_rules]
        if set(constructions) != set(CONSTRUCTION_AXES) or len(constructions) != len(
            CONSTRUCTION_AXES
        ):
            raise ValueError(
                "coverage rules must contain every construction exactly once"
            )
        return self


class CoverageCellV1(_Model):
    construction: Literal[*CONSTRUCTION_AXES]
    domain: Literal[*DOMAIN_AXES]
    status: CoverageStatus
    source_keys: tuple[str, ...]
    note: str


class InventoryReportV1(_Model):
    schema_version: Literal["linguistic-first-release-inventory-report-v1"]
    inventory_id: str
    inventory_revision: str
    target_pack: PackRef
    publication_status: Literal["not_authorized"]
    selected_donor_count: int
    included_component_count: int
    included_field_count: int
    not_yet_retained_field_count: int
    excluded_candidate_count: int
    coverage_cells: tuple[CoverageCellV1, ...]
    coverage_counts: dict[str, int]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_evidence(repo_root: Path, ref: EvidenceRefV1) -> Path:
    root = repo_root.resolve()
    path = (root / ref.path).resolve()
    if root not in path.parents or not path.is_file():
        raise InventoryError(f"INVENTORY_EVIDENCE_UNAVAILABLE path={ref.path}")
    observed = _sha256(path)
    if observed != ref.sha256:
        raise InventoryError(
            f"INVENTORY_EVIDENCE_DRIFT path={ref.path} expected={ref.sha256} observed={observed}"
        )
    return path


def _source_identity(source: LinguisticSourceSnapshotV1) -> str:
    if source.git_identity is not None:
        return (
            f"git:commit={source.git_identity.commit_sha};"
            f"tree={source.git_identity.tree_sha}"
        )
    if source.archive_identity is not None:
        return (
            f"archive:sha256={source.archive_identity.sha256};"
            f"bytes={source.archive_identity.byte_count};"
            f"filename={source.archive_identity.archive_filename}"
        )
    raise InventoryError(f"INVENTORY_SOURCE_NOT_PINNED source={source.source_key}")


def _validate_donor(
    donor: DonorSelectionV1,
    source_manifest: LinguisticSourceManifestV1,
    repo_root: Path,
) -> None:
    try:
        source = source_manifest.source_for(donor.source_key)
    except ValueError as exc:
        raise InventoryError(
            f"INVENTORY_SOURCE_NOT_DECLARED source={donor.source_key}"
        ) from exc
    if donor.family != source.family or donor.release_label != source.release_label:
        raise InventoryError(
            f"INVENTORY_SOURCE_METADATA_MISMATCH source={donor.source_key}"
        )
    if donor.identity != _source_identity(source):
        raise InventoryError(
            f"INVENTORY_SOURCE_IDENTITY_MISMATCH source={donor.source_key}"
        )
    if (
        donor.rights.license_disposition != source.license_disposition
        or donor.rights.redistribution_allowed != source.redistribution_allowed
    ):
        raise InventoryError(f"INVENTORY_RIGHTS_MISMATCH source={donor.source_key}")
    exact_license_ids = {
        item.license_id
        for item in (*source.license_evidence, *source.metadata_evidence)
        if item.license_id is not None
    }
    if (
        source.license_disposition == "verified_redistributable"
        and set(donor.rights.license_ids) != exact_license_ids
    ):
        raise InventoryError(f"INVENTORY_LICENSE_ID_MISMATCH source={donor.source_key}")
    if (
        source.license_disposition == "mixed_review_required"
        and not donor.rights.license_ids
    ):
        raise InventoryError(
            f"INVENTORY_MIXED_RIGHTS_UNDISPOSITIONED source={donor.source_key}"
        )
    for ref in donor.rights.evidence:
        _resolve_evidence(repo_root, ref)


def _validate_structured_count(repo_root: Path, count: StructuredCountV1) -> None:
    path = _resolve_evidence(repo_root, count.evidence)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(
            f"INVENTORY_COUNT_EVIDENCE_INVALID path={count.evidence.path}"
        ) from exc
    observed_selected = payload.get(count.selected_field)
    observed_available = payload.get(count.available_field)
    if observed_selected != count.selected or observed_available != count.available:
        raise InventoryError(
            f"INVENTORY_COMPONENT_COUNT_MISMATCH unit={count.unit} "
            f"expected={count.selected}/{count.available} "
            f"observed={observed_selected}/{observed_available}"
        )


def _validate_target_pack(repo_root: Path, inventory: FirstReleaseInventoryV1) -> None:
    expected_path = (
        f"ontology_packs/{inventory.target_pack.pack_id}/"
        f"{inventory.target_pack.pack_version}/manifest.yaml"
    )
    if inventory.target_pack_manifest.path != expected_path:
        raise InventoryError(
            f"INVENTORY_TARGET_PACK_PATH_MISMATCH expected={expected_path}"
        )
    path = _resolve_evidence(repo_root, inventory.target_pack_manifest)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        pack = payload["pack"]
    except (OSError, UnicodeError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise InventoryError("INVENTORY_TARGET_PACK_MANIFEST_INVALID") from exc
    if (
        pack.get("id") != inventory.target_pack.pack_id
        or pack.get("version") != inventory.target_pack.pack_version
    ):
        raise InventoryError("INVENTORY_TARGET_PACK_IDENTITY_MISMATCH")


def expand_coverage_matrix(
    inventory: FirstReleaseInventoryV1,
) -> tuple[CoverageCellV1, ...]:
    selected = {item.source_key for item in inventory.selected_donors}
    rules = {item.construction: item for item in inventory.coverage_rules}
    cells: list[CoverageCellV1] = []
    for construction in CONSTRUCTION_AXES:
        rule = rules[construction]
        for domain in DOMAIN_AXES:
            cell = rule.domain_overrides.get(domain, rule.default)
            unknown = set(cell.source_keys) - selected
            if unknown:
                raise InventoryError(
                    f"COVERAGE_REFERENCES_UNSELECTED_SOURCE construction={construction} "
                    f"domain={domain} sources={sorted(unknown)}"
                )
            cells.append(
                CoverageCellV1(
                    construction=construction,
                    domain=domain,
                    status=cell.status,
                    source_keys=cell.source_keys,
                    note=cell.note,
                )
            )
    return tuple(cells)


def load_and_validate_inventory(
    repo_root: Path, inventory_path: Path
) -> tuple[FirstReleaseInventoryV1, InventoryReportV1]:
    try:
        inventory = FirstReleaseInventoryV1.model_validate(
            yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        raise InventoryError(
            f"INVALID_FIRST_RELEASE_INVENTORY path={inventory_path}"
        ) from exc
    source_manifest_path = _resolve_evidence(repo_root, inventory.source_manifest)
    source_manifest = load_linguistic_source_manifest_v1(source_manifest_path)
    _validate_target_pack(repo_root, inventory)
    for ref in inventory.supporting_evidence:
        _resolve_evidence(repo_root, ref)
    for donor in inventory.selected_donors:
        _validate_donor(donor, source_manifest, repo_root)
        for component in donor.components:
            _validate_structured_count(repo_root, component.count)
    cells = expand_coverage_matrix(inventory)
    counts = {
        status: 0
        for status in (
            "selected_unmeasured",
            "contract_only",
            "explicit_gap",
            "out_of_scope_first_release",
        )
    }
    for cell in cells:
        counts[cell.status] += 1
    components = [
        component
        for donor in inventory.selected_donors
        for component in donor.components
        if component.disposition == "include"
    ]
    fields = [
        field
        for component in components
        for field in component.fields
        if field.disposition == "include"
    ]
    canonical = json.dumps(
        {
            "inventory": inventory.model_dump(mode="json"),
            "coverage_cells": [cell.model_dump(mode="json") for cell in cells],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    report = InventoryReportV1(
        schema_version="linguistic-first-release-inventory-report-v1",
        inventory_id=inventory.inventory_id,
        inventory_revision=inventory.revision,
        target_pack=inventory.target_pack,
        publication_status=inventory.publication_status,
        selected_donor_count=len(inventory.selected_donors),
        included_component_count=len(components),
        included_field_count=len(fields),
        not_yet_retained_field_count=sum(
            item.implementation_state == "not_yet_retained" for item in fields
        ),
        excluded_candidate_count=len(inventory.excluded_candidates),
        coverage_cells=cells,
        coverage_counts=counts,
        evidence_sha256=hashlib.sha256(canonical).hexdigest(),
    )
    return inventory, report


def render_inventory_markdown(
    inventory: FirstReleaseInventoryV1, report: InventoryReportV1
) -> str:
    lines = [
        "# Finite first-release inventory v1",
        "",
        f"Target: `{report.target_pack.pack_id}@{report.target_pack.pack_version}`. Publication status: **{report.publication_status}**.",
        "",
        "This is a bounded selection contract, not donor ingestion, audited coverage, release approval, or permission to use excluded sources.",
        "",
        "## Selected donors, components, fields, and rights",
        "",
    ]
    for donor in inventory.selected_donors:
        lines.extend(
            [
                f"### `{donor.source_key}` — {donor.family} ({donor.release_label})",
                "",
                f"- Exact identity: `{donor.identity}`",
                f"- Rights: `{donor.rights.license_disposition}`; redistribution `{donor.rights.redistribution_allowed}`; {donor.rights.release_condition}",
                "",
            ]
        )
        for component in donor.components:
            lines.append(
                f"- Component `{component.component_id}`: **{component.disposition}**, selector `{component.selector}`, rights scope: {component.rights_scope}"
            )
            lines.append(
                f"  - Finite count: {component.count.selected}/{component.count.available} `{component.count.unit}` bound to `{component.count.evidence.path}`."
            )
            for field in component.fields:
                lines.append(
                    f"  - `{field.field}` — `{field.disposition}` / `{field.implementation_state}`: {field.reason}"
                )
        lines.append("")
    lines.extend(["## Explicitly unselected candidates", ""])
    for candidate in inventory.excluded_candidates:
        lines.append(
            f"- `{candidate.candidate_key}` ({candidate.family}): `{candidate.disposition}` — {candidate.reason}"
        )
    lines.extend(["", "## Two-axis coverage matrix", ""])
    by_key = {(cell.construction, cell.domain): cell for cell in report.coverage_cells}
    lines.append("| Construction \\ domain | " + " | ".join(DOMAIN_AXES) + " |")
    lines.append("|---|" + "---|" * len(DOMAIN_AXES))
    for construction in CONSTRUCTION_AXES:
        values = [by_key[(construction, domain)].status for domain in DOMAIN_AXES]
        lines.append(
            f"| `{construction}` | "
            + " | ".join(f"`{value}`" for value in values)
            + " |"
        )
    lines.extend(
        [
            "",
            "`selected_unmeasured` means source fields are selected but record-level coverage remains M3 work. `contract_only` means M1 can represent the distinction but this inventory selects no donor field for it. `explicit_gap` means the first release has neither selected donor support nor a completed representation route.",
            "",
            "## Counts and boundary",
            "",
            f"- Selected donors: {report.selected_donor_count}; included components: {report.included_component_count}; included fields: {report.included_field_count}.",
            f"- Included fields not yet retained: {report.not_yet_retained_field_count}.",
            f"- Matrix cells: {len(report.coverage_cells)} ({report.coverage_counts}).",
            f"- Excluded/deferred candidate sources: {report.excluded_candidate_count}.",
            f"- Evidence digest: `{report.evidence_sha256}`.",
            "- Public release remains unauthorized; restricted and unselected sources remain outside the build.",
            "",
        ]
    )
    return "\n".join(lines)
