"""M4 acquisition mapping v2: predicate-local role identity over the v1 evidence receipt.

V2 is an additive enrichment. It preserves the complete v1 acquisition report
unchanged and resolves each donor-backed global role transform to exactly one
predicate-local role definition on each side. It does not change a published
pack or reinterpret donor evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from linguistic_core.m4_acquisition_mapping_v1 import (
    AcquisitionMappingReportV1,
    RoleTransformEvidenceV1,
    build_report as build_report_v1,
)
from linguistic_core.role_definition_v1 import (
    PredicateRoleSchemaV1,
    RoleDefinitionProbeInputV1,
    RoleDefinitionV1,
)
from linguistic_core.semantic_construction_v1 import ConstructionCaseV1, ExactPackClosureV1
from linguistic_core.m4_acquisition_mapping_v1 import PropBankEvidenceV1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LocalizedRoleTransformV2(_StrictModel):
    """One v1 global-role transform with explicit predicate-local identities."""

    source_role_definition_id: str = Field(pattern=r"^lc\.roledef\.")
    target_role_definition_id: str = Field(pattern=r"^lc\.roledef\.")
    global_transform: RoleTransformEvidenceV1


class LocalizedDirectionalMappingV2(_StrictModel):
    mapping_id: str = Field(pattern=r"^m4-acquisition-[a-z0-9-]+$")
    source_predicate_id: str = Field(pattern=r"^lc:")
    target_predicate_id: str = Field(pattern=r"^lc:")
    localized_role_transforms: tuple[LocalizedRoleTransformV2, ...]


class AcquisitionMappingReportV2(_StrictModel):
    schema_version: Literal["m4-acquisition-mapping-report.v2"]
    base_report: AcquisitionMappingReportV1
    role_definition_asset: str = Field(min_length=1)
    role_definition_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    localized_mappings: tuple[LocalizedDirectionalMappingV2, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class LocalRoleResolutionError(ValueError):
    """Raised when local role identity cannot be resolved uniquely."""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _schema_index(value: RoleDefinitionProbeInputV1) -> dict[str, PredicateRoleSchemaV1]:
    result: dict[str, PredicateRoleSchemaV1] = {}
    for schema in value.predicate_schemas:
        if schema.predicate_id in result:
            raise LocalRoleResolutionError(
                f"M4_V2_PREDICATE_ROLE_SCHEMA_DUPLICATE predicate={schema.predicate_id}"
            )
        result[schema.predicate_id] = schema
    return result


def _resolve_local_role(
    schema: PredicateRoleSchemaV1,
    grounded_role_id: str,
) -> RoleDefinitionV1:
    matches = tuple(
        role for role in schema.roles if role.grounded_role_id == grounded_role_id
    )
    if not matches:
        raise LocalRoleResolutionError(
            "M4_V2_LOCAL_ROLE_MISSING "
            f"predicate={schema.predicate_id} grounded_role={grounded_role_id}"
        )
    if len(matches) != 1:
        raise LocalRoleResolutionError(
            "M4_V2_LOCAL_ROLE_AMBIGUOUS "
            f"predicate={schema.predicate_id} grounded_role={grounded_role_id} count={len(matches)}"
        )
    return matches[0]


def _localized_mapping(
    *,
    source_predicate_id: str,
    target_predicate_id: str,
    mapping_id: str,
    transforms: tuple[RoleTransformEvidenceV1, ...],
    schemas: dict[str, PredicateRoleSchemaV1],
    declared_local_pairs: tuple[tuple[str, str], ...],
) -> LocalizedDirectionalMappingV2:
    try:
        source_schema = schemas[source_predicate_id]
        target_schema = schemas[target_predicate_id]
    except KeyError as exc:
        raise LocalRoleResolutionError(
            f"M4_V2_PREDICATE_ROLE_SCHEMA_MISSING predicate={exc.args[0]}"
        ) from exc

    localized: list[LocalizedRoleTransformV2] = []
    observed_pairs: list[tuple[str, str]] = []
    for transform in transforms:
        source = _resolve_local_role(source_schema, transform.source_role_id)
        target = _resolve_local_role(target_schema, transform.target_role_id)
        observed_pairs.append((source.role_definition_id, target.role_definition_id))
        localized.append(
            LocalizedRoleTransformV2(
                source_role_definition_id=source.role_definition_id,
                target_role_definition_id=target.role_definition_id,
                global_transform=transform,
            )
        )

    if tuple(observed_pairs) != declared_local_pairs:
        raise LocalRoleResolutionError(
            "M4_V2_LOCAL_TRANSFORM_DECLARATION_DRIFT "
            f"observed={tuple(observed_pairs)!r} declared={declared_local_pairs!r}"
        )

    return LocalizedDirectionalMappingV2(
        mapping_id=mapping_id,
        source_predicate_id=source_predicate_id,
        target_predicate_id=target_predicate_id,
        localized_role_transforms=tuple(localized),
    )


def build_report(
    *,
    closure: ExactPackClosureV1,
    cases: tuple[ConstructionCaseV1, ...],
    case_manifest: str,
    donor_mapping_asset: str,
    predicate_relation_asset: str,
    role_correspondence_asset: str,
    donor_rows: tuple[dict[str, object], ...],
    m3_evidence: PropBankEvidenceV1 | None = None,
    m3_reconciliation_asset: str = "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json",
    manifest_case_ids: tuple[str, ...] | None = None,
    role_definition_asset: str,
    role_definition_input: RoleDefinitionProbeInputV1,
    role_definition_asset_sha256: str | None = None,
) -> AcquisitionMappingReportV2:
    """Build v1 exactly, then attach unique predicate-local role identities."""

    base = build_report_v1(
        closure=closure,
        cases=cases,
        case_manifest=case_manifest,
        donor_mapping_asset=donor_mapping_asset,
        predicate_relation_asset=predicate_relation_asset,
        role_correspondence_asset=role_correspondence_asset,
        donor_rows=donor_rows,
        m3_evidence=m3_evidence,
        m3_reconciliation_asset=m3_reconciliation_asset,
        manifest_case_ids=manifest_case_ids,
    )
    if base.failed:
        raise ValueError(f"M4_V2_BASE_REPORT_FAILED failed={base.failed}")

    schemas = _schema_index(role_definition_input)
    declared_pairs = tuple(
        (item.source_role_definition_id, item.target_role_definition_id)
        for item in role_definition_input.acquisition_transforms
    )
    localized = tuple(
        _localized_mapping(
            source_predicate_id=mapping.source_predicate_id,
            target_predicate_id=mapping.target_predicate_id,
            mapping_id=mapping.mapping_id,
            transforms=mapping.role_transforms,
            schemas=schemas,
            declared_local_pairs=declared_pairs,
        )
        for mapping in base.directional_mappings
    )

    if role_definition_asset_sha256 is None:
        path = Path(role_definition_asset)
        if not path.is_file():
            root_path = Path(__file__).parents[2] / role_definition_asset
            if root_path.is_file():
                path = root_path
        if not path.is_file():
            raise ValueError(
                f"M4_V2_ROLE_DEFINITION_ASSET_UNAVAILABLE path={role_definition_asset}"
            )
        role_definition_asset_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    body = {
        "schema_version": "m4-acquisition-mapping-report.v2",
        "base_report": base.model_dump(mode="json"),
        "role_definition_asset": role_definition_asset,
        "role_definition_asset_sha256": role_definition_asset_sha256,
        "localized_mappings": [item.model_dump(mode="json") for item in localized],
    }
    return AcquisitionMappingReportV2(
        schema_version="m4-acquisition-mapping-report.v2",
        base_report=base,
        role_definition_asset=role_definition_asset,
        role_definition_asset_sha256=role_definition_asset_sha256,
        localized_mappings=localized,
        content_sha256=_digest(body),
    )


def render_report(report: AcquisitionMappingReportV2) -> str:
    mapping = report.localized_mappings[0]
    base_mapping = report.base_report.directional_mappings[0]
    lines = [
        "# M4 acquisition mapping report v2",
        "",
        "Predicate-local role identity layered over the unchanged v1 donor-backed mapping receipt.",
        "",
        f"- Pack target: `{report.base_report.pack_target}`",
        f"- Direction: `{mapping.source_predicate_id}` → `{mapping.target_predicate_id}` (`{base_mapping.relation}`)",
        f"- V1 receipt digest: `{report.base_report.content_sha256}`",
        f"- Role-definition asset: `{report.role_definition_asset}` (`{report.role_definition_asset_sha256}`)",
        f"- Localized transforms: `{len(mapping.localized_role_transforms)}`",
        "",
        "## Local + reusable role transforms",
        "",
    ]
    for item in mapping.localized_role_transforms:
        global_item = item.global_transform
        lines.append(
            "- "
            f"`{item.source_role_definition_id}` → `{item.target_role_definition_id}`; "
            f"grounds `{global_item.source_role_id}` → `{global_item.target_role_id}`; "
            f"donor `{global_item.source_donor.source_id}` → `{global_item.target_donor.source_id}`."
        )
    lines.extend(["", "## Preserved v1 case results", ""])
    for case in report.base_report.cases:
        lines.append(
            f"- `{case.case_id}`: **{'PASS' if case.passed else 'FAIL'}** — "
            f"expected `{case.expected_status}`, observed `{case.observed_status}` (`{case.reason}`)."
        )
    lines.extend(
        [
            "",
            f"**Result:** {report.base_report.passed} passed, {report.base_report.failed} failed; "
            f"v2 digest `{report.content_sha256}`.",
            "",
        ]
    )
    return "\n".join(lines)
