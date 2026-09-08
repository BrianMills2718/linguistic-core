# Consumer wiring: does the vocabulary change what a running system extracts?

Every prior measurement in this repo scored the vocabulary against itself — a
key, a reachability check, a paraphrase scorer. None of them asked whether a
consumer's behaviour changes when the pack changes. This one does.

**Consumer:** onto-canon6's `TextExtractionService.extract_candidate_run`,
`~/code/onto-canon6`, run against real OpenRouter
(`openrouter/deepseek/deepseek-v4-flash`, `reasoning_effort=high`).

**Question:** the published pack cannot represent negation — no `ARGM-NEG`
equivalent role exists. What does the extractor actually do with a negated
sentence, and does adding the role fix it?

## Design

Minimal pair, 3 runs each, on two profiles:

| Profile | What it is |
| --- | --- |
| `0.3.2` | the published lineage, unchanged — negative control |
| `0.3.3-neg` | `0.3.2` plus 4 roles (`modal`, `negation`, `adverbial`, `discourse`) and the verb-inflection value type, bound to `lc:acquire_get_obtain` |

The pair is *"Acme will acquire Beta."* / *"Acme will not acquire Beta."*, not
the *"acquired"* / *"did not acquire"* pair the design originally named. The
extractor narrows its prompt vocabulary with a **word-overlap ranker**
(`_rank_predicates_by_relevance`, `text_extraction.py:3663`), so `acquired`
scores 0 against `lc:acquire_get_obtain` while `acquire` scores 1. The original
pair would have varied the target predicate's presence in the prompt along with
the thing being tested.

`0.3.3-neg` is a **throwaway** composed from a scratch packs root via
`compose_profile(packs_root=...)`. Nothing was published to
`ontology_packs/linguistic_core/`. Its content is copied here as
`scratch_pack_0.3.3-neg/` so the run is reproducible.

## Result

```
0.3.3-neg | Acme will acquire Beta.     | candidates/run=[1, 1, 1]    | with negation role 0/3
0.3.3-neg | Acme will not acquire Beta. | candidates/run=[None, 1, 2] | with negation role 2/3
0.3.2     | Acme will acquire Beta.     | candidates/run=[1, 1, 1]    | with negation role 0/3
0.3.2     | Acme will not acquire Beta. | candidates/run=[0, 0, 0]    | with negation role 0/3
```

**The published pack silently drops negated statements.** Three runs out of
three, the negated sentence produced *zero assertions* — no error, no partial
object, no flag to the consumer. The extractor's own semantic inventory
recorded one meaning (`INVENTORY_MEANING_ID_REPAIR original='m1'`) and then
emitted nothing bound to it. This is honest abstention rather than a false
affirmative — the system does not claim Acme acquired Beta — but the
information loss is total and unsignalled.

**Adding the role fixes it, unreliably.** With `negation` available, 2 of 3
runs emitted it and the affirmative/negated objects differ. The third run
failed outright (`role 'recipient' requires an entity of type
lc:sumo_type.CognitiveAgent`, after all retries) rather than losing the
negation.

**Negative control holds:** the affirmative sentence never produced a negation
role on either profile, 6 runs out of 6. The role is not being emitted
spuriously.

## What this does not show

- **n=3.** Enough to distinguish 0/3 from 2/3; not enough to put a rate on
  either.
- **The predicate is not stable.** The affirmative sentence resolved to
  `lc:accrete_accumulate_gain` twice and `lc:acquire_get_obtain` once on
  `0.3.3-neg`, and to `lc:acquire_get_obtain` all three times on `0.3.2`.
  Predicate selection instability is a separate, unmeasured problem; this probe
  does not control for it, and the profiles are not identical in the prompt
  their ranker builds.
- **The negation filler shape is unconstrained.** One run emitted
  `value_kind="negation", normalized="not"`, another
  `value_kind="boolean", normalized="true"`. Declaring the role without a value
  type for it buys representability, not a canonical form. Closing that needs a
  `value_types` row and a `role_value_kinds` binding.

## Follow-up: declaring the value kind fixes half of it

The first probe found the negation filler's shape unconstrained — one run
emitted `value_kind="negation" normalized="not"`, another
`value_kind="boolean" normalized="true"`. The pack has a mechanism for this:
a `constraints.jsonl` row of `constraint_type: "role_expected_value_kind"`.
**No such row exists anywhere in the published pack**, in any version. One was
added to the throwaway (`negation` -> `boolean`) and the negated sentence run
five more times (`probe_negation_value_kind.py`).

| | before | after |
| --- | --- | --- |
| distinct `value_kind` emitted | `negation`, `boolean` | `boolean` only, 3 of 3 successful runs |
| distinct `normalized` emitted | `"not"`, `"true"` | `True` (bool) and `"true"` (str) — still two |
| hard failures | 1 of 3 | 2 of 5 |

**The constraint reaches the tag, not the value.** `value_kind` is now
canonical; `normalized` still arrives as a JSON boolean in some runs and the
string `"true"` in others, so two extractions of the same negated sentence
still produce non-identical objects. Canonicalizing polarity needs a
normalization rule downstream of the value kind, which the pack has no slot
for.

**A defect this surfaced.** Value fillers came back carrying an `entity_type`
— `lc:sumo_type.BeliefGroup` on one run, `lc:sumo_type.BinaryRelation` on
another — on a filler whose `kind` is `value`, not `entity`. The field is
meaningless there and nothing rejected it.

The failure-rate difference (1/3 vs 2/5) is one event at these sample sizes and
should not be read as the constraint making extraction less reliable.

## Two seam facts this surfaced in onto-canon6

1. **`max_predicates_in_prompt` narrows the prompt but not the response
   schema.** With the knob unset (its state in `config/config.yaml`), the
   5995-predicate prompt is rejected by OpenRouter with HTTP 413. Setting it to
   120 fixes the prompt — ~21k tokens — but `response_schema_mode`'s default,
   `predicate_variants`, still builds a per-predicate Pydantic variant over the
   whole pack and the request fails on a 1,048,576-token input limit. Only
   `response_schema_mode="compact_roles"` runs against a pack this size.

   **Correction, same day:** the first version of this note said the mechanism
   to narrow the schema did not exist. It does.
   `ontology_runtime/schema_selection.py` provides
   `select_schema_packet(profile, source_text=..., max_predicates=16)`, which
   builds a dependency-closed schema packet over selected predicates — exactly
   the missing piece. It is exported from `ontology_runtime/__init__.py` and
   covered by `tests/ontology/test_schema_selection.py`, and **nothing in the
   extraction path calls it**: on `main` its only callers are its own test and
   the package's `__all__`. The one production consumer lives in
   `plan0180-pack-neutral-relation-recovery`, an unmerged 40-day-old branch
   that no longer merges cleanly. So the accurate statement is not "no
   mechanism exists" but "the mechanism exists, is tested, and is unadopted" —
   implementation without adoption, which is a different problem with a much
   cheaper fix.
2. **Seven of eleven proposed modifier roles already ship.** Loading all eleven
   fails composition: `extension identity conflict: section=role_types
   identity=('lc.role.manner',)`. Detail in
   `../../ontology_packs/linguistic_core/_candidates/README.md`.

## Reproduce

```bash
cd ~/code/onto-canon6
SCRATCH=<a packs root containing linguistic_core 0.3.0-0.3.2 plus scratch_pack_0.3.3-neg as 0.3.3-neg> \
ONTO_CANON6_CONFIG=<path to>/onto_canon6_config_overlay.yaml \
OUT=/tmp/out.json \
.venv/bin/python <path to>/probe_negation_representability.py
```

The overlay is `onto-canon6/config/config.yaml` with one line added,
`max_predicates_in_prompt: 120`. It is a copy taken 2026-09-08 and will drift
from that file; regenerate it rather than trusting this one if the run behaves
differently.

`run_negation_representability.log` is the full stdout/stderr of the run that
produced `results_negation_representability.json`, retained because the
zero-candidate outcome is only interpretable alongside the absence of any
rejection message in it.
