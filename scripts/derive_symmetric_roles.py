"""Which predicates have interchangeable role pairs?

"Acme merged with Beta" and "Beta merged with Acme" produce different canonical
objects because `part_1` and `part_2` swap and nothing declares the order
immaterial. That was measured on 2026-09-08 as one of seven residual
under-collapse cases (VF-18), and the fact-oriented brief warns about it in its
§12 -- a section this design had recorded as unabsorbed.

SUMO knows about symmetry and it did not survive the import: `relations` has zero
rows whose `parent_relation` reaches `SymmetricRelation`, and `type_hierarchy`
carries only five rows about relation *classes*. Same shape of loss as the
dropped `ARGM` modifiers.

PropBank carries the signal instead, in its role descriptions -- `merge.01` has
'ingredient one' and 'ingredient two', `marry.01` has 'one half' and 'second
half'. So: **regex shortlists by shape, a model decides meaning.** That split is
required here; deciding whether two prose descriptions denote interchangeable
participants is not something a pattern can settle, and a first attempt at a
related check by word overlap flagged 11 of 15 falsely.

Usage:  python scripts/derive_symmetric_roles.py [--write]
"""
from __future__ import annotations

import argparse, glob, itertools, json, re, sys, zipfile
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
PROPBANK = Path.home() / "code/onto-canon6/data/nltk_data/corpora/propbank.zip"
OUT = ROOT / "ontology_packs/linguistic_core/_candidates/symmetric_role_pairs.jsonl"
MODEL = "openrouter/openai/gpt-5.6-luna"
SHAPE = re.compile(r"\b(one|two|three|first|second|third|1|2)\b|\bhalf\b", re.I)


class Verdict(BaseModel):
    interchangeable: bool = Field(
        description="True only if swapping the two participants leaves the asserted fact unchanged.")
    reason: str = Field(description="One short sentence.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if not PROPBANK.exists():
        sys.exit(f"PropBank not found at {PROPBANK} -- refusing to report a clean run over nothing")
    z = zipfile.ZipFile(PROPBANK)

    src: dict[str, str] = {}
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/source_mappings.jsonl")):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            if d.get("canonical_kind") == "predicate_type":
                src[d["canonical_id"]] = d["source_id"]
    argpos: dict[str, dict[str, str]] = {}
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/source_mappings.jsonl")):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            if d.get("mapping_type") != "positional_role":
                continue
            cid, sid = d.get("canonical_id", ""), d.get("source_id", "")
            if ":lc.role." in cid and ":ARG" in sid:
                p, r = cid.rsplit(":lc.role.", 1)
                argpos.setdefault(p, {})[sid.rsplit(":", 1)[1]] = "lc.role." + r

    cands = []
    for pid, rs in src.items():
        lemma, dotted = rs.split("-")[0], rs.replace("-", ".", 1)
        try:
            d = z.read(f"propbank/frames/{lemma}.xml").decode("utf-8", errors="replace")
        except KeyError:
            continue
        m = re.search(r'<roleset id="%s"' % re.escape(dotted), d)
        if not m:
            continue
        seg = d[m.start(): d.find("</roleset>", m.start())]
        roles = {n: desc for desc, n in re.findall(r'<role descr="([^"]*)"[^>]*n="(\d)"', seg)}
        for x, y in itertools.combinations(sorted(roles), 2):
            if SHAPE.search(roles[x]) and SHAPE.search(roles[y]):
                cands.append((pid, rs, x, roles[x], y, roles[y]))
    if not cands:
        sys.exit("no candidate role pairs shortlisted -- refusing to report a clean run over nothing")
    print(f"shortlisted by shape: {len(cands)} candidate pairs across {len({c[0] for c in cands})} predicates")

    from llm_client import call_llm_structured
    rows, rejected = [], []
    for pid, rs, x, dx, y, dy in cands:
        parsed, _ = call_llm_structured(
            model=MODEL,
            messages=[{"role": "user", "content":
                f"PropBank roleset {rs}. Two of its arguments:\n"
                f"  ARG{x}: {dx!r}\n  ARG{y}: {dy!r}\n\n"
                "Are these interchangeable -- would swapping the two participants leave the "
                "asserted fact unchanged? 'Acme merged with Beta' and 'Beta merged with Acme' "
                "assert the same thing, so those are interchangeable. A buyer and a seller are "
                "not."}],
            response_model=Verdict, reasoning_effort="low", num_retries=1)
        roles_here = argpos.get(pid, {})
        rx, ry = roles_here.get(f'ARG{x}'), roles_here.get(f'ARG{y}')
        if not parsed.interchangeable or not rx or not ry:
            rejected.append((rs, x, y, parsed.reason if not parsed.interchangeable else "role ids unresolved"))
            continue
        rows.append({"predicate_id": pid, "role_a": rx, "role_b": ry,
                     "argument_positions": [x, y],
                     "derivation_method": "shortlisted_by_shape_judged_by_model",
                     "confidence_basis": f"PropBank {rs} role descriptions {dx!r} / {dy!r}; "
                                         f"{parsed.reason}",
                     "source_verified": False})
    print(f"symmetric role pairs: {len(rows)} | rejected: {len(rejected)}")
    for rs, x, y, why in rejected[:6]:
        print(f"  rejected {rs} ARG{x}/ARG{y}: {why}")
    if a.write and not rows:
        sys.exit("every candidate was rejected -- refusing to write an empty file that would "
                 "read as 'no symmetric predicates exist' rather than 'nothing survived'")
    if a.write:
        OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        print("(dry run; pass --write to emit)")


if __name__ == "__main__":
    main()
