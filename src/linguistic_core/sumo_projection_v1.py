"""Compile pinned root SUO-KIF modules into a strict source-native projection.

The compiler deliberately supports only direct ontology declarations needed by
Plan 0147. It preserves exact formula provenance, inventories every selected
and excluded Git path, and never publishes or interprets the resulting graph
as a governed OntoCanon alignment.
"""

from __future__ import annotations

from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import cast, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.linguistic_sources_v1 import (
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    verify_linguistic_source_manifest_v1,
)


_SUPPORTED_PREDICATES = frozenset(
    {
        "instance",
        "subclass",
        "subrelation",
        "domain",
        "domainSubclass",
        "range",
        "rangeSubclass",
        "disjoint",
    }
)


class SumoProjectionError(ValueError):
    """Raised when exact SUMO bytes cannot produce a closed projection."""


class SumoFormulaRefV1(BaseModel):
    """Exact top-level source formula supplying one projected fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_path: str = Field(min_length=1, description="Root KIF module path.")
    module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Module SHA-256.")
    formula_index: int = Field(gt=0, description="One-based top-level formula index.")
    start_line: int = Field(gt=0, description="One-based source line where the formula starts.")
    formula_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the exact formula bytes."
    )

    @model_validator(mode="after")
    def _path_is_safe(self) -> "SumoFormulaRefV1":
        path = PurePosixPath(self.module_path)
        if path.is_absolute() or ".." in path.parts or path.name != self.module_path:
            raise ValueError("SUMO module path must be one safe root file")
        return self


class SumoModuleV1(BaseModel):
    """Complete identity and parse count for one selected root KIF module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, description="Selected root KIF path.")
    byte_count: int = Field(gt=0, description="Complete module byte length.")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Complete module SHA-256.")
    top_level_formula_count: int = Field(ge=0, description="All parsed top-level formulas.")
    projected_formula_count: int = Field(
        ge=0, description="Top-level formulas in the supported direct axiom families."
    )

    @model_validator(mode="after")
    def _path_is_selected_root_kif(self) -> "SumoModuleV1":
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or path.name != self.path:
            raise ValueError("selected SUMO module must be one safe root file")
        if path.suffix != ".kif":
            raise ValueError("selected SUMO module must be a KIF file")
        return self


class SumoTermV1(BaseModel):
    """One source-native term and every direct declaration reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    term: str = Field(min_length=1, description="Exact source-native SUMO symbol.")
    source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        min_length=1, description="Sorted direct formulas that establish the term."
    )


class SumoBinaryAxiomV1(BaseModel):
    """One direct binary hierarchy axiom."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    child: str = Field(min_length=1, description="Direct child term.")
    parent: str = Field(min_length=1, description="Direct parent term.")
    source_ref: SumoFormulaRefV1 = Field(description="Exact source formula.")


class SumoInstanceAxiomV1(BaseModel):
    """One direct instance declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instance: str = Field(min_length=1, description="Declared instance term.")
    class_term: str = Field(min_length=1, description="Declared class term.")
    source_ref: SumoFormulaRefV1 = Field(description="Exact source formula.")


class SumoArgumentConstraintV1(BaseModel):
    """One direct domain or range constraint without inferred strengthening."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["domain", "domainSubclass", "range", "rangeSubclass"] = Field(
        description="Exact SUO-KIF constraint predicate."
    )
    relation: str = Field(min_length=1, description="Constrained relation.")
    argument_position: int | Literal["range"] = Field(
        description="One-based domain position, or range when arity determines the position."
    )
    argument_type: str = Field(min_length=1, description="Exact constrained type expression.")
    source_ref: SumoFormulaRefV1 = Field(description="Exact source formula.")

    @model_validator(mode="after")
    def _position_matches_constraint_kind(self) -> "SumoArgumentConstraintV1":
        if self.kind.startswith("domain"):
            if not isinstance(self.argument_position, int) or self.argument_position < 1:
                raise ValueError("domain constraints require a positive argument position")
        elif self.argument_position != "range":
            raise ValueError("range constraints require the explicit range position")
        return self


class SumoDisjointAxiomV1(BaseModel):
    """One direct n-ary disjointness declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    terms: tuple[str, ...] = Field(min_length=2, description="Source-order disjoint terms.")
    source_ref: SumoFormulaRefV1 = Field(description="Exact source formula.")


class SumoBoundedContextV1(BaseModel):
    """Exact SUMO neighborhood required by the current linguistic predicate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_module: Literal["Merge.kif"] = Field(
        default="Merge.kif",
        description="Canonical merged KB module supplying the bounded constraints.",
    )
    leaving_type_hierarchy: tuple[str, ...] = Field(
        min_length=2, description="Direct Leaving-to-Entity source path."
    )
    autonomous_agent_type_hierarchy: tuple[str, ...] = Field(
        min_length=2, description="Direct AutonomousAgent-to-Entity source path."
    )
    case_roles: tuple[str, ...] = Field(description="Exact required SUMO case-role IDs.")
    agent_constraints: tuple[SumoArgumentConstraintV1, ...] = Field(
        min_length=1, description="Direct agent argument constraints."
    )
    patient_constraints: tuple[SumoArgumentConstraintV1, ...] = Field(
        min_length=1, description="Direct patient argument constraints."
    )

    @model_validator(mode="after")
    def _context_is_exactly_bounded(self) -> "SumoBoundedContextV1":
        if self.case_roles != tuple(sorted(set(self.case_roles))):
            raise ValueError("bounded SUMO case roles must be sorted and unique")
        if "location" in self.case_roles:
            raise ValueError("bounded SUMO context must not invent a location alignment")
        if {item.relation for item in self.agent_constraints} != {"agent"}:
            raise ValueError("agent constraints must bind only the agent relation")
        if {item.relation for item in self.patient_constraints} != {"patient"}:
            raise ValueError("patient constraints must bind only the patient relation")
        return self


def _content_payload(projection: "SumoProjectionV1") -> dict[str, object]:
    """Return every projection-owned field covered by the internal self-hash."""

    return {
        name: getattr(projection, name)
        for name in (
            "modules",
            "excluded_tree_paths",
            "types",
            "relations",
            "instance_axioms",
            "subclass_axioms",
            "subrelation_axioms",
            "argument_constraints",
            "disjoint_axioms",
            "bounded_context",
        )
    }


def _normalized_sha256(value: object) -> str:
    """Hash a Pydantic-compatible value using canonical JSON framing."""

    def default(item: object) -> object:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, tuple):
            return list(item)
        raise TypeError(f"cannot encode projection content: {type(item).__name__}")

    payload = json.dumps(
        value, default=default, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SumoProjectionV1(BaseModel):
    """Complete deterministic projection of one exact root-KIF selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-projection-v1"] = Field(
        default="sumo-projection-v1", description="Projection contract discriminator."
    )
    source_key: str = Field(min_length=1, description="Pinned linguistic source key.")
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Exact Git commit.")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Exact Git root tree.")
    selected_payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact selected-payload digest."
    )
    selection_globs: tuple[str, ...] = Field(
        min_length=1, description="Exact manifest selection used for this projection."
    )
    selected_file_count: int = Field(gt=0, description="Declared selected file count.")
    selected_byte_count: int = Field(gt=0, description="Declared selected byte count.")
    license_disposition: Literal["mixed_review_required"] = Field(
        description="Unresolved selected-module license disposition."
    )
    license_evidence: tuple[LicenseEvidenceV1, ...] = Field(
        min_length=1, description="Exact byte-bound evidence retained from the source manifest."
    )
    redistribution_allowed: Literal[False] = Field(
        description="Fail-closed redistribution decision for this non-publishing projection."
    )
    publication_status: Literal["blocked_mixed_license"] = Field(
        description="Explicit prohibition on installing or publishing this derived artifact."
    )
    excluded_tree_paths_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Digest of excluded tracked paths."
    )
    projection_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Digest of all projection-owned content."
    )
    formula_count: int = Field(ge=0, description="All top-level selected formulas.")
    modules: tuple[SumoModuleV1, ...] = Field(description="Complete selected module inventory.")
    excluded_tree_paths: tuple[str, ...] = Field(
        description="Every tracked Git path outside the selected payload."
    )
    types: tuple[SumoTermV1, ...] = Field(description="Sorted declared type inventory.")
    relations: tuple[SumoTermV1, ...] = Field(description="Sorted declared relation inventory.")
    instance_axioms: tuple[SumoInstanceAxiomV1, ...] = Field(
        description="All direct selected instance axioms."
    )
    subclass_axioms: tuple[SumoBinaryAxiomV1, ...] = Field(
        description="All direct selected subclass axioms."
    )
    subrelation_axioms: tuple[SumoBinaryAxiomV1, ...] = Field(
        description="All direct selected subrelation axioms."
    )
    argument_constraints: tuple[SumoArgumentConstraintV1, ...] = Field(
        description="All direct selected domain and range constraints."
    )
    disjoint_axioms: tuple[SumoDisjointAxiomV1, ...] = Field(
        description="All direct selected disjointness axioms."
    )
    bounded_context: SumoBoundedContextV1 = Field(
        description="Minimal source-grounded linguistic inspection context."
    )

    @model_validator(mode="after")
    def _projection_is_closed(self) -> "SumoProjectionV1":
        module_paths = [item.path for item in self.modules]
        if self.selection_globs != ("*.kif",):
            raise ValueError("SUMO projection v1 requires the exact root-KIF selection")
        if module_paths != sorted(set(module_paths)) or len(module_paths) != self.selected_file_count:
            raise ValueError("selected module inventory is not sorted, unique, and complete")
        if sum(item.byte_count for item in self.modules) != self.selected_byte_count:
            raise ValueError("selected module byte inventory does not reconcile")
        if sum(item.top_level_formula_count for item in self.modules) != self.formula_count:
            raise ValueError("selected module formula inventory does not reconcile")
        projected_formula_count = sum(item.projected_formula_count for item in self.modules)
        axiom_count = sum(
            len(items)
            for items in (
                self.instance_axioms,
                self.subclass_axioms,
                self.subrelation_axioms,
                self.argument_constraints,
                self.disjoint_axioms,
            )
        )
        if projected_formula_count != axiom_count:
            raise ValueError("supported formula inventory does not reconcile to projected axioms")
        if self.excluded_tree_paths != tuple(sorted(set(self.excluded_tree_paths))):
            raise ValueError("excluded tree path inventory must be sorted and unique")
        for value in self.excluded_tree_paths:
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or not value:
                raise ValueError("excluded tree paths must be safe repository-relative paths")
        excluded_digest = _normalized_sha256(self.excluded_tree_paths)
        if excluded_digest != self.excluded_tree_paths_sha256:
            raise ValueError("excluded tree path SHA-256 does not reconcile")
        module_by_path = {item.path: item for item in self.modules}
        axiom_refs = [
            *[item.source_ref for item in self.instance_axioms],
            *[item.source_ref for item in self.subclass_axioms],
            *[item.source_ref for item in self.subrelation_axioms],
            *[item.source_ref for item in self.argument_constraints],
            *[item.source_ref for item in self.disjoint_axioms],
        ]
        if len(axiom_refs) != len(set(axiom_refs)):
            raise ValueError("each supported source formula must project exactly once")
        refs = [
            *[ref for item in self.types for ref in item.source_refs],
            *[ref for item in self.relations for ref in item.source_refs],
            *axiom_refs,
        ]
        for ref in refs:
            module = module_by_path.get(ref.module_path)
            if (
                module is None
                or module.sha256 != ref.module_sha256
                or ref.formula_index > module.top_level_formula_count
            ):
                raise ValueError("formula reference does not close to selected module identity")
        for terms in (self.types, self.relations):
            names = [item.term for item in terms]
            if names != sorted(set(names)):
                raise ValueError("projected term inventories must be sorted and unique")
        type_names = {item.term for item in self.types}
        relation_names = {item.term for item in self.relations}
        required_types = {
            *[item.class_term for item in self.instance_axioms],
            *[item.child for item in self.subclass_axioms],
            *[item.parent for item in self.subclass_axioms],
            *[
                item.argument_type
                for item in self.argument_constraints
                if not item.argument_type.startswith("(")
            ],
            *[
                term
                for item in self.disjoint_axioms
                for term in item.terms
                if not term.startswith("(")
            ],
        }
        required_relations = {
            *[item.child for item in self.subrelation_axioms],
            *[item.parent for item in self.subrelation_axioms],
            *[item.relation for item in self.argument_constraints],
        }
        if not required_types <= type_names or not required_relations <= relation_names:
            raise ValueError("projected axioms contain dangling type or relation terms")
        subclass_edges = {(item.child, item.parent) for item in self.subclass_axioms}
        for hierarchy in (
            self.bounded_context.leaving_type_hierarchy,
            self.bounded_context.autonomous_agent_type_hierarchy,
        ):
            if any(edge not in subclass_edges for edge in zip(hierarchy, hierarchy[1:])):
                raise ValueError("bounded hierarchy is not supported by direct subclass axioms")
        constraint_set = set(self.argument_constraints)
        if not set(self.bounded_context.agent_constraints) <= constraint_set or not set(
            self.bounded_context.patient_constraints
        ) <= constraint_set:
            raise ValueError("bounded constraints are not present in the complete projection")
        if any(
            item.source_ref.module_path != self.bounded_context.source_module
            for item in (
                *self.bounded_context.agent_constraints,
                *self.bounded_context.patient_constraints,
            )
        ):
            raise ValueError("bounded constraints do not close to the declared source module")
        case_role_instances = {
            item.instance
            for item in self.instance_axioms
            if item.class_term == "CaseRole"
        }
        if not set(self.bounded_context.case_roles) <= case_role_instances:
            raise ValueError("bounded case roles lack direct CaseRole declarations")
        if _normalized_sha256(_content_payload(self)) != self.projection_content_sha256:
            raise ValueError("projection content SHA-256 does not reconcile")
        return self


def _git(checkout: Path, *args: str) -> str:
    """Read one exact Git value or fail with retained command context."""

    completed = subprocess.run(
        ["git", *args], cwd=checkout, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SumoProjectionError(f"unable to inspect SUMO Git checkout: {detail}")
    return completed.stdout


def _top_level_formulas(payload: bytes, *, module_path: str) -> list[tuple[str, int]]:
    """Extract exact top-level S-expressions with strict comment/string handling."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SumoProjectionError(f"SUMO module is not UTF-8: {module_path}") from exc
    formulas: list[tuple[str, int]] = []
    depth = 0
    start: int | None = None
    start_line = 0
    line = 1
    in_string = False
    escaped = False
    in_comment = False
    for index, char in enumerate(text):
        if in_comment:
            if char == "\n":
                in_comment = False
                line += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            if char == "\n":
                line += 1
            continue
        if char == ";":
            in_comment = True
        elif char == '"':
            if depth == 0:
                raise SumoProjectionError(f"string outside formula in {module_path}:{line}")
            in_string = True
        elif char == "(":
            if depth == 0:
                start = index
                start_line = line
            depth += 1
        elif char == ")":
            if depth == 0 or start is None:
                raise SumoProjectionError(f"unmatched close parenthesis in {module_path}:{line}")
            depth -= 1
            if depth == 0:
                formulas.append((text[start : index + 1], start_line))
                start = None
        elif depth == 0 and not char.isspace():
            raise SumoProjectionError(f"unexpected text outside formula in {module_path}:{line}")
        if char == "\n":
            line += 1
    if in_string:
        raise SumoProjectionError(f"unclosed string in {module_path}")
    if depth or start is not None:
        raise SumoProjectionError(f"unclosed formula in {module_path}")
    return formulas


def _tokens(raw: str, *, context: str) -> list[str]:
    """Tokenize one balanced formula while retaining nested terms as expressions."""

    tokens: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char.isspace():
            index += 1
            continue
        if char == ";":
            newline = raw.find("\n", index)
            index = len(raw) if newline < 0 else newline + 1
            continue
        if char in "()":
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            end = index + 1
            escaped = False
            while end < len(raw):
                current = raw[end]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    end += 1
                    break
                end += 1
            else:
                raise SumoProjectionError(f"unclosed string while tokenizing {context}")
            tokens.append(raw[index:end])
            index = end
            continue
        end = index
        while end < len(raw) and not raw[end].isspace() and raw[end] not in "()":
            end += 1
        tokens.append(raw[index:end])
        index = end
    return tokens


def _direct_parts(raw: str, *, context: str) -> tuple[str, ...]:
    """Return direct operands, serializing nested operands without interpretation."""

    tokens = _tokens(raw, context=context)
    if len(tokens) < 3 or tokens[0] != "(" or tokens[-1] != ")":
        raise SumoProjectionError(f"invalid top-level formula in {context}")
    parts: list[str] = []
    index = 1
    while index < len(tokens) - 1:
        if tokens[index] != "(":
            parts.append(tokens[index])
            index += 1
            continue
        start = index
        depth = 0
        while index < len(tokens) - 1:
            depth += (tokens[index] == "(") - (tokens[index] == ")")
            index += 1
            if depth == 0:
                break
        if depth:
            raise SumoProjectionError(f"unclosed nested term in {context}")
        parts.append(" ".join(tokens[start:index]))
    return tuple(parts)


def _source_ref(
    *, module: SumoModuleV1, formula_index: int, start_line: int, raw: str
) -> SumoFormulaRefV1:
    """Bind one parsed record to exact UTF-8 formula bytes."""

    return SumoFormulaRefV1(
        module_path=module.path,
        module_sha256=module.sha256,
        formula_index=formula_index,
        start_line=start_line,
        formula_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def _path(
    start: str, target: str, parents: dict[str, set[str]], *, label: str
) -> tuple[str, ...]:
    """Find the unique shortest direct hierarchy path required by the bounded view."""

    queue: list[tuple[str, ...]] = [(start,)]
    completed: list[tuple[str, ...]] = []
    shortest: int | None = None
    while queue:
        current = queue.pop(0)
        if shortest is not None and len(current) > shortest:
            break
        if current[-1] == target:
            shortest = len(current)
            completed.append(current)
            continue
        for parent in sorted(parents.get(current[-1], set())):
            if parent not in current:
                queue.append((*current, parent))
    if len(completed) != 1:
        raise SumoProjectionError(
            f"bounded {label} hierarchy requires one shortest {start}-to-{target} path; "
            f"observed {len(completed)}"
        )
    return completed[0]


def compile_sumo_projection_v1(
    manifest: LinguisticSourceManifestV1, *, source_checkout: Path
) -> SumoProjectionV1:
    """Compile verified selected root KIF files without publishing derived bytes."""

    source = next((item for item in manifest.sources if item.family == "sumo"), None)
    if (
        source is None
        or source.availability != "available"
        or source.git_identity is None
        or source.selected_payload is None
    ):
        raise SumoProjectionError("manifest lacks an available Git-backed SUMO source")
    if source.license_disposition != "mixed_review_required" or source.redistribution_allowed:
        raise SumoProjectionError(
            "SUMO projection v1 requires the explicit mixed-license, non-redistributable state"
        )
    verify_linguistic_source_manifest_v1(
        LinguisticSourceManifestV1(sources=(source,)),
        source_roots={source.source_key: source_checkout},
    )
    root = source_checkout.resolve()
    selected_paths = sorted(
        {
            path
            for pattern in source.selected_payload.selection_globs
            for path in root.glob(pattern)
            if path.is_file()
        },
        key=lambda path: path.relative_to(root).as_posix(),
    )
    modules: list[SumoModuleV1] = []
    parsed: list[tuple[SumoModuleV1, list[tuple[str, int]]]] = []
    for path in selected_paths:
        payload = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        formulas = _top_level_formulas(payload, module_path=relative)
        module = SumoModuleV1(
            path=relative,
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            top_level_formula_count=len(formulas),
            projected_formula_count=sum(
                1
                for raw, _line in formulas
                if raw[1:].lstrip().split(maxsplit=1)[0].rstrip("()")
                in _SUPPORTED_PREDICATES
            ),
        )
        modules.append(module)
        parsed.append((module, formulas))

    tree_paths = tuple(
        path
        for path in _git(source_checkout, "ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0")
        if path
    )
    selected_names = {item.path for item in modules}
    excluded_paths = tuple(sorted(set(tree_paths) - selected_names))

    instances: list[SumoInstanceAxiomV1] = []
    subclasses: list[SumoBinaryAxiomV1] = []
    subrelations: list[SumoBinaryAxiomV1] = []
    constraints: list[SumoArgumentConstraintV1] = []
    disjoints: list[SumoDisjointAxiomV1] = []
    term_refs: dict[str, set[SumoFormulaRefV1]] = defaultdict(set)
    relation_refs: dict[str, set[SumoFormulaRefV1]] = defaultdict(set)
    for module, formulas in parsed:
        for formula_index, (raw, start_line) in enumerate(formulas, start=1):
            stripped = raw[1:].lstrip()
            head_end = next(
                (index for index, char in enumerate(stripped) if char.isspace() or char in "()"),
                len(stripped),
            )
            if stripped[:head_end] not in _SUPPORTED_PREDICATES:
                continue
            parts = _direct_parts(raw, context=f"{module.path}:{start_line}")
            if not parts:
                continue
            predicate = parts[0]
            ref = _source_ref(
                module=module,
                formula_index=formula_index,
                start_line=start_line,
                raw=raw,
            )
            if predicate == "instance":
                if len(parts) != 3:
                    raise SumoProjectionError(f"invalid instance axiom in {module.path}:{start_line}")
                instance_axiom = SumoInstanceAxiomV1(
                    instance=parts[1], class_term=parts[2], source_ref=ref
                )
                instances.append(instance_axiom)
            elif predicate in {"subclass", "subrelation"}:
                if len(parts) != 3:
                    raise SumoProjectionError(f"invalid {predicate} axiom in {module.path}:{start_line}")
                binary_axiom = SumoBinaryAxiomV1(
                    child=parts[1], parent=parts[2], source_ref=ref
                )
                (subclasses if predicate == "subclass" else subrelations).append(
                    binary_axiom
                )
                target = relation_refs if predicate == "subrelation" else term_refs
                target[parts[1]].add(ref)
                target[parts[2]].add(ref)
            elif predicate in {"domain", "domainSubclass", "range", "rangeSubclass"}:
                expected = 4 if predicate.startswith("domain") else 3
                if len(parts) != expected:
                    raise SumoProjectionError(f"invalid {predicate} axiom in {module.path}:{start_line}")
                position: int | Literal["range"]
                if expected == 4:
                    try:
                        position = int(parts[2])
                    except ValueError as exc:
                        raise SumoProjectionError(
                            f"non-integer {predicate} position in {module.path}:{start_line}"
                        ) from exc
                else:
                    position = "range"
                argument_type = parts[3] if expected == 4 else parts[2]
                constraint_axiom = SumoArgumentConstraintV1(
                    kind=cast(
                        Literal["domain", "domainSubclass", "range", "rangeSubclass"],
                        predicate,
                    ),
                    relation=parts[1],
                    argument_position=position,
                    argument_type=argument_type,
                    source_ref=ref,
                )
                constraints.append(constraint_axiom)
                relation_refs[parts[1]].add(ref)
                if not argument_type.startswith("("):
                    term_refs[argument_type].add(ref)
            elif predicate == "disjoint":
                if len(parts) < 3:
                    raise SumoProjectionError(f"invalid disjoint axiom in {module.path}:{start_line}")
                disjoints.append(SumoDisjointAxiomV1(terms=parts[1:], source_ref=ref))
                for term in parts[1:]:
                    if not term.startswith("("):
                        term_refs[term].add(ref)

    class_parents: dict[str, set[str]] = defaultdict(set)
    for subclass_axiom in subclasses:
        class_parents[subclass_axiom.child].add(subclass_axiom.parent)

    def descends_from(term: str, ancestor: str) -> bool:
        """Return whether direct subclass closure reaches the requested ancestor."""

        pending = [term]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == ancestor:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(class_parents.get(current, set()) - visited)
        return False

    for instance_axiom in instances:
        term_refs[instance_axiom.class_term].add(instance_axiom.source_ref)
        if instance_axiom.class_term == "Class":
            term_refs[instance_axiom.instance].add(instance_axiom.source_ref)
        if descends_from(instance_axiom.class_term, "Relation"):
            relation_refs[instance_axiom.instance].add(instance_axiom.source_ref)
    leaving_path = _path("Leaving", "Entity", class_parents, label="Leaving")
    agent_path = _path("AutonomousAgent", "Entity", class_parents, label="AutonomousAgent")
    bounded_module: Literal["Merge.kif"] = "Merge.kif"
    agent_constraints = tuple(
        sorted(
            (
                item
                for item in constraints
                if item.relation == "agent"
                and item.source_ref.module_path == bounded_module
            ),
            key=lambda item: (str(item.argument_position), item.kind, item.argument_type),
        )
    )
    patient_constraints = tuple(
        sorted(
            (
                item
                for item in constraints
                if item.relation == "patient"
                and item.source_ref.module_path == bounded_module
            ),
            key=lambda item: (str(item.argument_position), item.kind, item.argument_type),
        )
    )
    instance_classes: dict[str, set[str]] = defaultdict(set)
    for axiom in instances:
        instance_classes[axiom.instance].add(axiom.class_term)
    required_roles = tuple(
        sorted(role for role in ("agent", "patient") if "CaseRole" in instance_classes[role])
    )
    if required_roles != ("agent", "patient") or not agent_constraints or not patient_constraints:
        raise SumoProjectionError("bounded agent/patient CaseRole declarations and constraints are incomplete")

    types = tuple(
        SumoTermV1(term=term, source_refs=tuple(sorted(refs, key=lambda ref: (ref.module_path, ref.formula_index))))
        for term, refs in sorted(term_refs.items())
    )
    relations = tuple(
        SumoTermV1(term=term, source_refs=tuple(sorted(refs, key=lambda ref: (ref.module_path, ref.formula_index))))
        for term, refs in sorted(relation_refs.items())
    )
    module_values = tuple(modules)
    instance_values = tuple(instances)
    subclass_values = tuple(subclasses)
    subrelation_values = tuple(subrelations)
    constraint_values = tuple(constraints)
    disjoint_values = tuple(disjoints)
    bounded_context = SumoBoundedContextV1(
        source_module=bounded_module,
        leaving_type_hierarchy=leaving_path,
        autonomous_agent_type_hierarchy=agent_path,
        case_roles=required_roles,
        agent_constraints=agent_constraints,
        patient_constraints=patient_constraints,
    )
    content_values: dict[str, object] = {
        "modules": module_values,
        "excluded_tree_paths": excluded_paths,
        "types": types,
        "relations": relations,
        "instance_axioms": instance_values,
        "subclass_axioms": subclass_values,
        "subrelation_axioms": subrelation_values,
        "argument_constraints": constraint_values,
        "disjoint_axioms": disjoint_values,
        "bounded_context": bounded_context,
    }
    return SumoProjectionV1(
        source_key=source.source_key,
        source_commit_sha=source.git_identity.commit_sha,
        source_tree_sha=source.git_identity.tree_sha,
        selected_payload_sha256=source.selected_payload.sha256,
        selection_globs=source.selected_payload.selection_globs,
        selected_file_count=source.selected_payload.file_count,
        selected_byte_count=source.selected_payload.byte_count,
        license_disposition="mixed_review_required",
        license_evidence=source.license_evidence,
        redistribution_allowed=False,
        publication_status="blocked_mixed_license",
        excluded_tree_paths_sha256=_normalized_sha256(excluded_paths),
        projection_content_sha256=_normalized_sha256(content_values),
        formula_count=sum(item.top_level_formula_count for item in modules),
        modules=module_values,
        excluded_tree_paths=excluded_paths,
        types=types,
        relations=relations,
        instance_axioms=instance_values,
        subclass_axioms=subclass_values,
        subrelation_axioms=subrelation_values,
        argument_constraints=constraint_values,
        disjoint_axioms=disjoint_values,
        bounded_context=bounded_context,
    )


def load_sumo_projection_v1(path: Path) -> SumoProjectionV1:
    """Load one strict projection from JSON or deterministic gzip JSON."""

    payload = path.read_bytes()
    if path.suffix == ".gz":
        try:
            payload = gzip.decompress(payload)
        except gzip.BadGzipFile as exc:
            raise SumoProjectionError("invalid gzip SUMO projection") from exc
    try:
        return SumoProjectionV1.model_validate_json(payload)
    except ValueError as exc:
        raise SumoProjectionError("invalid SUMO projection content") from exc
