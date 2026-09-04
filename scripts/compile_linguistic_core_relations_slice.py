"""Compile the linguistic_core@0.3.1 relations slice (Slice A, 2026-09-03).

Reads the ``relations`` and ``relation_constraints`` tables from
``sumo_plus.db`` — unread by ``scripts/compile_linguistic_core_pack.py`` — and
emits an ADDITIVE ``linguistic_core@0.3.1`` pack version that ``extends`` the
already-committed ``linguistic_core@0.3.0`` pack via the generic ontology-pack
extension mechanism (``src/onto_canon6/ontology_runtime/loaders.py``:
``manifest.extends`` + row-union composition, the same mechanism
``ontology_packs/dodaf_capability/0.1.0`` uses over ``dm2_foundation``).

Filtering, in order:

1. Keep only relations whose SUMO module has
   ``publication_disposition: "approved_for_linguistic_bounded_context"`` in
   ``docs/runs/artifacts/plan0147_sumo_module_publication_v1.json`` — today
   that is only ``Merge.kif``. A relation (or constraint) row whose source
   module has NO entry at all in that disposition file is a fail-loud error
   (no silently-unaccounted module), distinct from a present-but-excluded
   disposition (silently dropped, counted).
2. Drop ``*Fn``-suffixed relation IDs — SUO-KIF *Functions* (return a value),
   not assertable n-ary relations, and not representable in the ``lc:``
   predicate/role model.
3. Drop relation IDs that collide with an existing ``predicates.name`` —
   recorded as excluded rather than silently overwritten or duplicated.
4. Apply the SAME module-disposition filter to ``relation_constraints`` rows
   independently, keyed off each constraint's OWN ``source`` column — a
   constraint can cite a different module than the relation it constrains
   (observed: 22 of 594 candidate constraint rows for the final relation set
   are sourced from ``nlg_supplement_formats.kif``, which is
   ``excluded_pending_module_specific_review`` — those 22 rows are dropped
   even though their relation is Merge.kif-approved).

Output shape (why): a binary/ternary/quaternary SUMO relation has no
FrameNet-style named argument roles the way ``role_slots.named_label`` gives
donor predicates — ``relation_constraints`` is positional only
(``arg_position`` + ``required_type``). Per the plan doc, this compiles to a
small set of GENERIC, reused role types (``lc.role.relation_arg1`` ..
``relation_argN``, N = max arity in the filtered set) rather than inventing
per-predicate semantic role names that aren't in the source data. Each new
relation predicate gets one ``predicate_role_edges`` row per argument
position (1..arity, all required); ``required_type`` values become
``role_expected_entity_type`` constraint rows against ``lc:sumo_type.<Type>``
entity types, ancestor-closed through ``type_ancestors``/``type_hierarchy``
exactly as ``scripts/compile_linguistic_core_pack.py._build_hierarchy`` does
for donor predicates — but only for types/edges NOT already present in the
0.3.0 pack being extended (re-declaring an identity already owned by a parent
pack in the closure is a loader error, not a no-op).

This script deliberately does NOT reuse ``compile_linguistic_core_pack.py``'s
``compile_pack()``/``validate_compiled_pack()``: that machinery is a strict,
hardcoded consistency contract over the ``predicates``/``role_slots`` donor
tables (FrameNet mapping counts, `semantic_mappings.jsonl` provenance,
`predicate_canon_index.jsonl`) that has no meaning for relations-table content
and was never asked for by the Slice A spec. The generic pack schema this
script targets is what ``tests/packs/test_pack_schema.py`` and the ontology
runtime loader actually enforce.

Usage::

    python scripts/compile_linguistic_core_relations_slice.py
    python scripts/compile_linguistic_core_relations_slice.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import yaml

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

_DEFAULT_DB = _REPO_ROOT / "data" / "sumo_plus.db"
_DEFAULT_DISPOSITION_FILE = (
    _REPO_ROOT / "docs" / "runs" / "artifacts" / "plan0147_sumo_module_publication_v1.json"
)
_PACK_ID = "linguistic_core"
_NEW_VERSION = "0.3.1"
_BASE_VERSION = "0.3.0"
_APPROVED_DISPOSITION = "approved_for_linguistic_bounded_context"
_BUILD_TIMESTAMP = "2026-09-03T00:00:00Z"
_COMPILER_VERSION = "linguistic-core-relations-slice-v1"


class RelationsSliceCompileError(RuntimeError):
    """Raised when the relations-slice build cannot be produced atomically."""


def _sumo_type_id(type_name: str) -> str:
    """Return the lc.sumo namespace ID for a SUMO role-filler type.

    Mirrors ``compile_linguistic_core_pack.py::_sumo_type_id`` exactly so the
    two compilers agree on identity for the SAME SUMO type name.
    """
    return f"lc:sumo_type.{type_name.strip()}"


def _predicate_id(relation_id: str) -> str:
    return f"lc:{relation_id}"


def _role_id(n: int) -> str:
    return f"lc.role.relation_arg{n}"


def _module_basename(source: str) -> str:
    """Strip the 'sumo:' prefix used by relations.source/relation_constraints.source."""
    return source.removeprefix("sumo:")


def _load_module_dispositions(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dispositions = payload.get("module_dispositions")
    if not isinstance(dispositions, list):
        raise RelationsSliceCompileError(f"{path}: missing module_dispositions list")
    result: dict[str, str] = {}
    for entry in dispositions:
        result[str(entry["path"])] = str(entry["publication_disposition"])
    return result


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise RelationsSliceCompileError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
        if not isinstance(payload, dict):
            raise RelationsSliceCompileError(f"{path}:{line_number}: JSONL row must be object")
        rows.append(payload)
    return rows


def _collect_ancestor_identities(
    pack_dir: Path,
) -> tuple[set[str], set[tuple[str, str, str]], set[str], set[str]]:
    """Union entity, hierarchy-edge, predicate, and role identities across a pack's `extends` closure.

    Reads `pack_dir`'s own local rows plus every pack it transitively extends
    (each `extends` target resolved as a sibling version directory under the
    same `ontology_packs/<id>/` root), matching the identity semantics the
    ontology runtime loader (`src/onto_canon6/ontology_runtime/loaders.py`)
    enforces: an identity owned by any ancestor in the closure cannot be
    re-declared by a descendant. Predicate identities matter here specifically
    because this compiler may be re-run against a widened module disposition
    that re-derives relations an earlier, narrower run of the SAME compiler
    already emitted into an ancestor version (e.g. 0.3.1's Merge.kif-sourced
    relations reappearing in a 0.3.2 recompile against a wider disposition) --
    those must be treated as already-owned, not re-declared.
    """

    entity_ids: set[str] = set()
    hierarchy_identities: set[tuple[str, str, str]] = set()
    predicate_ids: set[str] = set()
    role_ids: set[str] = set()
    seen_dirs: set[Path] = set()
    stack = [pack_dir]
    while stack:
        current = stack.pop()
        resolved = current.resolve()
        if resolved in seen_dirs:
            continue
        seen_dirs.add(resolved)
        entity_ids.update(str(r["type_id"]) for r in _read_jsonl(current / "entity_types.jsonl"))
        hierarchy_identities.update(
            (str(r["child_id"]), str(r["parent_id"]), str(r["edge_type"]))
            for r in _read_jsonl(current / "hierarchy_edges.jsonl")
        )
        predicate_ids.update(
            str(r["predicate_id"]) for r in _read_jsonl(current / "predicate_types.jsonl")
        )
        role_ids.update(str(r["role_id"]) for r in _read_jsonl(current / "role_types.jsonl"))
        manifest = yaml.safe_load((current / "manifest.yaml").read_text(encoding="utf-8"))
        for ancestor in manifest.get("extends") or []:
            stack.append(current.parent.parent / str(ancestor["id"]) / str(ancestor["version"]))
    return entity_ids, hierarchy_identities, predicate_ids, role_ids


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def _write_yaml(path: Path, payload: object) -> None:
    path.write_text(
        yaml.dump(payload, default_flow_style=False, sort_keys=False, allow_unicode=True, width=10**9),
        encoding="utf-8",
    )


class CompileStats(dict[str, object]):
    """Row counts + exclusion counts for reporting."""


def compile_relations_slice(
    *,
    db_path: Path,
    disposition_path: Path,
    base_pack_dir: Path,
    output_dir: Path,
    pack_version: str = _NEW_VERSION,
    base_version: str = _BASE_VERSION,
    dry_run: bool = False,
) -> CompileStats:
    if not db_path.exists():
        raise RelationsSliceCompileError(f"sumo_plus database not found: {db_path}")
    if not disposition_path.exists():
        raise RelationsSliceCompileError(f"disposition file not found: {disposition_path}")
    if not (base_pack_dir / "manifest.yaml").exists():
        raise RelationsSliceCompileError(f"base pack not found: {base_pack_dir}")
    if not dry_run and output_dir.exists():
        raise RelationsSliceCompileError(
            f"output target already exists; refusing partial/overwrite build: {output_dir}"
        )

    dispositions = _load_module_dispositions(disposition_path)

    encoded_db_path = quote(db_path.resolve().as_posix(), safe="/")
    conn = sqlite3.connect(f"file:{encoded_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        all_relations = list(conn.execute("SELECT * FROM relations ORDER BY id"))
        pred_names = {row["name"] for row in conn.execute("SELECT name FROM predicates")}
        (
            ancestor_entity_ids,
            ancestor_hierarchy_identities,
            ancestor_predicate_ids,
            ancestor_role_ids,
        ) = _collect_ancestor_identities(base_pack_dir)
        pred_names = pred_names | {pid.removeprefix("lc:") for pid in ancestor_predicate_ids}

        # Per the plan doc: "filtered by joining relations.source ... against
        # module_dispositions, keeping only rows where publication_disposition
        # == approved..." — the join target is the 66 real SUMO .kif modules
        # named in the disposition file. A relation whose source module IS one
        # of those 66 but isn't approved is silently-excluded-and-counted (a
        # known, reviewed exclusion). A relation whose source string isn't a
        # real module name at all (observed: 53 rows with source='sumo:unknown'
        # — a donor-DB data-quality gap, not a SUMO module) is neither approved
        # nor a reviewed exclusion; fail loud on that distinct case so it is
        # never silently treated as either.
        approved_relations: list[sqlite3.Row] = []
        excluded_module_relation_count = 0
        unaccounted_relation_rows: list[tuple[str, str]] = []
        for row in all_relations:
            basename = _module_basename(row["source"])
            disposition = dispositions.get(basename)
            if disposition is None:
                unaccounted_relation_rows.append((row["id"], basename))
                continue
            if disposition == _APPROVED_DISPOSITION:
                approved_relations.append(row)
            else:
                excluded_module_relation_count += 1
        if unaccounted_relation_rows and not all(
            basename == "unknown" for _rid, basename in unaccounted_relation_rows
        ):
            raise RelationsSliceCompileError(
                "relation row(s) cite a module absent from the disposition file "
                "that is NOT the known 'unknown' donor-DB gap — fail loud, not "
                f"silent-skip: {unaccounted_relation_rows}"
            )

        fn_excluded = [row for row in approved_relations if row["id"].endswith("Fn")]
        non_fn = [row for row in approved_relations if not row["id"].endswith("Fn")]

        collision_excluded = [row for row in non_fn if row["id"] in pred_names]
        final_relations = [row for row in non_fn if row["id"] not in pred_names]
        final_relations.sort(key=lambda r: r["id"])
        final_ids = {row["id"] for row in final_relations}

        if not final_ids:
            constraint_rows: list[sqlite3.Row] = []
        else:
            placeholders = ",".join("?" for _ in final_ids)
            constraint_rows = list(
                conn.execute(
                    f"SELECT * FROM relation_constraints WHERE relation_id IN ({placeholders}) "
                    "ORDER BY relation_id, arg_position, required_type",
                    sorted(final_ids),
                )
            )

        kept_constraints: list[sqlite3.Row] = []
        dropped_constraint_module_count = 0
        for row in constraint_rows:
            basename = _module_basename(row["source"])
            disposition = dispositions.get(basename)
            if disposition is None:
                raise RelationsSliceCompileError(
                    f"relation_constraints row for {row['relation_id']!r} pos={row['arg_position']} "
                    f"cites unaccounted module {basename!r} — fail loud, not silent-skip"
                )
            if disposition == _APPROVED_DISPOSITION:
                kept_constraints.append(row)
            else:
                dropped_constraint_module_count += 1

        max_arity = max((row["arity"] for row in final_relations), default=0)

        # --- predicate_types.jsonl ---
        predicate_rows: list[dict[str, object]] = [
            {
                "predicate_id": _predicate_id(row["id"]),
                "family": "state",
                "preferred_label": row["id"],
                "description": row["description"] or "",
                "status": "active",
            }
            for row in final_relations
        ]

        # --- role_types.jsonl (generic, shared, positional; only NEW role ids) ---
        role_rows: list[dict[str, object]] = [
            {
                "role_id": _role_id(n),
                "runtime_name": f"relation_arg{n}",
                "preferred_label": f"Relation Arg {n}",
                "status": "active",
            }
            for n in range(1, max_arity + 1)
            if _role_id(n) not in ancestor_role_ids
        ]

        # --- predicate_role_edges.jsonl (one row per arg position, all required) ---
        predicate_role_edge_rows: list[dict[str, object]] = []
        for row in final_relations:
            for n in range(1, int(row["arity"]) + 1):
                predicate_role_edge_rows.append(
                    {
                        "predicate_id": _predicate_id(row["id"]),
                        "role_id": _role_id(n),
                        "required": True,
                        "min_count": 1,
                        "max_count": 1,
                    }
                )

        # --- constraints.jsonl (role_expected_entity_type, one row per kept required_type) ---
        constraint_out_rows: list[dict[str, object]] = []
        required_type_names: set[str] = set()
        seen_constraint_identity: set[tuple[str, str, str]] = set()
        for row in kept_constraints:
            predicate_id = _predicate_id(row["relation_id"])
            role_id = _role_id(int(row["arg_position"]))
            required_type = row["required_type"]
            required_type_names.add(required_type)
            identity = ("role_expected_entity_type", predicate_id, role_id + ":" + required_type)
            if identity in seen_constraint_identity:
                continue
            seen_constraint_identity.add(identity)
            constraint_out_rows.append(
                {
                    "constraint_type": "role_expected_entity_type",
                    "predicate_id": predicate_id,
                    "role_id": role_id,
                    "expected_type": _sumo_type_id(required_type),
                }
            )
        constraint_out_rows.sort(key=lambda r: (r["predicate_id"], r["role_id"], r["expected_type"]))

        # --- entity_types.jsonl + hierarchy_edges.jsonl: only NEW types/edges ---
        # Checked against the FULL ancestor closure (collected above, before the
        # predicate-collision filter) rather than just base_pack_dir's own local
        # rows -- an additive pack's local file only contains what IT added, so
        # checking only the immediate base would miss identities an older
        # ancestor (e.g. 0.3.0) already owns, causing a loader "extension
        # identity conflict" the first time a wider slice reintroduces one.
        base_entity_ids = ancestor_entity_ids
        base_hierarchy_identities = ancestor_hierarchy_identities

        closure_names: set[str] = set(required_type_names)
        if required_type_names:
            placeholders = ",".join("?" for _ in required_type_names)
            for row in conn.execute(
                f"SELECT DISTINCT ancestor_id FROM type_ancestors WHERE type_id IN ({placeholders})",
                sorted(required_type_names),
            ):
                closure_names.add(str(row["ancestor_id"]))

        new_entity_names = sorted(
            name for name in closure_names if _sumo_type_id(name) not in base_entity_ids
        )
        entity_type_rows: list[dict[str, object]] = [
            {"type_id": _sumo_type_id(name), "preferred_label": name, "status": "active"}
            for name in new_entity_names
        ]

        hierarchy_edge_rows: list[dict[str, object]] = []
        if closure_names:
            for row in conn.execute("SELECT child, parent FROM type_hierarchy"):
                child, parent = str(row["child"]), str(row["parent"])
                if child in closure_names and parent in closure_names:
                    identity = (_sumo_type_id(child), _sumo_type_id(parent), "subtype_of")
                    if identity not in base_hierarchy_identities:
                        hierarchy_edge_rows.append(
                            {
                                "edge_type": "subtype_of",
                                "child_id": identity[0],
                                "parent_id": identity[1],
                            }
                        )
        hierarchy_edge_rows.sort(key=lambda r: (r["child_id"], r["parent_id"]))
        # dedupe (identical child/parent could appear only once per (child,parent) pair anyway)
        seen_edges: set[tuple[str, str]] = set()
        deduped_hierarchy_edge_rows: list[dict[str, object]] = []
        for row in hierarchy_edge_rows:
            key = (str(row["child_id"]), str(row["parent_id"]))
            if key not in seen_edges:
                seen_edges.add(key)
                deduped_hierarchy_edge_rows.append(row)
        hierarchy_edge_rows = deduped_hierarchy_edge_rows

        # --- source_mappings.jsonl (provenance: predicate -> donor relation row) ---
        source_mapping_rows: list[dict[str, object]] = [
            {
                "canonical_id": _predicate_id(row["id"]),
                "canonical_kind": "predicate_type",
                "source_system": "onto_canon_sumo_plus_relations",
                "source_id": row["id"],
                "pack_predicate_id": _predicate_id(row["id"]),
                "mapping_type": "derived_from",
                "confidence": "donor_asserted",
                "notes": f"source module: {row['source']}",
            }
            for row in final_relations
        ]
    finally:
        conn.close()

    stats = CompileStats(
        all_relations_count=len(all_relations),
        excluded_by_module_disposition=excluded_module_relation_count,
        unaccounted_module_relation_count=len(unaccounted_relation_rows),
        merge_kif_or_approved_total=len(approved_relations),
        excluded_fn_count=len(fn_excluded),
        excluded_collision_count=len(collision_excluded),
        excluded_collision_ids=sorted(row["id"] for row in collision_excluded),
        final_relation_count=len(final_relations),
        max_arity=max_arity,
        constraint_candidate_count=len(constraint_rows),
        constraint_dropped_by_module_count=dropped_constraint_module_count,
        constraint_kept_count=len(kept_constraints),
        predicate_role_edge_count=len(predicate_role_edge_rows),
        constraint_out_count=len(constraint_out_rows),
        new_entity_type_count=len(entity_type_rows),
        new_hierarchy_edge_count=len(hierarchy_edge_rows),
        role_type_count=len(role_rows),
        source_mapping_count=len(source_mapping_rows),
    )

    if dry_run:
        return stats

    content: dict[str, list[dict[str, object]]] = {
        "entity_types": entity_type_rows,
        "predicate_types": predicate_rows,
        "role_types": role_rows,
        "value_types": [],
        "hierarchy_edges": hierarchy_edge_rows,
        "predicate_role_edges": predicate_role_edge_rows,
        "source_mappings": source_mapping_rows,
        "aliases": [],
        "constraints": constraint_out_rows,
    }

    disposition_rel_path = disposition_path.resolve().relative_to(_REPO_ROOT).as_posix()
    approved_module_count = sum(
        1 for value in dispositions.values() if value == _APPROVED_DISPOSITION
    )
    total_module_count = len(dispositions)
    description = (
        f"Additive relations slice for linguistic_core, extending {base_version}. "
        "Compiles SUMO relations and their positional argument-type constraints "
        "from sumo_plus.db's relations/relation_constraints tables (unread by the "
        f"base compiler), filtered to SUMO modules cleared for publication per "
        f"{disposition_rel_path} ({approved_module_count} of {total_module_count} "
        "modules approved). Excludes SUO-KIF Functions (*Fn) and relation IDs that "
        "collide with an existing linguistic_core predicate name. Provides "
        f"{len(predicate_rows)} new lc: relation predicates (kinship, spatial, "
        "semiotic, and other general relations) with generic positional role "
        "slots (lc.role.relation_arg1..N, N = max arity in this slice). "
        "Attribution: derived from the SUMO (Suggested Upper Merged Ontology) "
        "project by Adam Pease / Articulate Software and named module "
        "contributors (github.com/ontologyportal/sumo); see ADR-0040 for the "
        "per-module license basis and the GPL-compatible open-terms condition "
        "this pack's own publication satisfies."
    )

    manifest: dict[str, object] = {
        "pack": {
            "id": _PACK_ID,
            "version": pack_version,
            "name": _PACK_ID,
            "description": description,
        },
        "build": {
            "compiler_version": _COMPILER_VERSION,
            "built_at": _BUILD_TIMESTAMP,
            "source_inputs": [
                {
                    "system": "onto_canon_sumo_plus_relations",
                    "version": "2026-02-15",
                    "path": "data/sumo_plus.db",
                    "tables": "relations, relation_constraints, type_ancestors, type_hierarchy",
                },
                {
                    "system": "sumo_module_publication_disposition",
                    "version": disposition_rel_path.rsplit("_v", 1)[-1].removesuffix(".json"),
                    "path": disposition_rel_path,
                },
            ],
        },
        "extends": [{"id": _PACK_ID, "version": base_version}],
        "capabilities": {"assertion_type": "n-ary", "type_system": "sumo"},
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

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output_dir.parent, prefix=f".{output_dir.name}.build-"
    ) as temporary_root:
        stage_dir = Path(temporary_root) / output_dir.name
        stage_dir.mkdir()
        for section, rows in content.items():
            _write_jsonl(stage_dir / f"{section}.jsonl", rows)
        _write_yaml(stage_dir / "manifest.yaml", manifest)
        if output_dir.exists():
            raise RelationsSliceCompileError(
                f"output target appeared during build; refusing overwrite: {output_dir}"
            )
        stage_dir.replace(output_dir)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile the linguistic_core@0.3.1 relations slice (Slice A).",
    )
    parser.add_argument("--db", type=Path, default=_DEFAULT_DB)
    parser.add_argument("--disposition-file", type=Path, default=_DEFAULT_DISPOSITION_FILE)
    parser.add_argument(
        "--base-pack-dir",
        type=Path,
        default=None,
        help="Directory of the base pack version being extended (default: "
        "ontology_packs/linguistic_core/<base-version>)",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pack-version", default=_NEW_VERSION)
    parser.add_argument("--base-version", default=_BASE_VERSION)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base_pack_dir = args.base_pack_dir or (
        _REPO_ROOT / "ontology_packs" / _PACK_ID / args.base_version
    )
    output_dir = args.output or (_REPO_ROOT / "ontology_packs" / _PACK_ID / args.pack_version)

    try:
        stats = compile_relations_slice(
            db_path=args.db,
            disposition_path=args.disposition_file,
            base_pack_dir=base_pack_dir,
            output_dir=output_dir,
            pack_version=args.pack_version,
            base_version=args.base_version,
            dry_run=args.dry_run,
        )
    except RelationsSliceCompileError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("Dry run — no files written.")
    else:
        print(f"Pack written to: {output_dir}")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
