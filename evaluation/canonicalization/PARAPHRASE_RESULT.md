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
| 6 | + coreference pairs scope-excluded, empty optional roles treated as absent | over-collapse **0%**, under-collapse **44%** (7 of 16) |

Each iteration found the measurement at fault rather than the object. Citing any
one of these numbers without the others is citing a harness artifact.

**Stopped at six, and this time because the residual is legible rather than
large.** Seven failures remain and each is identified individually in the design:
three are the extractor over-filling optional roles, one is a real passive
inversion the test was built to catch, one is a genuine gap in the object
(symmetric predicates are not declarable, now VF-18), and two are content
differences the key may have labelled too generously.

A seventh pass would be tuning. The object-level findings stopped changing after
the fourth iteration, and what remains is either a known harness property, a true
positive, or a design gap already recorded.
