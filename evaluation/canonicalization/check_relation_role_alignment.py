"""Do the authored predicate relations survive their own argument structures?

A collapsing relation (exactMatch/closeMatch/broaderThan/narrowerThan) asserts
that two predicate senses denote one canonical object. That is only coherent if
their numbered arguments line up: if ARG1 is the *claim* on one side and the
*defendant* on the other, collapsing them puts the wrong entity in the wrong slot.

`check_collapse_reachability.py` validates that a relation is PRESENT. This one
asks whether it is PLAUSIBLE, by comparing the PropBank roleset argument
descriptions the two predicates derive from. Two relations were found false this
way on 2026-09-08, after passing the presence check.

It is a heuristic, not a proof: it flags for review, and a flag is not a verdict.

Usage:  python evaluation/canonicalization/check_relation_role_alignment.py
"""
from __future__ import annotations
import glob, json, re, sys, zipfile
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
PROPBANK = Path.home() / "code/onto-canon6/data/nltk_data/corpora/propbank.zip"
COLLAPSING = {"exactMatch", "closeMatch", "broaderThan", "narrowerThan"}

MODEL = "openrouter/openai/gpt-5.6-luna"


class _Alignment(BaseModel):
    aligned: bool = Field(description="True if both descriptions denote the same participant role.")
    reason: str = Field(description="One short sentence.")


def _judge_alignment(rel: str, a_rs: str, b_rs: str, args: dict[str, tuple[str, str]]):
    """Decide whether the shared arguments denote the same participants.

    Deliberately a model call, not string matching: deciding whether 'thing
    bought' and 'thing acquired' denote one participant is a question about
    meaning, and the workspace rule forbids inferring meaning from prose by
    pattern. A first version of this check used word overlap and flagged 11 of
    15 relations, almost all falsely.
    """
    from llm_client import call_llm_structured
    lines = "\n".join(f"  ARG{n}: {x!r}  vs  {y!r}" for n, (x, y) in sorted(args.items()))
    parsed, _ = call_llm_structured(
        model=MODEL,
        messages=[{"role": "user", "content":
            f"Two PropBank rolesets are asserted to stand in a '{rel}' relation:\n"
            f"  {a_rs} and {b_rs}\n\nTheir shared numbered arguments:\n{lines}\n\n"
            "Do these argument descriptions denote the same participant roles, such that "
            "collapsing the two predicates would put each entity in the right slot? "
            "Different wording for the same participant is aligned. A genuinely different "
            "participant (for example a claim versus a defendant) is not."}],
        response_model=_Alignment,
        reasoning_effort="low",
        num_retries=1,
    )
    return parsed


def load_rolesets(ids: set[str]) -> dict[str, dict[str, str]]:
    if not PROPBANK.exists():
        sys.exit(f"PropBank not found at {PROPBANK} -- refusing to report a clean run over nothing")
    z = zipfile.ZipFile(PROPBANK)
    out: dict[str, dict[str, str]] = {}
    for rs in ids:
        lemma, dotted = rs.split("-")[0], rs.replace("-", ".", 1)
        try:
            d = z.read(f"propbank/frames/{lemma}.xml").decode("utf-8", errors="replace")
        except KeyError:
            continue
        m = re.search(r'<roleset id="%s"[^>]*?name="' % re.escape(dotted), d)
        if not m:
            continue
        seg = d[m.start(): d.find("</roleset>", m.start())]
        out[rs] = {n: desc for desc, n in re.findall(r'<role descr="([^"]*)"[^>]*n="(\d)"', seg)}
    return out


def main() -> None:
    rels = [json.loads(l) for l in
            open(ROOT / "ontology_packs/linguistic_core/_candidates/predicate_relations.jsonl", encoding="utf-8")]
    src: dict[str, str] = {}
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/source_mappings.jsonl")):
        for l in open(g, encoding="utf-8"):
            d = json.loads(l)
            if d.get("canonical_kind") == "predicate_type":
                src[d["canonical_id"]] = d["source_id"]
    defs = load_rolesets({src[p] for d in rels for p in (d["from_predicate_id"], d["to_predicate_id"]) if p in src})
    if not defs:
        sys.exit("no roleset definitions resolved -- refusing to report a clean run over nothing")

    flagged = 0
    for d in rels:
        if d["relation"] not in COLLAPSING:
            continue
        a, b = src.get(d["from_predicate_id"]), src.get(d["to_predicate_id"])
        ra, rb = defs.get(a, {}), defs.get(b, {})
        shared = set(ra) & set(rb)
        if not shared:
            continue
        args = {n: (ra[n], rb[n]) for n in shared}
        v = _judge_alignment(d["relation"], a, b, args)
        if not v.aligned:
            flagged += 1
            print(f"FLAG  {d['relation']}  {a} -> {b}")
            print(f"        {v.reason}")
            for n in sorted(shared):
                print(f"        ARG{n}: {ra[n]!r}  vs  {rb[n]!r}")
    print(f"\ncollapsing relations checked: {sum(1 for d in rels if d['relation'] in COLLAPSING)}"
          f" | flagged for review: {flagged}")
    print("A flag is a prompt to re-read the relation, not a verdict that it is wrong.")


if __name__ == "__main__":
    main()
