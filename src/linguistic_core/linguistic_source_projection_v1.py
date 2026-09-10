"""Deterministic PropBank source-native projection with governed syntax repair.

Repairs are applied only in memory to exact pinned bytes. Original source files
remain immutable, and any unrepaired parse failure prevents a complete claim.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.linguistic_source_audit_v1 import SourceSyntaxIssueV1
from linguistic_core.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    verify_linguistic_source_manifest_v1,
)


class SourceProjectionError(ValueError):
    """Raised when exact source bytes cannot produce a truthful projection."""


class SourceSyntaxRepairV1(BaseModel):
    """One exact-fragment syntax repair bound to one exact source file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repair_id: str = Field(
        pattern=r"^[a-z0-9_]+$", description="Stable reviewed repair identifier."
    )
    repair_kind: Literal["xml_syntax"] = Field(
        default="xml_syntax",
        description="Narrow repair class; semantic repairs are forbidden.",
    )
    source_key: str = Field(
        min_length=1, description="Manifest source key owning the file."
    )
    relative_path: str = Field(
        min_length=1, description="Checkout-relative exact source file path."
    )
    source_file_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the unmodified source file."
    )
    old_fragment: str = Field(
        min_length=1, description="Exact malformed fragment required exactly once."
    )
    replacement_fragment: str = Field(
        min_length=1, description="Exact syntax-only replacement applied in memory."
    )
    reason: str = Field(
        min_length=1, description="Reviewed explanation of the syntax defect."
    )

    @model_validator(mode="after")
    def _repair_is_safe(self) -> SourceSyntaxRepairV1:
        path = Path(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "repair relative_path must remain inside the source checkout"
            )
        if self.old_fragment == self.replacement_fragment:
            raise ValueError("repair replacement must differ from old_fragment")
        return self


class LinguisticSourceRepairManifestV1(BaseModel):
    """Reviewed complete syntax-repair set for a projection run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-source-repairs-v1"] = Field(
        default="linguistic-source-repairs-v1",
        description="Repair manifest contract discriminator.",
    )
    repairs: tuple[SourceSyntaxRepairV1, ...] = Field(
        description="Complete exact syntax repairs for the pinned source selection."
    )

    @model_validator(mode="after")
    def _repairs_are_unique(self) -> LinguisticSourceRepairManifestV1:
        for field_name in ("repair_id", "relative_path"):
            values = [getattr(repair, field_name) for repair in self.repairs]
            if len(values) != len(set(values)):
                raise ValueError(f"repair manifest {field_name} values must be unique")
        return self


class AppliedSourceRepairV1(BaseModel):
    """Observed application of one exact declared repair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repair_id: str = Field(min_length=1, description="Applied repair identifier.")
    relative_path: str = Field(
        min_length=1, description="Repaired source-relative file."
    )
    original_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="Observed original complete-file SHA-256.",
    )
    repaired_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="Observed repaired in-memory bytes SHA-256.",
    )
    original_parse_error: str = Field(
        min_length=1, description="Parse failure retained from original exact bytes."
    )


class PropBankAliasV1(BaseModel):
    """One source-native PropBank alias."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(description="Alias text exactly represented by XML text content.")
    part_of_speech: str | None = Field(
        default=None, description="Source part-of-speech attribute when present."
    )


class PropBankResourceLinkV1(BaseModel):
    """One PropBank link to another named linguistic resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource: str = Field(min_length=1, description="Linked resource name.")
    version: str | None = Field(default=None, description="Linked resource version.")
    class_id: str = Field(min_length=1, description="Linked source class identifier.")
    method: str | None = Field(
        default=None, description="Source link-method attribute."
    )
    confidence: str | None = Field(
        default=None,
        description="Source confidence text preserved without reinterpretation.",
    )
    label: str | None = Field(
        default=None, description="Optional source link text, such as a thematic role."
    )


class PropBankArgumentV1(BaseModel):
    """One source-native numbered argument declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: str = Field(min_length=1, description="PropBank role number attribute.")
    function_tag: str | None = Field(default=None, description="PropBank function tag.")
    description: str | None = Field(
        default=None, description="Source argument description."
    )
    role_links: tuple[PropBankResourceLinkV1, ...] = Field(
        default=(), description="Declared resource links for this argument."
    )


class PropBankExampleRelationV1(BaseModel):
    """Source-native predicate realization in one PropBank example."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    token_locations: str = Field(
        min_length=1, description="Exact source relloc token-location string."
    )
    text: str = Field(
        description="Exact decoded relation text, including an empty source value."
    )


class PropBankExampleArgumentV1(BaseModel):
    """Source-native argument annotation in one PropBank example."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    argument_type: str = Field(min_length=1, description="Exact source argument type.")
    start: str = Field(min_length=1, description="Exact source start token or '?'.")
    end: str = Field(min_length=1, description="Exact source end token or '?'.")
    text: str = Field(
        description="Exact decoded argument text, including an empty source value."
    )


class PropBankExampleAmrV1(BaseModel):
    """Optional source-native AMR attached to one PropBank example."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1, description="Exact source AMR version label.")
    text: str = Field(
        min_length=1, description="Exact decoded AMR text, including layout."
    )


class PropBankExampleV1(BaseModel):
    """One complete source-native PropBank roleset example."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        description="Exact source example name, including an empty label."
    )
    source: str = Field(description="Exact source provenance label, including empty.")
    text: str = Field(min_length=1, description="Exact decoded example sentence.")
    relation: PropBankExampleRelationV1 | None = Field(
        default=None, description="Optional annotated predicate realization."
    )
    arguments: tuple[PropBankExampleArgumentV1, ...] = Field(
        default=(), description="Source annotations in document order."
    )
    amr: PropBankExampleAmrV1 | None = Field(
        default=None, description="Optional source AMR without reinterpretation."
    )
    note: str | None = Field(
        default=None, description="Optional exact decoded source note."
    )


class PropBankRoleSetV1(BaseModel):
    """One source-native PropBank roleset with arguments and resource links."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roleset_id: str = Field(
        min_length=1, description="Upstream PropBank roleset identity."
    )
    predicate_lemma: str = Field(
        min_length=1, description="Containing predicate lemma."
    )
    name: str = Field(description="Source roleset name.")
    aliases: tuple[PropBankAliasV1, ...] = Field(
        default=(), description="Source-declared aliases in document order."
    )
    arguments: tuple[PropBankArgumentV1, ...] = Field(
        default=(), description="Source-declared numbered arguments in document order."
    )
    lexical_links: tuple[PropBankResourceLinkV1, ...] = Field(
        default=(), description="Roleset-level source resource links."
    )
    examples: tuple[PropBankExampleV1, ...] = Field(
        default=(), description="Complete source examples in document order."
    )
    source_relative_path: str = Field(
        min_length=1, description="Exact selected source file containing the roleset."
    )


class SourceIdentityConflictV1(BaseModel):
    """One upstream identifier declared by multiple exact source records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Literal["propbank"] = Field(description="Affected source family.")
    source_id: str = Field(min_length=1, description="Duplicated upstream identifier.")
    source_relative_paths: tuple[str, ...] = Field(
        min_length=2,
        description="Sorted unique exact source paths declaring the identifier.",
    )

    @model_validator(mode="after")
    def _paths_are_sorted_and_unique(self) -> SourceIdentityConflictV1:
        if tuple(sorted(set(self.source_relative_paths))) != self.source_relative_paths:
            raise ValueError("identity-conflict paths must be sorted and unique")
        return self


class PropBankProjectionV1(BaseModel):
    """Deterministic source-native projection of one exact PropBank selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["propbank-projection-v1"] = Field(
        default="propbank-projection-v1",
        description="Projection contract discriminator.",
    )
    source_key: str = Field(min_length=1, description="Pinned source manifest key.")
    source_commit_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Exact verified source Git commit."
    )
    source_tree_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Exact verified source Git root tree."
    )
    selected_payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact verified selected payload digest."
    )
    repair_manifest_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized repair manifest SHA-256."
    )
    projection_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of normalized projected content.",
    )
    completeness: Literal[
        "complete", "complete_with_declared_syntax_repairs", "incomplete_source_syntax"
    ] = Field(description="Honest projection completeness disposition.")
    source_file_count: int = Field(gt=0, description="Selected source file count.")
    parsed_file_count: int = Field(
        ge=0, description="Successfully projected file count."
    )
    rolesets: tuple[PropBankRoleSetV1, ...] = Field(
        description="Unique rolesets sorted by upstream identity."
    )
    applied_repairs: tuple[AppliedSourceRepairV1, ...] = Field(
        default=(), description="Observed exact syntax repairs in repair-id order."
    )
    unrepaired_syntax_issues: tuple[SourceSyntaxIssueV1, ...] = Field(
        default=(), description="Parse failures that prevent complete projection."
    )
    identity_conflicts: tuple[SourceIdentityConflictV1, ...] = Field(
        default=(),
        description="Duplicate upstream identities retained without collapse.",
    )

    @model_validator(mode="after")
    def _content_reconciles(self) -> PropBankProjectionV1:
        if (
            self.parsed_file_count + len(self.unrepaired_syntax_issues)
            != self.source_file_count
        ):
            raise ValueError(
                "parsed and unrepaired source-file counts do not reconcile"
            )
        expected_completeness = (
            "incomplete_source_syntax"
            if self.unrepaired_syntax_issues
            else (
                "complete_with_declared_syntax_repairs"
                if self.applied_repairs
                else "complete"
            )
        )
        if self.completeness != expected_completeness:
            raise ValueError(
                "projection completeness does not reconcile with issues/repairs"
            )
        record_keys = [
            (record.roleset_id, record.source_relative_path) for record in self.rolesets
        ]
        if record_keys != sorted(record_keys) or len(record_keys) != len(
            set(record_keys)
        ):
            raise ValueError("projection rolesets must have sorted unique id/path keys")
        paths_by_id: dict[str, set[str]] = {}
        for record in self.rolesets:
            paths_by_id.setdefault(record.roleset_id, set()).add(
                record.source_relative_path
            )
        expected_conflicts = tuple(
            SourceIdentityConflictV1(
                family="propbank",
                source_id=roleset_id,
                source_relative_paths=tuple(sorted(paths)),
            )
            for roleset_id, paths in sorted(paths_by_id.items())
            if len(paths) > 1
        )
        if self.identity_conflicts != expected_conflicts:
            raise ValueError(
                "projection identity conflicts do not reconcile with rolesets"
            )
        projected_content = {
            "rolesets": [record.model_dump(mode="json") for record in self.rolesets],
            "applied_repairs": [
                repair.model_dump(mode="json") for repair in self.applied_repairs
            ],
            "unrepaired_syntax_issues": [
                issue.model_dump(mode="json") for issue in self.unrepaired_syntax_issues
            ],
            "identity_conflicts": [
                conflict.model_dump(mode="json") for conflict in self.identity_conflicts
            ],
        }
        if self.projection_content_sha256 != _normalized_sha256(projected_content):
            legacy_content = {
                **projected_content,
                "rolesets": [
                    record.model_dump(mode="json", exclude={"examples"})
                    for record in self.rolesets
                ],
            }
            if any(record.examples for record in self.rolesets) or (
                self.projection_content_sha256 != _normalized_sha256(legacy_content)
            ):
                raise ValueError(
                    "projection content SHA-256 does not match normalized content"
                )
        return self


def load_linguistic_source_repairs_v1(path: Path) -> LinguisticSourceRepairManifestV1:
    """Load one strict UTF-8 YAML repair manifest."""

    return LinguisticSourceRepairManifestV1.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def load_propbank_projection_v1(path: Path) -> PropBankProjectionV1:
    """Load one strict JSON projection, optionally deterministic-gzip encoded."""

    payload = path.read_bytes()
    if path.suffix == ".gz":
        payload = gzip.decompress(payload)
    return PropBankProjectionV1.model_validate_json(payload)


def _selected_files(source_root: Path, globs: tuple[str, ...]) -> tuple[Path, ...]:
    root = source_root.resolve()
    selected = {
        path for pattern in globs for path in root.glob(pattern) if path.is_file()
    }
    files = tuple(sorted(selected, key=lambda path: path.relative_to(root).as_posix()))
    if not files:
        raise SourceProjectionError("PropBank source selection contains no files")
    for path in files:
        if path.is_symlink() or root not in path.resolve().parents:
            raise SourceProjectionError(
                f"selected source file escapes checkout: {path}"
            )
    return files


def _resource_link(element: ET.Element) -> PropBankResourceLinkV1:
    resource = element.get("resource")
    class_id = element.get("class")
    if not resource or not class_id:
        raise SourceProjectionError("PropBank resource link lacks resource or class")
    label = element.text.strip() if element.text and element.text.strip() else None
    return PropBankResourceLinkV1(
        resource=resource,
        version=element.get("version"),
        class_id=class_id,
        method=element.get("src"),
        confidence=element.get("confidence"),
        label=label,
    )


def _require_exact_shape(
    element: ET.Element,
    *,
    attributes: set[str],
    children: set[str],
    context: str,
) -> None:
    unknown_attributes = set(element.attrib) - attributes
    unknown_children = {child.tag for child in element} - children
    if unknown_attributes or unknown_children:
        raise SourceProjectionError(
            f"unsupported PropBank example structure in {context}: "
            f"attributes={sorted(unknown_attributes)} children={sorted(unknown_children)}"
        )


def _one_optional_child(
    element: ET.Element, tag: str, *, context: str
) -> ET.Element | None:
    children = element.findall(tag)
    if len(children) > 1:
        raise SourceProjectionError(f"multiple {tag} elements in {context}")
    return children[0] if children else None


def _required_text(element: ET.Element | None, *, context: str) -> str:
    if element is None or element.text is None or not element.text.strip():
        raise SourceProjectionError(f"missing text in {context}")
    return element.text


def _example(element: ET.Element, *, context: str) -> PropBankExampleV1:
    _require_exact_shape(
        element,
        attributes={"name", "src"},
        children={"text", "propbank", "amr", "note"},
        context=context,
    )
    text_element = _one_optional_child(element, "text", context=context)
    propbank = _one_optional_child(element, "propbank", context=context)
    amr = _one_optional_child(element, "amr", context=context)
    note = _one_optional_child(element, "note", context=context)
    if propbank is not None:
        _require_exact_shape(
            propbank,
            attributes=set(),
            children={"rel", "arg"},
            context=f"{context}/propbank",
        )
    relation_element = (
        _one_optional_child(propbank, "rel", context=context)
        if propbank is not None
        else None
    )
    if relation_element is not None:
        _require_exact_shape(
            relation_element,
            attributes={"relloc"},
            children=set(),
            context=f"{context}/rel",
        )
        relation = PropBankExampleRelationV1(
            token_locations=relation_element.get("relloc") or "",
            text=relation_element.text or "",
        )
    else:
        relation = None
    arguments: list[PropBankExampleArgumentV1] = []
    for argument in propbank.findall("arg") if propbank is not None else ():
        _require_exact_shape(
            argument,
            attributes={"type", "start", "end"},
            children=set(),
            context=f"{context}/arg",
        )
        arguments.append(
            PropBankExampleArgumentV1(
                argument_type=argument.get("type") or "",
                start=argument.get("start") or "",
                end=argument.get("end") or "",
                text=argument.text or "",
            )
        )
    if amr is not None:
        _require_exact_shape(
            amr,
            attributes={"version"},
            children=set(),
            context=f"{context}/amr",
        )
        amr_record = PropBankExampleAmrV1(
            version=amr.get("version") or "",
            text=_required_text(amr, context=f"{context}/amr"),
        )
    else:
        amr_record = None
    if note is not None:
        _require_exact_shape(
            note,
            attributes=set(),
            children=set(),
            context=f"{context}/note",
        )
    return PropBankExampleV1(
        name=element.get("name") or "",
        source=element.get("src") or "",
        text=_required_text(text_element, context=f"{context}/text"),
        relation=relation,
        arguments=tuple(arguments),
        amr=amr_record,
        note=_required_text(note, context=f"{context}/note")
        if note is not None
        else None,
    )


def _rolesets(root: ET.Element, *, relative_path: str) -> list[PropBankRoleSetV1]:
    records: list[PropBankRoleSetV1] = []
    for predicate in root.findall("predicate"):
        lemma = predicate.get("lemma")
        if not lemma:
            raise SourceProjectionError(
                f"PropBank predicate lacks lemma in {relative_path}"
            )
        for roleset in predicate.findall("roleset"):
            roleset_id = roleset.get("id")
            if not roleset_id:
                raise SourceProjectionError(
                    f"PropBank roleset lacks id in {relative_path}"
                )
            aliases = tuple(
                PropBankAliasV1(text=alias.text or "", part_of_speech=alias.get("pos"))
                for alias in roleset.findall("./aliases/alias")
            )
            arguments: list[PropBankArgumentV1] = []
            for role in roleset.findall("./roles/role"):
                number = role.get("n")
                if number is None:
                    raise SourceProjectionError(
                        f"PropBank role lacks n in {relative_path}:{roleset_id}"
                    )
                arguments.append(
                    PropBankArgumentV1(
                        number=number,
                        function_tag=role.get("f"),
                        description=role.get("descr"),
                        role_links=tuple(
                            _resource_link(link)
                            for link in role.findall("./rolelinks/rolelink")
                        ),
                    )
                )
            records.append(
                PropBankRoleSetV1(
                    roleset_id=roleset_id,
                    predicate_lemma=lemma,
                    name=roleset.get("name") or "",
                    aliases=aliases,
                    arguments=tuple(arguments),
                    lexical_links=tuple(
                        _resource_link(link)
                        for link in roleset.findall("./lexlinks/lexlink")
                    ),
                    examples=tuple(
                        _example(
                            example,
                            context=f"{relative_path}:{roleset_id}:example[{index}]",
                        )
                        for index, example in enumerate(roleset.findall("./example"))
                    ),
                    source_relative_path=relative_path,
                )
            )
    return records


def _apply_repair(
    text: str, *, repair: SourceSyntaxRepairV1, observed_sha256: str
) -> tuple[str, AppliedSourceRepairV1]:
    if observed_sha256 != repair.source_file_sha256:
        raise SourceProjectionError(
            f"repair {repair.repair_id} file SHA-256 does not match"
        )
    try:
        ET.fromstring(text)
    except ET.ParseError as original_error:
        parse_error = str(original_error)
    else:
        raise SourceProjectionError(
            f"repair {repair.repair_id} targets already-valid XML"
        )
    if text.count(repair.old_fragment) != 1:
        raise SourceProjectionError(
            f"repair {repair.repair_id} old_fragment must occur exactly once"
        )
    repaired = text.replace(repair.old_fragment, repair.replacement_fragment, 1)
    try:
        ET.fromstring(repaired)
    except ET.ParseError as error:
        raise SourceProjectionError(
            f"repair {repair.repair_id} does not produce valid XML: {error}"
        ) from error
    return repaired, AppliedSourceRepairV1(
        repair_id=repair.repair_id,
        relative_path=repair.relative_path,
        original_sha256=observed_sha256,
        repaired_sha256=hashlib.sha256(repaired.encode("utf-8")).hexdigest(),
        original_parse_error=parse_error,
    )


def _normalized_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compile_propbank_projection_v1(
    manifest: LinguisticSourceManifestV1,
    *,
    source_root: Path,
    repair_manifest: LinguisticSourceRepairManifestV1,
    require_complete: bool = True,
) -> PropBankProjectionV1:
    """Compile exact PropBank rolesets and arguments without mutating source bytes."""

    propbank = next(
        (source for source in manifest.sources if source.family == "propbank"), None
    )
    if (
        propbank is None
        or propbank.selected_payload is None
        or propbank.git_identity is None
    ):
        raise SourceProjectionError("manifest lacks an available PropBank source")
    verify_linguistic_source_manifest_v1(
        LinguisticSourceManifestV1(sources=(propbank,)),
        source_roots={propbank.source_key: source_root},
    )
    repairs_by_path = {
        repair.relative_path: repair for repair in repair_manifest.repairs
    }
    if any(
        repair.source_key != propbank.source_key for repair in repair_manifest.repairs
    ):
        raise SourceProjectionError("repair manifest contains a foreign source_key")

    records: list[PropBankRoleSetV1] = []
    applied: list[AppliedSourceRepairV1] = []
    issues: list[SourceSyntaxIssueV1] = []
    consumed_repairs: set[str] = set()
    files = _selected_files(source_root, propbank.selected_payload.selection_globs)
    root_path = source_root.resolve()
    parsed_file_count = 0
    for path in files:
        relative_path = path.relative_to(root_path).as_posix()
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        repair = repairs_by_path.get(relative_path)
        if repair is not None:
            text, application = _apply_repair(
                text,
                repair=repair,
                observed_sha256=hashlib.sha256(raw).hexdigest(),
            )
            applied.append(application)
            consumed_repairs.add(relative_path)
        try:
            parsed = ET.fromstring(text)
        except ET.ParseError as error:
            issues.append(
                SourceSyntaxIssueV1(
                    family="propbank",
                    relative_path=relative_path,
                    issue_kind="invalid_xml",
                    detail=str(error),
                )
            )
            continue
        parsed_file_count += 1
        records.extend(_rolesets(parsed, relative_path=relative_path))

    unused_repairs = set(repairs_by_path) - consumed_repairs
    if unused_repairs:
        raise SourceProjectionError(
            f"repair paths are not selected source files: {sorted(unused_repairs)}"
        )
    if issues and require_complete:
        raise SourceProjectionError(
            "unrepaired PropBank XML prevents complete projection: "
            + ", ".join(issue.relative_path for issue in issues)
        )
    records.sort(key=lambda record: (record.roleset_id, record.source_relative_path))
    paths_by_id: dict[str, list[str]] = {}
    for record in records:
        paths_by_id.setdefault(record.roleset_id, []).append(
            record.source_relative_path
        )
    identity_conflicts = tuple(
        SourceIdentityConflictV1(
            family="propbank",
            source_id=roleset_id,
            source_relative_paths=tuple(sorted(set(paths))),
        )
        for roleset_id, paths in sorted(paths_by_id.items())
        if len(set(paths)) > 1
    )
    applied.sort(key=lambda repair: repair.repair_id)
    repair_digest = _normalized_sha256(repair_manifest.model_dump(mode="json"))
    projected_content = {
        "rolesets": [record.model_dump(mode="json") for record in records],
        "applied_repairs": [repair.model_dump(mode="json") for repair in applied],
        "unrepaired_syntax_issues": [issue.model_dump(mode="json") for issue in issues],
        "identity_conflicts": [
            conflict.model_dump(mode="json") for conflict in identity_conflicts
        ],
    }
    completeness: Literal[
        "complete", "complete_with_declared_syntax_repairs", "incomplete_source_syntax"
    ]
    if issues:
        completeness = "incomplete_source_syntax"
    elif applied:
        completeness = "complete_with_declared_syntax_repairs"
    else:
        completeness = "complete"
    return PropBankProjectionV1(
        source_key=propbank.source_key,
        source_commit_sha=propbank.git_identity.commit_sha,
        source_tree_sha=propbank.git_identity.tree_sha,
        selected_payload_sha256=propbank.selected_payload.sha256,
        repair_manifest_sha256=repair_digest,
        projection_content_sha256=_normalized_sha256(projected_content),
        completeness=completeness,
        source_file_count=len(files),
        parsed_file_count=parsed_file_count,
        rolesets=tuple(records),
        applied_repairs=tuple(applied),
        unrepaired_syntax_issues=tuple(issues),
        identity_conflicts=identity_conflicts,
    )
