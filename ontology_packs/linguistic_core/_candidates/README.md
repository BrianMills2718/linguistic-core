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

**Seven of the eleven were not missing.** A composition check on 2026-09-08
against the real pack lineage (0.3.0 -> 0.3.1 -> 0.3.2) found that
`lc.role.manner`, `lc.role.cause`, `lc.role.purpose`, `lc.role.direction` and
`lc.role.extent` already ship under exactly those ids, and that `ARGM-TMP` and
`ARGM-LOC` already ship under FrameNet-style names — `lc.role.time` and
`lc.role.location`. Loading all eleven fails composition outright:
`extension identity conflict: section=role_types identity=('lc.role.manner',)
owners=linguistic_core@0.3.0, linguistic_core@0.3.3-neg`.

The genuine gap is **four roles**: `modal` (`ARGM-MOD`), `negation`
(`ARGM-NEG`), `adverbial` (`ARGM-ADV`) and `discourse` (`ARGM-DIS`). This file
still lists eleven rows because the two name-variant cases need a
`role_correspondences`-style decision rather than a silent deletion — but any
consumer must filter to the four before composing, and the row count above is
not a count of new capability.

## What this check cannot catch

`check_collapse_reachability.py` asks whether *a* collapsing relation exists
between two predicates. It does not ask whether that relation is **true**.

An audit on 2026-09-08 found one of the fifteen was not:
`lc:resign_quit_employment narrowerThan lc:leave_move_away` asserted that
resigning is a narrower kind of *physically moving away* — `leave_move_away` is
glossed "move away from", and `lc:quit_leave_job` ("leave your job") existed all
along. The check passed on it, because a relation was present.

Corrected to target `lc:quit_leave_job`, which is true. The consequence is
honest rather than convenient: answer-key pair A08 names `lc:leave_move_away`
for "Jane left Acme", so with the false edge removed that pair reads
`same_UNREACHABLE` again. **`SCHEMA-BLOCKED TOTAL` is 1, not 0.** Either the
key's expected predicate for that sentence is the wrong sense, or the two
predicates genuinely cannot be related — and a false edge should not hide which.

So the class was swept rather than the instance. `check_relation_role_alignment.py`
compares the PropBank argument descriptions behind every collapsing relation and
asks whether the shared arguments denote the same participants — because a
collapse is only coherent if they do.

**Two of fifteen were disqualifying, not one:**

- `lc:resign_quit_employment` targeted the physical-motion sense of "leave".
  Retargeted to `lc:quit_leave_job`.
- `lc:file_seek_claim closeMatch lc:sue_call_to_court` — `file-02` ARG1 is the
  *claim*, `sue-01` ARG1 is the *defendant*. Collapsing them puts the lawsuit in
  the defendant's slot. Demoted to `evokes`, which does not license collapse.

Three more carry a recorded ARG2 divergence and stay: `claim`/`say` (party
claimed for versus hearer), `help`/`aid` (PropBank labels these `benefactive`
and `benefactor` — recipient versus provider), `sign`/`undertake` (co-signer
versus any participant). Their ARG0 and ARG1 align, which is what the answer key
exercises, but **a collapse must not carry ARG2 across**.

**`SCHEMA-BLOCKED TOTAL` is 2** — A08 and A12, both now honestly unreachable
rather than bridged by a relation that misplaces an argument.

The general limit stands: hand-authored judgements. Two in fifteen were wrong on
inspection, and the alignment check is a heuristic that flags for review rather
than a proof.

### A note on how that check is implemented

The first version compared argument descriptions by word overlap and flagged 11
of 15, almost all falsely — "thing bought" against "thing acquired" is one
participant, and no amount of stopword tuning fixes that reliably. Deciding
whether two prose descriptions denote the same role is a question about meaning,
and this workspace forbids inferring meaning from prose by pattern. The check now
asks a light model and flags 5, of which 2 were real.
