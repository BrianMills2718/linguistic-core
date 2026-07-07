"""linguistic_core@0.2.0 hierarchy-export tests (Plan 0116 Slice A, AC-1).

ADR-0028 finish-line item 1 requires the pack hierarchy to be exported so
ancestor-aware validation can run from the pack, not the raw sumo_plus DB.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = REPO_ROOT / "ontology_packs" / "linguistic_core" / "0.2.0"
OLD_PACK_DIR = REPO_ROOT / "ontology_packs" / "linguistic_core" / "0.1.0"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_hierarchy_is_exported_and_nonempty() -> None:
    """The 0.1.0 compiler stub (empty hierarchy) must be gone in 0.2.0."""

    edges = _rows(PACK_DIR / "hierarchy_edges.jsonl")
    assert len(edges) > 500
    assert all(edge["edge_type"] == "subtype_of" for edge in edges)


def test_every_edge_endpoint_is_a_pack_entity_type() -> None:
    """Hierarchy edges must not dangle outside entity_types.jsonl."""

    type_ids = {row["type_id"] for row in _rows(PACK_DIR / "entity_types.jsonl")}
    for edge in _rows(PACK_DIR / "hierarchy_edges.jsonl"):
        assert edge["child_id"] in type_ids, edge
        assert edge["parent_id"] in type_ids, edge


def test_every_constraint_seed_type_reaches_a_root() -> None:
    """Every role-filler type must have a complete ancestor chain (AC-1)."""

    parents: dict[str, set[str]] = {}
    for edge in _rows(PACK_DIR / "hierarchy_edges.jsonl"):
        parents.setdefault(edge["child_id"], set()).add(edge["parent_id"])

    seeds = {
        row["expected_type"]
        for row in _rows(PACK_DIR / "constraints.jsonl")
        if row.get("constraint_type") == "role_expected_entity_type"
    }
    assert seeds

    for seed in seeds:
        visited: set[str] = set()
        frontier = {seed}
        reached_root = False
        while frontier:
            node = frontier.pop()
            if node in visited:
                continue
            visited.add(node)
            node_parents = parents.get(node, set())
            if not node_parents:
                reached_root = True
                continue
            frontier.update(node_parents)
        assert reached_root, f"{seed} never reaches a hierarchy root"


def test_020_is_purely_additive_over_010() -> None:
    """Plan 0116 U5: same predicates/roles/constraints; only types+hierarchy grew."""

    for name in ("predicate_types.jsonl", "role_types.jsonl", "constraints.jsonl"):
        assert len(_rows(PACK_DIR / name)) == len(_rows(OLD_PACK_DIR / name)), name

    old_types = {row["type_id"] for row in _rows(OLD_PACK_DIR / "entity_types.jsonl")}
    new_types = {row["type_id"] for row in _rows(PACK_DIR / "entity_types.jsonl")}
    assert old_types <= new_types
    assert len(new_types) > len(old_types)
