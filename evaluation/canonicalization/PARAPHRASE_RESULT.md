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

Each iteration found the measurement at fault rather than the object. Citing any
one of these numbers without the others is citing a harness artifact.

**A fourth pass should**: scope-exclude the entity-resolution pairs per the
coreference ruling, normalise role-id case and prefix, and compare participants
by filler value with role id as a secondary signal. Each removes a known
confound; none is tuning toward a better number.
