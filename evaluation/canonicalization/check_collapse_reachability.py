"""Which answer-key pairs can the pack now decide, and which are schema-blocked?

Reports the two error directions separately and never as one accuracy number,
per the failure-mode taxonomy (VF-06 over-collapse, VF-07 under-collapse).

This scores the *representation*, not an extractor: it asks whether the pack
contains enough structure for a correct extractor to reach the key's verdict.
An extractor scorer is a separate thing and must not fold these results in.

Usage:  python evaluation/canonicalization/check_collapse_reachability.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from linguistic_core.contracts import PackRef
from linguistic_core.semantic_construction_v1 import load_exact_pack_closure

KEY = Path(__file__).parent / "canonicalization_key.jsonl"

# relations that license treating two predicates as one canonical object
COLLAPSING = {"exactMatch", "closeMatch"}


def load_relations() -> dict[frozenset[str], str]:
    rels: dict[frozenset[str], str] = {}
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs",
        PackRef(pack_id="linguistic_core", pack_version="0.3.3"),
    )
    for d in closure.predicate_relations:
        rels[frozenset((str(d["from_predicate_id"]), str(d["to_predicate_id"])))] = str(
            d["relation"]
        )
    return rels


def _modifier_roles_declared() -> bool:
    """True when the pack declares the modifier roles and inflection type that
    negation, modality and aspect require. Absence is reported, never silently
    treated as a pass."""
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs",
        PackRef(pack_id="linguistic_core", pack_version="0.3.3"),
    )
    members = [
        (
            ROOT
            / "ontology_packs"
            / item.pack_ref.pack_id
            / item.pack_ref.pack_version,
            item,
        )
        for item in closure.members
    ]
    labels = set()
    for pack_dir, member in members:
        if "modifier_role_types.jsonl" in member.declared_assets:
            for line in (
                (pack_dir / "modifier_role_types.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ):
                if line.strip():
                    labels.add(json.loads(line).get("propbank_label"))
    has_infl = any(
        json.loads(line).get("value_type_id") == "lc.value.verb_inflection"
        for pack_dir, member in members
        if "value_types.jsonl" in member.declared_assets
        for line in (pack_dir / "value_types.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    return {"ARGM-MOD", "ARGM-NEG"} <= labels and has_infl


def _pairings(a, b):
    """Every (a, b) predicate combination. A side may list several acceptable
    predicates; taking a[0] silently picks one, and two checks built that way
    disagreed on 2026-09-08 because sorting differed between them."""
    return [(x, y) for x in a for y in b if x != y]


def preds(row: dict, side: str) -> tuple[str, ...]:
    v = (row.get("expected_predicates") or {}).get(side)
    return tuple(sorted(v)) if isinstance(v, list) else ()


def main() -> None:
    rows = [
        json.loads(l) for l in KEY.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    rels = load_relations()
    buckets: dict[str, list[str]] = {
        k: []
        for k in (
            "same_via_identical_predicate",
            "same_via_declared_relation",
            "same_UNREACHABLE",
            "diff_via_distinct_predicate",
            "diff_needs_roles",
            "diff_via_modifier",
            "diff_UNREACHABLE",
            "no_expected_predicates",
        )
    }
    has_modifiers = _modifier_roles_declared()

    for r in rows:
        a, b = preds(r, "a"), preds(r, "b")
        label, pid = r["label"], r["id"]
        if not a or not b:
            buckets["no_expected_predicates"].append(pid)
            continue
        if label == "same-object":
            if a == b:
                buckets["same_via_identical_predicate"].append(pid)
            elif any(rels.get(frozenset(p)) in COLLAPSING for p in _pairings(a, b)):
                buckets["same_via_declared_relation"].append(pid)
            else:
                buckets["same_UNREACHABLE"].append(pid)
        else:
            if a != b:
                buckets["diff_via_distinct_predicate"].append(pid)
            elif r["failure_mode"] == "granularity":
                # negation/modality/aspect: reachable once the pack declares
                # modifier roles and a verb-inflection value type
                (
                    buckets["diff_via_modifier"]
                    if has_modifiers
                    else buckets["diff_UNREACHABLE"]
                ).append(pid)
            else:
                buckets["diff_needs_roles"].append(pid)

    print(
        f"answer key: {len(rows)} pairs | declared predicate relations: {len(rels)}\n"
    )
    print("UNDER-COLLAPSE side (key says same-object):")
    for k in (
        "same_via_identical_predicate",
        "same_via_declared_relation",
        "same_UNREACHABLE",
    ):
        print(f"  {k:<32} {len(buckets[k]):3d}  {' '.join(buckets[k])}")
    print("\nOVER-COLLAPSE side (key says different-object):")
    for k in (
        "diff_via_distinct_predicate",
        "diff_needs_roles",
        "diff_via_modifier",
        "diff_UNREACHABLE",
    ):
        print(f"  {k:<32} {len(buckets[k]):3d}  {' '.join(buckets[k])}")
    if buckets["no_expected_predicates"]:
        print(
            f"\n  no expected predicates recorded: {len(buckets['no_expected_predicates'])}"
        )
    blocked = len(buckets["same_UNREACHABLE"]) + len(buckets["diff_UNREACHABLE"])
    print(
        f"\nSCHEMA-BLOCKED TOTAL: {blocked}  "
        f"(under {len(buckets['same_UNREACHABLE'])}, over {len(buckets['diff_UNREACHABLE'])})"
    )
    print("These must be reported separately from any extractor accuracy figure.")
    print("\nRead the buckets as REACHABLE, not as CORRECT. This checks that the pack")
    print(
        "declares structure a correct extractor could use; nothing here has extracted"
    )
    print("anything, and it does not validate that a declared relation is TRUE -- one")
    print("authored relation was found false on 2026-09-08 while passing this check.")


if __name__ == "__main__":
    main()
