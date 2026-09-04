"""Compile exact FrameNet 1.7 XML into a deterministic source-native projection.

The compiler reads a checksum-verified external archive and preserves FrameNet
identities and relation direction without promoting any predicate alignment.
It never extracts or mutates the source archive.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import cast, Literal
import xml.etree.ElementTree as ET
import zipfile

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    verify_linguistic_source_manifest_v1,
)


_FRAMENET_NAMESPACE = "http://framenet.icsi.berkeley.edu"
FrameNetCoreType = Literal["Core", "Peripheral", "Extra-Thematic", "Core-Unexpressed"]


class FrameNetProjectionError(ValueError):
    """Raised when exact FrameNet bytes cannot produce a closed projection."""


class FrameNetSourceRefV1(BaseModel):
    """Exact archive member supplying one projected source record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1, description="Pinned linguistic source key.")
    archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete source archive."
    )
    member_path: str = Field(
        min_length=1, description="Archive-relative exact member containing the record."
    )
    member_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete member bytes."
    )

    @model_validator(mode="after")
    def _member_path_is_safe(self) -> "FrameNetSourceRefV1":
        path = PurePosixPath(self.member_path)
        if path.is_absolute() or ".." in path.parts or self.member_path.endswith("/"):
            raise ValueError("FrameNet source member must be one safe file path")
        if self.member_sha256 == "0" * 64:
            raise ValueError("FrameNet source member SHA-256 cannot be the null digest")
        return self


class FrameNetSemanticTypeRefV1(BaseModel):
    """Source-native semantic type attached to one frame element."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_type_id: int = Field(gt=0, description="FrameNet semantic-type ID.")
    name: str = Field(min_length=1, description="FrameNet semantic-type name.")


class FrameNetFrameElementV1(BaseModel):
    """One ordered FrameNet frame-element declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_element_id: int = Field(gt=0, description="FrameNet frame-element ID.")
    name: str = Field(min_length=1, description="FrameNet frame-element name.")
    abbreviation: str = Field(description="FrameNet frame-element abbreviation, if any.")
    core_type: FrameNetCoreType = Field(
        description="FrameNet 1.7 frame-element core-type label."
    )
    definition: str = Field(
        min_length=1, description="Exact decoded FrameNet frame-element definition markup."
    )
    semantic_types: tuple[FrameNetSemanticTypeRefV1, ...] = Field(
        default=(), description="Source semantic types in document order."
    )


class FrameNetLexicalUnitV1(BaseModel):
    """One FrameNet lexical unit retained for frame lookup and inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lexical_unit_id: int = Field(gt=0, description="FrameNet lexical-unit ID.")
    name: str = Field(min_length=1, description="FrameNet lexical-unit name.")
    part_of_speech: str = Field(min_length=1, description="FrameNet POS label.")
    status: str = Field(min_length=1, description="FrameNet lexical-unit status.")
    definition: str = Field(description="Decoded lexical-unit definition text.")
    indexed_for_lookup: bool = Field(
        description="Whether the exact FrameNet luIndex.xml includes this declaration."
    )


class FrameNetFrameElementRelationV1(BaseModel):
    """One exact source FE mapping nested under a frame relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_element_relation_id: int = Field(gt=0, description="FrameNet FE-relation ID.")
    sub_frame_element_id: int = Field(gt=0, description="Sub-frame FE ID.")
    sub_frame_element_name: str = Field(min_length=1, description="Sub-frame FE name.")
    super_frame_element_id: int = Field(gt=0, description="Super-frame FE ID.")
    super_frame_element_name: str = Field(min_length=1, description="Super-frame FE name.")


class FrameNetFrameRelationRefV1(BaseModel):
    """One typed incoming or outgoing relation from the containing frame."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_relation_id: int = Field(gt=0, description="FrameNet frame-relation ID.")
    relation_type_id: int = Field(gt=0, description="FrameNet relation-type ID.")
    relation_type_name: str = Field(min_length=1, description="FrameNet relation-type name.")
    direction: Literal["incoming", "outgoing"] = Field(
        description="Direction relative to the containing frame: sub-to-super is outgoing."
    )
    related_frame_id: int = Field(gt=0, description="FrameNet ID at the other endpoint.")
    related_frame_name: str = Field(min_length=1, description="FrameNet name at the other endpoint.")
    containing_frame_role: str = Field(
        min_length=1, description="Source relation-type role label for the containing frame."
    )
    related_frame_role: str = Field(
        min_length=1, description="Source relation-type role label for the related frame."
    )
    frame_element_relations: tuple[FrameNetFrameElementRelationV1, ...] = Field(
        default=(), description="FE mappings sorted by FrameNet FE-relation ID."
    )
    source_ref: FrameNetSourceRefV1 = Field(
        description="Exact frRelation.xml member supplying the relation."
    )

    @model_validator(mode="after")
    def _fe_relations_are_sorted_unique(self) -> "FrameNetFrameRelationRefV1":
        ids = [item.frame_element_relation_id for item in self.frame_element_relations]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("frame-element relations must have sorted unique IDs")
        return self


class FrameNetFrameRecordV1(BaseModel):
    """One complete source-native FrameNet frame and its relation neighborhood."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_id: int = Field(gt=0, description="FrameNet frame ID.")
    name: str = Field(min_length=1, description="FrameNet frame name.")
    definition: str = Field(
        min_length=1, description="Exact decoded FrameNet frame definition markup."
    )
    frame_elements: tuple[FrameNetFrameElementV1, ...] = Field(
        description="Frame elements in exact source-document order."
    )
    lexical_units: tuple[FrameNetLexicalUnitV1, ...] = Field(
        description="Lexical units in exact source-document order."
    )
    incoming_relations: tuple[FrameNetFrameRelationRefV1, ...] = Field(
        description="Relations where this frame is the source-declared super frame."
    )
    outgoing_relations: tuple[FrameNetFrameRelationRefV1, ...] = Field(
        description="Relations where this frame is the source-declared sub frame."
    )
    source_ref: FrameNetSourceRefV1 = Field(
        description="Exact frame XML member supplying frame-local content."
    )

    @model_validator(mode="after")
    def _frame_content_is_unique_and_directed(self) -> "FrameNetFrameRecordV1":
        for label, values in (
            ("frame-element IDs", [item.frame_element_id for item in self.frame_elements]),
            ("frame-element names", [item.name for item in self.frame_elements]),
            ("lexical-unit IDs", [item.lexical_unit_id for item in self.lexical_units]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"FrameNet {label} must be unique within a frame")
        if any(item.direction != "incoming" for item in self.incoming_relations):
            raise ValueError("incoming_relations contains a non-incoming relation")
        if any(item.direction != "outgoing" for item in self.outgoing_relations):
            raise ValueError("outgoing_relations contains a non-outgoing relation")
        for relations in (self.incoming_relations, self.outgoing_relations):
            keys = [
                (item.relation_type_id, item.frame_relation_id, item.related_frame_id)
                for item in relations
            ]
            if keys != sorted(keys) or len(keys) != len(set(keys)):
                raise ValueError("FrameNet relations must be sorted and unique")
        return self


class FrameNetProjectionV1(BaseModel):
    """Complete deterministic projection of one exact FrameNet archive."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["framenet-projection-v1"] = Field(
        default="framenet-projection-v1", description="Projection contract discriminator."
    )
    source_key: str = Field(min_length=1, description="Pinned linguistic source key.")
    source_archive_filename: str = Field(
        min_length=1, description="Exact basename of the verified FrameNet archive."
    )
    source_archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the verified FrameNet archive."
    )
    source_archive_byte_count: int = Field(gt=0, description="Verified archive byte length.")
    frame_index_ref: FrameNetSourceRefV1 = Field(description="Exact frameIndex.xml identity.")
    lexical_unit_index_ref: FrameNetSourceRefV1 = Field(
        description="Exact luIndex.xml identity defining the lookup subset."
    )
    relation_index_ref: FrameNetSourceRefV1 = Field(description="Exact frRelation.xml identity.")
    projection_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of normalized projected frame content."
    )
    frame_count: int = Field(gt=0, description="Exact projected frame count.")
    frame_element_count: int = Field(ge=0, description="Exact projected frame-element count.")
    lexical_unit_declaration_count: int = Field(
        ge=0, description="All lexical-unit declarations embedded in frame XML."
    )
    indexed_lexical_unit_count: int = Field(
        ge=0, description="Embedded declarations selected by exact luIndex.xml."
    )
    frame_relation_count: int = Field(ge=0, description="Exact source relation-edge count.")
    frame_element_relation_count: int = Field(
        ge=0, description="Exact FE mappings nested under source frame relations."
    )
    frames: tuple[FrameNetFrameRecordV1, ...] = Field(
        min_length=1, description="Frames sorted by numeric FrameNet ID."
    )

    @model_validator(mode="after")
    def _projection_is_closed(self) -> "FrameNetProjectionV1":
        archive_path = PurePosixPath(self.source_archive_filename)
        if (
            archive_path.name != self.source_archive_filename
            or self.source_archive_filename in {".", ".."}
        ):
            raise ValueError("FrameNet source archive filename must be one safe basename")
        source_prefix = archive_path.stem
        if not source_prefix:
            raise ValueError("FrameNet source archive filename must have a nonempty stem")
        for label, source_ref, expected_path in (
            ("frame-index", self.frame_index_ref, f"{source_prefix}/frameIndex.xml"),
            (
                "lexical-unit-index",
                self.lexical_unit_index_ref,
                f"{source_prefix}/luIndex.xml",
            ),
            ("relation-index", self.relation_index_ref, f"{source_prefix}/frRelation.xml"),
        ):
            _validate_source_ref(
                source_ref,
                source_key=self.source_key,
                archive_sha256=self.source_archive_sha256,
                expected_member_path=expected_path,
                label=label,
            )
        ids = [frame.frame_id for frame in self.frames]
        names = [frame.name for frame in self.frames]
        if ids != sorted(ids) or len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("FrameNet frames must have sorted unique IDs and unique names")
        if self.frame_count != len(self.frames):
            raise ValueError("FrameNet frame count does not reconcile")
        if self.frame_element_count != sum(len(frame.frame_elements) for frame in self.frames):
            raise ValueError("FrameNet frame-element count does not reconcile")
        lexical_units = [unit for frame in self.frames for unit in frame.lexical_units]
        lexical_ids = [unit.lexical_unit_id for unit in lexical_units]
        if len(lexical_ids) != len(set(lexical_ids)):
            raise ValueError("FrameNet lexical-unit IDs must be globally unique")
        if self.lexical_unit_declaration_count != len(lexical_units):
            raise ValueError("FrameNet lexical-unit declaration count does not reconcile")
        if self.indexed_lexical_unit_count != sum(
            unit.indexed_for_lookup for unit in lexical_units
        ):
            raise ValueError("FrameNet indexed lexical-unit count does not reconcile")
        if any(
            not unit.indexed_for_lookup and unit.status != "Problem" for unit in lexical_units
        ):
            raise ValueError("only source-status Problem lexical units may be absent from luIndex")
        frame_elements = [item for frame in self.frames for item in frame.frame_elements]
        frame_element_ids = [item.frame_element_id for item in frame_elements]
        if len(frame_element_ids) != len(set(frame_element_ids)):
            raise ValueError("FrameNet frame-element IDs must be globally unique")
        semantic_types_by_id: dict[int, str] = {}
        semantic_type_ids_by_name: dict[str, int] = {}
        for frame_element in frame_elements:
            for semantic_type in frame_element.semantic_types:
                if (
                    semantic_type.semantic_type_id in semantic_types_by_id
                    and semantic_types_by_id[semantic_type.semantic_type_id]
                    != semantic_type.name
                ):
                    raise ValueError("FrameNet semantic-type ID has conflicting names")
                if (
                    semantic_type.name in semantic_type_ids_by_name
                    and semantic_type_ids_by_name[semantic_type.name]
                    != semantic_type.semantic_type_id
                ):
                    raise ValueError("FrameNet semantic-type name has conflicting IDs")
                semantic_types_by_id[semantic_type.semantic_type_id] = semantic_type.name
                semantic_type_ids_by_name[semantic_type.name] = semantic_type.semantic_type_id
        frame_by_id = {frame.frame_id: frame for frame in self.frames}
        outgoing: dict[
            tuple[int, int, int, int], FrameNetFrameRelationRefV1
        ] = {}
        incoming: dict[
            tuple[int, int, int, int], FrameNetFrameRelationRefV1
        ] = {}
        fe_relation_ids: list[int] = []
        frame_relation_ids: set[int] = set()
        relation_types_by_id: dict[int, tuple[str, str, str]] = {}
        relation_type_ids_by_name: dict[str, int] = {}
        for frame in self.frames:
            _validate_source_ref(
                frame.source_ref,
                source_key=self.source_key,
                archive_sha256=self.source_archive_sha256,
                expected_member_path=f"{source_prefix}/frame/{frame.name}.xml",
                label="frame source reference",
            )
            for relation in frame.outgoing_relations:
                related = frame_by_id.get(relation.related_frame_id)
                if related is None or related.name != relation.related_frame_name:
                    raise ValueError("FrameNet outgoing relation has a dangling endpoint")
                if relation.source_ref != self.relation_index_ref:
                    raise ValueError("FrameNet relation source reference does not match the index")
                _validate_fe_relations(
                    relation,
                    sub_frame=frame,
                    super_frame=related,
                )
                relation_type_signature = (
                    relation.relation_type_name,
                    relation.containing_frame_role,
                    relation.related_frame_role,
                )
                if (
                    relation.relation_type_id in relation_types_by_id
                    and relation_types_by_id[relation.relation_type_id]
                    != relation_type_signature
                ):
                    raise ValueError("FrameNet relation-type ID has conflicting metadata")
                if (
                    relation.relation_type_name in relation_type_ids_by_name
                    and relation_type_ids_by_name[relation.relation_type_name]
                    != relation.relation_type_id
                ):
                    raise ValueError("FrameNet relation-type name has conflicting IDs")
                relation_types_by_id[relation.relation_type_id] = relation_type_signature
                relation_type_ids_by_name[relation.relation_type_name] = (
                    relation.relation_type_id
                )
                if relation.frame_relation_id in frame_relation_ids:
                    raise ValueError("FrameNet frame-relation IDs must be globally unique")
                frame_relation_ids.add(relation.frame_relation_id)
                key = (
                    relation.relation_type_id,
                    relation.frame_relation_id,
                    frame.frame_id,
                    related.frame_id,
                )
                if key in outgoing:
                    raise ValueError("FrameNet outgoing relation identity is duplicated")
                outgoing[key] = relation
                fe_relation_ids.extend(
                    item.frame_element_relation_id for item in relation.frame_element_relations
                )
            for relation in frame.incoming_relations:
                related = frame_by_id.get(relation.related_frame_id)
                if related is None or related.name != relation.related_frame_name:
                    raise ValueError("FrameNet incoming relation has a dangling endpoint")
                if relation.source_ref != self.relation_index_ref:
                    raise ValueError("FrameNet relation source reference does not match the index")
                _validate_fe_relations(
                    relation,
                    sub_frame=related,
                    super_frame=frame,
                )
                key = (
                    relation.relation_type_id,
                    relation.frame_relation_id,
                    related.frame_id,
                    frame.frame_id,
                )
                if key in incoming:
                    raise ValueError("FrameNet incoming relation identity is duplicated")
                incoming[key] = relation
        if outgoing.keys() != incoming.keys() or self.frame_relation_count != len(outgoing):
            raise ValueError("FrameNet incoming/outgoing relations do not reconcile")
        for key, outgoing_relation in outgoing.items():
            incoming_relation = incoming[key]
            if (
                incoming_relation.relation_type_name
                != outgoing_relation.relation_type_name
                or incoming_relation.containing_frame_role
                != outgoing_relation.related_frame_role
                or incoming_relation.related_frame_role
                != outgoing_relation.containing_frame_role
                or incoming_relation.frame_element_relations
                != outgoing_relation.frame_element_relations
                or incoming_relation.source_ref != outgoing_relation.source_ref
            ):
                raise ValueError(
                    "FrameNet incoming relation mirror does not match its outgoing relation"
                )
        if len(fe_relation_ids) != len(set(fe_relation_ids)):
            raise ValueError("FrameNet FE-relation IDs must be globally unique")
        if self.frame_element_relation_count != len(fe_relation_ids):
            raise ValueError("FrameNet FE-relation count does not reconcile")
        content = [frame.model_dump(mode="json") for frame in self.frames]
        if self.projection_content_sha256 != _normalized_sha256(content):
            raise ValueError("FrameNet projection content SHA-256 does not match content")
        return self


def _validate_source_ref(
    source_ref: FrameNetSourceRefV1,
    *,
    source_key: str,
    archive_sha256: str,
    expected_member_path: str,
    label: str,
) -> None:
    """Bind one nested source claim to the projection root and exact member path."""

    if (
        source_ref.source_key != source_key
        or source_ref.archive_sha256 != archive_sha256
        or source_ref.member_path != expected_member_path
    ):
        raise ValueError(f"FrameNet {label} does not match the projection source reference")


def _validate_fe_relations(
    relation: FrameNetFrameRelationRefV1,
    *,
    sub_frame: FrameNetFrameRecordV1,
    super_frame: FrameNetFrameRecordV1,
) -> None:
    """Require every FE mapping to resolve to the declared endpoint frame."""

    sub_elements = {item.frame_element_id: item.name for item in sub_frame.frame_elements}
    super_elements = {item.frame_element_id: item.name for item in super_frame.frame_elements}
    for item in relation.frame_element_relations:
        if (
            sub_elements.get(item.sub_frame_element_id) != item.sub_frame_element_name
            or super_elements.get(item.super_frame_element_id) != item.super_frame_element_name
        ):
            raise ValueError("FrameNet FE relation has a dangling or drifted endpoint")


@dataclass(frozen=True)
class _FrameParts:
    frame_id: int
    name: str
    definition: str
    frame_elements: tuple[FrameNetFrameElementV1, ...]
    lexical_units: tuple[FrameNetLexicalUnitV1, ...]
    source_ref: FrameNetSourceRefV1


@dataclass(frozen=True)
class _IndexedLexicalUnit:
    lexical_unit_id: int
    frame_id: int
    frame_name: str
    name: str
    status: str


def _normalized_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _required_attr(element: ET.Element, name: str, *, context: str) -> str:
    value = element.get(name)
    if value is None or not value.strip():
        raise FrameNetProjectionError(f"FrameNet {context} lacks {name}")
    return value


def _integer_attr(element: ET.Element, name: str, *, context: str) -> int:
    value = _required_attr(element, name, context=context)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise FrameNetProjectionError(f"FrameNet {context} has non-integer {name}") from exc
    if parsed <= 0:
        raise FrameNetProjectionError(f"FrameNet {context} has non-positive {name}")
    return parsed


def _source_ref(
    *, source_key: str, archive_sha256: str, member_path: str, payload: bytes
) -> FrameNetSourceRefV1:
    return FrameNetSourceRefV1(
        source_key=source_key,
        archive_sha256=archive_sha256,
        member_path=member_path,
        member_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _definition(element: ET.Element, namespace: str) -> str:
    value = element.findtext(f"{{{namespace}}}definition")
    return value if value is not None else ""


def _required_definition(element: ET.Element, namespace: str, *, context: str) -> str:
    value = _definition(element, namespace)
    if not value.strip():
        raise FrameNetProjectionError(f"FrameNet {context} lacks a nonempty definition")
    return value


def _require_framenet_namespace(root: ET.Element, *, context: str) -> str:
    namespace = root.tag.partition("}")[0].removeprefix("{")
    if namespace != _FRAMENET_NAMESPACE:
        raise FrameNetProjectionError(f"unexpected FrameNet namespace in {context}")
    return namespace


def _parse_lexical_unit_index(payload: bytes) -> dict[int, _IndexedLexicalUnit]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FrameNetProjectionError("invalid FrameNet luIndex.xml") from exc
    namespace = _require_framenet_namespace(root, context="luIndex.xml")
    records: dict[int, _IndexedLexicalUnit] = {}
    for item in root.findall(f"{{{namespace}}}lu"):
        lexical_unit_id = _integer_attr(item, "ID", context="lexical-unit index entry")
        if lexical_unit_id in records:
            raise FrameNetProjectionError("duplicate FrameNet lexical-unit index ID")
        records[lexical_unit_id] = _IndexedLexicalUnit(
            lexical_unit_id=lexical_unit_id,
            frame_id=_integer_attr(item, "frameID", context="lexical-unit index entry"),
            frame_name=_required_attr(
                item, "frameName", context="lexical-unit index entry"
            ),
            name=_required_attr(item, "name", context="lexical-unit index entry"),
            status=_required_attr(item, "status", context="lexical-unit index entry"),
        )
    if not records:
        raise FrameNetProjectionError("FrameNet lexical-unit index contains no records")
    return records


def _parse_frame(
    payload: bytes,
    *,
    member_path: str,
    source_key: str,
    archive_sha256: str,
    indexed_lexical_units: dict[int, _IndexedLexicalUnit],
) -> _FrameParts:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FrameNetProjectionError(f"invalid FrameNet frame XML: {member_path}") from exc
    namespace = _require_framenet_namespace(root, context=member_path)
    if root.tag.rpartition("}")[2] != "frame":
        raise FrameNetProjectionError(f"unexpected FrameNet frame root: {member_path}")
    frame_id = _integer_attr(root, "ID", context=f"frame {member_path}")
    frame_name = _required_attr(root, "name", context=f"frame {member_path}")
    frame_definition = _required_definition(
        root, namespace, context=f"frame {frame_name}"
    )
    frame_elements: list[FrameNetFrameElementV1] = []
    for element in root.findall(f"{{{namespace}}}FE"):
        semantic_types = tuple(
            FrameNetSemanticTypeRefV1(
                semantic_type_id=_integer_attr(
                    semantic_type, "ID", context=f"semantic type in frame {frame_name}"
                ),
                name=_required_attr(
                    semantic_type, "name", context=f"semantic type in frame {frame_name}"
                ),
            )
            for semantic_type in element.findall(f"{{{namespace}}}semType")
        )
        core_type_value = _required_attr(
            element, "coreType", context=f"frame element in frame {frame_name}"
        )
        if core_type_value not in {
            "Core",
            "Peripheral",
            "Extra-Thematic",
            "Core-Unexpressed",
        }:
            raise FrameNetProjectionError(
                f"unknown FrameNet core type {core_type_value!r} in frame {frame_name}"
            )
        core_type = cast(FrameNetCoreType, core_type_value)
        frame_elements.append(
            FrameNetFrameElementV1(
                frame_element_id=_integer_attr(
                    element, "ID", context=f"frame element in frame {frame_name}"
                ),
                name=_required_attr(element, "name", context=f"frame element in frame {frame_name}"),
                abbreviation=element.get("abbrev") or "",
                core_type=core_type,
                definition=_required_definition(
                    element,
                    namespace,
                    context=f"frame element in frame {frame_name}",
                ),
                semantic_types=semantic_types,
            )
        )
    lexical_units: list[FrameNetLexicalUnitV1] = []
    for unit in root.findall(f"{{{namespace}}}lexUnit"):
        lexical_unit_id = _integer_attr(
            unit, "ID", context=f"lexical unit in frame {frame_name}"
        )
        name = _required_attr(unit, "name", context=f"lexical unit in frame {frame_name}")
        status = _required_attr(
            unit, "status", context=f"lexical unit in frame {frame_name}"
        )
        indexed = indexed_lexical_units.get(lexical_unit_id)
        if indexed is not None and (
            indexed.frame_id != frame_id
            or indexed.frame_name != frame_name
            or indexed.name != name
            or indexed.status != status
        ):
            raise FrameNetProjectionError(
                f"FrameNet lexical-unit index/content mismatch: {lexical_unit_id}"
            )
        if indexed is None and status != "Problem":
            raise FrameNetProjectionError(
                f"non-Problem lexical unit missing from index: {lexical_unit_id}"
            )
        lexical_units.append(
            FrameNetLexicalUnitV1(
                lexical_unit_id=lexical_unit_id,
                name=name,
                part_of_speech=_required_attr(
                    unit, "POS", context=f"lexical unit in frame {frame_name}"
                ),
                status=status,
                definition=_definition(unit, namespace),
                indexed_for_lookup=indexed is not None,
            )
        )
    return _FrameParts(
        frame_id=frame_id,
        name=frame_name,
        definition=frame_definition,
        frame_elements=tuple(frame_elements),
        lexical_units=tuple(lexical_units),
        source_ref=_source_ref(
            source_key=source_key,
            archive_sha256=archive_sha256,
            member_path=member_path,
            payload=payload,
        ),
    )


def _parse_frame_index(payload: bytes) -> tuple[tuple[int, str], ...]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FrameNetProjectionError("invalid FrameNet frameIndex.xml") from exc
    namespace = _require_framenet_namespace(root, context="frameIndex.xml")
    records = tuple(
        (
            _integer_attr(item, "ID", context="frame index entry"),
            _required_attr(item, "name", context="frame index entry"),
        )
        for item in root.findall(f"{{{namespace}}}frame")
    )
    if not records:
        raise FrameNetProjectionError("FrameNet frame index contains no frames")
    ids = [record[0] for record in records]
    names = [record[1] for record in records]
    if len(ids) != len(set(ids)) or len(names) != len(set(names)):
        raise FrameNetProjectionError("FrameNet frame index IDs and names must be unique")
    return records


def _parse_relations(
    payload: bytes,
    *,
    source_ref: FrameNetSourceRefV1,
    frames_by_id: dict[int, _FrameParts],
) -> tuple[
    dict[int, list[FrameNetFrameRelationRefV1]],
    dict[int, list[FrameNetFrameRelationRefV1]],
    int,
]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FrameNetProjectionError("invalid FrameNet frRelation.xml") from exc
    namespace = _require_framenet_namespace(root, context="frRelation.xml")
    incoming: dict[int, list[FrameNetFrameRelationRefV1]] = {
        frame_id: [] for frame_id in frames_by_id
    }
    outgoing: dict[int, list[FrameNetFrameRelationRefV1]] = {
        frame_id: [] for frame_id in frames_by_id
    }
    relation_keys: set[tuple[int, int]] = set()
    relation_ids: set[int] = set()
    relation_type_ids: set[int] = set()
    relation_type_names: set[str] = set()
    for relation_type in root.findall(f"{{{namespace}}}frameRelationType"):
        relation_type_id = _integer_attr(relation_type, "ID", context="frame relation type")
        relation_type_name = _required_attr(
            relation_type, "name", context=f"frame relation type {relation_type_id}"
        )
        if relation_type_id in relation_type_ids or relation_type_name in relation_type_names:
            raise FrameNetProjectionError("duplicate FrameNet relation-type identity")
        relation_type_ids.add(relation_type_id)
        relation_type_names.add(relation_type_name)
        sub_frame_role = _required_attr(
            relation_type, "subFrameName", context=f"frame relation type {relation_type_id}"
        )
        super_frame_role = _required_attr(
            relation_type, "superFrameName", context=f"frame relation type {relation_type_id}"
        )
        for relation in relation_type.findall(f"{{{namespace}}}frameRelation"):
            relation_id = _integer_attr(relation, "ID", context="frame relation")
            relation_key = (relation_type_id, relation_id)
            if relation_key in relation_keys or relation_id in relation_ids:
                raise FrameNetProjectionError("duplicate FrameNet relation ID")
            relation_keys.add(relation_key)
            relation_ids.add(relation_id)
            sub_id = _integer_attr(relation, "subID", context=f"frame relation {relation_id}")
            super_id = _integer_attr(relation, "supID", context=f"frame relation {relation_id}")
            sub_name = _required_attr(
                relation, "subFrameName", context=f"frame relation {relation_id}"
            )
            super_name = _required_attr(
                relation, "superFrameName", context=f"frame relation {relation_id}"
            )
            sub_frame = frames_by_id.get(sub_id)
            super_frame = frames_by_id.get(super_id)
            if sub_frame is None or super_frame is None:
                raise FrameNetProjectionError(f"dangling FrameNet relation {relation_id}")
            if sub_frame.name != sub_name or super_frame.name != super_name:
                raise FrameNetProjectionError(f"FrameNet relation {relation_id} endpoint name drift")
            sub_elements = {
                item.frame_element_id: item.name for item in sub_frame.frame_elements
            }
            super_elements = {
                item.frame_element_id: item.name for item in super_frame.frame_elements
            }
            fe_relations = tuple(
                sorted(
                    (
                        FrameNetFrameElementRelationV1(
                            frame_element_relation_id=_integer_attr(
                                item, "ID", context=f"FE relation under {relation_id}"
                            ),
                            sub_frame_element_id=_integer_attr(
                                item, "subID", context=f"FE relation under {relation_id}"
                            ),
                            sub_frame_element_name=_required_attr(
                                item, "subFEName", context=f"FE relation under {relation_id}"
                            ),
                            super_frame_element_id=_integer_attr(
                                item, "supID", context=f"FE relation under {relation_id}"
                            ),
                            super_frame_element_name=_required_attr(
                                item, "superFEName", context=f"FE relation under {relation_id}"
                            ),
                        )
                        for item in relation.findall(f"{{{namespace}}}FERelation")
                    ),
                    key=lambda item: item.frame_element_relation_id,
                )
            )
            for fe_relation in fe_relations:
                if (
                    sub_elements.get(fe_relation.sub_frame_element_id)
                    != fe_relation.sub_frame_element_name
                    or super_elements.get(fe_relation.super_frame_element_id)
                    != fe_relation.super_frame_element_name
                ):
                    raise FrameNetProjectionError(
                        f"dangling FrameNet FE relation {fe_relation.frame_element_relation_id}"
                    )
            outgoing[sub_id].append(
                FrameNetFrameRelationRefV1(
                    frame_relation_id=relation_id,
                    relation_type_id=relation_type_id,
                    relation_type_name=relation_type_name,
                    direction="outgoing",
                    related_frame_id=super_id,
                    related_frame_name=super_name,
                    containing_frame_role=sub_frame_role,
                    related_frame_role=super_frame_role,
                    frame_element_relations=fe_relations,
                    source_ref=source_ref,
                )
            )
            incoming[super_id].append(
                FrameNetFrameRelationRefV1(
                    frame_relation_id=relation_id,
                    relation_type_id=relation_type_id,
                    relation_type_name=relation_type_name,
                    direction="incoming",
                    related_frame_id=sub_id,
                    related_frame_name=sub_name,
                    containing_frame_role=super_frame_role,
                    related_frame_role=sub_frame_role,
                    frame_element_relations=fe_relations,
                    source_ref=source_ref,
                )
            )
    return incoming, outgoing, len(relation_keys)


def _relation_sort_key(item: FrameNetFrameRelationRefV1) -> tuple[int, int, int]:
    return item.relation_type_id, item.frame_relation_id, item.related_frame_id


def compile_framenet_projection_v1(
    manifest: LinguisticSourceManifestV1,
    *,
    source_archive: Path,
) -> FrameNetProjectionV1:
    """Compile a complete, referentially closed projection from exact archive bytes."""

    source = next((item for item in manifest.sources if item.family == "framenet"), None)
    if source is None or source.archive_identity is None or source.availability != "available":
        raise FrameNetProjectionError("manifest lacks an available FrameNet archive source")
    verify_linguistic_source_manifest_v1(
        LinguisticSourceManifestV1(sources=(source,)),
        source_roots={source.source_key: source_archive},
    )
    archive = source.archive_identity
    prefix = f"{Path(archive.archive_filename).stem}/"
    index_path = f"{prefix}frameIndex.xml"
    lexical_unit_index_path = f"{prefix}luIndex.xml"
    relation_path = f"{prefix}frRelation.xml"
    try:
        with zipfile.ZipFile(source_archive) as source_zip:
            member_names = source_zip.namelist()
            if len(member_names) != len(set(member_names)):
                raise FrameNetProjectionError("FrameNet archive contains duplicate member paths")
            names = set(member_names)
            if (
                index_path not in names
                or lexical_unit_index_path not in names
                or relation_path not in names
            ):
                raise FrameNetProjectionError("FrameNet archive lacks required index members")
            index_payload = source_zip.read(index_path)
            lexical_unit_index_payload = source_zip.read(lexical_unit_index_path)
            relation_payload = source_zip.read(relation_path)
            index_records = _parse_frame_index(index_payload)
            indexed_lexical_units = _parse_lexical_unit_index(lexical_unit_index_payload)
            expected_members = {f"{prefix}frame/{name}.xml" for _frame_id, name in index_records}
            observed_members = {
                name
                for name in names
                if name.startswith(f"{prefix}frame/") and name.endswith(".xml")
            }
            if expected_members != observed_members:
                missing = sorted(expected_members - observed_members)
                extra = sorted(observed_members - expected_members)
                raise FrameNetProjectionError(
                    f"FrameNet frame index/member mismatch missing={missing[:3]} extra={extra[:3]}"
                )
            parsed_by_id: dict[int, _FrameParts] = {}
            for expected_id, expected_name in index_records:
                member_path = f"{prefix}frame/{expected_name}.xml"
                parsed = _parse_frame(
                    source_zip.read(member_path),
                    member_path=member_path,
                    source_key=source.source_key,
                    archive_sha256=archive.sha256,
                    indexed_lexical_units=indexed_lexical_units,
                )
                if parsed.frame_id != expected_id or parsed.name != expected_name:
                    raise FrameNetProjectionError(
                        f"FrameNet frame index/content mismatch: {member_path}"
                    )
                if parsed.frame_id in parsed_by_id:
                    raise FrameNetProjectionError("duplicate FrameNet frame ID")
                parsed_by_id[parsed.frame_id] = parsed
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise FrameNetProjectionError("unable to read exact FrameNet archive") from exc

    relation_ref = _source_ref(
        source_key=source.source_key,
        archive_sha256=archive.sha256,
        member_path=relation_path,
        payload=relation_payload,
    )
    incoming, outgoing, relation_count = _parse_relations(
        relation_payload,
        source_ref=relation_ref,
        frames_by_id=parsed_by_id,
    )
    embedded_lexical_unit_ids = {
        unit.lexical_unit_id
        for frame in parsed_by_id.values()
        for unit in frame.lexical_units
    }
    if set(indexed_lexical_units) - embedded_lexical_unit_ids:
        raise FrameNetProjectionError("FrameNet lexical-unit index has no embedded declaration")
    frames = tuple(
        FrameNetFrameRecordV1(
            frame_id=parts.frame_id,
            name=parts.name,
            definition=parts.definition,
            frame_elements=parts.frame_elements,
            lexical_units=parts.lexical_units,
            incoming_relations=tuple(sorted(incoming[parts.frame_id], key=_relation_sort_key)),
            outgoing_relations=tuple(sorted(outgoing[parts.frame_id], key=_relation_sort_key)),
            source_ref=parts.source_ref,
        )
        for parts in sorted(parsed_by_id.values(), key=lambda item: item.frame_id)
    )
    content = [frame.model_dump(mode="json") for frame in frames]
    return FrameNetProjectionV1(
        source_key=source.source_key,
        source_archive_filename=archive.archive_filename,
        source_archive_sha256=archive.sha256,
        source_archive_byte_count=archive.byte_count,
        frame_index_ref=_source_ref(
            source_key=source.source_key,
            archive_sha256=archive.sha256,
            member_path=index_path,
            payload=index_payload,
        ),
        lexical_unit_index_ref=_source_ref(
            source_key=source.source_key,
            archive_sha256=archive.sha256,
            member_path=lexical_unit_index_path,
            payload=lexical_unit_index_payload,
        ),
        relation_index_ref=relation_ref,
        projection_content_sha256=_normalized_sha256(content),
        frame_count=len(frames),
        frame_element_count=sum(len(frame.frame_elements) for frame in frames),
        lexical_unit_declaration_count=sum(len(frame.lexical_units) for frame in frames),
        indexed_lexical_unit_count=sum(
            unit.indexed_for_lookup for frame in frames for unit in frame.lexical_units
        ),
        frame_relation_count=relation_count,
        frame_element_relation_count=sum(
            len(relation.frame_element_relations)
            for frame in frames
            for relation in frame.outgoing_relations
        ),
        frames=frames,
    )


def load_framenet_projection_v1(path: Path) -> FrameNetProjectionV1:
    """Load one strict projection from JSON or deterministic gzip JSON."""

    payload = path.read_bytes()
    if path.suffix == ".gz":
        try:
            payload = gzip.decompress(payload)
        except gzip.BadGzipFile as exc:
            raise FrameNetProjectionError("invalid gzip FrameNet projection") from exc
    try:
        return FrameNetProjectionV1.model_validate_json(payload)
    except ValueError as exc:
        raise FrameNetProjectionError("invalid FrameNet projection content") from exc
