"""Strict pack-backed Predicate Canon lineage inspection.

This module reads traceability-only assets and never participates in runtime
alias loading. It supports canonical and source identifiers without requiring
the historical donor database.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .semantic_provenance import (
    SemanticMappingRecord,
    SemanticSourceDescriptor,
    SemanticSourcesDocument,
)


class CanonLineageInspectionError(RuntimeError):
    """Raised when a pack or requested lineage identifier is unavailable."""


class CanonLineageQuery(BaseModel):
    """Exact identifier used for one lineage inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["canonical_id", "source_id"]
    identifier: str = Field(min_length=1)


class CanonLineageReport(BaseModel):
    """Typed traceability-only matches for one canonical or source identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["predicate_canon_lineage_report.v1"]
    pack_id: Literal["linguistic_core"]
    pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    query: CanonLineageQuery
    sources: tuple[SemanticSourceDescriptor, ...]
    mappings: tuple[SemanticMappingRecord, ...] = Field(min_length=1)
    runtime_aliases_used: Literal[False] = False

    @model_validator(mode="after")
    def _matches_query(self) -> "CanonLineageReport":
        """Prevent a report from claiming matches unrelated to its query."""

        field = "canonical_id" if self.query.kind == "canonical_id" else "source_id"
        if any(getattr(mapping, field) != self.query.identifier for mapping in self.mappings):
            raise ValueError("every mapping must match the declared lineage query")
        source_keys = {source.source_key for source in self.sources}
        if source_keys != {mapping.source_key for mapping in self.mappings}:
            raise ValueError("sources must exactly describe matched mapping source keys")
        return self


def inspect_pack_lineage(
    pack_dir: Path,
    *,
    canonical_id: str | None = None,
    source_id: str | None = None,
) -> CanonLineageReport:
    """Resolve exactly one canonical/source query from strict packaged assets."""

    if (canonical_id is None) == (source_id is None):
        raise CanonLineageInspectionError("pass exactly one of canonical_id or source_id")
    manifest_path = pack_dir / "manifest.yaml"
    sources_path = pack_dir / "semantic_sources.yaml"
    mappings_path = pack_dir / "semantic_mappings.jsonl"
    for path in (manifest_path, sources_path, mappings_path):
        if not path.is_file():
            raise CanonLineageInspectionError(f"CANON_LINEAGE_PACK_ASSET_MISSING path={path}")
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CanonLineageInspectionError("CANON_LINEAGE_INVALID_MANIFEST") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("pack"), dict):
        raise CanonLineageInspectionError("CANON_LINEAGE_INVALID_MANIFEST")
    pack = manifest["pack"]
    provenance = manifest.get("provenance")
    build = manifest.get("build")
    if provenance != {
        "schema_version": "predicate_canon_provenance_assets.v1",
        "semantic_sources": "semantic_sources.yaml",
        "semantic_mappings": "semantic_mappings.jsonl",
        "predicate_canon_index": "predicate_canon_index.jsonl",
    } or not isinstance(build, dict):
        raise CanonLineageInspectionError("CANON_LINEAGE_INVALID_PROVENANCE_MANIFEST")
    declared_hashes = build.get("artifact_sha256")
    if not isinstance(declared_hashes, dict):
        raise CanonLineageInspectionError("CANON_LINEAGE_MISSING_ARTIFACT_HASHES")
    for path in (sources_path, mappings_path):
        expected_hash = declared_hashes.get(path.name)
        try:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise CanonLineageInspectionError(
                f"CANON_LINEAGE_ARTIFACT_READ_ERROR filename={path.name}"
            ) from exc
        if not isinstance(expected_hash, str) or actual_hash != expected_hash:
            raise CanonLineageInspectionError(
                f"CANON_LINEAGE_ARTIFACT_HASH_MISMATCH filename={path.name}"
            )
    try:
        sources_document = SemanticSourcesDocument.model_validate(
            yaml.safe_load(sources_path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise CanonLineageInspectionError("CANON_LINEAGE_INVALID_SOURCE_REGISTRY") from exc
    if (
        pack.get("id") != "linguistic_core"
        or pack.get("version") != pack_dir.name
        or sources_document.pack_id != pack.get("id")
        or sources_document.pack_version != pack.get("version")
    ):
        raise CanonLineageInspectionError("CANON_LINEAGE_PACK_IDENTITY_MISMATCH")

    query = CanonLineageQuery(
        kind="canonical_id" if canonical_id is not None else "source_id",
        identifier=canonical_id if canonical_id is not None else str(source_id),
    )
    field = query.kind
    mappings: list[SemanticMappingRecord] = []
    try:
        mapping_lines = mappings_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CanonLineageInspectionError("CANON_LINEAGE_INVALID_MAPPING encoding_or_read") from exc
    for line_number, line in enumerate(mapping_lines, 1):
        try:
            mapping = SemanticMappingRecord.model_validate_json(line)
        except ValueError as exc:
            raise CanonLineageInspectionError(
                f"CANON_LINEAGE_INVALID_MAPPING line={line_number}"
            ) from exc
        if getattr(mapping, field) == query.identifier:
            mappings.append(mapping)
    if not mappings:
        raise CanonLineageInspectionError(
            f"CANON_LINEAGE_UNKNOWN_{query.kind.upper()} identifier={query.identifier}"
        )
    descriptor_by_key = {
        sources_document.direct_build_input.source_key: sources_document.direct_build_input,
        **{source.source_key: source for source in sources_document.semantic_sources},
    }
    source_keys = sorted({mapping.source_key for mapping in mappings})
    try:
        sources = tuple(descriptor_by_key[source_key] for source_key in source_keys)
    except KeyError as exc:
        raise CanonLineageInspectionError(
            f"CANON_LINEAGE_UNDECLARED_SOURCE source_key={exc.args[0]}"
        ) from exc
    return CanonLineageReport(
        schema_version="predicate_canon_lineage_report.v1",
        pack_id="linguistic_core",
        pack_version=str(pack["version"]),
        query=query,
        sources=sources,
        mappings=tuple(mappings),
    )


def render_lineage_report_text(report: CanonLineageReport) -> str:
    """Render a compact report while preserving source-verification boundaries."""

    lines = [
        f"pack: {report.pack_id}@{report.pack_version}",
        f"query: {report.query.kind}={report.query.identifier}",
        "runtime_aliases_used: no",
        "mappings:",
    ]
    for mapping in report.mappings:
        lines.append(
            f"  - {mapping.canonical_id} <- {mapping.source_key}:{mapping.source_id} "
            f"({mapping.relation}; source_verified=no)"
        )
    return "\n".join(lines)
