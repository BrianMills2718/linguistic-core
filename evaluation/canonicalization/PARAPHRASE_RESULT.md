# Paraphrase invariance — run record

**The findings live in the design**, at `docs/design/SEMANTIC_PREDICATE_VOCABULARY.md`,
plan step 2. This file is the run record: how to reproduce it and what the
harness did, so the design does not have to carry that.

## Reproduce

```
pip install -e ".[review]"
python evaluation/canonicalization/score_paraphrase_invariance.py --dry-run
python evaluation/canonicalization/score_paraphrase_invariance.py
```

Seeded (`SEED = 20260908`). Raw output in `paraphrase_results.jsonl`, exclusions
in `paraphrase_excluded.json`. 57 of 66 pairs scored; 7 have no expected
predicates and 2 are schema-blocked, both reported separately and never folded
into an accuracy figure.

## The three iterations, kept because the headline is meaningless without them

| version | what it asked for | result |
|---|---|---|
| 1 | predicate only | over-collapse **69%** — but 14 of 24 differed only in participants it never asked about |
| 2 | predicate + participants + polarity + modality, role names free | under-collapse **82%** — 17 of 18 were identical fillers under different invented role names |
| 3 | same, role ids constrained to the pack's vocabulary | over-collapse **3%**, under-collapse **77%** |
| 4 | + role correspondences derived from PropBank argument positions | under-collapse **73%** |
| 5 | + role ids validated against the pack, retry then exclude | over-collapse **0%**, under-collapse **68%**, 3 excluded |

Each iteration found the measurement at fault rather than the object. Citing any
one of these numbers without the others is citing a harness artifact.

**A sixth pass should** scope-exclude the six entity-resolution pairs per the
coreference ruling, and treat a declared-but-empty optional role as absent rather
than as a difference — one side emitting `'lc.role.price': ''` where the other
omits it is a completeness difference, not a disagreement. Together those account
for roughly ten of the fifteen remaining failures. Neither is tuning toward a
better number; both remove a confound that is already understood.

**Stopped at five deliberately.** Each pass so far found the measurement at fault
rather than the object, and the object-level findings stopped changing after the
fourth. Continuing would be optimising a harness, not learning about the
vocabulary.
