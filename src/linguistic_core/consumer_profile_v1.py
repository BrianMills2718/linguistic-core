"""Versioned consumer-profile contracts over the Linguistic Core relation grammar.

Profiles are owned by downstream namespaces.  This module validates their exact
grammar dependency, retained relation-assertion bundle, and declared lossy views
without turning consumer vocabulary into Linguistic Core vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from linguistic_core.relation_assertion_v1 import (
    RelationAssertionBundleV1,
    load_relation_assertion_bundle,
    validate_relation_assertion_bundle,
)
from linguistic_core.role_definition_v1 import RelationSchemaV1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GrammarDependencyV1(_StrictModel):
    relation_schema_version: Literal["relation-schema.v1"]
    relation_assertion_bundle_version: Literal["relation-assertion-bundle.v1"]
    requires_objectification: bool = True

class ProjectionRuleV1(_StrictModel):
    projection_id: str = Field(min_length=1)
    source_relation_schema_id: str = Field(min_length=1)
    target_view: Literal["binary_edge", "table_row"]
    selected_role_definition_ids: tuple[str, ...] = Field(min_length=1)
    endpoint_role_definition_ids: tuple[str, ...] = ()
    omitted_role_definition_ids: tuple[str, ...] = ()
    loss_classification: Literal["lossless", "lossy"]
    loss_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_local_shape(self) -> "ProjectionRuleV1":
        selected = self.selected_role_definition_ids
        omitted = self.omitted_role_definition_ids
        endpoints = self.endpoint_role_definition_ids
        if len(selected) != len(set(selected)) or len(omitted) != len(set(omitted)):
            raise ValueError("PROFILE_PROJECTION_ROLE_DUPLICATE")
        if set(selected) & set(omitted):
            raise ValueError("PROFILE_PROJECTION_ROLE_OVERLAP")
        if self.target_view == "binary_edge":
            if len(endpoints) != 2 or len(set(endpoints)) != 2:
                raise ValueError("PROFILE_BINARY_PROJECTION_REQUIRES_TWO_ENDPOINTS")
            if not set(endpoints).issubset(set(selected)):
                raise ValueError("PROFILE_BINARY_ENDPOINT_NOT_SELECTED")
        elif endpoints:
            raise ValueError("PROFILE_TABLE_PROJECTION_HAS_ENDPOINTS")
        if self.loss_classification == "lossless" and omitted:
            raise ValueError("PROFILE_LOSSLESS_PROJECTION_OMITS_ROLES")
        return self

class ConsumerProfileContractV1(_StrictModel):
    schema_version: Literal["consumer-profile-contract.v1"]
    profile_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_]*$")
    profile_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    owner_namespace: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    status: Literal["candidate"] = "candidate"
    source_bundle: str = Field(min_length=1)
    source_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    grammar_dependency: GrammarDependencyV1
    relation_schema_ids: tuple[str, ...] = Field(min_length=1)
    top_assertion_id: str = Field(min_length=1)
    projections: tuple[ProjectionRuleV1, ...] = ()

    @model_validator(mode="after")
    def validate_identity(self) -> "ConsumerProfileContractV1":
        namespace = self.profile_id.split(":", 1)[0]
        if namespace != self.owner_namespace:
            raise ValueError("CONSUMER_PROFILE_OWNER_NAMESPACE_MISMATCH")
        if len(self.relation_schema_ids) != len(set(self.relation_schema_ids)):
            raise ValueError("CONSUMER_PROFILE_SCHEMA_ID_DUPLICATE")
        projection_ids = [item.projection_id for item in self.projections]
        if len(projection_ids) != len(set(projection_ids)):
            raise ValueError("CONSUMER_PROFILE_PROJECTION_ID_DUPLICATE")
        return self


class ConsumerProfileValidationReportV1(_StrictModel):
    schema_version: Literal["consumer-profile-validation-report.v1"]
    profile_id: str
    profile_version: str
    source_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relation_schema_count: int = Field(ge=0)
    assertion_count: int = Field(ge=0)
    projection_count: int = Field(ge=0)
    lossy_projection_count: int = Field(ge=0)
    checks: tuple[str, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

def load_consumer_profile_contract(path: Path) -> ConsumerProfileContractV1:
    try:
        return ConsumerProfileContractV1.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ValueError(f"CONSUMER_PROFILE_INVALID path={path}") from exc


def _validate_projection(rule: ProjectionRuleV1, schema: RelationSchemaV1) -> None:
    role_ids = {item.role_definition_id for item in schema.roles}
    selected = set(rule.selected_role_definition_ids)
    omitted = set(rule.omitted_role_definition_ids)
    if rule.source_relation_schema_id != schema.relation_schema_id:
        raise ValueError("PROFILE_PROJECTION_SCHEMA_MISMATCH")
    if selected | omitted != role_ids:
        missing = sorted(role_ids - (selected | omitted))
        extra = sorted((selected | omitted) - role_ids)
        raise ValueError(
            f"PROFILE_PROJECTION_ROLE_COVERAGE_MISMATCH missing={missing} extra={extra}"
        )
    if rule.target_view == "binary_edge" and len(schema.roles) > 2:
        if rule.loss_classification != "lossy":
            raise ValueError("PROFILE_NARY_BINARY_PROJECTION_MUST_BE_LOSSY")
    if rule.loss_classification == "lossy" and not rule.loss_note.strip():
        raise ValueError("PROFILE_LOSSY_PROJECTION_REQUIRES_NOTE")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_consumer_profile_contract(
    manifest_path: Path,
) -> ConsumerProfileValidationReportV1:
    contract = load_consumer_profile_contract(manifest_path)
    base = manifest_path.parent.resolve()
    bundle_path = (base / contract.source_bundle).resolve()
    if not bundle_path.is_relative_to(base):
        raise ValueError("CONSUMER_PROFILE_BUNDLE_ESCAPES_MANIFEST_DIRECTORY")
    observed_sha = _sha256(bundle_path)
    if observed_sha != contract.source_bundle_sha256:
        raise ValueError(
            "CONSUMER_PROFILE_BUNDLE_DIGEST_MISMATCH "
            f"expected={contract.source_bundle_sha256} observed={observed_sha}"
        )

    bundle: RelationAssertionBundleV1 = load_relation_assertion_bundle(bundle_path)
    assertion_report = validate_relation_assertion_bundle(bundle)
    schema_index = {item.relation_schema_id: item for item in bundle.schemas}
    if tuple(sorted(contract.relation_schema_ids)) != tuple(sorted(schema_index)):
        raise ValueError("CONSUMER_PROFILE_SCHEMA_SET_MISMATCH")
    if any(item.owner_namespace != contract.owner_namespace for item in bundle.schemas):
        raise ValueError("CONSUMER_PROFILE_CONTAINS_FOREIGN_SCHEMA")
    if contract.top_assertion_id != bundle.top_assertion_id:
        raise ValueError("CONSUMER_PROFILE_TOP_ASSERTION_MISMATCH")

    for projection in contract.projections:
        schema = schema_index.get(projection.source_relation_schema_id)
        if schema is None:
            raise ValueError(
                "PROFILE_PROJECTION_SOURCE_SCHEMA_MISSING "
                f"schema={projection.source_relation_schema_id}"
            )
        _validate_projection(projection, schema)

    checks = (
        "consumer_profile_owns_namespace",
        "grammar_dependency_is_explicit",
        "source_bundle_digest_is_pinned",
        "relation_schema_set_is_exact",
        "top_assertion_is_pinned",
        "projection_role_loss_is_explicit",
    )
    body = {
        "profile_id": contract.profile_id,
        "profile_version": contract.profile_version,
        "source_bundle_sha256": observed_sha,
        "relation_schema_count": assertion_report.schema_count,
        "assertion_count": assertion_report.assertion_count,
        "projection_count": len(contract.projections),
        "lossy_projection_count": sum(
            item.loss_classification == "lossy" for item in contract.projections
        ),
        "checks": checks,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ConsumerProfileValidationReportV1(
        schema_version="consumer-profile-validation-report.v1",
        content_sha256=digest,
        **body,
    )