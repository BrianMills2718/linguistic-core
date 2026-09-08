"""Do two phrasings of one meaning select the same canonical object?

This is the object's founding premise, and until now it could not be scored:
the answer key existed but the pack could not express that two predicates denote
one object, so most `same-object` pairs were unreachable by construction. That
gap is closed (`_candidates/predicate_relations.jsonl`), so this measures the
extractor rather than the schema.

**Bounded exception to the reuse rule, stated deliberately.**
`onto-canon6` owns the governed extractor (`extract_candidate_imports`). It is
not reused here because it requires a profile, a store and the promotion path,
and this question is about the *vocabulary* -- given the same candidates, does a
model land on the same object for two phrasings -- not about that runtime. Its
guards, coreference and promotion would all be confounds. `linguistic-core`'s own
instructions say onto-canon6 is a consumer whose runtime questions are not
answered here.

**Design choices that keep the measurement honest:**

- Each sentence is extracted in its *own* call. Asking for both in one call lets
  the model anchor the second on the first, which is the effect being measured.
- Both sides of a pair see the *same* candidate list, so this isolates collapse
  behaviour from retrieval over 4,669 predicates. Those are different questions.
- Over-collapse and under-collapse are reported separately and never averaged:
  under-collapse loses information, over-collapse fabricates it.
- Schema-blocked and no-expected-predicate pairs are excluded and reported
  separately, so a representation gap is never scored as an extraction failure.

Usage:  python evaluation/canonicalization/score_paraphrase_invariance.py [--dry-run]
        (needs `pip install -e ".[review]"` for llm_client)
"""
from __future__ import annotations

import argparse, glob, json, random, sys
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
KEY = Path(__file__).parent / "canonicalization_key.jsonl"
OUT = Path(__file__).parent
MODEL = "openrouter/openai/gpt-5.6-luna"
SEED = 20260908
DISTRACTORS = 3
COLLAPSING = {"exactMatch", "closeMatch", "broaderThan", "narrowerThan"}


class Selection(BaseModel):
    """A canonical object is a predicate AND its participants. A first version of
    this scorer asked only for the predicate and reported 69% over-collapse -- but
    14 of those 24 were pairs differing only in participants it had never asked
    about. Asking for the whole object is what makes the number mean anything."""

    predicate_id: str = Field(description="Exactly one id from the candidate list.")
    participants: dict[str, str] = Field(
        description="Role name to filler, verbatim from the sentence: who/what "
                    "fills each argument, plus any amount, date or price stated.")
    polarity: str = Field(description="affirmed, negated, or unknown")
    modality: str = Field(description="actual, planned, possible, attempted, failed, or unknown")
    rationale: str = Field(description="One short sentence.")


def load_pack() -> dict[str, str]:
    pred: dict[str, str] = {}
    for g in sorted(glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/predicate_types.jsonl"))):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            pred[d["predicate_id"]] = f'{d["preferred_label"]} ({d["description"]})'
    if not pred:
        sys.exit("no predicates loaded -- refusing to report a clean run over nothing")
    return pred


def load_roles() -> tuple[dict[str, list[str]], dict[str, str]]:
    """Declared role slots per predicate, and role id -> label.

    Version two of this scorer let the model invent role names and 17 of 18
    under-collapse cases turned out to be identical fillers under different
    labels -- {'killer','victim'} against {'agent','patient'} for the same
    sentence. Constraining roles to the pack's own vocabulary is the point of
    having one."""
    edges: dict[str, list[str]] = {}
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/predicate_role_edges.jsonl")):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            edges.setdefault(d["predicate_id"], []).append(d["role_id"])
    labels: dict[str, str] = {}
    for g in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/role_types.jsonl")):
        for line in open(g, encoding="utf-8"):
            d = json.loads(line)
            labels[d.get("role_id", "")] = d.get("preferred_label") or d.get("role_id", "")
    if not edges:
        sys.exit("no predicate_role_edges loaded -- refusing to report a clean run over nothing")
    return edges, labels


def load_role_correspondences() -> dict[tuple[str, str], dict[str, str]]:
    """(from_pred, to_pred) -> {from_role: to_role}, derived from PropBank
    argument positions. Without these, two predicates the pack declares related
    still produce different objects because their role vocabularies diverge --
    measured on 2026-09-08 as the leading genuine cause of under-collapse."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for f in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/role_correspondences.jsonl")):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            out.setdefault((d["from_predicate_id"], d["to_predicate_id"]), {})[d["from_role_id"]] = d["to_role_id"]
    return out


def _drop_empty(d: dict) -> dict:
    """A declared-but-unfilled optional role is absence, not a difference.

    One side emitting {'lc.role.price': ''} where the other omits it is a
    completeness difference; scoring it as disagreement conflated roughly four
    harness artifacts with real extraction errors on 2026-09-08."""
    return {k: v for k, v in d.items() if str(v).strip() not in ("", "unknown", "none", "n/a")}


def _participants_match(pa: dict, pb: dict, a_pred: str, b_pred: str,
                        corr: dict[tuple[str, str], dict[str, str]]) -> bool:
    """Same participants, allowing declared role correspondences to bridge
    differently-named roles. Compares filler values, since a correspondence is
    about which slot means what, not what it is called."""
    pa, pb = _drop_empty(pa), _drop_empty(pb)
    if pa == pb:
        return True
    m = corr.get((a_pred, b_pred)) or {v: k for k, v in (corr.get((b_pred, a_pred)) or {}).items()}
    if not m:
        return False
    translated = {m.get(k, k): v for k, v in pa.items()}
    return translated == pb


def load_relations() -> dict[frozenset[str], str]:
    rels: dict[frozenset[str], str] = {}
    for f in glob.glob(str(ROOT / "ontology_packs/linguistic_core/*/predicate_relations.jsonl")):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            rels[frozenset((d["from_predicate_id"], d["to_predicate_id"]))] = d["relation"]
    return rels


def _pairings(a, b):
    """Every (a, b) predicate combination. A side may list several acceptable
    predicates; taking a[0] silently picks one, and two checks built that way
    disagreed on 2026-09-08 because sorting differed between them."""
    return [(x, y) for x in a for y in b if x != y]


def select(sentence: str, candidates: list[tuple[str, str]], roles: dict[str, list[str]],
           labels: dict[str, str], attempts: int = 2):
    """Select a canonical object, rejecting role ids the pack does not declare.

    Without this, 11 of 16 under-collapse failures on 2026-09-08 were the model
    emitting bare 'Speaker' where the pack declares 'lc.role.speaker' -- a harness
    artifact indistinguishable from a real disagreement. Fail loud and retry
    rather than compare strings the vocabulary never sanctioned."""
    from llm_client import call_llm_structured
    parts = []
    for pid, desc in candidates:
        rs = roles.get(pid, [])
        shown = ", ".join(f"{r} ({labels.get(r, r)})" for r in sorted(set(rs))[:8]) or "(no declared roles)"
        parts.append(f"  {pid} = {desc}\n      roles: {shown}")
    listing = "\n".join(parts)
    last_bad: set[str] = set()
    for attempt in range(attempts):
      extra = ("\n\nYour previous answer used role ids this pack does not declare: "
               f"{sorted(last_bad)}. Use only the ids listed above." if last_bad else "")
      parsed, _ = call_llm_structured(
        model=MODEL,
        messages=[{"role": "user", "content":
            f"Sentence: {sentence}\n\nCandidate predicates:\n{listing}{extra}\n\n"
            "Represent this sentence as a canonical object: select the one predicate "
            "that best fits, list its participants with the filler text verbatim "
            "(including any amount, date or price the sentence states), and give its "
            "polarity and modality. Answer with a predicate id from the list."}],
        response_model=Selection,
        reasoning_effort="low",
        num_retries=1,
      )
      declared = set(roles.get(parsed.predicate_id, []))
      last_bad = {k for k in parsed.participants if k not in declared}
      if not last_bad:
          return parsed, True
    return parsed, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pred = load_pack()
    roles, labels = load_roles()
    corr = load_role_correspondences()
    rels = load_relations()
    rows = [json.loads(l) for l in KEY.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(SEED)
    pool = sorted(pred)

    scoreable, excluded = [], {"no_expected_predicates": [], "schema_blocked": [],
                               "out_of_scope_coreference": []}
    for r in rows:
        ep = r.get("expected_predicates") or {}
        a, b = ep.get("a"), ep.get("b")
        if not a or not b:
            excluded["no_expected_predicates"].append(r["id"]); continue
        if r["label"] == "same-object" and sorted(a) != sorted(b) \
           and not any(rels.get(frozenset(p)) in COLLAPSING for p in _pairings(a, b)):
            excluded["schema_blocked"].append(r["id"]); continue
        if r["failure_mode"] == "entity_resolution":
            # Brian's 2026-09-07 ruling puts coreference outside this object's
            # boundary: the IR consumes resolved mentions. Scoring these would
            # measure the resolver, so they are excluded and reported, not hidden.
            excluded["out_of_scope_coreference"].append(r["id"]); continue
        scoreable.append(r)

    print(f"key {len(rows)} pairs | scoreable {len(scoreable)} | "
          f"excluded {sum(len(v) for v in excluded.values())} "
          f"(no expected predicates {len(excluded['no_expected_predicates'])}, "
          f"schema-blocked {len(excluded['schema_blocked'])}, "
          f"out-of-scope coreference {len(excluded['out_of_scope_coreference'])})")
    if args.dry_run:
        print("dry run: no calls made")
        return

    results, invalid = [], []
    for i, r in enumerate(scoreable, 1):
        ep = r["expected_predicates"]
        cands = set(ep["a"]) | set(ep["b"])
        while len(cands) < len(set(ep["a"]) | set(ep["b"])) + DISTRACTORS:
            cands.add(rng.choice(pool))
        listing = [(p, pred[p]) for p in sorted(cands)]
        rng.shuffle(listing)
        sa, ok_a = select(r["a"], listing, roles, labels)
        sb, ok_b = select(r["b"], listing, roles, labels)
        if not (ok_a and ok_b):
            invalid.append(r["id"]); continue
        same_pred = sa.predicate_id == sb.predicate_id
        linked = rels.get(frozenset((sa.predicate_id, sb.predicate_id))) in COLLAPSING
        # a canonical object is predicate + participants + polarity + modality;
        # two sentences collapse only if all four agree
        same_parts = _participants_match(sa.participants, sb.participants,
                                         sa.predicate_id, sb.predicate_id, corr)
        same_stance = (sa.polarity, sa.modality) == (sb.polarity, sb.modality)
        collapsed = (same_pred or linked) and same_parts and same_stance
        expected = (r["label"] == "same-object")
        results.append({**{k: r[k] for k in ("id", "label", "failure_mode", "a", "b")},
                        "picked_a": sa.predicate_id, "picked_b": sb.predicate_id,
                        "same_predicate": same_pred, "linked_by_relation": linked,
                        "same_participants": same_parts, "same_stance": same_stance,
                        "participants_a": sa.participants, "participants_b": sb.participants,
                        "stance_a": [sa.polarity, sa.modality], "stance_b": [sb.polarity, sb.modality],
                        "collapsed": collapsed, "correct": collapsed == expected})
        if i % 15 == 0:
            print(f"  scored {i}/{len(scoreable)}")

    (OUT / "paraphrase_results.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in results), encoding="utf-8")
    (OUT / "paraphrase_excluded.json").write_text(json.dumps(excluded, indent=1), encoding="utf-8")

    if invalid:
        print(f"\nEXCLUDED {len(invalid)}: model would not confine itself to the pack's declared "
              f"role ids after retry -- {' '.join(invalid)}")
        print("Reported rather than compared: an unsanctioned role id is a harness failure,")
        print("not a disagreement between two phrasings.")
    same = [x for x in results if x["label"] == "same-object"]
    diff = [x for x in results if x["label"] != "same-object"]
    under = [x for x in same if not x["collapsed"]]
    over = [x for x in diff if x["collapsed"]]
    print(f"\nUNDER-COLLAPSE  {len(under)}/{len(same)} same-object pairs did NOT collapse"
          f"  ({100*len(under)/len(same):.0f}%)" if same else "no same-object pairs")
    print(f"OVER-COLLAPSE   {len(over)}/{len(diff)} different-object pairs DID collapse"
          f"  ({100*len(over)/len(diff):.0f}%)" if diff else "no different-object pairs")
    print("\nThese are reported separately on purpose: under-collapse loses information,")
    print("over-collapse fabricates it. They must never be averaged into one accuracy figure.")
    if over:
        print("\nover-collapse cases (the ones that fabricate):")
        for x in over:
            print(f"  {x['id']} [{x['failure_mode']}] {x['a']!r} / {x['b']!r} -> {x['picked_a']}")


if __name__ == "__main__":
    main()
