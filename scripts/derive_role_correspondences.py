"""Derive role correspondences for every collapsing predicate relation.

Declaring that `buy` and `acquire` denote one object does nothing if nothing says
that `buy`'s buyer is `acquire`'s recipient. That gap was measured on 2026-09-08
as the leading genuine cause of under-collapse: the pack's role vocabularies
diverge between predicates it declares related.

This is **derived, not authored**. PropBank numbers its arguments consistently
within a roleset, and the pack already records which role id sits at which
argument position (`source_mappings.jsonl`, `mapping_type: positional_role`).
Two corresponding rolesets therefore align by argument number, and the
correspondence falls out of data already in hand rather than out of judgement --
unlike `predicate_relations.jsonl`, where two of fifteen hand-authored rows
turned out wrong.

Argument positions that a role-alignment review found genuinely divergent are
excluded by name, with the reason recorded on the exclusion rather than dropped
silently.

Usage:  python scripts/derive_role_correspondences.py [--write]
"""
from __future__ import annotations

import argparse, collections, glob, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ontology_packs/linguistic_core/_candidates/role_correspondences.jsonl"
COLLAPSING = {"exactMatch", "closeMatch", "broaderThan", "narrowerThan"}

# argument positions a 2026-09-08 role-alignment review found to denote different
# participants despite the predicates corresponding. Excluded with the reason.
DIVERGENT: dict[tuple[str, str], dict[str, str]] = {
    ("lc:claim_assert", "lc:say_speak"): {
        "ARG2": "claim-01 ARG2 is the party claimed for; say-01 ARG2 is the hearer"},
    ("lc:help_aid", "lc:aid_help"): {
        "ARG2": "PropBank labels these 'benefactive' and 'benefactor' - recipient against provider"},
    ("lc:sign_enter_agreement", "lc:undertake_agree_to_do"): {
        "ARG2": "sign-02 ARG2 is a co-signer; undertake-01 ARG2 is any other participant"},
}


def load_arg_positions() -> dict[str, dict[str, str]]:
    """predicate_id -> {ARGn: role_id}, from the pack's own positional mappings."""
    out: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/source_mappings.jsonl")):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            if d.get("mapping_type") != "positional_role":
                continue
            cid, sid = d.get("canonical_id", ""), d.get("source_id", "")
            if ":lc.role." not in cid or ":ARG" not in sid:
                continue
            pred, role = cid.rsplit(":lc.role.", 1)
            out[pred][sid.rsplit(":", 1)[1]] = "lc.role." + role
    if not out:
        sys.exit("no positional_role mappings found -- refusing to report a clean run over nothing")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    argpos = load_arg_positions()
    rels = [json.loads(l) for l in
            open(ROOT / "ontology_packs/linguistic_core/_candidates/predicate_relations.jsonl",
                 encoding="utf-8")]

    rows, skipped, excluded = [], [], []
    for r in rels:
        if r["relation"] not in COLLAPSING:
            skipped.append((r["from_predicate_id"], r["to_predicate_id"], r["relation"]))
            continue
        a, b = r["from_predicate_id"], r["to_predicate_id"]
        pa, pb = argpos.get(a, {}), argpos.get(b, {})
        if not pa or not pb:
            skipped.append((a, b, "no positional roles"))
            continue
        div = DIVERGENT.get((a, b), {})
        for arg in sorted(set(pa) & set(pb)):
            if arg in div:
                excluded.append((a, b, arg, div[arg]))
                continue
            rows.append({
                "from_predicate_id": a, "from_role_id": pa[arg],
                "to_predicate_id": b, "to_role_id": pb[arg],
                "argument_position": arg,
                "via_relation": r["relation"],
                "derivation_method": "derived",
                "confidence_basis": "PropBank argument position, from the pack's own "
                                    "positional_role mappings; not hand-authored",
                "source_verified": False,
            })

    print(f"collapsing relations: {sum(1 for r in rels if r['relation'] in COLLAPSING)}")
    print(f"role correspondences derived: {len(rows)}")
    if excluded:
        print(f"\nexcluded as divergent ({len(excluded)}):")
        for a, b, arg, why in excluded:
            print(f"  {a} {arg} {b}: {why}")
    if skipped:
        print(f"\nrelations skipped ({len(skipped)}): " +
              ", ".join(f"{a.split(':')[1]}->{b.split(':')[1]} ({w})" for a, b, w in skipped))
    if args.write:
        OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
        print(f"\nwrote {OUT.relative_to(ROOT)}")
    else:
        print("\n(dry run; pass --write to emit)")


if __name__ == "__main__":
    main()
