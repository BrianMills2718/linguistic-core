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
- ``manifest.yaml`` — pack identity and content inventory

The pack uses the ``lc:`` namespace for predicates and ``lc.role.`` namespace
for role types. ARG positions (ARG0, ARG1, ...) appear only in source_mappings
as provenance; all semantic identifiers use named_label values.

Usage::

    python scripts/compile_linguistic_core_pack.py [--db PATH] [--output DIR] [--dry-run]

Examples::

    python scripts/compile_linguistic_core_pack.py
    python scripts/compile_linguistic_core_pack.py --db data/sumo_plus.db --output ontology_packs/linguistic_core/0.1.0
    python scripts/compile_linguistic_core_pack.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Allow running as a script from the repo root.
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from onto_canon6.packs.role_slots_lookup import RoleSlotsError, RoleSlotsLookup

_DEFAULT_DB = _REPO_ROOT / "data" / "sumo_plus.db"
_DEFAULT_OUTPUT = _REPO_ROOT / "ontology_packs" / "linguistic_core" / "0.2.0"
_PACK_VERSION = "0.2.0"
_COMPILER_VERSION = "0.1.0"


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
    dry_run: bool = False,
) -> dict:
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
    with RoleSlotsLookup(db_path) as lookup:
        predicates = lookup.all_predicates()
        predicate_count = len(predicates)

        # --- predicate_types.jsonl ---
        predicate_rows = []
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
        role_rows = []
        entity_type_rows = []
        predicate_role_edge_rows = []
        constraint_rows = []
        source_mapping_rows = []
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
    seed_type_names = {row["preferred_label"] for row in entity_type_rows}
    ancestor_rows, hierarchy_edge_rows = _build_hierarchy(db_path, seed_type_names)
    entity_type_rows = entity_type_rows + ancestor_rows

    stats = {
        "predicate_count": predicate_count,
        "role_slot_count": role_slot_count,
        "role_type_count": len(role_rows),
        "entity_type_count": len(entity_type_rows),
        "hierarchy_edge_count": len(hierarchy_edge_rows),
        "predicate_role_edge_count": len(predicate_role_edge_rows),
        "constraint_count": len(constraint_rows),
        "source_mapping_count": len(source_mapping_rows),
        "blank_named_label_count": blank_count,
    }

    if dry_run:
        return stats

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write predicate_types.jsonl
    _write_jsonl(output_dir / "predicate_types.jsonl", predicate_rows)

    # Write role_types.jsonl
    _write_jsonl(output_dir / "role_types.jsonl", role_rows)

    # Write runtime-required pack content files
    _write_jsonl(output_dir / "entity_types.jsonl", entity_type_rows)
    _write_jsonl(output_dir / "value_types.jsonl", [])
    _write_jsonl(output_dir / "hierarchy_edges.jsonl", hierarchy_edge_rows)
    _write_jsonl(output_dir / "predicate_role_edges.jsonl", predicate_role_edge_rows)
    _write_jsonl(output_dir / "aliases.jsonl", [])
    _write_jsonl(output_dir / "constraints.jsonl", constraint_rows)

    # Write source_mappings.jsonl
    _write_jsonl(output_dir / "source_mappings.jsonl", source_mapping_rows)

    # Write manifest.yaml
    manifest = {
        "pack": {
            "id": "linguistic_core",
            "version": _PACK_VERSION,
            "name": "linguistic_core",
            "description": (
                "Foundational predicate vocabulary synthesized from PropBank, FrameNet, "
                "and SUMO. Provides 4,669 predicates and 11,890 semantic role slots "
                "for use as the base pack from which domain packs extend."
            ),
        },
        "build": {
            "compiler_version": _COMPILER_VERSION,
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_inputs": [
                {
                    "system": "onto_canon_sumo_plus",
                    "version": "2026-02-15",
                    "path": "data/sumo_plus.db",
                }
            ],
        },
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
    with open(output_dir / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return stats


def _build_hierarchy(
    db_path: Path,
    seed_type_names: set[str],
) -> tuple[list[dict], list[dict]]:
    """Return (ancestor_entity_type_rows, hierarchy_edge_rows) for the seeds.

    Ancestor-closes the seed SUMO type names through ``type_ancestors``, then
    emits ``subtype_of`` edges from ``type_hierarchy`` restricted to the
    closure, so every role-filler type in the pack reaches its SUMO roots
    through exported edges (ADR-0028 item 1: "with hierarchy exported").
    """

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        closure = set(seed_type_names)
        placeholders = ",".join("?" for _ in seed_type_names)
        for row in conn.execute(
            f"SELECT DISTINCT ancestor_id FROM type_ancestors WHERE type_id IN ({placeholders})",
            sorted(seed_type_names),
        ):
            closure.add(str(row["ancestor_id"]))

        edge_rows = []
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

    ancestor_rows = [
        {
            "type_id": _sumo_type_id(name),
            "preferred_label": name,
            "status": "active",
        }
        for name in sorted(closure - seed_type_names)
    ]
    edge_rows.sort(key=lambda row: (row["child_id"], row["parent_id"]))
    seen: set[tuple[str, str]] = set()
    deduped_edges = []
    for row in edge_rows:
        key = (row["child_id"], row["parent_id"])
        if key not in seen:
            seen.add(key)
            deduped_edges.append(row)
    return ancestor_rows, deduped_edges


def _write_jsonl(path: Path, rows: list[dict]) -> None:
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
        default=_DEFAULT_OUTPUT,
        help=f"Output directory (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute data but do not write files; print stats and exit.",
    )
    args = parser.parse_args()

    try:
        stats = compile_pack(args.db, args.output, dry_run=args.dry_run)
    except RoleSlotsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("Dry run — no files written.")
    else:
        print(f"Pack written to: {args.output}")
    print(f"  predicates:       {stats['predicate_count']:,}")
    print(f"  role slots:       {stats['role_slot_count']:,}")
    print(f"  role types:       {stats['role_type_count']:,}")
    print(f"  entity types:     {stats['entity_type_count']:,}")
    print(f"  role edges:       {stats['predicate_role_edge_count']:,}")
    print(f"  constraints:      {stats['constraint_count']:,}")
    print(f"  source mappings:  {stats['source_mapping_count']:,}")
    if stats["blank_named_label_count"]:
        print(f"  BLANK labels:     {stats['blank_named_label_count']:,}  ← FIX REQUIRED")


if __name__ == "__main__":
    main()
