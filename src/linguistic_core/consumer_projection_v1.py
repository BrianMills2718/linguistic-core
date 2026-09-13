"""Execute declared consumer-profile projections over grouped relation assertions.

Projection output is downstream of canonical grouped assertions. Lossy views
carry explicit receipts naming omitted roles and fillers and are never licensed
as canonically equivalent round trips.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from linguistic_core.consumer_profile_v1 import (
    ProjectionRuleV1,
    load_consumer_profile_contract,
    validate_consumer_profile_contract,
)
from linguistic_core.relation_assertion_v1 import (
    FillerRefV1,
    RelationAssertionV1,
    load_relation_assertion_bundle,
)
from linguistic_core.role_definition_v1 import RelationSchemaV1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProjectedRoleValueV1(_StrictModel):
    role_definition_id: str
    local_name: str
    fillers: tuple[FillerRefV1, ...]

class ProjectionLossReceiptV1(_StrictModel):
    projection_id: str
    loss_classification: Literal["lossless", "lossy"]
    omitted_roles: tuple[ProjectedRoleValueV1, ...]
    loss_note: str
    canonical_equivalence: bool


class ProjectionExecutionV1(_StrictModel):
    schema_version: Literal["consumer-projection-execution.v1"]
    profile_id: str
    profile_version: str
    projection_id: str
    target_view: Literal["binary_edge", "table_row"]
    source_assertion_id: str
    source_relation_schema_id: str
    selected_roles: tuple[ProjectedRoleValueV1, ...]
    endpoint_fillers: tuple[FillerRefV1, ...]
    loss_receipt: ProjectionLossReceiptV1
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _binding_index(assertion: RelationAssertionV1) -> dict[str, list[FillerRefV1]]:
    result: dict[str, list[FillerRefV1]] = {}
    for binding in assertion.bindings:
        result.setdefault(binding.role_definition_id, []).append(binding.filler)
    return result


def _role_values(
    role_ids: tuple[str, ...],
    schema: RelationSchemaV1,
    fillers_by_role: dict[str, list[FillerRefV1]],
) -> tuple[ProjectedRoleValueV1, ...]:
    role_index = {item.role_definition_id: item for item in schema.roles}
    result: list[ProjectedRoleValueV1] = []
    for role_id in role_ids:
        role = role_index.get(role_id)
        if role is None:
            raise ValueError(f"PROJECTION_ROLE_DEFINITION_MISSING role={role_id}")
        result.append(
            ProjectedRoleValueV1(
                role_definition_id=role_id,
                local_name=role.local_name,
                fillers=tuple(fillers_by_role.get(role_id, ())),
            )
        )
    return tuple(result)


def _projection_rule(contract, projection_id: str) -> ProjectionRuleV1:
    rule = next(
        (item for item in contract.projections if item.projection_id == projection_id),
        None,
    )
    if rule is None:
        raise ValueError(f"PROFILE_PROJECTION_UNKNOWN projection={projection_id}")
    return rule


def execute_consumer_projection(
    manifest_path: Path,
    *,
    projection_id: str,
    source_assertion_id: str,
) -> ProjectionExecutionV1:
    validate_consumer_profile_contract(manifest_path)
    contract = load_consumer_profile_contract(manifest_path)
    rule = _projection_rule(contract, projection_id)
    bundle_path = (manifest_path.parent / contract.source_bundle).resolve()
    bundle = load_relation_assertion_bundle(bundle_path)
    assertion = next(
        (item for item in bundle.assertions if item.assertion_id == source_assertion_id),
        None,
    )
    if assertion is None:
        raise ValueError(
            f"PROJECTION_SOURCE_ASSERTION_MISSING assertion={source_assertion_id}"
        )
    if assertion.relation_schema_id != rule.source_relation_schema_id:
        raise ValueError(
            "PROJECTION_SOURCE_RELATION_MISMATCH "
            f"expected={rule.source_relation_schema_id} observed={assertion.relation_schema_id}"
        )
    schema = next(
        item for item in bundle.schemas
        if item.relation_schema_id == assertion.relation_schema_id
    )
    fillers_by_role = _binding_index(assertion)
    selected = _role_values(rule.selected_role_definition_ids, schema, fillers_by_role)
    omitted = _role_values(rule.omitted_role_definition_ids, schema, fillers_by_role)
    endpoints: list[FillerRefV1] = []
    for role_id in rule.endpoint_role_definition_ids:
        fillers = fillers_by_role.get(role_id, ())
        if len(fillers) != 1:
            raise ValueError(
                "PROFILE_BINARY_ENDPOINT_CARDINALITY_UNSUPPORTED "
                f"role={role_id} count={len(fillers)}"
            )
        endpoints.append(fillers[0])

    receipt = ProjectionLossReceiptV1(
        projection_id=rule.projection_id,
        loss_classification=rule.loss_classification,
        omitted_roles=omitted,
        loss_note=rule.loss_note,
        canonical_equivalence=rule.loss_classification == "lossless",
    )
    body = {
        "profile_id": contract.profile_id,
        "profile_version": contract.profile_version,
        "projection_id": rule.projection_id,
        "target_view": rule.target_view,
        "source_assertion_id": assertion.assertion_id,
        "source_relation_schema_id": assertion.relation_schema_id,
        "selected_roles": [item.model_dump(mode="json") for item in selected],
        "endpoint_fillers": [item.model_dump(mode="json") for item in endpoints],
        "loss_receipt": receipt.model_dump(mode="json"),
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProjectionExecutionV1(
        schema_version="consumer-projection-execution.v1",
        profile_id=contract.profile_id,
        profile_version=contract.profile_version,
        projection_id=rule.projection_id,
        target_view=rule.target_view,
        source_assertion_id=assertion.assertion_id,
        source_relation_schema_id=assertion.relation_schema_id,
        selected_roles=selected,
        endpoint_fillers=tuple(endpoints),
        loss_receipt=receipt,
        content_sha256=digest,
    )


def require_canonical_projection_equivalence(view: ProjectionExecutionV1) -> None:
    """Refuse to treat a lossy view as equivalent canonical semantics."""

    if not view.loss_receipt.canonical_equivalence:
        raise ValueError(
            "LOSSY_PROJECTION_CANNOT_ROUND_TRIP_EQUIVALENTLY "
            f"projection={view.projection_id} source={view.source_assertion_id}"
        )
