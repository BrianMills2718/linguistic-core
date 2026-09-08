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
