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

## Five-run result, aggregated per pair

`--runs 5`. Under-collapse 6, 8, 8, 9, 7 of 16; over-collapse 0, 0, 1, 1, 0 of 28.

| | pairs |
|---|---|
| always right | 33 |
| flaky (instrument noise) | 8 — A03 A05 B01 B07 C11 C12 C15 G02 |
| always wrong (object, extractor, or key) | 5 — A01 A10 A11 C13 G01 |

**Aggregating per pair is what made this legible.** A rate mixes a case that
fails every run with one that flips between runs, and those mean opposite things:
the first is a property of the system, the second is the instrument. Eight of the
thirteen failures in any given run are the second kind.

Note that B01 (passive inversion) and B07 (merge symmetry) are *flaky*, not
stable — the extractor sometimes handles them. Symmetry declaration helps
sometimes; it is not reliable, and a single run cannot show that.

## The variance check, which should have come first

Three consecutive runs of **identical code** gave under-collapse of 6, 7 and 8 of
16 — **38%, 44%, 50%**. Over-collapse was 0 in all of them, and in a fourth.

So the iteration table above is partly a record of noise. Only version 6's drop is
real, and it comes from excluding ten coreference pairs rather than from any
improvement. The 77→73 and 73→68 steps were one- and two-pair changes at n=16.

**A harness comparison at this sample size cannot resolve a single-pair
difference, and every intermediate claim that one version improved on the last
should be read with that in mind.** The check costs three re-runs and about six
cents; it belonged before the fourth iteration, not after the sixth.

**Stopped at six, and this time because the residual is legible rather than
large.** Seven failures remain and each is identified individually in the design:
three are the extractor over-filling optional roles, one is a real passive
inversion the test was built to catch, one is a genuine gap in the object
(symmetric predicates are not declarable, now VF-18), and two are content
differences the key may have labelled too generously.

A seventh pass would be tuning. The object-level findings stopped changing after
the fourth iteration, and what remains is either a known harness property, a true
positive, or a design gap already recorded.
