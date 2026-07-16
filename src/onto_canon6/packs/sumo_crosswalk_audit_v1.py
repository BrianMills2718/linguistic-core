"""Reconcile donor SUMO candidates with one exact source-native projection.

The audit classifies mechanical identity and direct constraint support only.
Every donor mapping remains unreviewed, the donor database is opened immutable,
and this module exposes no mutation or promotion operation.
"""

from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from onto_canon6.packs.sumo_projection_v1 import (
    SumoFormulaRefV1,
    SumoProjectionV1,
)


ReviewState = Literal["candidate_unreviewed"]
IdentityStatus = Literal[
    "exact_current_source", "missing_current_source", "unmapped"
]
RoleIdentityStatus = Literal[
    "exact_case_role",
    "exact_non_case_relation",
    "missing_current_source",
    "unmapped",
]
ConstraintStatus = Literal[
    "direct_match",
    "compatible_donor_subtype",
    "incompatible_donor_supertype",
    "incomparable_types",
    "no_direct_constraint",
    "not_applicable",
]
StatusT = TypeVar("StatusT", bound=str)

_PREDICATE_COLUMNS = frozenset(
    {
        "name",
        "propbank_sense_id",
        "process_type",
        "frame_id",
        "source",
        "mapping_confidence",
        "mapping_source",
    }
)
_ROLE_COLUMNS = frozenset(
    {
        "event_sense_id",
        "named_label",
        "arg_position",
        "abstract_role",
        "type_constraint",
        "required",
        "source",
    }
)


class SumoCrosswalkAuditError(ValueError):
    """Raised when donor candidates cannot be audited without guessing."""


class SumoPredicateCandidateV1(BaseModel):
    """One donor predicate and its mechanical SUMO process-type disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    donor_predicate_id: str = Field(min_length=1, description="Exact donor predicate key.")
    canonical_predicate_id: str = Field(
        min_length=1, description="Mechanical lc:-prefixed candidate identifier."
    )
    propbank_sense_id: str | None = Field(
        default=None, description="Exact donor PropBank identifier when present."
    )
    frame_id: str | None = Field(
        default=None, description="Exact donor FrameNet candidate identifier when present."
    )
    process_type: str | None = Field(
        default=None, description="Donor SUMO process-type candidate when present."
    )
    donor_source: str = Field(min_length=1, description="Exact donor source label.")
    mapping_method_ref: str | None = Field(
        default=None, description="Uninterpreted donor row mapping-method tag."
    )
    mapping_method_scope: Literal["unknown"] | None = Field(
        default=None,
        description="Unknown semantic scope retained for any donor method tag.",
    )
    mapping_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Uncalibrated finite donor row confidence when present.",
    )
    process_type_status: IdentityStatus = Field(
        description="Mechanical current-source identity disposition."
    )
    process_type_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        default=(), description="Exact source formulas establishing a matched type."
    )
    review_state: ReviewState = Field(
        default="candidate_unreviewed",
        description="Non-promotable review state for this audit contract.",
    )

    @model_validator(mode="after")
    def _candidate_is_consistent(self) -> "SumoPredicateCandidateV1":
        if self.canonical_predicate_id != f"lc:{self.donor_predicate_id}":
            raise ValueError("canonical predicate ID must be the mechanical donor projection")
        if (self.mapping_method_ref is None) != (self.mapping_method_scope is None):
            raise ValueError("mapping method and unknown scope must appear together")
        if self.mapping_confidence is not None and not math.isfinite(
            self.mapping_confidence
        ):
            raise ValueError("mapping confidence must be finite")
        if self.process_type is None:
            if self.process_type_status != "unmapped":
                raise ValueError("absent process type must remain unmapped")
        elif self.process_type_status == "unmapped":
            raise ValueError("present process type cannot be marked unmapped")
        if self.process_type_status == "exact_current_source":
            if not self.process_type_source_refs:
                raise ValueError("exact process type requires source formula references")
        elif self.process_type_source_refs:
            raise ValueError("non-exact process type cannot carry source formula references")
        return self


class SumoRoleCandidateV1(BaseModel):
    """One donor role with separate identity and direct-constraint evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    donor_predicate_id: str = Field(min_length=1, description="Owning donor predicate key.")
    canonical_predicate_id: str = Field(
        min_length=1, description="Mechanical lc:-prefixed predicate candidate."
    )
    named_label: str = Field(min_length=1, description="Exact donor role label.")
    arg_position: str = Field(min_length=1, description="Exact donor positional role.")
    abstract_role: str | None = Field(
        default=None, description="Donor SUMO abstract-role candidate when present."
    )
    type_constraint: str | None = Field(
        default=None, description="Donor SUMO type-constraint candidate when present."
    )
    required: bool = Field(description="Exact donor required-role flag.")
    donor_source: str = Field(min_length=1, description="Exact donor source label.")
    role_status: RoleIdentityStatus = Field(
        description="CaseRole-aware current-source identity disposition."
    )
    type_status: IdentityStatus = Field(
        description="Mechanical current-source type identity disposition."
    )
    constraint_status: ConstraintStatus = Field(
        description="Direct canonical-module argument-2 constraint disposition."
    )
    observed_constraint_types: tuple[str, ...] = Field(
        default=(), description="Sorted direct canonical-module constraint types."
    )
    role_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        default=(), description="Exact formulas establishing a matched relation."
    )
    type_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        default=(), description="Exact formulas establishing a matched type."
    )
    constraint_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        default=(), description="Exact direct constraints considered by the audit."
    )
    review_state: ReviewState = Field(
        default="candidate_unreviewed",
        description="Non-promotable review state for this audit contract.",
    )

    @model_validator(mode="after")
    def _candidate_is_consistent(self) -> "SumoRoleCandidateV1":
        if self.canonical_predicate_id != f"lc:{self.donor_predicate_id}":
            raise ValueError("canonical predicate ID must be the mechanical donor projection")
        if self.abstract_role is None:
            if self.role_status != "unmapped":
                raise ValueError("absent abstract role must remain unmapped")
        elif self.role_status == "unmapped":
            raise ValueError("present abstract role cannot be marked unmapped")
        if self.role_status.startswith("exact_"):
            if not self.role_source_refs:
                raise ValueError("exact relation identity requires source references")
        elif self.role_source_refs:
            raise ValueError("non-exact relation cannot carry source references")
        if self.type_constraint is None:
            if self.type_status != "unmapped":
                raise ValueError("absent type constraint must remain unmapped")
        elif self.type_status == "unmapped":
            raise ValueError("present type constraint cannot be marked unmapped")
        if self.type_status == "exact_current_source":
            if not self.type_source_refs:
                raise ValueError("exact type identity requires source references")
        elif self.type_source_refs:
            raise ValueError("non-exact type cannot carry source references")
        if self.observed_constraint_types != tuple(
            sorted(set(self.observed_constraint_types))
        ):
            raise ValueError("observed constraint types must be sorted and unique")
        if self.constraint_status == "direct_match":
            if (
                self.type_constraint not in self.observed_constraint_types
                or not self.constraint_source_refs
            ):
                raise ValueError("direct match requires exact type and constraint evidence")
        elif self.constraint_status in {
            "compatible_donor_subtype",
            "incompatible_donor_supertype",
            "incomparable_types",
        }:
            if (
                not self.observed_constraint_types
                or self.type_constraint in self.observed_constraint_types
                or not self.constraint_source_refs
            ):
                raise ValueError("non-exact comparison requires distinct constraint evidence")
        elif self.constraint_status == "no_direct_constraint":
            if self.observed_constraint_types or self.constraint_source_refs:
                raise ValueError("absent direct constraint cannot carry constraint evidence")
        elif self.observed_constraint_types or self.constraint_source_refs:
            raise ValueError("not-applicable constraint cannot carry constraint evidence")
        if self.constraint_status != "not_applicable" and (
            self.role_status != "exact_case_role"
            or self.type_status != "exact_current_source"
        ):
            raise ValueError("constraint comparison requires exact CaseRole and type identities")
        return self


class SumoCrosswalkSummaryV1(BaseModel):
    """Reconciled counts for one complete donor-to-source audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_count: int = Field(ge=0, description="Audited donor predicates.")
    role_count: int = Field(ge=0, description="Audited donor roles.")
    process_type_status_counts: dict[IdentityStatus, int] = Field(
        description="Predicate process-type counts by status."
    )
    role_status_counts: dict[RoleIdentityStatus, int] = Field(
        description="Role identity counts by status."
    )
    type_status_counts: dict[IdentityStatus, int] = Field(
        description="Role type-constraint counts by status."
    )
    constraint_status_counts: dict[ConstraintStatus, int] = Field(
        description="Direct constraint counts by status."
    )

    @model_validator(mode="after")
    def _counts_reconcile(self) -> "SumoCrosswalkSummaryV1":
        for label, counts, expected in (
            ("process type", self.process_type_status_counts, self.predicate_count),
            ("role", self.role_status_counts, self.role_count),
            ("type", self.type_status_counts, self.role_count),
            ("constraint", self.constraint_status_counts, self.role_count),
        ):
            if any(value < 0 for value in counts.values()) or sum(counts.values()) != expected:
                raise ValueError(f"{label} summary counts do not reconcile")
        return self


def _normalized_sha256(value: object) -> str:
    """Hash Pydantic-compatible content using canonical JSON framing."""

    def default(item: object) -> object:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, tuple):
            return list(item)
        raise TypeError(f"cannot encode SUMO crosswalk content: {type(item).__name__}")

    payload = json.dumps(
        value, default=default, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SumoCrosswalkAuditV1(BaseModel):
    """Complete read-only donor SUMO reconciliation report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-crosswalk-audit-v1"] = Field(
        default="sumo-crosswalk-audit-v1", description="Audit contract discriminator."
    )
    donor_db_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete donor database."
    )
    sumo_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned SUMO commit.")
    sumo_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned SUMO tree.")
    sumo_payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Pinned SUMO selected-payload digest."
    )
    sumo_projection_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact source projection content digest."
    )
    constraint_module: str = Field(
        min_length=1, description="Exact selected module used for direct constraint comparison."
    )
    constraint_rule: Literal["case-role-argument-2-subclass-closure-v1"] = Field(
        default="case-role-argument-2-subclass-closure-v1",
        description=(
            "Structural comparison rule; it does not establish semantic equivalence."
        ),
    )
    review_authority: Literal["none_audit_only"] = Field(
        default="none_audit_only",
        description="Explicit denial of review or promotion authority.",
    )
    summary: SumoCrosswalkSummaryV1 = Field(description="Reconciled audit counts.")
    predicates: tuple[SumoPredicateCandidateV1, ...] = Field(
        description="All donor predicates sorted by donor identity."
    )
    roles: tuple[SumoRoleCandidateV1, ...] = Field(
        description="All donor roles sorted by predicate and role identity."
    )
    report_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized summary-and-row content digest."
    )

    @model_validator(mode="after")
    def _report_reconciles(self) -> "SumoCrosswalkAuditV1":
        predicate_keys = [item.donor_predicate_id for item in self.predicates]
        role_keys = [(item.donor_predicate_id, item.named_label) for item in self.roles]
        if predicate_keys != sorted(set(predicate_keys)):
            raise ValueError("predicate rows must be sorted and unique")
        if role_keys != sorted(set(role_keys)):
            raise ValueError("role rows must be sorted and unique")
        predicate_set = set(predicate_keys)
        if any(item.donor_predicate_id not in predicate_set for item in self.roles):
            raise ValueError("role row has a dangling donor predicate")
        expected_summary = _summary(self.predicates, self.roles)
        if self.summary != expected_summary:
            raise ValueError("summary does not reconcile with candidate rows")
        content = {
            "summary": self.summary,
            "predicates": self.predicates,
            "roles": self.roles,
        }
        if self.report_content_sha256 != _normalized_sha256(content):
            raise ValueError("report content SHA-256 does not reconcile")
        return self


def _status_counts(values: list[StatusT]) -> dict[StatusT, int]:
    """Return a deterministic complete-enough status count mapping."""

    return dict(sorted(Counter(values).items()))


def _summary(
    predicates: tuple[SumoPredicateCandidateV1, ...],
    roles: tuple[SumoRoleCandidateV1, ...],
) -> SumoCrosswalkSummaryV1:
    """Derive the sole valid summary from complete candidate rows."""

    return SumoCrosswalkSummaryV1(
        predicate_count=len(predicates),
        role_count=len(roles),
        process_type_status_counts=_status_counts(
            [item.process_type_status for item in predicates]
        ),
        role_status_counts=_status_counts([item.role_status for item in roles]),
        type_status_counts=_status_counts([item.type_status for item in roles]),
        constraint_status_counts=_status_counts(
            [item.constraint_status for item in roles]
        ),
    )


def _database_sha256(path: Path) -> str:
    """Hash a complete donor database without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Read one SQLite table's declared column names."""

    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _required_text(value: object, *, field: str) -> str:
    """Return one nonempty donor text value or fail with its exact field."""

    if not isinstance(value, str) or not value:
        raise SumoCrosswalkAuditError(f"invalid donor field {field}")
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    """Return one optional nonempty donor text value."""

    if value is None:
        return None
    return _required_text(value, field=field)


def _source_refs_by_term(
    projection: SumoProjectionV1, *, preferred_module: str
) -> tuple[
    dict[str, tuple[SumoFormulaRefV1, ...]],
    dict[str, tuple[SumoFormulaRefV1, ...]],
]:
    """Index exact projected type and relation evidence by source-native ID."""

    def preferred(
        refs: tuple[SumoFormulaRefV1, ...], *, module: str
    ) -> tuple[SumoFormulaRefV1, ...]:
        """Retain one deterministic declaration witness instead of every use."""

        ordered = sorted(
            refs,
            key=lambda ref: (
                ref.module_path != module,
                ref.module_path,
                ref.formula_index,
            ),
        )
        return (ordered[0],) if ordered else ()

    type_declarations: dict[str, list[SumoFormulaRefV1]] = {}
    relation_declarations: dict[str, list[SumoFormulaRefV1]] = {}
    relation_terms = {relation.term for relation in projection.relations}
    for item in projection.instance_axioms:
        if item.class_term == "Class":
            type_declarations.setdefault(item.instance, []).append(item.source_ref)
        if item.instance in relation_terms:
            relation_declarations.setdefault(item.instance, []).append(item.source_ref)
    type_refs = {
        item.term: preferred(
            tuple(type_declarations.get(item.term, ())) or item.source_refs,
            module=preferred_module,
        )
        for item in projection.types
    }
    relation_refs = {
        item.term: preferred(
            tuple(relation_declarations.get(item.term, ())) or item.source_refs,
            module=preferred_module,
        )
        for item in projection.relations
    }
    return type_refs, relation_refs


def audit_sumo_crosswalk_v1(
    donor_database: Path,
    *,
    projection: SumoProjectionV1,
    constraint_module: str = "Merge.kif",
) -> SumoCrosswalkAuditV1:
    """Classify every donor SUMO candidate without review or mutation authority."""

    database = donor_database.resolve()
    if not database.is_file():
        raise SumoCrosswalkAuditError(f"donor database is missing: {donor_database}")
    module_paths = {item.path for item in projection.modules}
    if constraint_module not in module_paths:
        raise SumoCrosswalkAuditError(
            f"constraint module is absent from exact SUMO projection: {constraint_module}"
        )
    before_sha256 = _database_sha256(database)
    uri = f"{database.as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        predicate_columns = _table_columns(connection, "predicates")
        role_columns = _table_columns(connection, "role_slots")
        if not _PREDICATE_COLUMNS <= predicate_columns or not _ROLE_COLUMNS <= role_columns:
            raise SumoCrosswalkAuditError(
                "donor schema lacks required predicates or role_slots columns"
            )
        predicate_rows = connection.execute(
            "SELECT name, propbank_sense_id, process_type, frame_id, source, "
            "mapping_confidence, mapping_source FROM predicates ORDER BY name"
        ).fetchall()
        role_rows = connection.execute(
            "SELECT event_sense_id, named_label, arg_position, abstract_role, "
            "type_constraint, required, source FROM role_slots "
            "ORDER BY event_sense_id, named_label"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise SumoCrosswalkAuditError("unable to read immutable donor database") from exc
    finally:
        connection.close()
    after_sha256 = _database_sha256(database)
    if after_sha256 != before_sha256:
        raise SumoCrosswalkAuditError("donor database bytes changed during audit")

    type_refs, relation_refs = _source_refs_by_term(
        projection, preferred_module=constraint_module
    )
    parents: dict[str, set[str]] = {}
    for item in projection.subclass_axioms:
        parents.setdefault(item.child, set()).add(item.parent)

    def descends_from(term: str, ancestor: str) -> bool:
        """Return whether the selected direct subclass closure reaches an ancestor."""

        pending = [term]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == ancestor:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(parents.get(current, set()) - visited)
        return False

    case_roles = {
        item.instance
        for item in projection.instance_axioms
        if item.class_term == "CaseRole"
    }
    constraints_by_relation: dict[
        str, tuple[tuple[str, SumoFormulaRefV1], ...]
    ] = {}
    for relation in relation_refs:
        constraints_by_relation[relation] = tuple(
            sorted(
                (
                    (item.argument_type, item.source_ref)
                    for item in projection.argument_constraints
                    if item.relation == relation
                    and item.kind == "domain"
                    and item.argument_position == 2
                    and item.source_ref.module_path == constraint_module
                ),
                key=lambda value: (
                    value[0],
                    value[1].module_path,
                    value[1].formula_index,
                ),
            )
        )

    predicates: list[SumoPredicateCandidateV1] = []
    predicate_ids: set[str] = set()
    for row in predicate_rows:
        predicate_id = _required_text(row["name"], field="predicates.name")
        if predicate_id in predicate_ids:
            raise SumoCrosswalkAuditError("duplicate donor predicate identity")
        predicate_ids.add(predicate_id)
        process_type = _optional_text(
            row["process_type"], field="predicates.process_type"
        )
        process_refs = type_refs.get(process_type or "", ())
        process_status: IdentityStatus = (
            "unmapped"
            if process_type is None
            else (
                "exact_current_source"
                if process_refs
                else "missing_current_source"
            )
        )
        method = _optional_text(
            row["mapping_source"], field="predicates.mapping_source"
        )
        confidence_value = row["mapping_confidence"]
        confidence: float | None
        if confidence_value is None:
            confidence = None
        elif isinstance(confidence_value, (int, float)):
            confidence = float(confidence_value)
        else:
            raise SumoCrosswalkAuditError(
                "invalid donor field predicates.mapping_confidence"
            )
        predicates.append(
            SumoPredicateCandidateV1(
                donor_predicate_id=predicate_id,
                canonical_predicate_id=f"lc:{predicate_id}",
                propbank_sense_id=_optional_text(
                    row["propbank_sense_id"], field="predicates.propbank_sense_id"
                ),
                frame_id=_optional_text(row["frame_id"], field="predicates.frame_id"),
                process_type=process_type,
                donor_source=_required_text(row["source"], field="predicates.source"),
                mapping_method_ref=method,
                mapping_method_scope="unknown" if method is not None else None,
                mapping_confidence=confidence,
                process_type_status=process_status,
                process_type_source_refs=process_refs,
            )
        )

    roles: list[SumoRoleCandidateV1] = []
    role_keys: set[tuple[str, str]] = set()
    for row in role_rows:
        predicate_id = _required_text(
            row["event_sense_id"], field="role_slots.event_sense_id"
        )
        label = _required_text(row["named_label"], field="role_slots.named_label")
        key = predicate_id, label
        if key in role_keys:
            raise SumoCrosswalkAuditError("duplicate donor role identity")
        role_keys.add(key)
        if predicate_id not in predicate_ids:
            raise SumoCrosswalkAuditError("donor role references an unknown predicate")
        abstract_role = _optional_text(
            row["abstract_role"], field="role_slots.abstract_role"
        )
        type_constraint = _optional_text(
            row["type_constraint"], field="role_slots.type_constraint"
        )
        role_refs = relation_refs.get(abstract_role or "", ())
        type_source_refs = type_refs.get(type_constraint or "", ())
        role_status: RoleIdentityStatus
        if abstract_role is None:
            role_status = "unmapped"
        elif not role_refs:
            role_status = "missing_current_source"
        elif abstract_role in case_roles:
            role_status = "exact_case_role"
        else:
            role_status = "exact_non_case_relation"
        type_status: IdentityStatus = (
            "unmapped"
            if type_constraint is None
            else (
                "exact_current_source"
                if type_source_refs
                else "missing_current_source"
            )
        )
        relevant_constraints = constraints_by_relation.get(abstract_role or "", ())
        observed_types = tuple(sorted({item[0] for item in relevant_constraints}))
        constraint_refs = tuple(item[1] for item in relevant_constraints)
        if role_status != "exact_case_role" or type_status != "exact_current_source":
            constraint_status: ConstraintStatus = "not_applicable"
            observed_types = ()
            constraint_refs = ()
        elif not relevant_constraints:
            constraint_status = "no_direct_constraint"
        elif observed_types == (type_constraint,):
            constraint_status = "direct_match"
        elif all(descends_from(type_constraint or "", item) for item in observed_types):
            constraint_status = "compatible_donor_subtype"
        elif all(descends_from(item, type_constraint or "") for item in observed_types):
            constraint_status = "incompatible_donor_supertype"
        else:
            constraint_status = "incomparable_types"
        required_value = row["required"]
        if required_value not in (0, 1, False, True):
            raise SumoCrosswalkAuditError("invalid donor field role_slots.required")
        roles.append(
            SumoRoleCandidateV1(
                donor_predicate_id=predicate_id,
                canonical_predicate_id=f"lc:{predicate_id}",
                named_label=label,
                arg_position=_required_text(
                    row["arg_position"], field="role_slots.arg_position"
                ),
                abstract_role=abstract_role,
                type_constraint=type_constraint,
                required=bool(required_value),
                donor_source=_required_text(row["source"], field="role_slots.source"),
                role_status=role_status,
                type_status=type_status,
                constraint_status=constraint_status,
                observed_constraint_types=observed_types,
                role_source_refs=role_refs,
                type_source_refs=type_source_refs,
                constraint_source_refs=constraint_refs,
            )
        )

    predicate_values = tuple(predicates)
    role_values = tuple(roles)
    summary = _summary(predicate_values, role_values)
    content = {
        "summary": summary,
        "predicates": predicate_values,
        "roles": role_values,
    }
    return SumoCrosswalkAuditV1(
        donor_db_sha256=before_sha256,
        sumo_commit_sha=projection.source_commit_sha,
        sumo_tree_sha=projection.source_tree_sha,
        sumo_payload_sha256=projection.selected_payload_sha256,
        sumo_projection_content_sha256=projection.projection_content_sha256,
        constraint_module=constraint_module,
        summary=summary,
        predicates=predicate_values,
        roles=role_values,
        report_content_sha256=_normalized_sha256(content),
    )


def load_sumo_crosswalk_audit_v1(path: Path) -> SumoCrosswalkAuditV1:
    """Load and fully reconcile one strict JSON or gzip-JSON audit report."""

    try:
        payload = path.read_bytes()
        if path.name.endswith(".gz"):
            payload = gzip.decompress(payload)
        return SumoCrosswalkAuditV1.model_validate_json(payload)
    except (OSError, gzip.BadGzipFile, ValidationError) as exc:
        raise SumoCrosswalkAuditError(f"invalid SUMO crosswalk audit: {path}") from exc
