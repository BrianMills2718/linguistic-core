# Candidates — not a pack version

Content proposed for the pack and **not yet released**. A directory here is
deliberately not a version number: `onto-canon6` and other consumers pin pack
versions, and publishing `0.4.0` would assert a release this has not earned.

## `predicate_relations.jsonl`

Fifteen hand-authored predicate-to-predicate relations, drawn from the nine-term
mapping vocabulary in the design document, answering one bounded question: can
the pack express that two different predicates denote one canonical object?

It could not — `hierarchy_edges.jsonl` carries only `subtype_of`, so nothing
related `lc:acquire_get_obtain` to `lc:buy_purchase`. That left 15 of the 24
`same-object` pairs in the canonicalization answer key structurally unscoreable.

**Result:** all 15 are now reachable.
`python evaluation/canonicalization/check_collapse_reachability.py` reports
`same_UNREACHABLE 0`, down from 15.

**Provenance, stated because it constrains use:** every row is
`derivation_method: authored` and `source_verified: false`. These are judgements
made against the answer key, not derived from PropBank, FrameNet or SUMO. A
donor-derived crosswalk would be stronger and does not exist.

**Why a separate file rather than extending `hierarchy_edges.jsonl`:** consumers
read that file expecting `subtype_of` semantics. Adding `closeMatch` and
`narrowerThan` rows would silently change what an existing file means to an
existing reader. A new file is ignored by anything that does not know it.

**What promotion would need:** relations for the pack at large rather than the 15
the key happens to exercise, a derivation route that is not hand-authoring, and
a consumer that actually reads the file — none of which this slice attempts.

## `modifier_role_types.jsonl` and `value_types.jsonl`

Eleven universal modifier roles and a verb-inflection value type, closing the
last three schema-blocked pairs (C08 "did not acquire", C09 "may acquire", C12
"was acquiring" — each against "acquired").

**This corrects a claim the design made on 2026-09-07.** That revision said
PropBank annotates modality and negation as `ARGM-MOD`/`ARGM-NEG` and "the
import dropped them", implying a recovery from donor data already in hand. Two
parts of that were wrong:

- **`ARGM` appears zero times in PropBank's frame files** — all 3,323 of them.
  The `<roles>` elements declare `n="0"` through `n="5"` and a scattering of
  `n="M"`. There was nothing in the frame data to drop.
- **The `ARGM` annotations live in `prop.txt`**, the annotated corpus: 112,917
  propositions carrying `ARGM-MOD` 11,318 times and `ARGM-NEG` 3,995 times — as
  *token offsets into the LDC-licensed WSJ treebank*. That is the same structure
  that caused NomBank to be dropped, so the instances are not usable here.

**What is usable, and why this is still not a build from nothing.** The *tag
inventory* is universal and documented in PropBank's own README: these modifiers
apply to any predicate, so declaring them needs no instance data and no LDC
licence. Eleven rows, not an import.

**Aspect is not an `ARGM` tag at all.** PropBank encodes it in a five-character
inflection field — form, tense, aspect, voice, person — documented in the same
README (`aspect: p=perfect o=progressive b=both`). "Was acquiring" is
`aspect=o`, not a modifier role. `value_types.jsonl` declares that decomposition;
the shipped pack's `value_types.jsonl` is 0 bytes in every released version.

**Result:** `check_collapse_reachability.py` reports `SCHEMA-BLOCKED TOTAL: 0`,
down from 18 before either candidate slice.

**Provenance:** `derivation_method: donor_asserted`, `source_verified: false` —
taken from PropBank's documented annotation scheme, not from its instance data,
and not independently validated against usage.
