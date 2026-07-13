"""Compile the linguistic_core ontology pack from sumo_plus.db.

Reads the ``predicates`` and ``role_slots`` tables from ``sumo_plus.db`` and
emits the ``linguistic_core/<version>/`` pack files:

- ``predicate_types.jsonl`` — 4,669 predicates with semantic metadata
- ``role_types.jsonl`` — 11,890 role slots with FrameNet named labels
- ``predicate_role_edges.jsonl`` — predicate-specific role-slot declarations
- ``entity_types.jsonl`` — SUMO role-filler types referenced by role slots,
  plus their full SUMO ancestor closure (Plan 0116 Slice A)
- ``hierarchy_edges.jsonl`` — ``subtype_of`` edges over that closure so
  ancestor-aware validation can run from the exported pack, not the raw DB
- ``source_mappings.jsonl`` — provenance: predicate → PropBank sense,
  role slot → PropBank ARG position
- ``semantic_sources.yaml`` — byte-bound donor plus honest external-source states
- ``semantic_mappings.jsonl`` — traceability-only donor/PropBank/FrameNet/SUMO rows
- ``manifest.yaml`` — pack identity and content inventory

The pack uses the ``lc:`` namespace for predicates and ``lc.role.`` namespace
for role types. ARG positions (ARG0, ARG1, ...) appear only in source_mappings
as provenance; all semantic identifiers use named_label values.

Usage::

    python scripts/compile_linguistic_core_pack.py [--db PATH] [--output DIR]
        [--pack-version VERSION] [--build-timestamp RFC3339] [--dry-run]

Examples::

    python scripts/compile_linguistic_core_pack.py
    python scripts/compile_linguistic_core_pack.py --pack-version 0.3.0 \
        --build-timestamp 2026-07-12T19:00:00Z \
        --output ontology_packs/linguistic_core/0.3.0
    python scripts/compile_linguistic_core_pack.py --dry-run
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import re
import tempfile
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote

import yaml

# Allow running as a script from the repo root.
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from onto_canon6.packs.role_slots_lookup import (  # type: ignore[import-untyped]  # noqa: E402
    RoleSlotsError,
    RoleSlotsLookup,
)
from onto_canon6.packs.semantic_provenance import (  # type: ignore[import-untyped]  # noqa: E402
    SemanticMappingRecord,
    SemanticSourcesDocument,
    compile_predicate_provenance,
    compile_semantic_sources_document,
)

_DEFAULT_DB = _REPO_ROOT / "data" / "sumo_plus.db"
_PACK_VERSION = "0.2.0"
_COMPILER_VERSION = "0.1.0"
_SUCCESSOR_COMPILER_VERSION = "0.2.0"
_CANONICAL_020_BUILT_AT = "2026-07-07T05:05:15Z"
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_RUNTIME_FILENAMES = (
    "aliases.jsonl",
    "constraints.jsonl",
    "entity_types.jsonl",
    "hierarchy_edges.jsonl",
    "predicate_role_edges.jsonl",
    "predicate_types.jsonl",
    "role_types.jsonl",
    "source_mappings.jsonl",
    "value_types.jsonl",
)
_PROVENANCE_FILENAMES = ("semantic_mappings.jsonl", "semantic_sources.yaml")
_CANONICAL_DONOR_FRAMENET_MAPPING_COUNT = 2263
_RELEASE_SEMANTIC_MAPPING_SHA256 = {
    "0.3.0": "16f18feafe28a2cce14e8e25f417c082f8dd910b2fd6b859b01d337d86b0c6a9",
}


class LinguisticCoreCompileError(RuntimeError):
    """Raised when a linguistic-core build cannot be published atomically."""


class DonorPredicateRow(TypedDict):
    """Validated donor fields consumed by the pack compiler."""

    name: str
    propbank_sense_id: str | None
    lemma: str | None
    description: str | None
    is_static: int


class CompileStats(TypedDict):
    """Deterministic row counts emitted by one compiler run."""

    predicate_count: int
    role_slot_count: int
    role_type_count: int
    entity_type_count: int
    hierarchy_edge_count: int
    predicate_role_edge_count: int
    constraint_count: int
    source_mapping_count: int
    semantic_mapping_count: int
    blank_named_label_count: int


def _normalize_predicate_row(raw: dict[str, object]) -> DonorPredicateRow:
    """Validate the donor fields consumed by runtime-row compilation."""

    name = raw.get("name")
    is_static = raw.get("is_static")
    if not isinstance(name, str) or not name.strip():
        raise LinguisticCoreCompileError("predicate row requires non-empty string name")
    if not isinstance(is_static, int) or isinstance(is_static, bool):
        raise LinguisticCoreCompileError(f"predicate {name} requires integer is_static")
    normalized_optional: dict[str, str | None] = {}
    for field in ("propbank_sense_id", "lemma", "description"):
        value = raw.get(field)
        if value is not None and not isinstance(value, str):
            raise LinguisticCoreCompileError(f"predicate {name} field {field} must be string/null")
        normalized_optional[field] = value
    return DonorPredicateRow(
        name=name,
        propbank_sense_id=normalized_optional["propbank_sense_id"],
        lemma=normalized_optional["lemma"],
        description=normalized_optional["description"],
        is_static=is_static,
    )


def _validate_pack_version(value: str) -> str:
    """Return one exact semantic version or fail before producing files."""

    if not _VERSION_RE.fullmatch(value):
        raise LinguisticCoreCompileError(f"invalid pack version: {value!r}")
    return value


def _resolve_build_timestamp(*, pack_version: str, build_timestamp: str | None) -> str:
    """Resolve an explicit reproducible UTC timestamp without consulting wall clock."""

    candidate = build_timestamp
    if candidate is None and (source_date_epoch := os.environ.get("SOURCE_DATE_EPOCH")):
        try:
            epoch = int(source_date_epoch)
        except ValueError as exc:
            raise LinguisticCoreCompileError("SOURCE_DATE_EPOCH must be an integer") from exc
        candidate = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if candidate is None and pack_version == _PACK_VERSION:
        candidate = _CANONICAL_020_BUILT_AT
    if candidate is None:
        raise LinguisticCoreCompileError(
            "non-legacy pack builds require --build-timestamp or SOURCE_DATE_EPOCH"
        )
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LinguisticCoreCompileError(
            f"build timestamp must be RFC3339 UTC: {candidate!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise LinguisticCoreCompileError("build timestamp must carry UTC timezone")
    if parsed.microsecond:
        raise LinguisticCoreCompileError("build timestamp must have whole-second precision")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _predicate_id(name: str) -> str:
    """Return the lc-namespaced predicate ID."""
    return f"lc:{name}"


def _role_id(named_label: str) -> str:
    """Return the lc.role-namespaced role ID from a FrameNet named label.

    Examples::

        _role_id("Supplier")     → "lc.role.supplier"
        _role_id("Imposed_purpose") → "lc.role.imposed_purpose"
    """
    return f"lc.role.{named_label.lower()}"


def _family(is_static: int) -> str:
    """Return 'state' for static predicates, 'event' for dynamic ones."""
    return "state" if is_static else "event"


def compile_pack(
    db_path: Path,
    output_dir: Path,
    *,
    pack_version: str = _PACK_VERSION,
    build_timestamp: str | None = None,
    dry_run: bool = False,
) -> CompileStats:
    """Compile the linguistic_core pack and write files to output_dir.

    Parameters
    ----------
    db_path:
        Path to sumo_plus.db.
    output_dir:
        Directory to write pack files into (created if it does not exist).
    dry_run:
        If True, compute all data but do not write files. Returns stats.

    Returns
    -------
    dict
        Statistics: predicate_count, role_slot_count, source_mapping_count,
        blank_named_label_count.

    Raises
    ------
    RoleSlotsError:
        If the database is missing or malformed.
    SystemExit:
        If any named_label values are blank (fail loud).
    """
    normalized_version = _validate_pack_version(pack_version)
    normalized_timestamp = _resolve_build_timestamp(
        pack_version=normalized_version,
        build_timestamp=build_timestamp,
    )
    if not dry_run and output_dir.exists():
        raise LinguisticCoreCompileError(
            f"output target already exists; refusing partial/overwrite build: {output_dir}"
        )

    with RoleSlotsLookup(db_path) as lookup:
        predicates = [_normalize_predicate_row(row) for row in lookup.all_predicates()]
        predicate_count = len(predicates)

        # --- predicate_types.jsonl ---
        predicate_rows: list[dict[str, object]] = []
        for pred in predicates:
            predicate_rows.append({
                "predicate_id": _predicate_id(pred["name"]),
                "family": _family(pred["is_static"]),
                "preferred_label": pred["lemma"] or pred["name"],
                "description": pred["description"] or "",
                "status": "active",
            })

        # --- role_types.jsonl + predicate_role_edges + constraints + source_mappings ---
        seen_role_ids: set[str] = set()
        seen_entity_type_ids: set[str] = set()
        role_rows: list[dict[str, object]] = []
        entity_type_rows: list[dict[str, object]] = []
        predicate_role_edge_rows: list[dict[str, object]] = []
        constraint_rows: list[dict[str, object]] = []
        source_mapping_rows: list[dict[str, object]] = []
        blank_count = 0

        # Predicate-level source mappings (predicate → PropBank sense)
        for pred in predicates:
            if pred["propbank_sense_id"]:
                source_mapping_rows.append({
                    "canonical_id": _predicate_id(pred["name"]),
                    "canonical_kind": "predicate_type",
                    "source_system": "propbank_nltk",
                    "source_id": pred["propbank_sense_id"],
                    "pack_predicate_id": _predicate_id(pred["name"]),
                    "mapping_type": "derived_from",
                    "confidence": "corpus_derived",
                })

        # Role-slot rows and per-slot source mappings
        for pred in predicates:
            roles = lookup.roles_for_predicate(pred["name"])
            for slot in roles:
                if not slot.named_label or not slot.named_label.strip():
                    blank_count += 1
                    warnings.warn(
                        f"Blank named_label for {slot.predicate_id} {slot.arg_position}",
                        stacklevel=2,
                    )
                    continue

                rid = _role_id(slot.named_label)
                if rid not in seen_role_ids:
                    seen_role_ids.add(rid)
                    role_rows.append({
                        "role_id": rid,
                        "runtime_name": slot.named_label.lower(),
                        "preferred_label": slot.named_label,
                        "status": "active",
                    })

                required = bool(slot.required)
                predicate_role_edge_rows.append({
                    "predicate_id": _predicate_id(pred["name"]),
                    "role_id": rid,
                    "required": required,
                    "min_count": 1 if required else 0,
                    "max_count": 1,
                })

                if slot.type_constraint and slot.type_constraint.strip():
                    type_id = _sumo_type_id(slot.type_constraint)
                    if type_id not in seen_entity_type_ids:
                        seen_entity_type_ids.add(type_id)
                        entity_type_rows.append({
                            "type_id": type_id,
                            "preferred_label": slot.type_constraint,
                            "status": "active",
                        })
                    constraint_rows.append({
                        "constraint_type": "role_expected_entity_type",
                        "predicate_id": _predicate_id(pred["name"]),
                        "role_id": rid,
                        "expected_type": type_id,
                    })

                # Per-slot source mapping: predicate+role → PropBank ARG position
                if pred["propbank_sense_id"]:
                    source_mapping_rows.append({
                        "canonical_id": f"{_predicate_id(pred['name'])}:{rid}",
                        "canonical_kind": "role_slot",
                        "source_system": "propbank_nltk",
                        "source_id": f"{pred['propbank_sense_id']}:{slot.arg_position}",
                        "mapping_type": "positional_role",
                        "confidence": "corpus_derived",
                        "notes": f"Semantic role: {slot.named_label}",
                    })

        role_slot_count = lookup.role_slot_count()

    if blank_count > 0:
        print(f"ERROR: {blank_count} blank named_label values found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Plan 0116 Slice A: ancestor-close the role-filler types and export the
    # SUMO hierarchy so pack-based validation can be ancestor-aware.
    seed_type_names = {str(row["preferred_label"]) for row in entity_type_rows}
    ancestor_rows, hierarchy_edge_rows = _build_hierarchy(db_path, seed_type_names)
    entity_type_rows = entity_type_rows + ancestor_rows

    semantic_sources_document = None
    semantic_mapping_rows: list[dict[str, object]] = []
    if normalized_version != _PACK_VERSION:
        semantic_sources_document = compile_semantic_sources_document(
            db_path,
            pack_version=normalized_version,
        )
        for pred in predicates:
            predicate_name = str(pred["name"])
            bundle = compile_predicate_provenance(db_path, predicate_id=predicate_name)
            semantic_mapping_rows.extend(
                mapping.model_dump(mode="json") for mapping in bundle.mappings
            )
        for edge in hierarchy_edge_rows:
            child_id = str(edge["child_id"])
            parent_id = str(edge["parent_id"])
            child_name = child_id.removeprefix("lc:sumo_type.")
            parent_name = parent_id.removeprefix("lc:sumo_type.")
            semantic_mapping_rows.append(
                SemanticMappingRecord(
                    canonical_id=f"{child_id}:subtype_of:{parent_id}",
                    canonical_kind="hierarchy_edge",
                    source_key="sumo_donor_types",
                    source_id=f"{child_name}:subclass_of:{parent_name}",
                    relation="subtype_of",
                    derivation_method="donor_asserted",
                    confidence_basis="donor type_hierarchy row exported into the pack closure",
                    evidence_ref=(
                        f"sqlite:type_hierarchy[child={child_name},parent={parent_name}]"
                    ),
                ).model_dump(mode="json")
            )
        semantic_mapping_rows.sort(key=_semantic_mapping_sort_key)

    stats = CompileStats(
        predicate_count=predicate_count,
        role_slot_count=role_slot_count,
        role_type_count=len(role_rows),
        entity_type_count=len(entity_type_rows),
        hierarchy_edge_count=len(hierarchy_edge_rows),
        predicate_role_edge_count=len(predicate_role_edge_rows),
        constraint_count=len(constraint_rows),
        source_mapping_count=len(source_mapping_rows),
        semantic_mapping_count=len(semantic_mapping_rows),
        blank_named_label_count=blank_count,
    )

    if dry_run:
        return stats

    runtime_rows: dict[str, list[dict[str, object]]] = {
        "aliases.jsonl": [],
        "constraints.jsonl": constraint_rows,
        "entity_types.jsonl": entity_type_rows,
        "hierarchy_edges.jsonl": hierarchy_edge_rows,
        "predicate_role_edges.jsonl": predicate_role_edge_rows,
        "predicate_types.jsonl": predicate_rows,
        "role_types.jsonl": role_rows,
        "source_mappings.jsonl": source_mapping_rows,
        "value_types.jsonl": [],
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output_dir.parent,
        prefix=f".{output_dir.name}.build-",
    ) as temporary_root:
        stage_dir = Path(temporary_root) / output_dir.name
        stage_dir.mkdir()
        for filename in _RUNTIME_FILENAMES:
            _write_jsonl(stage_dir / filename, runtime_rows[filename])

        if semantic_sources_document is not None:
            _write_jsonl(stage_dir / "semantic_mappings.jsonl", semantic_mapping_rows)
            _write_yaml(
                stage_dir / "semantic_sources.yaml",
                semantic_sources_document.model_dump(mode="json"),
            )

        artifact_filenames = list(_RUNTIME_FILENAMES)
        if semantic_sources_document is not None:
            artifact_filenames.extend(_PROVENANCE_FILENAMES)
        artifact_sha256 = {
            filename: _sha256_file(stage_dir / filename)
            for filename in sorted(artifact_filenames)
        }
        source_input: dict[str, object] = {
            "system": "onto_canon_sumo_plus",
            "version": "2026-02-15",
            "path": "data/sumo_plus.db",
        }
        build_block: dict[str, object] = {
            "compiler_version": (
                _SUCCESSOR_COMPILER_VERSION
                if normalized_version != _PACK_VERSION
                else _COMPILER_VERSION
            ),
            "built_at": normalized_timestamp,
            "source_inputs": [source_input],
        }
        manifest: dict[str, object] = {
            "pack": {
                "id": "linguistic_core",
                "version": normalized_version,
                "name": "linguistic_core",
                "description": (
                    "Foundational predicate vocabulary compiled from the predecessor Predicate "
                    "Canon with donor-derived PropBank identifiers, FrameNet candidate alignments, "
                    "and SUMO type lineage. Provides 4,669 predicates and 11,890 semantic role "
                    "slots; historical upstream versions remain explicit unknowns."
                    if normalized_version != _PACK_VERSION
                    else "Foundational predicate vocabulary synthesized from PropBank, FrameNet, "
                    "and SUMO. Provides 4,669 predicates and 11,890 semantic role slots "
                    "for use as the base pack from which domain packs extend."
                ),
            },
            "build": build_block,
            "capabilities": {
                "assertion_type": "n-ary",
                "type_system": "sumo",
            },
            "content": {
                "entity_types": "entity_types.jsonl",
                "predicate_types": "predicate_types.jsonl",
                "role_types": "role_types.jsonl",
                "value_types": "value_types.jsonl",
                "hierarchy_edges": "hierarchy_edges.jsonl",
                "predicate_role_edges": "predicate_role_edges.jsonl",
                "source_mappings": "source_mappings.jsonl",
                "aliases": "aliases.jsonl",
                "constraints": "constraints.jsonl",
            },
        }
        if semantic_sources_document is not None:
            direct_source = semantic_sources_document.direct_build_input
            source_input.update(
                version=direct_source.resource_version,
                version_status=direct_source.resource_version_status,
                artifact_sha256=direct_source.artifact_sha256,
            )
            build_block["artifact_sha256"] = artifact_sha256
            manifest["provenance"] = {
                "schema_version": "predicate_canon_provenance_assets.v1",
                "semantic_sources": "semantic_sources.yaml",
                "semantic_mappings": "semantic_mappings.jsonl",
            }
        _write_yaml(stage_dir / "manifest.yaml", manifest)
        validate_compiled_pack(stage_dir, require_provenance=semantic_sources_document is not None)
        if output_dir.exists():
            raise LinguisticCoreCompileError(
                f"output target appeared during build; refusing overwrite: {output_dir}"
            )
        stage_dir.replace(output_dir)

    return stats


def _semantic_mapping_sort_key(row: dict[str, object]) -> tuple[str, ...]:
    """Return the complete stable ordering key for one traceability row."""

    return tuple(
        str(row.get(field, ""))
        for field in (
            "canonical_kind",
            "canonical_id",
            "source_key",
            "relation",
            "source_id",
            "evidence_ref",
        )
    )


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 of exact emitted bytes."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_yaml(path: Path, payload: object) -> None:
    """Write deterministic YAML with stable insertion order and UTF-8 encoding."""

    path.write_text(
        yaml.dump(
            payload,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def validate_compiled_pack(pack_dir: Path, *, require_provenance: bool) -> None:
    """Validate exact artifact inventory, hashes, and strict provenance contracts."""

    manifest_path = pack_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise LinguisticCoreCompileError("compiled pack is missing manifest.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise LinguisticCoreCompileError("compiled manifest must be an object")
    expected_files = {*_RUNTIME_FILENAMES, "manifest.yaml"}
    if require_provenance:
        expected_files.update(_PROVENANCE_FILENAMES)
    actual_files = {path.name for path in pack_dir.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise LinguisticCoreCompileError(
            f"compiled artifact inventory mismatch missing={sorted(expected_files - actual_files)} "
            f"unexpected={sorted(actual_files - expected_files)}"
        )
    if not require_provenance:
        return
    build = manifest.get("build")
    provenance = manifest.get("provenance")
    if not isinstance(build, dict) or not isinstance(provenance, dict):
        raise LinguisticCoreCompileError("successor manifest requires build and provenance objects")
    if provenance != {
        "schema_version": "predicate_canon_provenance_assets.v1",
        "semantic_sources": "semantic_sources.yaml",
        "semantic_mappings": "semantic_mappings.jsonl",
    }:
        raise LinguisticCoreCompileError("unsupported or incomplete provenance manifest")
    declared_hashes = build.get("artifact_sha256")
    if not isinstance(declared_hashes, dict) or set(declared_hashes) != expected_files - {
        "manifest.yaml"
    }:
        raise LinguisticCoreCompileError("artifact hash inventory does not match emitted files")
    for filename, expected_hash in declared_hashes.items():
        if not isinstance(filename, str) or not isinstance(expected_hash, str):
            raise LinguisticCoreCompileError("artifact hashes must map filenames to strings")
        actual_hash = _sha256_file(pack_dir / filename)
        if actual_hash != expected_hash:
            raise LinguisticCoreCompileError(
                f"artifact hash mismatch filename={filename} expected={expected_hash} actual={actual_hash}"
            )
    source_payload = yaml.safe_load(
        (pack_dir / "semantic_sources.yaml").read_text(encoding="utf-8")
    )
    try:
        source_document = SemanticSourcesDocument.model_validate(source_payload)
    except ValueError as exc:
        raise LinguisticCoreCompileError(f"invalid semantic source registry: {exc}") from exc
    pack_block = manifest.get("pack")
    if (
        not isinstance(pack_block, dict)
        or pack_block.get("id") != "linguistic_core"
        or pack_block.get("name") != "linguistic_core"
        or pack_block.get("version") != pack_dir.name
        or source_document.pack_id != "linguistic_core"
        or source_document.pack_version != pack_block.get("version")
    ):
        raise LinguisticCoreCompileError("semantic source registry pack identity mismatch")
    source_inputs = build.get("source_inputs")
    if not isinstance(source_inputs, list) or len(source_inputs) != 1:
        raise LinguisticCoreCompileError("successor manifest requires one direct source input")
    source_input = source_inputs[0]
    direct_source = source_document.direct_build_input
    if not isinstance(source_input, dict) or source_input != {
        "system": direct_source.source_key,
        "version": direct_source.resource_version,
        "path": "data/sumo_plus.db",
        "version_status": direct_source.resource_version_status,
        "artifact_sha256": direct_source.artifact_sha256,
    }:
        raise LinguisticCoreCompileError("manifest direct source input does not match source registry")
    mapping_records: list[SemanticMappingRecord] = []
    for line_number, line in enumerate(
        (pack_dir / "semantic_mappings.jsonl").read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        try:
            mapping_records.append(SemanticMappingRecord.model_validate_json(line))
        except ValueError as exc:
            raise LinguisticCoreCompileError(
                f"invalid semantic mapping line={line_number}: {exc}"
            ) from exc
    source_keys = {
        source_document.direct_build_input.source_key,
        *(source.source_key for source in source_document.semantic_sources),
    }
    if any(mapping.source_key not in source_keys for mapping in mapping_records):
        raise LinguisticCoreCompileError("semantic mapping references an undeclared source key")
    predicate_rows = _read_jsonl(pack_dir / "predicate_types.jsonl")
    role_edge_rows = _read_jsonl(pack_dir / "predicate_role_edges.jsonl")
    entity_rows = _read_jsonl(pack_dir / "entity_types.jsonl")
    hierarchy_rows = _read_jsonl(pack_dir / "hierarchy_edges.jsonl")
    predicate_ids = {str(row["predicate_id"]) for row in predicate_rows}
    role_ids = {
        f"{row['predicate_id']}:{row['role_id']}"
        for row in role_edge_rows
    }
    entity_ids = {str(row["type_id"]) for row in entity_rows}
    hierarchy_ids = {
        f"{row['child_id']}:subtype_of:{row['parent_id']}"
        for row in hierarchy_rows
    }
    allowed_by_kind = {
        "predicate_type": predicate_ids,
        "role_slot": role_ids,
        "entity_type": entity_ids,
        "hierarchy_edge": hierarchy_ids,
    }
    for mapping in mapping_records:
        if mapping.canonical_id not in allowed_by_kind[mapping.canonical_kind]:
            raise LinguisticCoreCompileError(
                f"semantic mapping has dangling {mapping.canonical_kind}: {mapping.canonical_id}"
            )
    emitted_hierarchy_ids = {
        mapping.canonical_id
        for mapping in mapping_records
        if mapping.canonical_kind == "hierarchy_edge"
    }
    if emitted_hierarchy_ids != hierarchy_ids:
        raise LinguisticCoreCompileError("hierarchy provenance does not cover exact runtime edges")
    direct_predicates = {
        mapping.canonical_id
        for mapping in mapping_records
        if mapping.canonical_kind == "predicate_type"
        and mapping.source_key == "onto_canon_sumo_plus"
    }
    if direct_predicates != predicate_ids:
        raise LinguisticCoreCompileError("direct donor provenance does not cover every predicate")
    direct_role_counter = Counter(
        mapping.canonical_id
        for mapping in mapping_records
        if mapping.canonical_kind == "role_slot"
        and mapping.source_key == "onto_canon_sumo_plus"
    )
    runtime_role_counter = Counter(
        f"{row['predicate_id']}:{row['role_id']}" for row in role_edge_rows
    )
    if direct_role_counter != runtime_role_counter:
        raise LinguisticCoreCompileError(
            "direct donor provenance does not preserve every runtime role edge"
        )
    constraint_rows = _read_jsonl(pack_dir / "constraints.jsonl")
    expected_sumo_entity_counter = Counter(
        str(expected_type)
        for _predicate_id_value, expected_type in {
            (str(row.get("predicate_id")), row.get("expected_type"))
            for row in constraint_rows
        }
        if expected_type is not None
    )
    semantic_sumo_entity_counter = Counter(
        mapping.canonical_id
        for mapping in mapping_records
        if mapping.canonical_kind == "entity_type"
        and mapping.source_key == "sumo_donor_types"
    )
    if semantic_sumo_entity_counter != expected_sumo_entity_counter:
        raise LinguisticCoreCompileError(
            "SUMO entity provenance does not preserve every predicate/type constraint"
        )
    framenet_mappings = [
        mapping
        for mapping in mapping_records
        if mapping.canonical_kind == "predicate_type"
        and mapping.source_key == "framenet_candidate"
    ]
    if (
        len(framenet_mappings) != _CANONICAL_DONOR_FRAMENET_MAPPING_COUNT
        or len({mapping.canonical_id for mapping in framenet_mappings})
        != _CANONICAL_DONOR_FRAMENET_MAPPING_COUNT
    ):
        raise LinguisticCoreCompileError(
            "FrameNet candidate provenance does not preserve the canonical donor inventory"
        )
    runtime_source_rows = _read_jsonl(pack_dir / "source_mappings.jsonl")
    runtime_propbank = Counter(
        (
            str(row.get("canonical_id")),
            str(row.get("canonical_kind")),
            str(row.get("source_id")),
            str(row.get("mapping_type")),
        )
        for row in runtime_source_rows
        if row.get("source_system") == "propbank_nltk"
    )
    semantic_propbank = Counter(
        (
            mapping.canonical_id,
            mapping.canonical_kind,
            mapping.source_id,
            mapping.relation,
        )
        for mapping in mapping_records
        if mapping.source_key == "propbank_nltk"
    )
    if semantic_propbank != runtime_propbank:
        raise LinguisticCoreCompileError(
            "PropBank semantic provenance does not preserve runtime source-mapping multiplicity"
        )
    pack_version = str(pack_block["version"])
    if expected_mapping_hash := _RELEASE_SEMANTIC_MAPPING_SHA256.get(pack_version):
        actual_mapping_hash = _sha256_file(pack_dir / "semantic_mappings.jsonl")
        if actual_mapping_hash != expected_mapping_hash:
            raise LinguisticCoreCompileError(
                "released semantic provenance does not match its independently anchored digest "
                f"version={pack_version} expected={expected_mapping_hash} "
                f"actual={actual_mapping_hash}"
            )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Load one compiler-owned JSONL artifact for strict cross-file validation."""

    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LinguisticCoreCompileError(
                f"invalid JSONL filename={path.name} line={line_number}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise LinguisticCoreCompileError(
                f"JSONL row must be object filename={path.name} line={line_number}"
            )
        rows.append(payload)
    return rows


def _build_hierarchy(
    db_path: Path,
    seed_type_names: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return (ancestor_entity_type_rows, hierarchy_edge_rows) for the seeds.

    Ancestor-closes the seed SUMO type names through ``type_ancestors``, then
    emits ``subtype_of`` edges from ``type_hierarchy`` restricted to the
    closure, so every role-filler type in the pack reaches its SUMO roots
    through exported edges (ADR-0028 item 1: "with hierarchy exported").
    """

    import sqlite3

    encoded_db_path = quote(db_path.resolve().as_posix(), safe="/")
    conn = sqlite3.connect(f"file:{encoded_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        closure = set(seed_type_names)
        placeholders = ",".join("?" for _ in seed_type_names)
        for row in conn.execute(
            f"SELECT DISTINCT ancestor_id FROM type_ancestors WHERE type_id IN ({placeholders})",
            sorted(seed_type_names),
        ):
            closure.add(str(row["ancestor_id"]))

        edge_rows: list[dict[str, object]] = []
        for row in conn.execute("SELECT child, parent FROM type_hierarchy"):
            child = str(row["child"])
            parent = str(row["parent"])
            if child in closure and parent in closure:
                edge_rows.append({
                    "edge_type": "subtype_of",
                    "child_id": _sumo_type_id(child),
                    "parent_id": _sumo_type_id(parent),
                })
    finally:
        conn.close()

    ancestor_rows: list[dict[str, object]] = [
        {
            "type_id": _sumo_type_id(name),
            "preferred_label": name,
            "status": "active",
        }
        for name in sorted(closure - seed_type_names)
    ]
    edge_rows.sort(key=lambda row: (row["child_id"], row["parent_id"]))
    seen: set[tuple[str, str]] = set()
    deduped_edges: list[dict[str, object]] = []
    for row in edge_rows:
        key = (str(row["child_id"]), str(row["parent_id"]))
        if key not in seen:
            seen.add(key)
            deduped_edges.append(row)
    return ancestor_rows, deduped_edges


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a list of dicts to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sumo_type_id(type_name: str) -> str:
    """Return the lc.sumo namespace ID for a SUMO role-filler type."""
    return f"lc:sumo_type.{type_name.strip()}"


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compile the linguistic_core ontology pack from sumo_plus.db.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB,
        help=f"Path to sumo_plus.db (default: {_DEFAULT_DB})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: ontology_packs/linguistic_core/<pack-version>)",
    )
    parser.add_argument(
        "--pack-version",
        default=_PACK_VERSION,
        help=f"Exact semantic pack version (default: {_PACK_VERSION})",
    )
    parser.add_argument(
        "--build-timestamp",
        help=(
            "Explicit RFC3339 UTC build timestamp. Required for non-0.2.0 builds unless "
            "SOURCE_DATE_EPOCH is set."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute data but do not write files; print stats and exit.",
    )
    args = parser.parse_args()
    output_dir = args.output or (_REPO_ROOT / "ontology_packs" / "linguistic_core" / args.pack_version)

    try:
        stats = compile_pack(
            args.db,
            output_dir,
            pack_version=args.pack_version,
            build_timestamp=args.build_timestamp,
            dry_run=args.dry_run,
        )
    except (LinguisticCoreCompileError, RoleSlotsError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("Dry run — no files written.")
    else:
        print(f"Pack written to: {output_dir}")
    print(f"  predicates:       {stats['predicate_count']:,}")
    print(f"  role slots:       {stats['role_slot_count']:,}")
    print(f"  role types:       {stats['role_type_count']:,}")
    print(f"  entity types:     {stats['entity_type_count']:,}")
    print(f"  role edges:       {stats['predicate_role_edge_count']:,}")
    print(f"  constraints:      {stats['constraint_count']:,}")
    print(f"  source mappings:  {stats['source_mapping_count']:,}")
    print(f"  semantic mappings:{stats['semantic_mapping_count']:>10,}")
    if stats["blank_named_label_count"]:
        print(f"  BLANK labels:     {stats['blank_named_label_count']:,}  ← FIX REQUIRED")


if __name__ == "__main__":
    main()
