# Paraphrase invariance — first measurement, 2026-09-08

The object's founding premise is that two phrasings of one meaning produce one
canonical object. This is the first time it has been scored.

**The headline is not a single number, and treating it as one would mislead.**

| | |
|---|---|
| pairs scored | 57 of 66 (7 have no expected predicates; 2 are schema-blocked) |
| **over-collapse** | **1 of 35 (3%)** — the direction that fabricates |
| **under-collapse** | 17 of 22 (77%) — but see the decomposition |

## Over-collapse is genuinely low, and that is the result worth keeping

3% is the number that matters most, because over-collapse *fabricates*: reading
"Acme failed to acquire Beta" as "Acme acquired Beta" invents a completed deal.
Capturing polarity and modality alongside the predicate is what holds it down —
an earlier version of this scorer asked only for a predicate and over-collapse
was **69%**.

## Under-collapse decomposes, and most of it is not the extractor

Of the 17:

- **~4 are entity-name variants** — "Acme" / "Acme Corp" / "The company". Brian
  ruled coreference *outside* this object's boundary, so the key labels them
  same-object assuming resolved mentions. These should be excluded by scope, not
  scored as failures.
- **~5 are identical filler values under different role ids.** The extractor found
  the same participants; the pack named them differently.
- **~4 are genuine pack role divergence.** `kill` declares killer/victim while
  `murder` declares cause/instrument/victim; `rise` declares theme/distance while
  `increase` declares item/extent. **The relations declare that two predicates
  correspond; nothing declares which of their roles correspond.** A perfect
  extractor cannot collapse these. This is VF-09, now with a consequence.
- **~4 are the harness.** The role constraint is not reliably honoured — the same
  run emits `lc.role.beneficiary`, `beneficiary` and `Beneficiary`.

## What this actually establishes

1. **Over-collapse is controllable** and polarity/modality capture is what
   controls it. That is a real, reusable finding.
2. **Role alignment is the missing piece**, not predicate alignment. Declaring
   that `buy` and `acquire` correspond does nothing if their role vocabularies
   do not.
3. **Three iterations of this scorer each found the measurement at fault**, not
   the object: asking only for a predicate (69% over-collapse), letting role
   names be invented (82% under-collapse), then constraining them (77%). Anyone
   citing one of those numbers without the others is citing a harness artifact.

## What a fourth iteration should fix

Exclude the entity-resolution pairs by the scope ruling, normalise role-id case
and prefix before comparing, and compare participants by filler value with role
id as a secondary signal. None is tuning — each removes a known confound. The
number is not trustworthy as a headline until they are done.

## Reproduce

```
pip install -e ".[review]"
python evaluation/canonicalization/score_paraphrase_invariance.py --dry-run
python evaluation/canonicalization/score_paraphrase_invariance.py
```
Seeded (`SEED = 20260908`). Raw output in `paraphrase_results.jsonl`, exclusions
in `paraphrase_excluded.json`.
