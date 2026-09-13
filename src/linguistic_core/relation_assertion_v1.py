"""Candidate first-class relation assertion and objectification contract.

A relation assertion preserves grouped role bindings and may itself fill a role
in another relation.  This is additive M4 construction work; it does not change
published packs or install consumer execution semantics.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from linguistic_core.role_definition_v1 import RelationSchemaV1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FillerRefV1(_StrictModel):
    filler_kind: Literal["reference", "relation_assertion"]
    filler_id: str = Field(min_length=1)


class RoleBindingV1(_StrictModel):
    role_definition_id: str = Field(min_length=1)
    filler: FillerRefV1

class RelationAssertionV1(_StrictModel):
    assertion_id: str = Field(min_length=1)
    relation_schema_id: str = Field(min_length=1)
    bindings: tuple[RoleBindingV1, ...] = Field(min_length=1)


class RelationAssertionBundleV1(_StrictModel):
    schema_version: Literal["relation-assertion-bundle.v1"]
    schemas: tuple[RelationSchemaV1, ...] = Field(min_length=1)
    assertions: tuple[RelationAssertionV1, ...] = Field(min_length=1)
    top_assertion_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_sets(self) -> "RelationAssertionBundleV1":
        schema_ids = [item.relation_schema_id for item in self.schemas]
        if len(schema_ids) != len(set(schema_ids)):
            raise ValueError("RELATION_ASSERTION_SCHEMA_ID_DUPLICATE")
        assertion_ids = [item.assertion_id for item in self.assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("RELATION_ASSERTION_ID_DUPLICATE")
        if self.top_assertion_id not in set(assertion_ids):
            raise ValueError("RELATION_ASSERTION_TOP_MISSING")
        return self


class RelationAssertionProbeReportV1(_StrictModel):
    schema_version: Literal["relation-assertion-probe-report.v1"]
    schema_count: int = Field(ge=0)
    assertion_count: int = Field(ge=0)
    relation_assertion_filler_count: int = Field(ge=0)
    top_assertion_id: str
    checks: tuple[str, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

def load_relation_assertion_bundle(path: Path) -> RelationAssertionBundleV1:
    try:
        return RelationAssertionBundleV1.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ValueError(f"RELATION_ASSERTION_BUNDLE_INVALID path={path}") from exc


def _indexes(bundle: RelationAssertionBundleV1):
    return (
        {item.relation_schema_id: item for item in bundle.schemas},
        {item.assertion_id: item for item in bundle.assertions},
    )


def validate_relation_assertion_bundle(
    bundle: RelationAssertionBundleV1,
) -> RelationAssertionProbeReportV1:
    schemas, assertions = _indexes(bundle)
    nested_count = 0

    for assertion in bundle.assertions:
        schema = schemas.get(assertion.relation_schema_id)
        if schema is None:
            raise ValueError(
                f"RELATION_ASSERTION_SCHEMA_MISSING relation={assertion.relation_schema_id}"
            )
        role_index = {role.role_definition_id: role for role in schema.roles}
        observed_counts = {role_id: 0 for role_id in role_index}

        for binding in assertion.bindings:
            role = role_index.get(binding.role_definition_id)
            if role is None:
                raise ValueError(
                    "RELATION_ASSERTION_ROLE_UNKNOWN "
                    f"assertion={assertion.assertion_id} role={binding.role_definition_id}"
                )
            observed_counts[binding.role_definition_id] += 1
            filler = binding.filler
            expected_relation = role.expected_filler_type if role.expected_filler_type in schemas else None
            if filler.filler_kind == "relation_assertion":
                nested_count += 1
                if filler.filler_id == assertion.assertion_id:
                    raise ValueError("RELATION_ASSERTION_SELF_REFERENCE")
                target = assertions.get(filler.filler_id)
                if target is None:
                    raise ValueError(
                        "RELATION_ASSERTION_FILLER_MISSING "
                        f"filler={filler.filler_id}"
                    )
                if expected_relation is not None and target.relation_schema_id != expected_relation:
                    raise ValueError(
                        "RELATION_ASSERTION_FILLER_TYPE_MISMATCH "
                        f"expected={expected_relation} observed={target.relation_schema_id}"
                    )
            elif expected_relation is not None:
                raise ValueError(
                    "RELATION_ASSERTION_FILLER_REQUIRED "
                    f"role={role.role_definition_id} expected_relation={expected_relation}"
                )

        for role_id, role in role_index.items():
            count = observed_counts[role_id]
            if count < role.min_count:
                raise ValueError(
                    "RELATION_ASSERTION_ROLE_MIN_COUNT "
                    f"role={role_id} expected={role.min_count} observed={count}"
                )
            if role.max_count is not None and count > role.max_count:
                raise ValueError(
                    "RELATION_ASSERTION_ROLE_MAX_COUNT "
                    f"role={role_id} expected={role.max_count} observed={count}"
                )
    checks = (
        "relation_assertion_preserves_grouped_role_bindings",
        "relation_assertion_can_fill_another_relation_role",
        "nested_relation_filler_type_is_checked_against_schema",
        "role_cardinality_is_enforced_on_assertions",
        "binary_reference_cannot_silently_replace_required_objectification",
    )
    body = {
        "schema_count": len(bundle.schemas),
        "assertion_count": len(bundle.assertions),
        "relation_assertion_filler_count": nested_count,
        "top_assertion_id": bundle.top_assertion_id,
        "checks": checks,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RelationAssertionProbeReportV1(
        schema_version="relation-assertion-probe-report.v1",
        content_sha256=digest,
        **body,
    )
