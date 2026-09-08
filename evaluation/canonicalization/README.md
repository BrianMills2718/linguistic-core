# Canonicalization answer key

`canonicalization_key.jsonl` — 66 sentence pairs labelled `same-object`,
`different-object` or `BRIAN`, built to make the paraphrase-invariance test
scoreable.

## Why this exists

The design's core premise is that different phrasings of one meaning produce one
representation. That premise could not be tested, because no one had decided
*which distinctions the object should discard*. Without that decision a test that
collapses two sentences cannot be scored: collapsing is correct or incorrect only
relative to a policy, and the policy was unwritten.

This file is that policy, written down for 66 cases — 53 of them decided, 13
deliberately not.

Read alongside `docs/design/SEMANTIC_PREDICATE_VOCABULARY.md`, sections
"Canonicalization is a choice, not a property" and "How canonicalization fails,
concretely". This directory adds no claim to that design and does not modify it.

## Schema

One JSON object per line:

| field | meaning |
| --- | --- |
| `id` | Stable identifier. Letter prefix groups by failure mode. |
| `failure_mode` | Which failure mode the pair probes (see below). |
| `a`, `b` | The two sentences. |
| `label` | `same-object`, `different-object`, or `BRIAN`. |
| `contested_axis` | For `BRIAN` rows only: which decision the case turns on. Null otherwise. |
| `expected_predicates` | Pack predicate IDs each side should select. An empty list means nothing in the pack can represent that side. |
| `pack_gap` | A defect or absence in the 0.3.x pack that affects this pair, or null. |
| `reasoning` | Why the label is what it is. |

Predicates are drawn from the cumulative `linguistic_core` 0.3.2 pack
(0.3.2 extends 0.3.1 extends 0.3.0; 5,995 predicates, 4,658 of them events).
Every predicate ID in the file was checked to exist in that union.

## `BRIAN` means unresolved on purpose

A key that quietly picks a side on a contested case is worse than one that flags
the fork, because it silently scores a correct system as wrong. `BRIAN` rows are
cases where two defensible policies disagree, and the choice belongs to the
object's owner rather than to whoever wrote the key.

## The two error directions are not symmetric

Recorded here because it governs how the key should be scored. Under-collapse
loses information; over-collapse **fabricates** it. A scorer that reports a single
accuracy number over this file has already destroyed the distinction the file
exists to preserve. Report the two directions separately.

The `C` series is built around this. `C01` — "Acme agreed to acquire Beta" versus
"Acme acquired Beta" — is the flagship: collapsing it turns a pending deal into a
completed one. `C02`–`C09` and `C12`, `C14`, `C15` are the same shape at other
stages of the same ladder, so a system's behaviour across the series shows
*where* on the pending/completed boundary it fails rather than only that it does.

## Coverage

| Failure mode | Prefix | Pairs |
| --- | --- | --- |
| Different predicates, both defensible | `A` | 12 |
| Roles invert | `B` | 8 |
| Granularity, aspect, modality | `C` | 15 |
| Entity resolution diverges | `D` | 10 |
| Nominalizations unsourced | `E` | 8 |
| Clear negatives | `F` | 10 |
| Vocabulary defect (not in the design's five) | `G` | 3 |

Labels: 34 `different-object`, 19 `same-object`, 13 `BRIAN`.

`different-object` outnumbers `same-object` deliberately. A key weighted toward
collapsing rewards a system that collapses everything, which is the failure the
design says costs most.

Not every negative lives in the `F` series — `B02`, `B06`, `D04`, `D10`, `E03`
and others are negatives placed inside their own failure mode so that each mode
contains both directions. A system cannot pass a mode by always answering one way.

## Findings

### 1. Canonicalization is at least five decisions, not one

13 of 66 pairs (20%) are genuinely contested. They do **not** all turn on the
same question:

| Axis | Contested pairs | The decision |
| --- | --- | --- |
| `entailment-discard` | 6 | How much entailed-but-unasserted content may be dropped (acquired/bought, killed/murdered, said/claimed, gave/donated, left/resigned, said/announced). |
| `role-alignment` | 2 | Whether converse predicates describe one object, which requires a role correspondence the pack does not contain. |
| `event-state-boundary` | 2 | Whether an event and its resulting state are one object. |
| `reference-resolution-scope` | 2 | Whether coreference resolution is inside the canonicalization boundary at all. |
| `light-verb-decomposition` | 1 | Whether "filed a lawsuit" decomposes to the predicate of its nominal. |

`entailment-discard` is the largest cluster but is under half. The design frames
canonicalization as "a knob set per profile" — singular. These pairs say it is at
least five independent knobs, and they are not ordered along one aggressiveness
dial. A profile could reasonably discard lexical entailment aggressively while
refusing to collapse the event/state boundary at all; those settings do not
trade off against each other.

`reference-resolution-scope` is not even the same *kind* of decision as the other
four. It is a scope question about what the object is responsible for, not a
judgement about meaning. It should probably be settled first and separately.

`C13` is contested on two axes simultaneously, so the axes are not fully
independent either.

### 2. A sixth failure mode: the divergence is inside the vocabulary

The design lists five ways canonicalization fails, all of them properties of
language. There is a sixth that is a property of *this pack*: it contains
multiple predicate IDs for one sense, so two systems given the **identical
sentence** can produce different objects with no linguistic difference to explain
it.

Measured across the 4,658 event predicates: **130 mirror pairs**, where predicate
A's gloss names predicate B's label and B's gloss names A's. Examples:

- `lc:aid_help` ("aid" / gloss "help") and `lc:help_aid` ("help" / gloss "help, aid")
- `lc:anticipate_expect` and `lc:expect_anticipate`
- `lc:acquire_get_obtain` and `lc:get_acquire_goods` — the flagship verb is one of them

Related, and worse because the pack asserts the identity itself:
`lc:kill_cause_to_die` and `lc:murder_cause_to_die` carry the **identical gloss**
"cause to die", while the lemmas differ in a legally decisive way.
`lc:rise_go_up` and `lc:increase_go_up` likewise share the gloss "go up".
`lc:buy_purchase` and `lc:purchase_buy` are mirror entries for one sense.

This matters because it is not fixable by profile selection. Both members of a
mirror pair belong to any profile containing the concept, so restricting the
vocabulary does not remove the ambiguity — the `G` series exists to keep this
measurable separately from genuine canonicalization error.

### 3. Three things the pack cannot represent

Found while grounding the pairs, all verified directly against the 0.3.x files:

**No polarity, modality or aspect.** `value_types.jsonl` is empty (0 bytes) in
0.3.0, 0.3.1 and 0.3.2, and the only constraint type present is
`role_expected_entity_type` (11,620 of 11,620). Nothing marks an event as
negated, possible, or non-culminating. So `C08` ("did not acquire" versus
"acquired"), `C09` ("may acquire") and `C12` ("was acquiring") produce identical
structures on both sides. These pairs are labelled `different-object` on meaning
and are currently **unrepresentable**, which is a different failure from getting
them wrong. The five roles whose names suggest modality
(`hypothetical_event`, `future_phenomenon`, `uncertain_situation`, `aspect`,
`sensorymodality`) are frame-specific slots on particular predicates, not an
event-level feature any predicate can carry.

**Roles are frame-specific with no crosswalk.** 903 role types, and converse or
near-synonymous predicates do not share them. `lc:acquire_get_obtain` carries
recipient/theme/source/beneficiary; `lc:buy_purchase` carries
buyer/goods/seller/asset/beneficiary; `lc:lend_give_temporarily` carries
donor/theme/recipient against `lc:borrow_get_temporarily`'s
borrower/theme/lender. There is no edge stating that donor corresponds to lender.
So deciding two predicates should collapse is not sufficient — the role alignment
must be authored too, and no mechanism for it exists. This is the hidden second
half of every `predicate_choice` decision.

Separately: **6 of 11,890** role edges are `required: true`. Effectively no role
is mandatory, so a representation with every role empty is schema-valid and role
inversion cannot be caught structurally.

**The nominal gap is total.** As predicate labels, "acquisition", "merger",
"investment" and "lawsuit" all return zero matches across the predicate union.
"purchase" does return `lc:purchase_buy`, but that is a verb entry glossed "buy" —
the pack's `family` field distinguishes only `event` from `state`, never noun from
verb, so there is no nominal entry as such anywhere in it. Every `E`-series pair
therefore has an empty `expected_predicates` list on one side. This is the known
NomBank licensing consequence, recorded here as eight concrete pairs rather than a
general caution.

### 4. The flagship case has a trap in it

`C01` is the pair the design most cares about. Getting it right requires
selecting `lc:undertake_agree_to_do` (roles speaker/message/undertaking, both
message and undertaking constrained to `sumo_type.Process`, so the acquisition
embeds correctly).

The lemma-obvious choice, `lc:agree_reach_agreement`, is the **wrong frame**: its
roles are cognizer_1/opinion/cognizer_2, and cognizer_2 is constrained to
`sumo_type.Agreement`. That is mutual agreement *about* an agreement object, not
commitment to a future action.

So avoiding the flagship over-collapse error requires selecting a predicate whose
label — "undertake" — does not appear in the input sentence. Any selector that
matches on the input lemma will reach for `agree` and get a structure that cannot
hold the pending acquisition. The good news is that event embedding does work in
general: 233 role constraints expect `sumo_type.Process`.

### 5. One design-document reference is stale

`SEMANTIC_PREDICATE_VOCABULARY.md` cites `lc:acquire_get` in "How canonicalization
fails, concretely". No such predicate exists in the pack; the real ID is
`lc:acquire_get_obtain`. Recorded here rather than fixed, since this work does not
modify the design.

## What this key does not settle

It fixes a policy for 53 pairs and names the fork for 13. It does not decide the
13, and it is scoped to English business and news prose with a synthetic
Acme/Beta cast — chosen so entity-resolution cases stay controlled, at the cost of
not exercising real-world naming noise. The five contested axes are the useful
output; sixty labels without them would be less valuable.
