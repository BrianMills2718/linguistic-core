"""Executable semantic-construction contract over one exact pack closure.

This module does not mutate or infer additions to published packs.  It loads a
declared pack lineage, validates semantic operations against that lineage, and
fails closed when direction, conditions, roles, scope, or identity disagree.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.contracts import PackRef


class SemanticConstructionError(RuntimeError):
    """Raised when a requested semantic operation is not licensed."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ClosureMemberV1(_StrictModel):
    pack_ref: PackRef
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    declared_assets: tuple[str, ...]


class ExactPackClosureV1(_StrictModel):
    target: PackRef
    members: tuple[ClosureMemberV1, ...]
    predicate_ids: frozenset[str]
    role_ids: frozenset[str]
    predicate_roles: frozenset[tuple[str, str]]
    predicate_relations: tuple[dict[str, object], ...]
    role_correspondences: tuple[dict[str, object], ...]

    def relation(self, source: str, target: str) -> dict[str, object] | None:
        for row in self.predicate_relations:
            if (
                row.get("from_predicate_id") == source
                and row.get("to_predicate_id") == target
            ):
                return row
        return None

    def role_correspondence(
        self,
        source_predicate: str,
        source_role: str,
        target_predicate: str,
        target_role: str,
    ) -> dict[str, object] | None:
        for row in self.role_correspondences:
            if (
                row.get("from_predicate_id") == source_predicate
                and row.get("from_role_id") == source_role
                and row.get("to_predicate_id") == target_predicate
                and row.get("to_role_id") == target_role
            ):
                return row
        return None


class IdentityV1(_StrictModel):
    predicate_id: str = Field(pattern=r"^lc:")
    proposition_id: str = Field(min_length=1)
    occurrence_id: str = Field(min_length=1)
    assertion_id: str = Field(min_length=1)
    support_record_id: str = Field(min_length=1)


class ScopeV1(_StrictModel):
    polarity: Literal["positive", "negative"]
    modality: Literal["asserted", "intended", "possible", "required"]
    aspect: Literal["completed", "ongoing", "prospective", "unspecified"]
    temporal_scope: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    quantification: str = Field(min_length=1)


class SemanticObjectV1(_StrictModel):
    identity: IdentityV1
    roles: dict[str, str]
    scope: ScopeV1


class RoleTransformV1(_StrictModel):
    source_role_id: str = Field(pattern=r"^lc\.role\.")
    target_role_id: str = Field(pattern=r"^lc\.role\.")


class LossContractV1(_StrictModel):
    classification: Literal["lossless", "lossy", "unsupported"]
    lost_distinctions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _loss_is_explained(self) -> LossContractV1:
        if self.classification == "lossless" and self.lost_distinctions:
            raise ValueError("lossless operations cannot declare lost distinctions")
        if self.classification == "lossy" and not self.lost_distinctions:
            raise ValueError("lossy operations must name at least one lost distinction")
        return self


class MappingRequestV1(_StrictModel):
    identity_level: Literal[
        "predicate", "proposition", "occurrence", "assertion", "support"
    ]
    direction: Literal["source_to_target"]
    conditions: tuple[str, ...] = ()
    role_transforms: tuple[RoleTransformV1, ...]
    loss: LossContractV1


class ConstructionCaseV1(_StrictModel):
    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: SemanticObjectV1
    target: SemanticObjectV1
    request: MappingRequestV1
    expected_status: Literal["allowed", "rejected"]
    expected_reason: str = Field(min_length=1)


class CaseResultV1(_StrictModel):
    case_id: str
    case: ConstructionCaseV1
    passed: bool
    observed_status: Literal["allowed", "rejected"]
    reason: str
    relation: str | None
    loss: LossContractV1


class ConstructionReportV1(_StrictModel):
    schema_version: Literal["semantic-construction-report.v1"]
    pack_closure: tuple[ClosureMemberV1, ...]
    cases: tuple[CaseResultV1, ...]
    passed: int
    failed: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticConstructionError(f"INVALID_DECLARED_ASSET path={path}") from exc


def load_exact_pack_closure(packs_root: Path, target: PackRef) -> ExactPackClosureV1:
    """Load only ``target`` and ancestors explicitly named by ``extends``."""

    if (
        re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", target.pack_version)
        is None
    ):
        raise SemanticConstructionError(
            f"EXACT_SEMANTIC_VERSION_REQUIRED version={target.pack_version}"
        )
    seen: set[tuple[str, str]] = set()
    members_reverse: list[tuple[ClosureMemberV1, Path, dict[str, object]]] = []
    current = target
    while True:
        identity = (current.pack_id, current.pack_version)
        if identity in seen:
            raise SemanticConstructionError(
                f"PACK_CLOSURE_CYCLE pack={current.pack_id}@{current.pack_version}"
            )
        seen.add(identity)
        pack_dir = packs_root / current.pack_id / current.pack_version
        manifest_path = pack_dir / "manifest.yaml"
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise SemanticConstructionError(
                f"PACK_MANIFEST_UNAVAILABLE pack={current.pack_id}@{current.pack_version}"
            ) from exc
        pack = manifest.get("pack") if isinstance(manifest, dict) else None
        content = manifest.get("content") if isinstance(manifest, dict) else None
        if not isinstance(pack, dict) or not isinstance(content, dict):
            raise SemanticConstructionError("INVALID_PACK_MANIFEST")
        if (
            pack.get("id") != current.pack_id
            or pack.get("version") != current.pack_version
        ):
            raise SemanticConstructionError("PACK_IDENTITY_MISMATCH")
        assets = tuple(
            sorted(value for value in content.values() if isinstance(value, str))
        )
        for asset in assets:
            if not (pack_dir / asset).is_file():
                raise SemanticConstructionError(
                    f"DECLARED_ASSET_MISSING pack={current.pack_id}@{current.pack_version} asset={asset}"
                )
        member = ClosureMemberV1(
            pack_ref=current,
            manifest_sha256=_sha256(manifest_path),
            declared_assets=assets,
        )
        members_reverse.append((member, pack_dir, content))
        ancestors = manifest.get("extends", [])
        if not ancestors:
            break
        if (
            not isinstance(ancestors, list)
            or len(ancestors) != 1
            or not isinstance(ancestors[0], dict)
        ):
            raise SemanticConstructionError(
                "PACK_CLOSURE_REQUIRES_SINGLE_DECLARED_ANCESTOR"
            )
        ancestor = ancestors[0]
        try:
            current = PackRef(pack_id=ancestor["id"], pack_version=ancestor["version"])
        except (KeyError, ValueError) as exc:
            raise SemanticConstructionError("INVALID_PACK_ANCESTOR") from exc

    predicate_ids: set[str] = set()
    role_ids: set[str] = set()
    predicate_roles: set[tuple[str, str]] = set()
    predicate_relations: list[dict[str, object]] = []
    role_correspondences: list[dict[str, object]] = []
    ordered = list(reversed(members_reverse))
    for _member, pack_dir, content in ordered:
        if "predicate_types" in content:
            predicate_ids.update(
                str(row["predicate_id"])
                for row in _read_jsonl(pack_dir / str(content["predicate_types"]))
            )
        if "role_types" in content:
            role_ids.update(
                str(row["role_id"])
                for row in _read_jsonl(pack_dir / str(content["role_types"]))
            )
        if "predicate_role_edges" in content:
            predicate_roles.update(
                (str(row["predicate_id"]), str(row["role_id"]))
                for row in _read_jsonl(pack_dir / str(content["predicate_role_edges"]))
            )
        if "predicate_relations" in content:
            predicate_relations.extend(
                _read_jsonl(pack_dir / str(content["predicate_relations"]))
            )
        if "role_correspondences" in content:
            role_correspondences.extend(
                _read_jsonl(pack_dir / str(content["role_correspondences"]))
            )

    for row in predicate_relations:
        endpoints = (str(row.get("from_predicate_id")), str(row.get("to_predicate_id")))
        if any(predicate_id not in predicate_ids for predicate_id in endpoints):
            raise SemanticConstructionError(
                f"RELATION_REFERENCES_UNKNOWN_PREDICATE endpoints={endpoints}"
            )
    for row in role_correspondences:
        source_edge = (str(row.get("from_predicate_id")), str(row.get("from_role_id")))
        target_edge = (str(row.get("to_predicate_id")), str(row.get("to_role_id")))
        if source_edge not in predicate_roles or target_edge not in predicate_roles:
            raise SemanticConstructionError(
                f"CORRESPONDENCE_REFERENCES_UNDECLARED_ROLE source={source_edge} target={target_edge}"
            )

    return ExactPackClosureV1(
        target=target,
        members=tuple(item[0] for item in ordered),
        predicate_ids=frozenset(predicate_ids),
        role_ids=frozenset(role_ids),
        predicate_roles=frozenset(predicate_roles),
        predicate_relations=tuple(predicate_relations),
        role_correspondences=tuple(role_correspondences),
    )


def _reject(code: str) -> None:
    raise SemanticConstructionError(code)


def apply_mapping(
    case: ConstructionCaseV1, closure: ExactPackClosureV1
) -> tuple[str, str | None]:
    source = case.source
    target = case.target
    request = case.request
    for obj in (source, target):
        if obj.identity.predicate_id not in closure.predicate_ids:
            _reject(f"UNKNOWN_PREDICATE predicate={obj.identity.predicate_id}")
        for role in obj.roles:
            if (
                role not in closure.role_ids
                or (obj.identity.predicate_id, role) not in closure.predicate_roles
            ):
                _reject(
                    f"UNDECLARED_PREDICATE_ROLE predicate={obj.identity.predicate_id} role={role}"
                )

    same_predicate = source.identity.predicate_id == target.identity.predicate_id
    relation_row = (
        None
        if same_predicate
        else closure.relation(
            source.identity.predicate_id, target.identity.predicate_id
        )
    )
    reverse_row = (
        None
        if same_predicate
        else closure.relation(
            target.identity.predicate_id, source.identity.predicate_id
        )
    )
    relation = (
        "identity"
        if same_predicate
        else (str(relation_row["relation"]) if relation_row is not None else None)
    )
    if relation_row is None and not same_predicate:
        if reverse_row is not None:
            _reject(
                "MAPPING_DIRECTION_UNSUPPORTED "
                f"declared={target.identity.predicate_id}->{source.identity.predicate_id}"
            )
        _reject("PREDICATE_MAPPING_UNSUPPORTED")
    if relation == "narrowerThan":
        if request.loss.classification != "lossy":
            _reject("NARROWER_PROJECTION_REQUIRES_LOSSY_CONTRACT")
        if "commercial_transaction" not in request.conditions:
            _reject("MAPPING_CONDITION_MISSING commercial_transaction")
    elif relation == "closeMatch":
        if "contextual_equivalence_reviewed" not in request.conditions:
            _reject("CLOSE_MATCH_REQUIRES_CONTEXTUAL_REVIEW")
    elif relation == "identity":
        if request.loss.classification != "lossless":
            _reject("IDENTITY_MAPPING_MUST_BE_LOSSLESS")
    else:
        _reject(f"RELATION_NOT_EXECUTABLE relation={relation}")

    transforms = {
        item.source_role_id: item.target_role_id for item in request.role_transforms
    }
    if len(transforms) != len(request.role_transforms):
        _reject("DUPLICATE_SOURCE_ROLE_TRANSFORM")
    if set(transforms) != set(source.roles):
        _reject("ROLE_TRANSFORM_SOURCE_COVERAGE_MISMATCH")
    if set(transforms.values()) != set(target.roles):
        _reject("ROLE_TRANSFORM_TARGET_COVERAGE_MISMATCH")
    for source_role, target_role in transforms.items():
        if not same_predicate:
            correspondence = closure.role_correspondence(
                source.identity.predicate_id,
                source_role,
                target.identity.predicate_id,
                target_role,
            )
            if correspondence is None or correspondence.get("via_relation") != relation:
                _reject(
                    f"ROLE_TRANSFORM_UNSUPPORTED source_role={source_role} target_role={target_role}"
                )
        if source.roles[source_role] != target.roles[target_role]:
            _reject(
                f"ROLE_FILLER_MISMATCH source_role={source_role} target_role={target_role}"
            )

    if source.scope != target.scope and not (
        request.identity_level == "proposition"
        and "compare_embedded_proposition" in request.conditions
    ):
        _reject("SCOPE_MISMATCH")
    identity_fields = {
        "proposition": ("proposition_id",),
        "occurrence": ("proposition_id", "occurrence_id"),
        "assertion": ("proposition_id", "occurrence_id", "assertion_id"),
        "support": (
            "proposition_id",
            "occurrence_id",
            "assertion_id",
            "support_record_id",
        ),
    }
    for field in identity_fields.get(request.identity_level, ()):
        if getattr(source.identity, field) != getattr(target.identity, field):
            _reject(f"IDENTITY_MISMATCH level={field.removesuffix('_id')}")
    return "allowed", relation


def evaluate_cases(
    cases: Iterable[ConstructionCaseV1], closure: ExactPackClosureV1
) -> ConstructionReportV1:
    results: list[CaseResultV1] = []
    for case in cases:
        try:
            _status, relation = apply_mapping(case, closure)
            observed: Literal["allowed", "rejected"] = "allowed"
            reason = "ALLOWED"
        except SemanticConstructionError as exc:
            observed = "rejected"
            reason = str(exc)
            relation = None
        passed = observed == case.expected_status and (
            case.expected_reason == reason or reason.startswith(case.expected_reason)
        )
        results.append(
            CaseResultV1(
                case_id=case.case_id,
                case=case,
                passed=passed,
                observed_status=observed,
                reason=reason,
                relation=relation,
                loss=case.request.loss,
            )
        )
    passed_count = sum(result.passed for result in results)
    return ConstructionReportV1(
        schema_version="semantic-construction-report.v1",
        pack_closure=closure.members,
        cases=tuple(results),
        passed=passed_count,
        failed=len(results) - passed_count,
    )


def load_cases(path: Path) -> tuple[ConstructionCaseV1, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return tuple(
            ConstructionCaseV1.model_validate_json(json.dumps(item))
            for item in payload["cases"]
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise SemanticConstructionError(
            f"INVALID_CONSTRUCTION_CASES path={path}"
        ) from exc


def render_report_markdown(report: ConstructionReportV1) -> str:
    lines = [
        "# Acquisition semantic construction report v1",
        "",
        "This report was executed against one exact declared pack closure; it is not an extractor benchmark.",
        "",
        "## Exact closure",
        "",
    ]
    for member in report.pack_closure:
        lines.append(
            f"- `{member.pack_ref.pack_id}@{member.pack_ref.pack_version}` — manifest `{member.manifest_sha256}`"
        )
    lines.extend(["", "## Machine assertions", ""])
    for result in report.cases:
        verdict = "PASS" if result.passed else "FAIL"
        case = result.case
        transforms = ", ".join(
            f"{item.source_role_id} → {item.target_role_id}"
            for item in case.request.role_transforms
        )
        lines.extend(
            [
                f"### `{result.case_id}` — {case.description}",
                "",
                f"- Result: **{verdict}**; expected `{case.expected_status}`, observed `{result.observed_status}` (`{result.reason}`).",
                f"- Predicates: `{case.source.identity.predicate_id}` → `{case.target.identity.predicate_id}`.",
                f"- Identity comparison: `{case.request.identity_level}`; source `{case.source.identity.model_dump_json()}`; target `{case.target.identity.model_dump_json()}`.",
                f"- Scope: source `{case.source.scope.model_dump_json()}`; target `{case.target.scope.model_dump_json()}`.",
                f"- Mapping: direction `{case.request.direction}`, relation `{result.relation or 'none'}`, conditions `{list(case.request.conditions)}`.",
                f"- Roles: source `{case.source.roles}`, target `{case.target.roles}`; transforms {transforms}.",
                f"- Loss contract: `{result.loss.classification}`; lost distinctions `{list(result.loss.lost_distinctions)}`.",
                "",
            ]
        )
    lines.extend(
        [
            "",
            f"**Result:** {report.passed} passed, {report.failed} failed.",
            "",
            "Unsupported directions, absent mappings, scope changes, identity collapses, and role-filler reversals are explicit rejection codes.",
            "",
        ]
    )
    return "\n".join(lines)
