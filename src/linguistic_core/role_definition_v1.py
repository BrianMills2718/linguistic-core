"""Candidate predicate-local role-definition contract.

This module is additive construction work for M4.  It does not change any
published ontology pack.  It makes explicit a distinction already implicit in
Linguistic Core's fact-oriented design:

* a reusable semantic role concept (for example ``lc.role.theme``); and
* one predicate-local role definition that may be grounded in that concept.

The local role owns predicate context, a stable identity, local name,
cardinality, and optional filler/constraint information.  Consumer profiles may
bind their own participant names to those local roles while keeping application
mechanics outside Linguistic Core.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RoleDefinitionV1(_StrictModel):
    """One role owned by one predicate/fact schema."""

    role_definition_id: str = Field(pattern=r"^lc\.roledef\.[a-z0-9_]+\.[a-z0-9_]+$")
    predicate_id: str = Field(pattern=r"^lc:")
    local_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    grounded_role_id: str | None = Field(default=None, pattern=r"^lc\.role\.")
    expected_filler_type: str | None = Field(default=None, min_length=1)
    min_count: int = Field(default=1, ge=0)
    max_count: int | None = Field(default=1, ge=1)
    presentation_ordinal: int = Field(ge=0)
    constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_cardinality(self) -> "RoleDefinitionV1":
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("ROLE_DEFINITION_CARDINALITY_INVALID")
        return self


class PredicateRoleSchemaV1(_StrictModel):
    """Candidate local-role schema for one LC predicate."""

    schema_version: Literal["predicate-role-schema.v1"] = "predicate-role-schema.v1"
    predicate_id: str = Field(pattern=r"^lc:")
    review_status: Literal["candidate"] = "candidate"
    roles: tuple[RoleDefinitionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_local_role_set(self) -> "PredicateRoleSchemaV1":
        if any(role.predicate_id != self.predicate_id for role in self.roles):
            raise ValueError("ROLE_DEFINITION_PREDICATE_MISMATCH")
        ids = [role.role_definition_id for role in self.roles]
        if len(ids) != len(set(ids)):
            raise ValueError("ROLE_DEFINITION_ID_DUPLICATE")
        names = [role.local_name for role in self.roles]
        if len(names) != len(set(names)):
            raise ValueError("ROLE_DEFINITION_LOCAL_NAME_DUPLICATE")
        ordinals = [role.presentation_ordinal for role in self.roles]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("ROLE_DEFINITION_PRESENTATION_ORDINAL_DUPLICATE")
        return self

    def role_by_id(self, role_definition_id: str) -> RoleDefinitionV1 | None:
        return next(
            (role for role in self.roles if role.role_definition_id == role_definition_id),
            None,
        )


class LocalRoleTransformV1(_StrictModel):
    """Transform between predicate-local roles rather than bare global roles."""

    source_role_definition_id: str = Field(pattern=r"^lc\.roledef\.")
    target_role_definition_id: str = Field(pattern=r"^lc\.roledef\.")


class ConsumerRoleMappingV1(_StrictModel):
    """Map one consumer-local participant name to one LC local role."""

    consumer_role_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    role_definition_id: str = Field(pattern=r"^lc\.roledef\.")
    grounded_role_id: str = Field(pattern=r"^lc\.role\.")


class ConsumerRoleProfileV1(_StrictModel):
    """Semantic-only consumer projection over a predicate-local role schema."""

    schema_version: Literal["consumer-role-profile.v1"] = "consumer-role-profile.v1"
    consumer_id: str = Field(min_length=1)
    predicate_id: str = Field(pattern=r"^lc:")
    mappings: tuple[ConsumerRoleMappingV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_consumer_names(self) -> "ConsumerRoleProfileV1":
        names = [item.consumer_role_name for item in self.mappings]
        if len(names) != len(set(names)):
            raise ValueError("CONSUMER_ROLE_NAME_DUPLICATE")
        local_ids = [item.role_definition_id for item in self.mappings]
        if len(local_ids) != len(set(local_ids)):
            raise ValueError("CONSUMER_ROLE_DEFINITION_DUPLICATE")
        return self


class RoleDefinitionProbeInputV1(_StrictModel):
    schema_version: Literal["role-definition-probe-input.v1"]
    predicate_schemas: tuple[PredicateRoleSchemaV1, ...] = Field(min_length=1)
    acquisition_transforms: tuple[LocalRoleTransformV1, ...] = Field(min_length=1)
    world_substrate_give: ConsumerRoleProfileV1


class RoleDefinitionProbeReportV1(_StrictModel):
    schema_version: Literal["role-definition-probe-report.v1"]
    predicate_schema_count: int = Field(ge=0)
    role_definition_count: int = Field(ge=0)
    acquisition_transform_count: int = Field(ge=0)
    world_substrate_mapping_count: int = Field(ge=0)
    checks: tuple[str, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def load_probe_input(path: Path) -> RoleDefinitionProbeInputV1:
    """Load one inspectable candidate fixture and fail closed on shape drift."""

    try:
        raw = path.read_text(encoding="utf-8")
        return RoleDefinitionProbeInputV1.model_validate_json(raw)
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ValueError(f"ROLE_DEFINITION_PROBE_INPUT_INVALID path={path}") from exc


def _schema_index(
    schemas: tuple[PredicateRoleSchemaV1, ...],
) -> dict[str, PredicateRoleSchemaV1]:
    result: dict[str, PredicateRoleSchemaV1] = {}
    for schema in schemas:
        if schema.predicate_id in result:
            raise ValueError(f"PREDICATE_ROLE_SCHEMA_DUPLICATE predicate={schema.predicate_id}")
        result[schema.predicate_id] = schema
    return result


def resolve_local_transform(
    source_schema: PredicateRoleSchemaV1,
    target_schema: PredicateRoleSchemaV1,
    transform: LocalRoleTransformV1,
) -> tuple[str, str]:
    """Resolve one local-role transform to the current reusable LC role concepts."""

    source = source_schema.role_by_id(transform.source_role_definition_id)
    target = target_schema.role_by_id(transform.target_role_definition_id)
    if source is None:
        raise ValueError(
            "LOCAL_ROLE_TRANSFORM_SOURCE_MISSING "
            f"role_definition_id={transform.source_role_definition_id}"
        )
    if target is None:
        raise ValueError(
            "LOCAL_ROLE_TRANSFORM_TARGET_MISSING "
            f"role_definition_id={transform.target_role_definition_id}"
        )
    if source.grounded_role_id is None or target.grounded_role_id is None:
        raise ValueError("LOCAL_ROLE_TRANSFORM_UNGROUNDED")
    return source.grounded_role_id, target.grounded_role_id


def validate_consumer_profile(
    schema: PredicateRoleSchemaV1,
    profile: ConsumerRoleProfileV1,
) -> tuple[tuple[str, str], ...]:
    """Validate a consumer profile without importing application mechanics into LC."""

    if profile.predicate_id != schema.predicate_id:
        raise ValueError("CONSUMER_ROLE_PROFILE_PREDICATE_MISMATCH")
    resolved: list[tuple[str, str]] = []
    for mapping in profile.mappings:
        role = schema.role_by_id(mapping.role_definition_id)
        if role is None:
            raise ValueError(
                "CONSUMER_ROLE_DEFINITION_MISSING "
                f"role_definition_id={mapping.role_definition_id}"
            )
        if role.grounded_role_id != mapping.grounded_role_id:
            raise ValueError(
                "CONSUMER_GROUNDED_ROLE_MISMATCH "
                f"consumer={mapping.consumer_role_name}"
            )
        resolved.append((mapping.consumer_role_name, mapping.grounded_role_id))
    return tuple(resolved)


def build_probe_report(value: RoleDefinitionProbeInputV1) -> RoleDefinitionProbeReportV1:
    """Run the bounded acquisition + World Substrate compatibility construction."""

    schemas = _schema_index(value.predicate_schemas)
    required = {
        "lc:buy_purchase",
        "lc:acquire_get_obtain",
        "lc:give_transfer",
    }
    if not required.issubset(schemas):
        raise ValueError(
            "ROLE_DEFINITION_REQUIRED_PREDICATE_MISSING "
            f"missing={sorted(required - set(schemas))}"
        )

    buy = schemas["lc:buy_purchase"]
    acquire = schemas["lc:acquire_get_obtain"]
    give = schemas["lc:give_transfer"]

    observed_pairs = tuple(
        resolve_local_transform(buy, acquire, transform)
        for transform in value.acquisition_transforms
    )
    expected_pairs = (
        ("lc.role.buyer", "lc.role.recipient"),
        ("lc.role.goods", "lc.role.theme"),
        ("lc.role.seller", "lc.role.source"),
    )
    if observed_pairs != expected_pairs:
        raise ValueError(
            "ACQUISITION_LOCAL_ROLE_TRANSFORM_DRIFT "
            f"observed={observed_pairs!r}"
        )

    observed_give = validate_consumer_profile(give, value.world_substrate_give)
    expected_give = (
        ("giver", "lc.role.donor"),
        ("transferred_object", "lc.role.theme"),
        ("recipient", "lc.role.recipient"),
    )
    if observed_give != expected_give:
        raise ValueError(
            "WORLD_SUBSTRATE_GIVE_ROLE_DRIFT "
            f"observed={observed_give!r}"
        )

    checks = (
        "predicate_local_role_identity",
        "local_roles_ground_to_reusable_lc_role_concepts",
        "acquisition_local_transforms_match_existing_m4_role_pairs",
        "world_substrate_give_profile_resolves_without_mechanic_semantics",
    )
    body = {
        "predicate_schema_count": len(schemas),
        "role_definition_count": sum(len(schema.roles) for schema in schemas.values()),
        "acquisition_transform_count": len(value.acquisition_transforms),
        "world_substrate_mapping_count": len(value.world_substrate_give.mappings),
        "checks": checks,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RoleDefinitionProbeReportV1(
        schema_version="role-definition-probe-report.v1",
        content_sha256=digest,
        **body,
    )


class RelationRoleDefinitionV1(_StrictModel):
    """One locally owned role for any namespaced relation schema.

    Unlike ``RoleDefinitionV1`` this is not restricted to ``lc:`` predicates.
    Downstream consumers may own relation schemas in their own namespace while
    optionally grounding a local role in a reusable Linguistic Core role
    concept.
    """

    role_definition_id: str = Field(
        pattern=r"^[a-z][a-z0-9_-]*\.roledef\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"
    )
    relation_schema_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_]*$")
    local_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    grounded_role_id: str | None = Field(default=None, pattern=r"^lc\.role\.")
    expected_filler_type: str | None = Field(default=None, min_length=1)
    min_count: int = Field(default=1, ge=0)
    max_count: int | None = Field(default=1, ge=1)
    presentation_ordinal: int = Field(ge=0)
    constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_cardinality(self) -> "RelationRoleDefinitionV1":
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("RELATION_ROLE_DEFINITION_CARDINALITY_INVALID")
        return self


class RelationSchemaV1(_StrictModel):
    """Application-independent role-typed relation schema grammar."""

    schema_version: Literal["relation-schema.v1"] = "relation-schema.v1"
    relation_schema_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_]*$")
    owner_namespace: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    review_status: Literal["candidate"] = "candidate"
    roles: tuple[RelationRoleDefinitionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_local_role_set(self) -> "RelationSchemaV1":
        namespace, relation_name = self.relation_schema_id.split(":", 1)
        if namespace != self.owner_namespace:
            raise ValueError("RELATION_SCHEMA_OWNER_NAMESPACE_MISMATCH")
        expected_prefix = f"{namespace}.roledef.{relation_name}."
        for role in self.roles:
            if role.relation_schema_id != self.relation_schema_id:
                raise ValueError("RELATION_ROLE_DEFINITION_SCHEMA_MISMATCH")
            if not role.role_definition_id.startswith(expected_prefix):
                raise ValueError("RELATION_ROLE_DEFINITION_NAMESPACE_MISMATCH")
        ids = [role.role_definition_id for role in self.roles]
        if len(ids) != len(set(ids)):
            raise ValueError("RELATION_ROLE_DEFINITION_ID_DUPLICATE")
        names = [role.local_name for role in self.roles]
        if len(names) != len(set(names)):
            raise ValueError("RELATION_ROLE_DEFINITION_LOCAL_NAME_DUPLICATE")
        ordinals = [role.presentation_ordinal for role in self.roles]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("RELATION_ROLE_DEFINITION_PRESENTATION_ORDINAL_DUPLICATE")
        return self

    def role_by_name(self, local_name: str) -> RelationRoleDefinitionV1 | None:
        return next((role for role in self.roles if role.local_name == local_name), None)


class ConsumerRelationSchemaProbeInputV1(_StrictModel):
    schema_version: Literal["consumer-relation-schema-probe-input.v1"]
    consumer_id: str = Field(min_length=1)
    source_contract_ref: str = Field(min_length=1)
    relation_schema: RelationSchemaV1


class ConsumerRelationSchemaProbeReportV1(_StrictModel):
    schema_version: Literal["consumer-relation-schema-probe-report.v1"]
    consumer_id: str
    relation_schema_id: str
    owner_namespace: str
    role_definition_count: int = Field(ge=0)
    grounded_role_count: int = Field(ge=0)
    ungrounded_role_count: int = Field(ge=0)
    repeatable_role_count: int = Field(ge=0)
    checks: tuple[str, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def load_consumer_relation_schema_probe(
    path: Path,
) -> ConsumerRelationSchemaProbeInputV1:
    try:
        return ConsumerRelationSchemaProbeInputV1.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ValueError(f"CONSUMER_RELATION_SCHEMA_PROBE_INVALID path={path}") from exc


def build_consumer_relation_schema_probe_report(
    value: ConsumerRelationSchemaProbeInputV1,
) -> ConsumerRelationSchemaProbeReportV1:
    schema = value.relation_schema
    grounded = sum(role.grounded_role_id is not None for role in schema.roles)
    repeatable = sum(role.max_count is None or role.max_count > 1 for role in schema.roles)
    checks = (
        "relation_schema_has_consumer_owned_namespace",
        "relation_roles_have_local_identity",
        "local_roles_may_optionally_ground_lc_role_concepts",
        "role_cardinality_is_explicit",
        "consumer_schema_does_not_become_lc_vocabulary",
    )
    body = {
        "consumer_id": value.consumer_id,
        "relation_schema_id": schema.relation_schema_id,
        "owner_namespace": schema.owner_namespace,
        "role_definition_count": len(schema.roles),
        "grounded_role_count": grounded,
        "ungrounded_role_count": len(schema.roles) - grounded,
        "repeatable_role_count": repeatable,
        "checks": checks,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ConsumerRelationSchemaProbeReportV1(
        schema_version="consumer-relation-schema-probe-report.v1",
        content_sha256=digest,
        **body,
    )
