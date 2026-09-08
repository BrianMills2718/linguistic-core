"""Which answer-key pairs can the pack now decide, and which are schema-blocked?

Reports the two error directions separately and never as one accuracy number,
per the failure-mode taxonomy (VF-06 over-collapse, VF-07 under-collapse).

This scores the *representation*, not an extractor: it asks whether the pack
contains enough structure for a correct extractor to reach the key's verdict.
An extractor scorer is a separate thing and must not fold these results in.

Usage:  python evaluation/canonicalization/check_collapse_reachability.py
"""
from __future__ import annotations
import glob, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = Path(__file__).parent / "canonicalization_key.jsonl"

# relations that license treating two predicates as one canonical object
COLLAPSING = {"exactMatch", "closeMatch", "broaderThan", "narrowerThan"}


def load_relations() -> dict[frozenset[str], str]:
    rels: dict[frozenset[str], str] = {}
    files = sorted(glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/predicate_relations.jsonl")))
    if not files:
        raise SystemExit("no predicate_relations.jsonl in any pack version -- refusing to report a clean run over nothing")
    for f in files:
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            rels[frozenset((d["from_predicate_id"], d["to_predicate_id"]))] = d["relation"]
    return rels


def preds(row: dict, side: str) -> tuple[str, ...]:
    v = (row.get("expected_predicates") or {}).get(side)
    return tuple(sorted(v)) if isinstance(v, list) else ()


def main() -> None:
    rows = [json.loads(l) for l in KEY.read_text(encoding="utf-8").splitlines() if l.strip()]
    rels = load_relations()
    buckets: dict[str, list[str]] = {k: [] for k in
        ("same_via_identical_predicate", "same_via_declared_relation",
         "same_UNREACHABLE", "diff_via_distinct_predicate",
         "diff_needs_roles", "diff_UNREACHABLE", "no_expected_predicates")}

    for r in rows:
        a, b = preds(r, "a"), preds(r, "b")
        label, pid = r["label"], r["id"]
        if not a or not b:
            buckets["no_expected_predicates"].append(pid); continue
        if label == "same-object":
            if a == b:
                buckets["same_via_identical_predicate"].append(pid)
            elif rels.get(frozenset((a[0], b[0]))) in COLLAPSING:
                buckets["same_via_declared_relation"].append(pid)
            else:
                buckets["same_UNREACHABLE"].append(pid)
        else:
            if a != b:
                buckets["diff_via_distinct_predicate"].append(pid)
            elif r["failure_mode"] == "granularity":
                buckets["diff_UNREACHABLE"].append(pid)   # needs modality/negation/aspect
            else:
                buckets["diff_needs_roles"].append(pid)

    print(f"answer key: {len(rows)} pairs | declared predicate relations: {len(rels)}\n")
    print("UNDER-COLLAPSE side (key says same-object):")
    for k in ("same_via_identical_predicate", "same_via_declared_relation", "same_UNREACHABLE"):
        print(f"  {k:<32} {len(buckets[k]):3d}  {' '.join(buckets[k])}")
    print("\nOVER-COLLAPSE side (key says different-object):")
    for k in ("diff_via_distinct_predicate", "diff_needs_roles", "diff_UNREACHABLE"):
        print(f"  {k:<32} {len(buckets[k]):3d}  {' '.join(buckets[k])}")
    if buckets["no_expected_predicates"]:
        print(f"\n  no expected predicates recorded: {len(buckets['no_expected_predicates'])}")
    blocked = len(buckets["same_UNREACHABLE"]) + len(buckets["diff_UNREACHABLE"])
    print(f"\nSCHEMA-BLOCKED TOTAL: {blocked}  "
          f"(under {len(buckets['same_UNREACHABLE'])}, over {len(buckets['diff_UNREACHABLE'])})")
    print("These must be reported separately from any extractor accuracy figure.")


if __name__ == "__main__":
    main()
