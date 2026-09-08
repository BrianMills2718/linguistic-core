# The Semantic Predicate Vocabulary — design

*(Renamed from "The Semantic Interlingua" 2026-09-07 to resolve a naming
collision with the unrelated `brianmills-spec/requirement-to-runtime-semantic-compiler`
repository — a neurosymbolic world-model / semantic-compiler project that also
used "semantic interlingua" as a name. This document is the SUMO/PropBank/
FrameNet-derived predicate and relation vocabulary; the two projects are
otherwise unrelated, though both draw on the same 2026-09-05 ChatGPT
conversation as source material — see the "Related work" section below.)*

**Status: living document.** Re-derived on each update rather than appended, so
it reads as current state rather than history. `docs/design/DESIGN_LOG.md`
carries what changed and why.

This is the design for what `ontology_packs/linguistic_core/` is becoming. It
was previously a separate repository, `linguistic-vocabulary-research`, on the
reasoning that design discussion should not be pulled into `onto-canon6`. That
reasoning was sound against a *consumer* and wrong against the object itself:
it produced a 500-line design describing an artifact in a different repository,
and within a day it had duplicated a synthesis page in a third. Consolidated
here 2026-09-06.

**Scope boundary that still holds:** `onto-canon6` is a consumer. It cites this
design; this design does not describe its runtime.

## Contents

- [Goal](#goal) — what the object is and why licensing constrains the product
- [What to do, in order](#what-to-do-in-order) — the three bets, ranked by what wastes the most work if false
- [What richness actually buys](#what-richness-actually-buys) — *fixed* and *rich* are different properties
- [What the representation contains](#what-the-representation-contains--first-draft) — the specification draft, its settled commitments, and the July 2026 implementation that already exists
- [Use cases](#use-cases) — which need breadth, which do not, and the consolidated list
- [Current state of the object](#current-state-of-the-object-linguistic-core) and [known gaps](#known-gaps-in-the-current-integration)
- [Proposed architecture](#proposed-architecture) — the resource stack beneath the canonical layer
- [Canonicalization is the hard part](#canonicalization-is-the-hard-part-and-there-is-evidence) — with measured evidence from a prior failure
- [Wikidata belongs in the design](#wikidata-belongs-in-the-design-scoped-to-states) — a correction
- [What the symbolic side can and cannot check](#what-the-symbolic-side-can-and-cannot-check)
- [The neurosymbolic question](#the-neurosymbolic-question) — tested twice, unresolved
- [Licensing](#licensing) — checked against primary sources; two resources removed
- [Open questions](#open-questions)
- [Related work, and where the evidence lives](#related-work-and-where-the-evidence-lives) — prior design on the same question, the implementation that already exists, the consumer's state, the parallel project, external resources and their terms

## Goal

Build the broadest, richest, best-integrated combination of decades of pre-LLM
linguistic and ontological research into a single vocabulary, valued as an
object in its own right rather than for any specific downstream application.

The sharper framing: the object is a **semantic interlingua**. It states what
kinds of things can exist and what can be true of them, so that arbitrary
language can be normalized into typed, canonical events, entities, roles and
relations. "Acme acquired Beta," "Beta's acquisition by Acme," and "Acme bought
Beta" become one representation. The historical resources are the scaffolding;
the interlingua is the product.

Its defining properties: **fixed**, so representations don't drift when a model
changes; **formal**, so a machine can check and reason over it;
**human-authored** by experts rather than induced from data; and
**application-independent**.

**Why this matters:** the vocabulary is meant to be written up publicly and may
become the foundation of a separate paid product.

**Licensing constrains that second goal and the constraint is now checked, not
assumed.** A merged artifact containing PropBank at the current granularity
**cannot be proprietary**, because PropBank's grant is CC BY-SA 4.0 and its
ShareAlike condition reaches a database containing a substantial portion of its
contents. SUMO's GPL extension modules impose the same outcome independently.
So the paid product must be a separate layer that does not redistribute the
licensed content — which is what `linguistic-core` ADR-0040 decision 7 already
concluded for SUMO. The vocabulary is an open artifact; the product sits above
it.

## What to do, in order

This document had described the object thoroughly and never said what to do
about it. The ordering below is by **blast radius** — what, if false, wastes the
most work — not by what is most interesting.

### Three bets, and only one is load-bearing for the rest

1. **Canonicalization is set correctly.** Not "works" — that framing is wrong and
   is corrected in the section below. Canonicalization is a *choice about which
   distinctions to discard*, so there is no standard against which collapsing is
   right or wrong until that choice is made. **The choice has never been made
   here**, which means the experiment cannot yet be specified, let alone run.
   Everything downstream depends on it.
2. **Breadth earns its place.** 4,669 predicates beat a small task-specific
   ontology. **Current evidence is against it**: the one neurosymbolic operator
   that demonstrably worked used *zero* Linguistic Core predicates and was plain
   Python and Pydantic.
3. **The symbolic layer makes operations possible that a neural pass cannot do
   at all.** Catching errors is the narrowest of four, and framing it that way
   undersells it. The vision document's own formulation is that prior reviewed
   structure should *support an operation, expose a violation, constrain a state
   transition, or produce evidence that improves the next proposal.* Only the
   second is error-catching. The others are a feature set rather than a check:
   querying a claim graph, propagating a retraction so dependent conclusions
   fall with it, constraining what transitions are legal, planning over typed
   state, running counterfactuals on a branched scenario. None of those is
   something a neural pass does poorly — they are things it does not do.
   Error-catching is partially answered and conditional (yes for evidence
   grounding, no for recommendation binding); the operations half is untested
   *here* — but **executable implementations of all four exist** in
   `~/code/requirement-to-runtime-semantic-compiler`: truth maintenance with
   retraction propagation, four WTL planners, causal intervention engines and
   scenario branching, with real scaling measurements (retraction under 1 ms and
   `stale_inferred_assertions_after_retraction: 0` from 100 to 50,000
   assertions). **Caveat that changes how to cite it:** that repo's *headline
   benchmark* numbers are not model inference. Verified by opening
   `09_evaluation/run_v0_3_same_session_materialization.py` — every "model
   output" comes from a hardcoded case-index table (`n=int(cid[-2:])`) and the
   file contains no network call or client import. Its deterministic substrate
   measurements are real; its accuracy claims are not yet evidence.

### The order

**0. Settled, 2026-09-07 — and it removes vocabulary breadth from the plan.**
This step used to read "find out whether the backbone already exists at 98.1% in
the donor repo." It was checked against the data. **The pack already ships every
predicate the donor backbone has** — an exact identifier intersection of
4,655 of 4,655, with eleven extra. There is nothing to import and no backbone to
build. Details and the corrected numbers are under "The backbone claim" below.

What that leaves is a different and smaller target: **frame coverage and its
verification.** 2,263 of 4,669 predicates carry a frame candidate — 48.47% — and
every one of them is `source_verified: false`, assigned by a model rather than by
a crosswalk. That, not breadth, is the concrete gap.

**1. Answered, 2026-09-07 — the frame layer must be regenerated, not verified.**
Measured on a seeded sample of 100 of the 2,263 frame candidates, judged against
full FrameNet definitions (available for 100% of rows, so no weakening caveat
applies), classified by the nine-relation vocabulary rather than right-and-wrong,
and stress-tested with a second judge instructed to defend every failure.

- **`exactMatch`: 14%.** Usable under any non-incompatible relation: **39–45%**.
  **`incompatibleWith`: 55–61%.**
- **The relation vocabulary does not rescue it.** An adversarial defence pass
  over the 61 incompatible rows rescued 6. `pour-01`→`Mass_motion` is genuinely
  `broaderThan`; `smolder-01`→`Giving_birth` is not any relation.
- **The assigner's confidence is uncalibrated and faintly *anti*-correlated with
  precision.** Spearman ρ = +0.11. At confidence **1.0, 55% are still
  incompatible.** `exactMatch` rows average 0.736 confidence while
  `incompatibleWith` averages 0.757 and `broaderThan` 0.870. No threshold
  salvages the layer.
- **The errors are not near misses.** Verified directly against `sumo_plus.db`:
  `compute-01` "to calculate" → `Reshaping` at confidence 1.0; `bathe-01` "have a
  bath" → `Filling` at 1.0; `smolder-01` → `Giving_birth`; `shave-01` "to cut" →
  `Soaking`; `demolish-01` "destroy" → `Cause_emotion`. A distinct 10% are sense
  collisions, where the frame fits a *different* sense of the same lemma —
  `punch-01` "press a key" → `Damaging`. The assigner matched lemmas and ignored
  sense numbers.
- **Not a pipeline bug.** Checked: frame ids are self-consistent, neighbours are
  independently mixed, and correlation between row order and correctness is
  +0.012. This is model output.

**So real usable coverage is ≈20% of predicates, not 48.47%, and exact coverage
is ≈7%.** Verification is not the job either: checking 2,263 assignments that are
~58% wrong costs more than redoing them. Regeneration is cheap — 100 alignments
with definitions in-prompt cost $0.05, so all 2,263 is roughly **$1.20**. The
original pass evidently ran without frame definitions in front of it, which with
the ignored sense numbers explains both dominant error shapes. Whatever replaces
it should emit a relation from the vocabulary above rather than a bare link and a
float.

**"Regenerate the frame layer" is not "rebuild the pack", and the difference is
large.** See the provenance split under "Current state" below: a model touched
3.7% of this object's mappings, and that 3.7% is exactly the part that measured
badly. The predicates themselves, their role slots, and the SUMO type layer are
mechanical derivations and are not implicated.

*A note on the 98.1% figure.* The original artifact was **found** on 2026-09-07,
at two independent locations with matching checksums, and verified at 4,575/4,663
= 98.11%. It is still not worth building on, for a better reason than
unavailability: **coverage is not a quality measure.** The two runs agree on only
59.3% of the frames they both assigned, which converges from a different
instrument on the 55–61% incompatible rate measured above. Coverage counts
whether a model emitted a resolvable frame name, not whether it was right.

**2. Answered 2026-09-08, across five runs, aggregated per pair rather than as a
rate — and the rate was hiding the answer.** 47 of 66 pairs scored, after
excluding 7 with no expected predicates, 2 schema-blocked, and 10 entity-name
variants the coreference ruling puts outside this object's boundary.

**Over-collapse: 0 in three runs of five, 1 in the other two.** The direction
that *fabricates* is essentially absent once the canonical object carries polarity
and modality alongside the predicate. A version of the scorer asking only for a
predicate measured **69%**. **The control on fabrication is stance capture, not a
better model.** This is the finding the design was built to get.

**Under-collapse ranged 6 to 9 of 16 across five runs** — 38% to 56%. Quoting any
one of those is quoting noise. Per pair, over five runs:

| | pairs | what it means |
|---|---|---|
| always right | **33** | stable success |
| **flaky** | **8** | the extractor is inconsistent here — *instrument*, not object |
| **always wrong** | **5** | the object, the extractor's limits, or the key |

**Read individually, none of the five stable failures is the vocabulary lacking
something:**

- **A01, A10, G01 — the extractor picks inconsistent or extra slots.** For "Acme
  acquired Beta" it put Acme in `beneficiary` (ARG4) while the paraphrase used
  `buyer` (ARG0); for "Revenue rose 8%" it used ARG2 on one side and ARG3 on the
  other. The declared correspondences map ARG*n* to ARG*n* and cannot bridge a
  slot the extractor chose wrongly.
- **A11 — a real content difference.** "cut 400 jobs" against "reduced headcount
  by 400": *jobs* and *headcount* are not the same filler.
- **C13 — arguably a key labelling error.** "agreed to acquire" and "signed an
  agreement to acquire" fill genuinely disjoint frames (`speaker`/`undertaking`
  against `signatory`/`agreement`), and "an agreement" is not "acquire Beta".

**So the vocabulary work holds.** Predicate relations, derived role
correspondences, symmetric role pairs and modifier roles are each doing their
job; what remains is extractor slot-discipline and two arguable labels. **The
premise is not failing — the instrument was.**

*Six scorer iterations preceded this, each finding the measurement at fault
rather than the object, and four of those six comparisons were later shown to be
inside the noise band. The run record carries all of it; per-pair aggregation
over repeated runs is what finally separated signal from instrument.*

**3. Run the coverage audit that has been specified and never executed.** The
eight categories in `world-substrate`'s binding contract, checked against this
pack and its donors. This converts "the broadest, richest object" from an
aspiration with no stopping condition into a finite list of what is missing —
which is the only thing that makes "richest" a plannable goal rather than an
open-ended one. Its measured findings already include three concrete absences:
reversative senses, rights, and any way to express *unowned*.

**4. Close the representation gaps that block every use case equally.** Entity
resolution, which is absent and is most of the real engineering cost; a
representable state for an extractor that returned nothing, against a measured
one-in-eight rate; and coverage as an evaluation metric, since it is missing
from the inherited seven and is the number that ended the previous attempt at
47%.

**5. Then commit to one use case.** This ecosystem's own documentation is the
leading candidate and is under test — it is simultaneously a use case, the
claim-shaped evaluation corpus that has never existed, and a direct exercise of
proposition identity.

### What not to do yet, and why

- **Do not add source vocabularies** until 0 and 2 are answered. Adding sources
  before knowing whether the backbone exists, or what is actually missing, is
  motion without a target.
- **Do not regenerate the PropBank glosses.** That work was scoped to make the
  object non-ShareAlike, and ShareAlike does not obstruct the actual goal — using
  this object inside a commercial product is unaffected. It would also be larger
  than it looked, since the predicate identifiers embed the same sense
  distinctions as the descriptions.
- **Do not adopt the July propositional implementation** until the reification
  question is decided, because that decision changes its cost from a
  promotion-path rewrite to a convention.

## What richness actually buys

*Fixed* and *rich* are separate properties, and most of what gets claimed for
rich vocabularies is really the value of fixed ones. Fixedness is what lets
knowledge accumulate across time and systems: predicates that come from a
model's momentary judgment produce graphs that cannot be joined a year later.
Twenty stable predicates give that as completely as four thousand do.

Richness specifically buys three things:

1. **Speaking other people's dialects.** Every annotated corpus, published
   dataset and partner schema uses labels that are not yours. You cannot
   translate a label you do not hold, so this scales directly with breadth.
2. **The long tail.** Models handle common relations well and rare ones
   unreliably. A resource encodes rare ones at the same fidelity as common
   ones. This matters for legal, military and scientific text where the rare
   relation is the point.
3. **Entailment and nominalization.** That "gave" entails "received," and that
   "the destruction of the city" is the same predicate as "destroyed the city,"
   lets a system answer questions the text never literally states. NomBank
   exists for the second half.

A fourth property is unique to the full five-layer stack: **multi-level
representation.** The same fact is readable as a word sense, a predicate with
numbered arguments, a frame with named elements, thematic roles, and an
ontological type. A rule about acquisitions, one about ownership transfer, and
one about events can all fire on the same input at different abstraction
levels. Nothing built here yet exploits this.

## What the representation contains — first draft

This is a draft to argue against, not a settled specification. It states what
the canonical layer holds, which is a different axis from the resource stack
below: that section says what feeds the object, this says what the object *is*.

Two design commitments are settled and the rest follow from them.

**Settled: the object is a canonical layer, not a merge.** Canonical classes are
authored independently and each source resource attaches by a versioned mapping
object. Nothing collapses WordNet, PropBank and FrameNet into one table. This
preserves the distinctions the resources exist to make, and it is the same
position `~/code/semantic-foundry` holds, reached independently.

*The representation and the distribution are different levels, and conflating
them produced an apparent contradiction in an earlier revision of this document.*
The IR is a canonical layer by construction — its predicates carry `lc:`
identifiers and independently authored labels. Whether a **shipped pack** also
embeds source text is a packaging decision, and licensing attaches to what is
distributed, not to what the representation permits. See "Licensing" for where
the current pack actually stands.

**Settled: a proposition can fill a role.** This is what makes one mechanism
serve both event-shaped and claim-shaped text. An event is a proposition with
participants. A claim is a proposition with another proposition as a
participant. Without this, claims need a parallel vocabulary; with it, the
speech-act frames the resources already carry (`say.01`, `argue.01`, FrameNet's
Statement and Reasoning) do the work.

### The primitives

| Primitive | What it holds |
|---|---|
| **Entity** | Something with identity that persists across mentions |
| **Proposition** | A statement that can be true or false, with its own identity, able to fill a role in another proposition |
| **Event** | A proposition with participants and a time |
| **Role** | A typed slot whose filler may be an entity, a value, *or* a proposition. Roles carry stable identity independent of position and player type: two roles sharing a type are not interchangeable |
| **Stance** | Attitude predicates taking propositions: asserts, doubts, argues, concedes, attributes |
| **Modality** | Hedging and likelihood on propositions, including calibrated terms where a community defines them |
| **Value** | Including gradable terms that stay terms, and kind-level claims that stay kind-level |
| **Time** | Source time and valid time kept separate (the four-clock model the Inside Success graph-maintenance methodology already specifies) |
| **Provenance** | Source, exact span, extractor, and three separate uncertainty numbers |
| **Reading** | A human-readable template for a predicate, e.g. `"{part} is in {bin} in {warehouse}"` — a review surface, a diagnostic, and the path to verbalization |
| **Mapping** | How a canonical class attaches to a resource, under the typed relation vocabulary below — never a bare "same as" |

### Three requirements that are easy to get wrong

**Do not coerce gradable values into numbers.** "A significant increase in risk"
is not ambiguous — a reader knows what it conveys — but there is no threshold,
so there is no number. A schema demanding one gets given an invented 0.7, and
downstream everything treats that as measured. Degree terms stay terms.

**Do not flatten kind-level claims into universals.** "Dogs bark" is a claim
about a kind, not about individual dogs. A representation with only
individual-level predication turns it into a false universal.

**Keep three uncertainty numbers separate.** How confident the parser was that
it read the sentence correctly; how strongly evidence supports the assertion;
how likely the thing is to be true or to occur. Collapsing them into one
confidence float is the mistake most systems make and regret.

Ambiguity, by contrast, is handled and is not a gap: multiple hypotheses with
explicit uncertainty, and where a human cannot resolve it, neither can anything
else.

### Settled: the IR permits, the profile restricts

Propositions-as-arguments is a property of the *representation*, not an
obligation on every pack. A domain pack that never needs nesting never pays for
it, exactly as a pack today ships eight predicates while the runtime supports
thousands. This dissolves most of the apparent cost: query and extraction
complexity are borne only where the use case actually calls for claims about
claims.

### Settled: proposition identity is the design, not a tax on it

Deciding that "Smith argues deterrence failed" and "deterrence failure is
Smith's contention" are the same claim is the same problem as deciding two
mentions are the same entity. If the object's core value is that different
phrasings of one meaning get one representation, then propositional identity is
that value applied to propositions — not an extra cost incurred by allowing
them. It is also unavoidable: separate machinery for claims would still have to
decide when two claims are the same in order to aggregate or contradict them.

### This was already decided, in July 2026

Every path in this subsection is relative to the `onto-canon6` repository
(`~/code/onto-canon6`), not to this one.

`src/onto_canon6/document_map/operational_semantics_v1.py` defines a **semantic
object** as `event | state | proposition`, and an argument target as
`entity | semantic_object | literal`. So an argument can already point at a
proposition. The same module types polarity (`affirmed | negated | unknown`),
modality (`actual | planned | possible | expected | required`), temporal scope,
and a relation vocabulary including `supports`, `contradicts`, `responds_to`,
`updates` and `supersedes`.

That is the claim-shaped half of this specification, already typed, written in
July and never carried to the production path. The live extraction path still
allows only `entity | value | unknown` as filler kinds.

The subtree it lives in is marked retained research: 90 modules, ~61k lines,
frozen since July 2026, referenced by no product entrypoint *directly* — the
qualifier matters, since `src/onto_canon6/__init__.py` re-exports 30 of its
modules and the workbench reaches one through `workbench/governed_model.py` —
with its own
instruction to preserve rather than extend it and not to wire it into a product
path without a plan that says so.

### It ran once, on 2026-07-24, and the evidence is mixed

Verified directly against 95 provider traces: 80 parseable responses, **$4.28**,
producing 823 semantic objects (600 event, 190 state, 33 proposition) over real
Slack work-status messages from a daily-log channel.

The distinctive capability was barely exercised. Of **2,335 arguments, 6 pointed
at another semantic object** — 0.26% — and all six are work-item or blocker
composition (a status object hanging off an activity), never the strong case of
an argument pointing at a *claim*. The two relation kinds that would carry
argumentation, `contradicts` and `supersedes`, **never fired once**.

**But the corpus was wrong for the feature.** Slack standup messages are
event-shaped; nobody writes "Smith argues that X" in a work update. So 6/2,335
is weak evidence against propositions-as-arguments, because the run tested them
where they would not be needed. This is not a settled negative.

It was **never scored** — no precision, recall or agreement exists anywhere, the
plan's capability checklist has every relevant box unchecked, and the artifact
table has no row for it. Its one human review found a safety failure (source
author assigned as responsible person for reported work) and rejected the
result. The plan declared it "not an active acceptance gate" the same day.

Contrast on the identical document: the production `entity | value` route
produced 4 accepted assertions for under a cent.

### The real barrier is the promotion core, not the extraction schema

This part is corpus-independent and decides the effort question. Widening
extraction is a day. The blockers are:

- `src/onto_canon6/core/graph_models.py` types the promoted filler kind as `entity | value`;
- `src/onto_canon6/core/graph_store.py` raises on any third value — in Python
  only. The SQLite column is a bare `filler_kind TEXT NOT NULL` with no `CHECK`
  (`graph_store.py:693`; the file's only two `CHECK` constraints, at :705 and
  :715, are on other columns). That is worse than a narrow schema, not better:
  the store's guarantee lives entirely in application code, so widening it means
  auditing every write path rather than altering one constraint;
- `src/onto_canon6/core/assertion_identity.py` computes identity from entity IDs plus a value
  digest, with no branch for a proposition-valued role;
- there is **no adapter at all** from the semantic bundle into candidates or
  promotion. The lane terminates at a digest-bound bundle.

### But that cost is for one implementation, not for the commitment

The estimate above prices *widening the filler kind*. A 2026-09-06 review
pointed out that propositions-as-role-fillers may not require that at all, and
inspecting the store confirms it. **Reification is available today, with no core
change:**

- `promoted_graph_entities` is `(entity_id, entity_type, first_candidate_id,
  created_at)`, and `entity_type` is unconstrained free text — so an entity typed
  `Proposition` is already legal.
- A role filler with `filler_kind="entity"` satisfies its foreign key as long as
  a real entity row exists. Nothing inspects what the entity denotes.
- `assertion_identity.py` hashes `(role_name, entity_id)` for entity fillers and
  looks no further. Two roles pointing at the same proposition therefore get the
  same digest, which is the behaviour wanted.

So a proposition can fill a role today by minting a proxy entity that stands for
an assertion. No new filler kind, no schema migration, no rewrite of the
promotion path.

**What it costs instead**, because it is a convention rather than a type:

- A rule for deriving the proxy's `entity_id` from the assertion it reifies.
- `first_candidate_id` is `NOT NULL`, so every proxy entity must name a
  candidate it was born from. For a proposition that reifies an existing
  assertion, which candidate that is needs deciding.
- **Proposition identity is relocated, not solved.** It becomes the question of
  when two proxy entities denote the same proposition — the same open problem,
  now inside the entity resolver.
- Traversal gains a hop, and any consumer that does not know the convention sees
  a bare entity with no attributes rather than a claim.
- Nothing enforces that a `Proposition`-typed entity has an assertion behind it.
  The type system stops helping exactly where it was helping before.

**This is the fork that actually matters for the disposition question**, and it
is not adopt-versus-reimplement. It is: pay once in the core for a checked third
filler kind, or pay continuously in conventions and a resolver for reification.
The July implementation assumed the first. Nothing has yet tested the second.

Plus the n-ary model would have to state what a role edge pointing at an
assertion rather than an entity *means*, and every export would have to carry it.

**So: a rewrite of the promotion path, not a port.** The port surface is 8
modules and ~7,080 lines, and the subtree's own instructions require an explicit
plan before any of it reaches a product entrypoint.

### What this leaves open

**Does the July work become the production shape, get reimplemented in the
current path, or stay where it is?** That is now the real question, and it is
narrower than the design question it replaced. Before answering it: establish
whether that code was ever run against real text and what it produced. Evidence
that it worked is worth more than a fresh experiment.

Composition: how a binary entity-edge operator composes losslessly with an
n-ary assertion-and-role operator. Open in the Inside Success graph-maintenance
methodology too (§24.12), and the exact seam this representation sits on.

### The mapping relation vocabulary

> **This was derived here on 2026-09-07 and already existed.**
> `requirement-to-runtime-semantic-compiler/15_lexical_grounding/GROUNDING_SCHEMA_V1_0.json:69-82`
> is a frozen JSON Schema whose relation enum carries eight of the nine below
> plus `eventSemanticsContributes`, `nominalizes` and `crosswalkEvidence`; only
> `incompatibleWith` is missing. Its `LEXICAL_GROUNDING_SPEC_V1_0.md:34` carries
> the same `acquire` worked example, and `ACQUISITION_CROSSWALK_V1_0.yaml` is a
> 432-line implementation of it. Both derivations come from the same source
> conversation — one source harvested twice, not independent corroboration.


A mapping is not an equality. The source design specifies nine relations, for
the stated reason that anything less "destroys distinctions in the source
resources":

`exactMatch` · `closeMatch` · `broaderThan` · `narrowerThan` · `lexicalizes` ·
`evokes` · `roleEquivalentInContext` · `roleSpecializes` · `incompatibleWith`

Each mapping carries this relation plus a **confidence** and a **provenance** —
which resource, which version, assigned by whom or what.

**The worked case in the source** maps WordNet `acquire.v.01` to a domain class
`AcquisitionEvent`. That is not `exactMatch`: the WordNet sense also covers "she
acquired a reputation", which a corporate-acquisition schema should exclude. The
honest relation is `closeMatch`, with the distinction recovered by hierarchy
rather than by the mapping —

```
WordNet acquire.v.01 --closeMatch--> AcquisitionEvent
                                       └─subclass─> CommercialAcquisition
                                                      └─subclass─> CorporateAcquisition
```

**The current schema cannot express any of this**, storing each frame mapping as
a bare predicate-to-frame link with a confidence float. That is a real defect —
but, as measured below, it is not the defect causing the frame layer's problem.

## Use cases

Those that genuinely require breadth:

- **Framing detection.** The same event as an attack, a raid, or an operation
  is one event with three stances. Predicate choice *is* framing, and a rich
  vocabulary makes that measurable rather than impressionistic. Twenty
  predicates flatten exactly the distinctions that carry it. This is already
  Brian's F1 fixture (Iran framing across four federal instruments), complete
  for its bounded scope, with the open question being whether it recurs as a
  real workflow and beats the manual baseline.
- **Gold-standard evaluation.** PropBank and FrameNet are not only resources to
  merge; they are answer keys written by linguists over years. A crosswalk to
  them converts extraction quality from one person's judgment on a handful of
  paragraphs into a number over thousands of expert-labeled sentences. This is
  the shortest path from idea to defensible claim.
- **Cross-lingual comparison.** PropBank and FrameNet exist for other
  languages. The predicate becomes the interlingua, and comparison across
  languages comes nearly free.
- **Obligation and compliance typing.** Regulations and contracts are dense
  with must, shall, may, is exempt from. Typing obligations lets a policy be
  checked against the regulation it claims to satisfy. Needs fine deontic
  distinctions a small pack will not carry.
- **Agent interoperability.** One agent says `purchase`, another `acquisition`,
  a third `change_of_control`. A shared semantic layer says these are the same
  concept and how their arguments correspond. This is the most modern framing
  and the least explored here.

Those that a small fixed vocabulary serves equally well: cross-study
comparison, policy tracing, agent memory durability, action grounding.

The pattern: breadth earns out wherever the task is **comparison across
something** — across sources, languages, time, or schemes. A single project
analyzing its own documents never needs it.

### The fuller list, consolidated

Earlier passes kept re-deriving a narrow subset. The complete set raised so far,
grouped by what they need from the object:

**Normalization — many phrasings, one representation.** Retrieval that finds
"Microsoft's acquisition of X," "X was bought by Microsoft" and "Microsoft
purchased X" as one thing. Schema integration between organizations whose
`Customer`, `Client` and `Account` mean different things. Explainability, where
a system can say *why* two statements match by naming the frame, sense and type
they share rather than asserting similarity.

**Interface — one representation, many systems.** Natural-language front ends to
databases and tools, where language compiles to a semantic form and then to a
query or call, making the step auditable instead of prompt-dependent. Agent
interoperability, where one agent's `purchase`, another's `acquisition` and a
third's `change_of_control` are known to correspond and their arguments map.
The semantic control plane for a composable software library, where capabilities
declare what they provide and consume in shared terms so they compose safely.

**The first corpus should be this ecosystem's own documentation.** Brian's
observation, 2026-09-07, and it is three things at once rather than a use case
with a cute framing.

*As a use case*, it is contradiction detection over a claim graph — the reasoning
application already listed below, run on documents rather than on external
prose. Two real instances from 2026-09-06: one wiki page asserted a predicate
family had zero members while its sibling recorded eleven from the pack's own
metadata; and this design asserted that events carry effects while
`world-substrate`'s accepted decision states a predicate never implies an
implemented effect. Both are pairs of propositions that cannot both be true, and
both survived every structural gate in the ecosystem because those gates check
whether a document was edited recently or in step with code, never whether it is
consistent with another document.

*As an evaluation corpus*, it supplies what the claim-shaped half of this
specification has never had. The single run of the propositional schema used
Slack standup messages, which are event-shaped — nobody writes "Smith argues
that X" in a work update — so propositions-as-arguments fired 6 times in 2,335
arguments and the result was recorded as weak evidence rather than a negative.
**Design documents are claim-shaped text.** They are the corpus that experiment
was missing, they are already written, and four labelled positives exist from
2026-09-06 alone. Ground truth is judgeable by the person who owns the
documents, which removes the annotated-corpus cost that normally gates this kind
of evaluation.

*As a test of the load-bearing commitment*, it exercises exactly the mechanism
this design says makes one representation serve both halves: a claim is a
proposition with another proposition as a participant. "This document asserts P"
and "that decision asserts not-P" is that shape, and detecting the conflict
requires proposition identity — the open question this design already calls
central.

### It was tested, 2026-09-07, and the corpus works

One pass, no prompt tuning, **$0.14**. The retained July schema was called
unmodified over four pre-correction revisions of these documents — 15 calls, 13
usable. Numbers recomputed from the raw records rather than taken on report.

| | July, Slack standups | 2026-09-07, design documents |
|---|---|---|
| semantic objects | 823 | 291 |
| **proposition-typed** | **33 (4.0%)** | **176 (60.5%)** |
| event-typed | 600 (72.9%) | 17 (5.8%) |
| **arguments targeting another object** | **6 / 2,335 (0.26%)** | **12 / 929 (1.29%)** |
| `contradicts` / `supersedes` fired | 0 / 0 | 2 / 3 |

**The 6-in-2,335 result is dead as a negative.** It measured the corpus, not the
capability, exactly as this document predicted: proposition share rises fifteen-
fold on claim-shaped text. The type system carries real load — `proposition`,
polarity and modality all did work.

**The strong case came out well.** For the effects-versus-no-effects pair, both
sides extracted as propositions with *opposing polarity* — affirmed against
negated — and, more usefully, opposing modality: **possible** against
**actual**. That distinction is precisely what makes "events *can* carry
effects" and "a predicate *never* implies an effect" a genuine conflict rather
than a difference of emphasis.

**Three things block automatic detection, and only the third is fundamental.**

1. *Argument role names are invented per call.* The same fact was labelled
   `missing_predicate_count` in one call and `state_predicate_count` in another,
   so no check can align them.
2. *Subjects split between literal strings and entity references* for the same
   referent, and counts stay unparsed prose.
3. **`object_relations` are proposal-local, and both known contradictions span
   two documents in two calls — so `contradicts` could not have fired on either,
   by construction.** This IR has no representation for a relation between
   claims in different documents. That is not a model failure or a tuning
   problem; it is a gap in the specification, and it blocks contradiction
   detection as a use case regardless of extraction quality.

The weaker half of the result is that argument nesting rose only fivefold and
stays at 1.29% — the model types objects as propositions readily but rarely
points one argument at another. Whether that is a prompt property or a real
limit is untested.

Also measured: the empty-output problem does not appear as an empty return here,
because the schema makes one unrepresentable. It surfaces instead as a
**post-parse schema rejection** — 2 of 15, 13.3%, the same magnitude as the
one-in-eight baseline. Provider-accepted JSON that the model then failed to
validate. The absence named above still has no representable state; it has moved
where it shows up.

Two limits, recorded rather than glossed. Not every failure is a contradiction:
the case where this design cited a superseded precision figure is a *supersession*
problem, not a conflict, and catching it needs the `supersedes` relation the July
schema types and nothing currently uses. And extraction returns nothing on
roughly one call in eight, so claims would be missed silently — which is the
absence this document names above as having no representable state.

**Reasoning and state.** World modeling — but **not** by making canonical events
carry effects. An earlier revision of this document said exactly that, and it is
contradicted by the only real world-model consumer. `world-substrate`'s accepted
decision 003 (2026-09-02) is explicit: *"A Linguistic Core predicate never
implies an implemented effect."* The vocabulary identifies predicate senses,
participant roles and semantic relationships; **installed mechanics** supply
persistence, applicability, authority, quantities, effects, scheduling,
invariants and commit behaviour. Treat that as a settled constraint on this
object, not an open question.

What that consumer asks of the vocabulary instead is a **binding
classification** — for each occurrence, which of seven mechanical roles it plays:
primitive intentional action; autonomous or environmental process; state
relation; composite event; analytic or emergent pattern; plan, intention or
declaration; or institutionally enforced transition. Nothing in the primitives
table above can express that distinction today, and it is the concrete
world-modeling requirement.

It also supplies the test for deciding: *if lower-level events were held fixed
and the named phenomenon were removed, would future state transitions or
affordances change?* If not, the phenomenon is a derived description and must not
duplicate the effects of what it summarizes.

Planning, which is the same transition model read in the other direction. Counterfactual and
scenario simulation over typed state. Digital twins of an organization, where
suppliers, contracts and obligations are live state rather than documents.

**Generation and evaluation.** Synthetic training data, where one formal
representation yields many linguistically varied expressions of the same
meaning. Benchmark construction targeting sense distinction, role assignment,
paraphrase equivalence and type consistency.

Most of these are normalization or interface use cases, which is the tell: the
object's value is concentrated in being an *interface*, and the reasoning
applications sit downstream of that rather than beside it.

## Current state of the object (`linguistic-core`)

- Public repo, real git history, GPL-compatible license with SUMO/PropBank/
  FrameNet attribution.
- SUMO: 45 of 66 upstream modules cleared for publication after a
  module-by-module license read (ADR-0040, in the `linguistic-core` repo).
  1,061 relation predicates and 268 entity types from the cleared set.
- PropBank and FrameNet integrated only as a lexical/ID-level correspondence.
  Inspecting the data shows it is weaker than "unverified": each row carries
  `row_mapping_method_ref: llm:gemini/gemini-2.5-flash` and a
  `row_mapping_confidence` — measured over the 2,262 such rows in `0.3.0`, the
  range is 0.1 to 1.0, with 311 rows below 0.7 and 290 at 1.0. (The upstream
  SQLite columns are named `mapping_source`/`mapping_confidence`; the pack's
  field names differ, so grep for the `row_`-prefixed ones.) The correspondence
  is a model's guess with a score attached, not an expert crosswalk, and the
  scores run lower than a summary band suggests.
- The PropBank content is tagged `source: propbank:nltk` — 4,666 predicates and
  11,880 role slots — and includes verbatim PropBank description text. See the
  licensing section: NLTK's package is "distributed with permission" to NLTK,
  which is not a redistribution grant flowing downstream.
- **The event-only description is out of date and applied only to `0.3.0`**,
  where the split was 4,658 event and 11 state predicates. The state gap was
  closed in the two versions since: `0.3.1` adds 265 predicates and `0.3.2`
  adds 1,061, and `lc:citizen`, `lc:birthplace` and `lc:birthdate` all ship
  today. What remains open is coverage breadth across the state family, not its
  absence — and the Wikidata section below should be read as extending a
  populated family rather than founding an empty one.

### How each part of the pack was actually produced

Counted across both mapping files at `0.3.0`, by derivation method rather than by
description:

| content | rows | how produced |
|---|---|---|
| PropBank role slots | 11,880 | `corpus_derived` — read from PropBank |
| PropBank predicate derivations | 4,666 | `corpus_derived` |
| SUMO role positions | 23,770 | `donor_asserted` — read from the donor database |
| SUMO type constraints | 10,093 | `donor_asserted` |
| SUMO derivations and subtypes | 10,024 | `donor_asserted` |
| **FrameNet frame candidates** | **2,262** | **`llm:gemini/gemini-2.5-flash`** |
| SemLink | 1 | crosswalk |

**60,433 mappings; a model produced 2,262 of them — 3.7% — and that 3.7% is the
layer measured at 55–61% incompatible.** Everything else is mechanical
derivation from PropBank rolesets and SUMO modules, with no model judgement
anywhere in it. The 4,669 predicates themselves (`abandon-01` →
`lc:abandon_leave_behind`) are not in question; what broke is the layer asserting
which FrameNet frame each one evokes.

**A schema defect this exposed.** `source_verified: false` appears on the
mechanical rows *and* on the model-generated ones. "Nobody re-checked what SUMO
asserts" and "a model guessed and nobody checked" are very different claims, and
this pack cannot distinguish them. That is why a layer that is 61% wrong sat
indistinguishable from 58,000 sound rows for months. The fix is to surface *how*
a row was derived at the same prominence as whether it was verified — the
`derivation_method` values already exist in the data and are simply not used as a
trust signal.

## Known gaps in the current integration

Checked, not assumed:

- **PropBank↔FrameNet correspondence is unverified.** It comes from an internal
  database join. The pack's provenance file marks it `license_status: unknown`
  and `historical_evidence_kind: current_reference_only` — the same looseness
  the SUMO modules had before ADR-0040.
- **No thematic-role backbone.** Roles are named ad hoc per predicate.
- **No nominal-predicate coverage.**
- **No WordNet integration**, despite WordNet being the hub the other resources
  link through.
- **SUMO's own official WordNet→SUMO mapping is not imported.**

## Proposed architecture

Each layer keying into the one below rather than being independently
re-derived:

1. **WordNet synsets** as the base lexical identity layer.
2. **VerbNet** as the thematic-role backbone. Its role inventory is more
   systematic than PropBank's numbered arguments or FrameNet's per-frame
   elements, and its classes already link to WordNet senses.
3. **The crosswalk layer — not SemLink.** SemLink was the obvious choice and it
   is unusable: its repository carries no license of any kind, so it cannot be
   redistributed. Two licensed substitutes together replace it:
   - **PropBank's own `rolelink` elements**, CC BY-SA 4.0: 39,810 VerbNet role
     links and 11,314 FrameNet role links across 11,208 rolesets, at role-level
     granularity. Adds no obligation the design did not already carry, since
     PropBank is layer 4 regardless.
   - **VerbNet 3.4's inline `wn`, `grouping` and `fn_mapping` attributes**,
     permissive with no copyleft. On a sampled 1,024 members: WordNet sense keys
     on 80%, PropBank rolesets on 48%, FrameNet frames on 23%. Version 3.3 has
     no `fn_mapping` at all, so 3.4 is required for the FrameNet half.

   If the crosswalk must be free of copyleft, VerbNet 3.4 alone is the only
   route, at roughly a quarter FrameNet coverage. Accepting ShareAlike buys far
   more.
4. **PropBank + FrameNet, but not NomBank.** NomBank's 1.0 distribution carries
   no license, so it cannot be redistributed either. Its propositions are also
   token offsets into the LDC Wall Street Journal corpus, so they are inert
   without an LDC Treebank license regardless of NomBank's own terms. The
   nominal-predicate gap therefore stays open, and closing it needs either a
   grant from NYU or a different source.
5. **SUMO** for upper-ontology grounding, via its own WordNet mapping plus the
   KIF relation content already cleared under ADR-0040.

## Canonicalization is the hard part, and there is evidence

These resources do not snap together. They disagree about granularity and
sometimes about what the basic units are. The valuable asset is therefore not
the merged dataset but the **principles, mappings, conflict-resolution rules
and evaluation system** that make the merge coherent.

Brian has direct evidence of this failing. Across five approaches at mapping
into Wikidata's 13,054 properties — LLM-generated search terms, embedding
top-one, hybrid retrieval with reranking, fine-tuning on 82,044 examples — the
ceiling reached was **47% coverage**, and the work was abandoned in February
2026. The recorded reason is a vocabulary-fit problem, not a retrieval one:
property codes are property-centric, built for structured data, not narrative
events, while the needed predicates are verb-centric.

Two cautions from that episode. Several of its documents are titled as
successes whose bodies do not support it, including one marked ready for
production over a body reporting 27% accuracy. And no approach was validated on
more than thirty cases.

The selection problem itself is tractable with more compute and latency —
cascade the retrieval, embed definitions rather than labels, let a slower model
arbitrate. The vocabulary-fit problem is not solved that way.

### How canonicalization fails, concretely

That evidence is about mapping *between resources*. A different and more basic
failure is two phrasings of one event not landing on the same object, which is
the premise the whole design rests on. It can break in five ways, none exotic:

- **Different predicates, both defensible.** "Acme acquired Beta" selects
  `lc:acquire_get`; "Acme bought Beta" selects a purchase sense. Same event, two
  canonical objects, and neither choice is wrong.
- **Roles invert under the passive.** "Beta was acquired by Acme" puts Beta in
  the agent slot, producing a relation that reads backwards.
- **Granularity differs.** "Acme acquired Beta" versus "Acme completed its
  acquisition of Beta" — one event, or an event plus a completion state?
- **Entity resolution diverges.** "Acme", "Acme Corp" and "Acme Corporation"
  become three entities, so even identical predicates yield different objects.
- **Nominalizations are unsourced.** "Beta's acquisition by Acme" is a noun
  phrase; NomBank was the resource for those and it is dropped on licensing, so
  nothing covers this case.

### Settled 2026-09-07: what this object discards, and what it does not

Brian's answers to the five axes the answer key surfaced. These convert the
thirteen contested pairs and are decisions, not proposals.

**1. Coreference is not this object's job, and the question was badly posed.**
Work divides into pre-processing, processing and post-processing. Coreference is
a *stage*, not a property of a representation — asking whether "the object does
coreferencing" is a category error. The IR consumes resolved mentions. This axis
is closed and should not have been opened.

**2. An event and its resulting state are not the same object — but should be
linked.** "Completed its acquisition of Beta" and "acquired Beta" are distinct
objects with an association between them, not one collapsed object. And
**"agreed to acquire" must never collapse into "acquired"** — that is the
pending-deal error this document already names as the flagship case.

*This is off-the-shelf, but not where an earlier revision of this document said.*
It claimed PropBank's `ARGM-MOD`/`ARGM-NEG` were donor data the import dropped.
**`ARGM` appears zero times across PropBank's 3,323 frame files** — there was
nothing there to drop. The annotations live in `prop.txt` (112,917 propositions,
`ARGM-MOD` 11,318 times, `ARGM-NEG` 3,995) as **token offsets into the
LDC-licensed WSJ treebank** — the same structure that removed NomBank, so the
instances are unusable here.

What *is* usable is the **tag inventory**, which is universal and documented in
PropBank's README: these modifiers apply to any predicate, so declaring them
needs no instance data and no licence. And **aspect is not an `ARGM` tag** — it
sits in a five-character inflection field (form, tense, aspect, voice, person),
so "was acquiring" is `aspect=o`, not a modifier role. Both are declared in
`ontology_packs/linguistic_core/_candidates/`.

Other established options rather than authoring one: **FactBank** (event
factuality), **ISO-TimeML** (an ISO standard covering event modality),
**UMR/AMR** (modal strength and polarity), Searle's speech-act taxonomy, and
FrameNet's own Statement and Reasoning frames — already a donor here. The Inside
Success graph-maintenance methodology specifies modality at `§516`/`§527`/`§2120`
but records at `§663` that no first-class modality field exists in its baseline
either, so it is a second statement of the requirement rather than a source.

**3. Converse predicates are one relation, handled by inference, not by
collapsing.** `owl:inverseOf` is the standard mechanism and SUMO already carries
the concept — `lc:inverse` is in the pack, with SUMO's own definition ("one
BinaryRelation is the inverse of another if they are equivalent when their
arguments are swapped"). Buy/sell and lend/borrow stay distinct predicates with a
declared inverse relation between them.

**The gap is in the pack format, not the theory.** `hierarchy_edges.jsonl`
carries exactly one `edge_type` across all 1,774 edges: `subtype_of`. There is no
way to state that two predicates are inverses. That is a concrete, bounded
schema addition.

**4. "Acme sued Beta" and "Acme filed a lawsuit against Beta" are the same
object, and the predicate is `sue`.** An earlier revision of this document called
this "currently impossible" because the pack has no nominal predicates. **That
was wrong.** `lc:sue_call_to_court` exists. In a light-verb construction the noun
is the *argument*, not the predicate — "filed a lawsuit" resolves to the verb
sense, so the missing-nominals gap does not bite here. It still bites where a
nominalization is the whole reference ("the acquisition closed Tuesday"), which
is a narrower problem than previously recorded.

**5. Take the nearest predicate; record the difference as prose annotation.**
For the six entailment pairs — acquired/bought, killed/murdered, said/claimed,
said/announced, gave/donated, left/resigned — select the closest available
predicate and carry the residue as an annotation rather than discarding it or
forcing a new predicate. This keeps the canonical object stable while preserving
what the paraphrase added, and it degrades gracefully: an annotation nobody reads
costs nothing, whereas a discarded distinction cannot be recovered.

**A pack defect this exposes, and its answer is not a judgement call.**
`lc:kill_cause_to_die` and `lc:murder_cause_to_die` carry the **identical** gloss
"cause to die", so a selector reading descriptions cannot tell which is nearer
and will sometimes put `murder` on a plain "killed" — adding an
unlawfulness-and-intent claim the text never made, which is the fabrication
direction.

Either consolidate such pairs or distinguish them, and **the data decides**:
across all **332** duplicate-description groups, covering 907 predicates, every
single one maps to *different* PropBank rolesets. Zero share one. `kill-01` and
`murder-01` are separate rolesets, so PropBank's annotators already ruled these
distinct senses. **The answer is uniformly "distinguish"; there is no
consolidation case in the pack.** The predicate identifiers already carry the
distinction — only the human-readable field collapsed.

### Three defects, one cause: the import kept less than the source had

These were found separately and share a mechanism, so they should be fixed in one
pass rather than three.

| what is wrong | what the source has | consequence |
|---|---|---|
| Descriptions average 18 characters and 332 groups are duplicated across 907 predicates | PropBank roleset data far richer than the short gloss | a selector cannot distinguish `kill` from `murder`; almost certainly the cause of the frame failure below |
| No modality or negation anywhere — 908 role IDs, none modal | PropBank's `ARGM-MOD` and `ARGM-NEG` | "did not acquire", "may acquire" and "acquired" produce identical structures |
| Frame mappings 55–61% `incompatibleWith` | FrameNet definitions, and PropBank sense numbers | a model asked to frame `lc:donate_give` from the gloss "give" has nothing to work with |

**None of these is a modelling problem and none needs a better model.** All three
are the same act — reading the donor shallowly — and all three are repaired by
reading it properly. That also makes the third cheaper than it looked: fix the
descriptions first and the frame regeneration gets an adequate input for the
first time.

### Canonicalization is a choice, not a property

"Different phrasings of one meaning get one representation" is not well formed as
stated, and treating it as a property the object either has or lacks has been
holding this design back.

Take the pair it always uses. "Acme acquired Beta" and "Acme bought Beta" are not
synonymous: buying entails consideration changing hands, acquiring does not. They
are *compatible*, and nearly every pair worth collapsing is like this. So one
representation cannot mean identical meaning. It means identical **after
discarding chosen differences**.

That makes canonicalization deliberate information loss, and therefore a
judgement rather than a fact about language. Nothing makes `acquire` more basic
than `buy`. **And the judgements are inherited.** PropBank's roleset boundaries
were drawn to make treebank annotation tractable; adopting the vocabulary adopts
those boundaries wholesale, for a purpose they were not drawn for. That is a
real and unexamined dependency, not a detail.

**The two failure directions are not symmetric.**

- **Under-collapse.** "Acquired" and "bought" land on different predicates,
  downstream sees two events where there is one, and deduplication and
  contradiction detection both miss.
- **Over-collapse.** "Agreed to acquire" and "acquired" both land on `acquire`,
  and a pending deal now reads as a completed one. This is the exact error class
  cited elsewhere in this document as the symbolic layer's flagship catch — here
  produced *by* the canonicalization.

Under-collapse loses information; over-collapse **fabricates** it. They are not
equally bad and should never be traded off as if they were.

**So the measurable object is a curve, not a rate**, and where to sit on it is
task-dependent. Deduplication across sources wants aggressive collapse.
Contradiction detection wants cautious collapse, since over-collapse manufactures
false conflicts. Simulation must never collapse agreement into completion.

Which reaches the same place as the breadth argument below, from the other
direction: canonicalization is **a knob set per profile**, not a property of the
object. The IR should preserve every distinction it can; a profile chooses which
to discard for its task. Step 1 of the plan above is therefore misstated as
"measure the collapse rate" — it must first decide what *should* collapse for a
named task, then measure both error directions against that.

### Breadth works against canonicalization, and this is a real tension

The two goals in this document's own title — the *broadest, richest* object, and
a *canonical* one — pull against each other. Every additional sense distinction
is one more way two phrasings of the same meaning can diverge. With 4,669
predicates carrying many near-synonyms, breadth is not neutral with respect to
the core bet; it actively raises the failure rate of the thing the object exists
to do.

This sharpens what a profile is for. Restricting a pack to the predicates a task
needs is not only a cost saving on prompt size and authoring — **it is a quality
mechanism**, because a smaller vocabulary has fewer ways to disagree with itself.
That reframes "the IR permits, the profile restricts" from a concession into a
design feature, and it means the paraphrase-invariance test above should be run
at more than one profile size. If invariance is materially better on a narrow
profile, that is an argument about how this object should be *used*, not
evidence against it.

## Wikidata belongs in the design, scoped to states

Earlier versions of this plan excluded general-purpose knowledge graphs, first
on the grounds that they broaden domain scope and later on a shape mismatch.
Both reasons were wrong, and the second was wrong in an instructive way: shapes
differing is an argument for assigning each to what it does well, not for
throwing one away.

A Wikidata property **is** a state relation. Born in, spouse of, employer,
headquartered in. A PropBank roleset is an event with participants. Those are
the two halves this specification already names, not competitors.

The evidence is direct. Nineteen CC0 Wikidata properties were standardized into
the pack format with roles and type constraints, and they work: the birth
relations bind 5/5 on real benchmark prose, closing a gap that had killed four
of thirteen questions.

The earlier P-code failure is consistent with this rather than against it. That
attempt asked property codes to carry **narrative events**, which they cannot,
and it hit a 47% ceiling for exactly that reason. Used for what they are, they
succeed; used for what they are not, they fail.

So the rule is scope, not exclusion:

- **State relations** — property-style vocabulary (Wikidata, SUMO relations).
- **Events** — verb-sense resources (PropBank, FrameNet, VerbNet).
- **Crosswalk between them**, so a query can cross the boundary rather than
  stopping at it.

ConceptNet remains out, but on its own merits rather than by association, and
that has not been re-examined.

## What the symbolic side can and cannot check

Type constraints are weaker in practice than they sound. In the encyclopedic
pack the constraints ran and did **not** catch a village being asserted as a
citizen of the United States, because the subject type was deliberately widened
to the top type — a narrower guess would hard-fail correct candidates. Tighter
constraints catch more errors and reject more correct extractions. That
tradeoff is real work and does not disappear with a better ontology.

**Three different things get called "a constraint" and they should not share a
namespace** (from the fact-oriented brief, §11):

1. **Domain constraints** — statements about valid populations. Uniqueness,
   mandatory participation, frequency, value ranges, subset and exclusion.
2. **Model-shape rules** — properties of the schema itself. Every fact has
   arity two, the graph is connected, no anonymous roles. These are lint.
3. **Enforcement status** — a *result*, not a model truth value, reported per
   constraint per target: `NATIVE_ENFORCED`, `EMULATED_ENFORCED`,
   `REPRESENTED_NOT_ENFORCED`, `METADATA_ONLY`, `UNSUPPORTED`.

The third is what the village case actually needed. That constraint was
`REPRESENTED_NOT_ENFORCED`: present in the model, not enforced where it would
have caught the error. Reporting that is more useful than either "constraints
work" or "constraints don't".

## Gaps this design does not currently address

Named because each is load-bearing and absent, not because they are wishes.

**Entity resolution is missing entirely, and it is most of the engineering
cost.** Every worked example in the source material steps from the string
"Orion" to the identifier `entity:Orion` without comment. That step decides
whether a graph merges or fragments, and no ontology fixes it. A canonical
representation whose whole value is that different phrasings collapse to one
object cannot leave the question of when two mentions are the same entity
outside its scope — it is the same question as proposition identity, which this
document does treat as central.

**There is no representable state for the extractor returning nothing.**
Confidence, epistemic status and hypothesis sets all presuppose at least one
hypothesis. Against a measured rate of roughly one call in eight returning zero
candidates, a sentence that produced nothing is indistinguishable from a
sentence that changed nothing. That is a hole in the representation, not a
quality problem.

**Coverage is absent from the evaluation metrics this design inherited.**
Temporal consistency, multi-hop reasoning, paraphrase invariance, contradiction
detection, event extraction, planning correctness and hallucination rate are all
conditional on something having been extracted. A system covering a fifth of a
corpus perfectly outscores one covering four fifths well. Coverage is precisely
the number that ended the Wikidata attempt at 47%, recorded above — and it is
not in the plan that would measure this object's success.

**State modelling primitives — specified in the source conversation and *already
implemented* one directory over.** Checked 2026-09-07 against
`~/code/requirement-to-runtime-semantic-compiler` (a local repository —
registered in `PROJECT_GRAPH.json` on 2026-09-07, *after* the consolidation that
missed it — imported wholesale 2026-09-07 from a Windows
checkpoint and drawing on the *same* 10,012-line source conversation). **Six of
the seven below exist there as frozen schemas and SQL, not sketches** —
`02_world_model/WORLD_STATE_SCHEMA.md` covers six in 39 lines, and
`16_temporal_world_model/TEMPORAL_SQL_SCHEMA_V1_0.sql:56` is a real
`CREATE TABLE quantity_assertions`. Inertia is the sharpest case: that repo's
`03_wtl/WTL_SPEC.md:23-25` states the persistence rule *and* the derived-facts
exemption this document names as unaddressed. Only the causal-link vocabulary
and QUDT are genuinely absent on both sides.

Listed here as requirements rather than deleted, because this vocabulary must
still be able to express them — but **do not re-derive them a third time.** From `~/code/requirement-to-runtime-semantic-compiler/sources/semantic_interlingua_part1.md`, roughly lines
3400–8400, of which this document harvested almost nothing:

- The unit of state is an **assertion, not a triple**, carrying scenario, valid
  time, epistemic status, provenance, `derived_from` and `supersedes`. Its
  epistemic status enum is `observed | asserted | inferred | predicted |
  hypothetical | assumed | disputed`; the `Provenance` primitive above has none
  of this.
- **Quantity is its own primitive**, not an ordinary relation — separating
  quantity, dimension, unit, measurement and uncertainty, and naming QUDT for
  units. The pack already ships SUMO's unit *type hierarchy*, so what is missing
  is a representation for a magnitude with a unit and a dimension.
- **Process is distinct from event** — things unfolding through time, with a
  lifecycle state and internal transitions. Employment, negotiation, pregnancy.
- **Scenario is first-class**, so counterfactuals branch without duplicating the
  graph.
- **Inertia is an explicit frame assumption**: state assertions persist until an
  effect ends or supersedes them, with derived facts exempt. This is the frame
  problem, and nothing here addresses it.
- A **causal-link vocabulary** distinguishing `causes` from `enables`,
  `prevents`, `requires` and `inhibits` — a regulatory approval *enables* a deal
  closing rather than causing it.
- **Ontic, epistemic and linguistic as three separate layers** — what exists,
  what agents believe, what documents said. `Stance` and `Modality` cover the
  third and part of the second; the first is absent.

### The backbone claim, checked against the data and false

An earlier revision of this document carried a prioritization argument from the
ontology platform's status documents: that the PropBank + FrameNet + SemLink
backbone proposed above **already exists at 98.1% predicate-to-frame coverage**
in the donor repository `onto-canon`, and that the real gap is an unbuilt
`backbone → pack` compiler. Every load-bearing part of that is false, and the
finding underneath it is more useful.

- **The 98.1% artifact is not in the repository, but it does exist.** An earlier
  revision of this section said it had been deleted and could not be reproduced.
  That was wrong and is corrected here rather than removed. `onto-canon`
  gitignores `data/` and every `*.db`, so it is in no commit and on no GitHub ref
  — but two copies with matching checksums were recovered on 2026-09-07, one on
  the desktop machine and one inside a OneDrive-backed archive tarball, verified
  at 4,575/4,663 = **98.11%**.
- **The 2026-09-04 regeneration is a *partial* rebuild, not a slightly worse
  copy.** Its script has four phases — PropBank, FrameNet, SemLink, LLM gap-fill
  — and **no SUMO phase**. Verified by direct query: `sumo_types` 0 against the
  original's 725, `sumo_hierarchy` 0 against 857, `domain_range_constraints` 0
  against 11,126. The whole type layer is absent, so the two artifacts were never
  comparable and the "two-point difference" everyone was discussing was measuring
  a partial rebuild against a complete one. The original also carries 70 `manual`
  and 10 `llm_legacy` rows — hand-curated work no re-run recreates.
- **Coverage was never the quality claim, in any version.** The surviving donor
  artifact `sumo_plus.db` gives **48.47%** (2,263 of 4,669), of which 2,262 rows
  are `llm:gemini/gemini-2.5-flash` and exactly one is SemLink. The regeneration
  reaches 96.07% with SemLink supplying 542 of 4,472. The two runs agree on only
  **59.3%** of the frames they both assigned. In every measurable version the
  crosswalk is overwhelmingly a model's assignment rather than the SemLink bridge
  the claim names, and a higher percentage of unverified assignments is not a
  better artifact.
- **"Regeneratable" was false in three separate ways**, which is the transferable
  lesson: the generator is nondeterministic, its original model was later
  de-allowlisted, and its script covers only some of the phases that built the
  artifact. None of those is visible from the gitignore line that called it
  regeneratable.
- **The compiler is not unimplemented.** It exists in `onto-canon6`'s working
  tree as a 491-line module with tests and a regeneration script, uncommitted,
  producing a spike pack of **four** predicates.
- **And it is not the thing this document proposes anyway.** The architecture
  above specifies WordNet synsets as the identity layer, VerbNet as the
  thematic-role backbone, and a *licensed* crosswalk from PropBank's own
  `rolelink` elements and VerbNet 3.4's mappings, chosen precisely because
  SemLink is unusable. Neither surviving database has a WordNet layer or a
  VerbNet role inventory. The donor backbone is the thing this design rejected.

**What is actually true, and it still rewrites the architecture section.** This
pack is a strict superset of the donor backbone: 4,655 of 4,655 identifiers
intersect exactly, with eleven extra, and 0.3.1 and 0.3.2 are further ingestion
from the same donor rather than new vocabulary. **Proposing to construct a
PropBank + FrameNet backbone is aimed at a layer this repository already has.**
The missing thing is frame coverage and verification — 48.47% covered, every row
unverified, every row but one model-assigned. The 47% Wikidata ceiling recorded
above is the direct precedent for why unverified model alignment at scale is the
risk to design against.

**One licensing consequence.** Adopting the regenerated backbone would import a
15,441-row `semlink_mappings` table plus verbatim PropBank and FrameNet
definition text. This pack's current SemLink exposure is one row. That is a real
reason not to take the regeneration wholesale.

**And the failure mode is the one this document keeps hitting.** A number was
measured, its artifact was deleted as regeneratable, the prose survived, and it
was cited as a live fact for six months — into this design, in a revision
written the day before it was checked.

## The neurosymbolic question

The thesis is that the neural model interprets messy language and the symbolic
layer represents, constrains and reasons over the interpretation, with the
vocabulary sitting at that boundary.

**The record is better than "unresolved", and an earlier revision of this
document reported it wrongly.** There was not one real-document test. Three
independent experiments collided in a single shared worktree, all originally
filed as plan 0206: one on recommendation-*number* binding, one on
recommendation-*ordinal* binding, and one on **evidence-span grounding**. The
first two found no gap. The third found one, and the symbolic condition closed
it where neural-only did not.

On real traced calls against `gpt-5.6-luna`, both conditions starting from an
identical shared pass-1 output, the transfer document went 1 violation → **0**
under the symbolic condition and 1 → **1 unchanged** under neural-only, whose
self-review re-emitted the same ungrounded evidence span verbatim. The negative
control fired correctly and specifically: an induced role inversion was rejected
by exactly `RULE_ACTOR_CONTENT_COLLAPSE` and a dangling reference by exactly
`RULE_DANGLING_RECOMMENDATION_REF`, both provider-free.

**It survived its own audit.** That readout self-audits and retracts the
*primary* document's result as a preprocessing artifact of a flat newline join —
but explicitly exempts the transfer document, whose fixture had a real paragraph
break the bug never touched, and where the model spliced sentence 1 to sentence
3 while skipping the middle sentence entirely. A genuine non-contiguous quote,
not a formatting artifact.

**The useful finding is that the loop's value is not uniform across failure
modes.** That model self-corrects recommendation-number binding without symbolic
help, and does *not* self-correct a paraphrased or spliced evidence quote
without it. That is sharper and more actionable than "unresolved", and it says
where a symbolic layer earns its cost: grounding, not binding.

Two caveats kept rather than smoothed. The null half cannot yet distinguish "the
loop is unnecessary" from "this model was strong enough here" — its own readout
says so and names running the same operator against a weaker model as the next
step. And that operator **used zero Linguistic Core predicates**; it is plain
Python and Pydantic, which is evidence against the donor crosswalk being
load-bearing for this task class and should be weighed rather than buried.

The synthetic result is also softer than stated: it ran twice and the runs
disagreed about where recall broke — 0.625 at N=1000, 0.875 at N=300 — so
"roughly 300 items" is the optimistic end of a two-point spread, not a measured
threshold.

**Where this evidence lives is itself a finding.** It is not on `onto-canon6`
main. It sits on an unmerged branch that had no upstream until 2026-09-05, and
fourteen of its files were recovered from an untracked directory inside another
repository's stray agent worktree, reachable on one machine and in no version
control anywhere. Which readout supersedes which is still unestablished.

**The loop is specified, not merely wished for.** `project-meta/vision/analyses/
NEUROSYMBOLIC_AI_VISION.md` gives six stages, not three: neural interpretation →
source-grounded proposal → symbolic validation or contradiction → **precise
diagnostic** → neural repair → **reviewed state transition** → changed context
for the next cycle. Its governing constraint is that the goal is not a large
graph but useful prior structure: it should support an operation, expose a
violation, constrain a transition, or produce evidence that improves the next
proposal.

That document also carries the evaluation design this section previously said
was missing — a seven-gate roadmap whose Gate 6 requires an unseen, differently
worded task, the same model producing the same initial proposal, ordinary
reconsideration compared against a precise symbolic diagnostic, **a
corrupted-rule or role-swap negative control**, retained before/after artefacts,
and a test that the operator transfers without document-specific branches. It
states a **disproof condition**: if stable symbolic structure does not enable
transferable operations, diagnostics or revision beyond a well-prompted neural
baseline, then this vocabulary is reduced to optional normalization metadata
rather than a mandatory reasoning substrate.

**And it splits the question usefully.** Does the mechanism work correctly —
does contradiction detection fire on a real contradiction, does retraction
propagate, does an operator return the right set — is cheap, mechanical and
answerable now without a corpus. Does it beat neural-only *at the scale where it
should matter* genuinely requires scale and should be deferred. This document had
been treating those as one question.

**A working instance already exists in this ecosystem.** `agent_ontology` runs
this loop over agent specifications rather than documents: an LLM proposes a
mutation, 23 structural rules validate it, the validator catches that the model
dropped a required section, and the invalid mutation is rejected. Different
domain, same mechanism, already running.

## Licensing

Checked against primary sources, not assumed. The expectation that these are
all permissive was wrong for two of them.

| Resource | License | Redistribute | Commercial | Copyleft |
|---|---|---|---|---|
| WordNet 3.0 | WordNet License | Yes | Yes, explicitly | No |
| VerbNet 3.x | VerbNet 3.0 License (CU Boulder) | Yes | Yes | No |
| **SemLink** | **None** | **No** | **No** | — |
| **NomBank 1.0** | **None** | **No** | **No** | — |
| PropBank frames | CC BY-SA 4.0 | Yes | Yes | **ShareAlike** |
| FrameNet 1.5–1.7 | CC BY 3.0 Unported | Yes | Yes | No |
| SUMO | IEEE permissive core; GPL extension modules | Yes | Yes | **GPL modules** |

Consequences for the design:

- **Two of the seven cannot be redistributed at all**, and both sat in the
  architecture: SemLink as layer 3 and NomBank as part of layer 4. Both are
  replaced or dropped above.
- **The merged object cannot be proprietary**, on two independent grounds:
  PropBank's ShareAlike and SUMO's GPL modules.
- **VerbNet's license does not travel with its data.** Neither the distribution
  tarball nor the GitHub repository contains a license file; it exists only as a
  page on the Colorado site, while its terms require the notice to appear on all
  copies. Vendoring VerbNet means copying that notice in by hand.
- **FrameNet's grant is perpetual and irrevocable** under CC BY 3.0 §7(b), so
  the dead distribution host and the successor site's all-rights-reserved footer
  do not retract it. NLTK's index describing FrameNet 1.5 as non-commercial is
  wrong; ICSI's own statement governs.

Two live residuals rather than closed questions. **CC BY 3.0's GPL
compatibility is not established** — the FSF list covers CC BY 4.0 and has no
entry for 3.0 — which matters if the merged artifact is GPLv3. And **whether
ShareAlike reaches derived mappings that contain no verbatim text** is genuinely
unsettled; ADR-0040 hit the identical question for SUMO and deliberately
declined to answer it.

**But that question is smaller than it looks, and it is one column wide.** The
shipped pack has five fields per predicate — `predicate_id`, `preferred_label`,
`family`, `status`, `description` — and the first four are independently
authored. Source text is confined to `description`, which averages 18.3
characters across the 4,669 rows in `0.3.0`: glosses like `"exchange"` and
`"leave behind"`. So the artifact is already a canonical layer structurally, and
carries source content only in one short, regenerable column.

That makes the unsettled ShareAlike question avoidable rather than answerable:
regenerating those descriptions in independent wording removes the only verbatim
content, at which point nothing of PropBank's is redistributed and the question
does not have to be resolved at all. That is a bounded task — 4,669 short glosses,
a model job with human spot-checks — not an architectural change. **It should be
done before any commercial layer depends on this reading**, since ADR-0040
decision 8 is explicit that this is a non-lawyer reading of license text and
recommends actual counsel before shipping anything commercial that relies on it.

Two unchecked corners, named rather than closed, because the one absence claim
that was wrong in this review was wrong for exactly this reason: NomBank's two
`DOCS` PDFs were not opened, and Colorado serves multi-resource download bundles
behind a page whose linked license file covers VerbNet only. For SemLink
specifically the cheapest real answer is an email to the Colorado group.

## Failure modes, prevention, and recovery

Modelled on the Inside Success graph-maintenance methodology's §22, which does
this for a knowledge graph. This one is for **the vocabulary object itself**.

**Status column is the point.** `MEASURED` means a number exists and is cited
here; `OBSERVED` means it was seen at least once but not quantified;
`ANTICIPATED` means it follows from the design and has not been looked for. A
taxonomy that does not separate these becomes a worry list.

### Content defects — the object says something wrong

| ID | Failure mode | Status | Consequence | Prevention / detection | Recovery |
|---|---|---|---|---|---|
| VF-01 | Frame mapping asserts an unrelated frame | **MEASURED, REPRODUCED** 52% `incompatibleWith` (n=100, `evaluation/frame_layer/`); an earlier lost run gave 55–61%. `exactMatch` does *not* reproduce — 5% here against 14% — so treat the incompatible rate as reliable and exact-match as judge-dependent | Anything reasoning over frames inherits a majority-wrong layer; coverage figures overstate usable coverage by more than half | Sample and judge against full FrameNet definitions, classified by relation not right/wrong; only `incompatibleWith` is unambiguous failure | Regenerate with definitions and sense numbers in prompt; do not verify — checking 2,263 rows that are ~58% wrong costs more than redoing them |
| VF-02 | Two predicates share an identical description | **MEASURED** 332 groups over 907 predicates | A selector cannot tell `kill` from `murder` and will sometimes add an unlawfulness claim the text never made | Group by description; any group larger than one is a defect | Distinguish, never consolidate — all 332 groups map to *different* PropBank rolesets, so upstream already ruled them distinct |
| VF-03 | Donor content silently dropped at import | **MEASURED** 0 `ARGM` rows; `value_types.jsonl` 0 bytes in all versions | No modality, negation or aspect: "did not acquire", "may acquire" and "acquired" produce identical structures | Diff the donor's field inventory against the pack's on every import | Recover `ARGM-MOD`/`ARGM-NEG` from PropBank; they were never unavailable |
| VF-04 | A relation the theory needs is inexpressible in the format | **MEASURED** `hierarchy_edges` has one `edge_type` across 1,774 edges | Inverse pairs (buy/sell, lend/borrow) cannot be declared, so converse phrasings stay unrelated | Enumerate the relation kinds the design commits to, then grep the schema for each | Add the edge type; SUMO already supplies the concept as `lc:inverse` |
| VF-05 | Nominalization has no predicate | **OBSERVED** "acquisition", "merger", "investment" return zero; "lawsuit" does *not* — `lc:try_lawsuit` and `lc:retry_lawsuit` exist | Noun-phrase references to events are unrepresentable where the noun *is* the reference | Probe the pack with nominal forms of its top predicates | Narrower than it looks — light-verb cases resolve to the verb sense; only whole-reference nominals bite. NomBank is unlicensed, so this needs another source |

### Canonicalization defects — the object collapses wrongly

| ID | Failure mode | Status | Consequence | Prevention / detection | Recovery |
|---|---|---|---|---|---|
| VF-06 | **Over-collapse** — distinct meanings become one object | **MEASURED** 1/35 = 3% (2026-09-08); 69% when the scorer captured only a predicate, so the control is polarity+modality capture | "Agreed to acquire" reading as "acquired" *fabricates* a completed deal; unlike under-collapse this cannot be recovered downstream | `evaluation/canonicalization/canonicalization_key.jsonl` — 66 pairs, 37 `different-object`, all adjudicated 2026-09-07. Over-collapse and under-collapse must be reported separately, never as one accuracy number | Split the predicate; add the labelled pair as a regression case |
| VF-07 | **Under-collapse** — one meaning becomes several objects | **MEASURED** 17/22, but ~4 are scope-excluded entity variants, ~5 role-id naming, ~4 harness, ~4 genuine role divergence | Deduplication and contradiction detection both miss; the object fails its founding premise | Same key, the 29 `same-object` pairs | Declare the mapping relation between them rather than merging the predicates |
| VF-08 | Breadth raises the collapse failure rate | **ANTICIPATED** | Every added sense distinction is another way two phrasings of one meaning diverge — richness and canonicality pull against each other | Run paraphrase invariance at more than one profile size | If narrow profiles invariance-test better, that is a fact about *use*, not evidence against the object |
| VF-09 | Roles are frame-specific with no crosswalk | **MEASURED, and now the leading cause of under-collapse.** `kill` declares killer/victim while `murder` declares cause/instrument/victim; `rise` declares theme/distance while `increase` declares item/extent. Predicate relations are declared, role correspondences are not. (Pack has 38,650 role edges, 2,998 `required`; an earlier revision said "6 of 11,890", which is the *donor* table.) | Deciding two predicates correspond does not say which roles align; role inversion cannot be caught structurally | Check whether converse predicate pairs declare aligned roles | Author role alignments alongside any inverse declaration |

### Epistemic defects — the object misrepresents its own reliability

| ID | Failure mode | Status | Consequence | Prevention / detection | Recovery |
|---|---|---|---|---|---|
| VF-10 | A confidence score uncorrelated with precision | **MEASURED, RE-DERIVED** 2026-09-07 with artifacts in `evaluation/frame_layer/` — Spearman ρ = **+0.017**; incompatible rate by confidence band runs 58/65/38/53/53% from lowest to 1.00, flat rather than weak; 55% incompatible at confidence 1.0; `exactMatch` rows average *lower* confidence than `incompatibleWith` | A consumer thresholds on it and the selection gets worse | Rank-correlate the score against a judged sample before shipping it | Drop the column — its presence implies a calibration nobody established |
| VF-11 | One flag conflates unverified-donor with unverified-model | **MEASURED** `source_verified: false` on both mechanical and model-generated rows | A 61%-wrong layer sat indistinguishable from 58,000 sound rows for months | Surface `derivation_method` at the same prominence as verification status | The values already exist in the data; expose them as a trust signal |
| VF-12 | A coverage figure read as a quality figure | **MEASURED** 98.11% coverage against 55–61% incompatible; the two runs agree on **17.6%** of the 2,205 predicates both assigned (recomputed 2026-09-07; an earlier revision said 59.3%, which does not reproduce) | Six months of planning built on a number that counted *resolvable* frame names, not correct ones | Never publish coverage without an accuracy figure beside it | State both, or state neither |
| VF-13 | A measurement outlives its artifact as prose | **MEASURED** the 98.1% figure survived its deleted database by six months and propagated into three documents | Planning proceeds on a claim nobody can re-check | Do not gitignore a generated artifact unless its generator is deterministic, its model pinned, and its rebuild covers every phase | Recover or re-measure; never re-cite |

### Pipeline defects — the object is fine, its use is not

| ID | Failure mode | Status | Consequence | Prevention / detection | Recovery |
|---|---|---|---|---|---|
| VF-14 | Extraction returns nothing, indistinguishable from nothing-to-say | **MEASURED** ~1 call in 8; in the propositional schema it relocates to post-parse rejection at 2/15 | A sentence that produced nothing looks like a sentence that changed nothing | Count and report the empty rate beside every extraction metric | Give the representation an explicit "nothing extracted" state — it currently has none |
| VF-15 | No relation can be expressed between claims in different documents | **MEASURED** `object_relations` are proposal-local; both known contradictions spanned two calls, so `contradicts` could not fire | Contradiction detection is impossible regardless of extraction quality | Test with a known cross-document contradiction | Specification gap — needs a cross-proposal relation, not better extraction |
| VF-16 | Argument role names invented per call | **MEASURED** the same fact labelled `missing_predicate_count` and `state_predicate_count` in two calls | Nothing downstream can align two extractions of the same fact | Extract one fact twice and diff the role names | Constrain role names to the pack's vocabulary rather than free text |
| VF-18 | Symmetric predicates are not declared symmetric | **OBSERVED** in 1 residual case; 17 symmetric role pairs now declared, but the effect is below this key's noise floor | "Acme merged with Beta" and "Beta merged with Acme" are different objects because `part_1`/`part_2` swap and nothing says the order is immaterial | Score a symmetric-predicate pair in both argument orders | Declare symmetry per predicate. The fact-oriented brief's §12 warns that "symmetric" currently means two different things, and that section was among those this design did not absorb |
| VF-17 | Entity resolution diverges | **MEASURED** ~4 of 17 under-collapse cases (2026-09-08), exactly as the ruling predicts | "Acme", "Acme Corp" and "Acme Corporation" become three entities, so identical predicates still yield different objects | Out of scope for this object by decision — belongs to pre-processing | Not this object's recovery; but its evaluations must control for it or they measure the resolver |

**The collapse ceiling is bounded by the pack, not the extractor — computed
2026-09-08 from the key alone, no model calls.** Comparing each pair's expected
predicates:

| | pairs | consequence |
|---|---|---|
| `same-object` whose two sides expect **different** predicates | **15 of 24** | Cannot collapse. Nothing in the pack relates `lc:acquire_get_obtain` to `lc:buy_purchase`, or `lc:kill_cause_to_die` to `lc:murder_cause_to_die` — there are no predicate-to-predicate relation edges at all (VF-04). |
| `different-object` sharing a predicate, separable only by negation/modality/aspect | **3 of 35** | Cannot be separated. "Acme did not acquire Beta", "may acquire", and "was acquiring" are structurally identical to "acquired" (VF-03). |
| `different-object` sharing a predicate, separable by role fillers or entities | 14 | Scoreable — these do test the extractor. |

**One of the two gaps is now closed, 2026-09-08.**
`ontology_packs/linguistic_core/_candidates/predicate_relations.jsonl` declares
15 predicate-to-predicate relations from the nine-term mapping vocabulary —
`lc:buy_purchase narrowerThan lc:acquire_get_obtain`,
`lc:murder_cause_to_die narrowerThan lc:kill_cause_to_die`, and so on.
`evaluation/canonicalization/check_collapse_reachability.py` reports
**`same_UNREACHABLE` at 0, down from 15**. The under-collapse half of the key is
now scoreable.

It is a **candidate, not a pack version**, and deliberately not numbered:
consumers pin versions, and publishing `0.4.0` would assert a release this has
not earned. Every row is `derivation_method: authored`, `source_verified: false`
— judgements made against the key, not derived from a donor. It went in a new
file rather than extending `hierarchy_edges.jsonl` because consumers read that
expecting `subtype_of`, and adding other edge types would silently change what an
existing file means to an existing reader.

**Both gaps are now closed. `SCHEMA-BLOCKED TOTAL: 2`, down from 18** — A08 and
A12, each left honestly unreachable after an audit found the relations bridging
them were false. C08, C09 and C12 are reachable through the modifier roles and
inflection type in the same candidates directory.

**A scorer now measures the extractor rather than the schema**, which was the
point of doing this first; step 2 above reports what it found.
Under-collapse would read as roughly 60% failure on the same-object half when the
representation simply cannot express the collapse, and three over-collapse cases
are unwinnable for the same reason. The scorer is still worth building — most of
the key is scoreable — but it must report those 18 pairs as *schema-blocked*
rather than folding them into an accuracy figure. This is the measurement
equivalent of the coverage-versus-quality error recorded above.

**VF-06 and VF-07 moved from `ANTICIPATED` to `MEASURED` on 2026-09-08**, on the
first scored pass over the merged answer key — 66 pairs, all thirteen contested
ones adjudicated against the five canonicalization rulings above.

**VF-10 and VF-01 now have durable evidence.** `evaluation/frame_layer/` holds
the script, the seeded sample, the judged output and the analysis; the
measurement reruns for about 1.5 cents. It reproduced the two claims the design
depends on — roughly half the layer incompatible, and confidence uncorrelated
with correctness — and failed to reproduce `exactMatch`, which is recorded rather
than smoothed.

**Provenance discipline, added 2026-09-07 after an audit found three bad rows.**
`MEASURED` was applied to numbers relayed from subagents without independent
re-derivation, and three of thirteen were wrong: VF-09 cited a donor table as if
it were the pack, VF-12 reported 59.3% cross-run agreement where recomputation
gives 17.6%, and VF-05 named a nominalization that does exist. VF-10's evidence
no longer exists at all — which is the failure VF-13 in this same table describes.
So: **a row is `MEASURED` only when the number was derived from a durable
artifact by whoever wrote the row**, and the artifact must outlive the session.
A relayed number is `OBSERVED` until re-derived.

**How to use this.** Two rules keep it from decaying into the prose-with-no-mechanism
shape that §22 has: every new row arrives with a status and, if `MEASURED`, the
command or artifact that produced the number; and a row moves from `ANTICIPATED`
only when someone actually looks. Seventeen rows and thirteen measured is the
state on 2026-09-07.

## Open questions
- **One integrated artifact, or federated theories with mappings as claims?**
  This design assumes a single merged object. Semantic Foundry
  (`~/code/semantic-foundry`) has built much of the same stack — pinned
  PropBank, VerbNet, SUMO and BFO slices with SemLink cross-checks — on the
  opposite principle: never merge, keep each theory's native meaning and
  represent correspondences as claims carrying provenance. Both are defensible.
  Brian's own vision documents lean toward a resolution: they decide *against*
  universalizing the analysis layer (no universal Case, Evidence or
  MethodResult semantics) while arguing *for* sharing at the vocabulary layer.
  Read that way, federated claims are right for the analysis built on top and a
  shared vocabulary is right underneath — but this is a reading, not a recorded
  decision.
- **Which use case first.** Evaluation is the candidate that produces a number
  rather than a demonstration.
- **Proposition identity.** When are two differently worded propositions the
  same proposition? Load-bearing for the claim half, and open in the Inside
  Success methodology too.
- **Set semantics versus occurrence identity.** A fact type is a *set* of
  tuples, so one role tuple is one fact. But extracted assertions are asserted
  repeatedly, by different sources, with different confidence. Either support
  attaches to the fact (which onto-canon6 implements) or occurrences are
  objectified (which the fact-oriented brief prefers). Choosing quietly, by
  letting fact populations drift from sets to bags, is the failure mode that
  brief explicitly warns against.
- **How the judgment half of coherence gets closed.** Logical consistency is
  mechanically checkable by description-logic reasoners. Whether the classes
  carve the domain usefully, leave gaps, or quietly overlap is not. The
  answer is to instrument rather than solve upfront: ship a vocabulary, measure
  what it fails to express, and let the residual drive revision. onto-canon6
  already records the per-run half of this — every extracted meaning carries a
  `bound` / `unmapped` / `ambiguous_fit` disposition — and already has a
  governed proposal-to-overlay path. What is missing is aggregation across runs,
  which is a query over data the system already writes. Tyler's Reverse Ontology
  Engine is built around exactly this residual-measurement loop.
- **Where implementation lands** is still undecided: inside `linguistic-core`,
  inside Semantic Foundry, or elsewhere.
- **The eight-category coverage audit is specified and has never been run.**
  `world-substrate`'s binding contract lists what to inspect this vocabulary and
  its donors for before adding any overlay term: persistent state relations;
  identity and lifecycle; location, topology, containment and routing;
  possession, custody, access, control, title, beneficiary and transfer
  authority; material qualities, damage and capabilities; quantities, dimensions
  and units; temporal validity and process roles; and institutional roles and
  enforceable relations. It names **QUDT** as a candidate donor alongside SUMO,
  FrameNet, PropBank and Wikidata — QUDT appears nowhere else in this design.
  Every statement of this audit is in obligation tense; it is a hypothesised gap
  surface, not measured findings.

- **Three gaps in this vocabulary that *were* measured, by that consumer.**
  Reversative senses have no representation — `unheat` is absent, and the
  nearest predicate is the *application* of heat, whose reversal is not a sense
  it carries; that consumer files this as an open item *owned by the upstream
  ontology*, which makes it an outstanding requirement against this repository.
  There is no rights system, so acquisition is a change of ownership reference
  rather than a claim about rights. And there is no vocabulary for *unowned* —
  an authored mechanic had no way to say "no owner" except by emptying a
  reference. The summary diagnosis is that this object is much stronger in event
  vocabulary than in persistent state relations and quantitative value modelling,
  which the 4,658-event to 1,061-relation ratio corroborates.

- **What else genuinely belongs.** WordNet and VerbNet are in. SemLink and
  NomBank are out on licensing, so the nominal-predicate gap needs either a
  grant from NYU or a different source, and that is now an open sourcing
  question rather than an integration one.
- **Two fixes owed on the public `linguistic-core` repo.** Its FrameNet
  attribution cites NLTK as the license source rather than ICSI's own statement,
  which is now citable. And its PropBank content came from NLTK's
  "distributed with permission" package rather than from the CC BY-SA 4.0
  repository, so it should be re-derived from `propbank-frames` at a pinned
  commit with a real notice. Neither is large; both are outstanding.

---

## The sibling project, and why it is not a competitor

`~/code/requirement-to-runtime-semantic-compiler` (GitHub `brianmills-spec`) is
**complementary, and each project names the other's product as its own gap.**

It has the world model, runtime and transition language this document lacks —
15,702 lines of Python, a temporal store, truth maintenance, planners. Its
canonical vocabulary is **75 hand-authored business terms** and it ships no bulk
lexical data; this object is 4,669 predicates with no world model. Its own review
asks whether canonical semantics can stay grounded in expert-built
WordNet/PropBank/FrameNet resources and answers "current evidence is one rigorous
AcquisitionEvent exemplar, not broad coverage" — which is this object's product.
It also explicitly declines to build one: *"Do not attempt a full WordNet +
FrameNet + PropBank + VerbNet + SUMO/DOLCE/BFO merge."*

Neither supersedes the other. What is **not** written down anywhere is whether it
should consume this pack or stay self-contained — no dependency is declared in
either direction, and the only place the connection exists is a derived vision
wiki page.

# Related work, and where the evidence lives

This design cites evidence produced elsewhere, though not exclusively — this
repository's own `docs/runs/artifacts/` holds measured coverage and quality
records, including the crosswalk artifact reporting `verified_count: 0` against
`crosswalk_record_count: 46184`.

**Every path below was verified to resolve on 2026-09-06. That is not the same
as verifying what each one says**, and a 2026-09-06 review found several cited
numbers had drifted from their sources. Re-read the source before re-citing a
figure from here.

## Prior design work on the same representation question

**`docs/design/FACT_ORIENTED_HYPERGRAPH_COMPILER_BRIEF.md`** (1,988 lines) — a
design brief for a fact-based / Object-Role Modeling semantic compiler with a
role-aware hypergraph intermediate representation. Reconciled against this
specification 2026-09-06; the result is below.

### What it independently corroborates

Its §8 asks the specification's load-bearing question in different words: *"When
do I treat a relationship instance as an object that may itself play roles?"*
That is objectification, and it is the same commitment recorded above as "a
proposition can fill a role." The brief argues it should be an **early** feature,
"more important than adding a fourth output target." Two independent derivations
of the same decision.

Its §5.2 models a fact type as `F(r1:T1, … rn:Tn)` interpreted as a set of
tuples, with each role a typed argument position — the same n-ary shape this
design uses.

### Four things it has that this specification lacked

**1. Facts are set-like by default (§5.3).** The same role tuple is *one* fact.
A membership cannot occur eleven times as eleven facts unless the model
introduces an identity-bearing occurrence. Its rule: *"Do not silently switch
fact populations from sets to bags/multisets."*

This bears directly on the open proposition-identity question. If the same claim
asserted in two documents is one proposition, identity is set membership and
provenance attaches to the assertion rather than the proposition. If it is two,
something must carry occurrence identity. The brief's answer — model the
occurrence explicitly rather than quietly changing the semantics — is a
constraint this design should adopt whichever way identity resolves.

**2. Identity is conceptual, not incidental (§9).** *"Entity identity should be
conceptual, not merely whatever became a SQL primary key."* It wants
identification schemes declared (`entity Person identifiedBy personId`),
compound identification supported, and — separately — every model element to
carry a stable internal identifier distinct from its display name, so a rename
is not an identity change.

That last distinction is missing here and matters: this design has repeatedly
conflated what a thing is called with what it is.

**3. Three kinds of constraint, kept apart (§11).** This is sharper than the
"what the symbolic side can and cannot check" section above, and it dissolves a
confusion this design has been carrying:

- **Domain constraints** — statements about valid populations: uniqueness,
  mandatory participation, frequency, value ranges, subset/exclusion.
- **Model-shape rules** — properties of the schema itself: every fact has arity
  two, the graph is connected, no anonymous roles, readings cover every role.
  These are lint, not semantics, and should not share a namespace with "each
  person has at most one birth date."
- **Target enforcement status** — a *compiler result*, not a model truth value,
  reported per constraint per target as `NATIVE_ENFORCED`,
  `EMULATED_ENFORCED`, `REPRESENTED_NOT_ENFORCED`, `METADATA_ONLY` or
  `UNSUPPORTED`.

That third vocabulary is exactly what the village-asserted-as-a-citizen case
needed. The type constraint existed and was `REPRESENTED_NOT_ENFORCED` — present
in the model, not enforced at the point it would have caught the error. Saying
so is more useful than either "constraints work" or "constraints do not work."

**4. Readings (§10).** A fact type optionally carries a human-readable template:
`reading "{part} is in {bin} in {warehouse}"`. It gives a human validation
surface, better diagnostics, and a verbalization path. Nothing here has an
equivalent, and for a vocabulary meant to be reviewed by people it is cheap and
load-bearing.

Also worth carrying: **roles need stable identity independent of position and
type (§14)**. In `Transfer(sender: Account, receiver: Account, asset: Asset)`
two roles share a player type and are not interchangeable. *"Do not infer
identity solely from ordinal; do not infer role name solely from object type."*
The brief notes this is precisely where a naive "hyperedge contains a set of
vertex types" representation fails.

### Where its scope differs, and what does not transfer

The brief designs a **schema compiler**: a declared data model translated to
PostgreSQL, MongoDB and GraphQL, with round-trip recovery and a capability
report. Its populations are database rows. This design is an **intermediate
representation for meaning extracted from text**, whose populations are
assertions with provenance and uncertainty.

So its §5 semantic kernel transfers — what a fact type *is* does not depend on
where instances come from. Its target-mapping, round-trip and DSL sections
(§17–§25) do not, and should not be read as recommendations here.

One real tension to resolve rather than paper over: the brief's set semantics
assumes a fact is asserted once. Extracted assertions are asserted repeatedly,
by different sources, with different confidence. Reconciling those needs either
support-level lifecycle attached to the fact (which `onto-canon6` already
implements) or occurrence objectification (which the brief prefers). **Not
resolved here.**

## The claim-shaped implementation that already exists

**`~/code/onto-canon6/src/onto_canon6/document_map/operational_semantics_v1.py`**
— types a semantic object as `event | state | proposition` and an argument
target as `entity | semantic_object | literal`, plus polarity, modality,
temporal scope, and a relation vocabulary including `supports`, `contradicts`,
`responds_to`, `updates`, `supersedes`. Written July 2026, never wired to a
product path. Its subtree (`document_map/`, 90 modules, ~61k lines) is marked
retained research and frozen; its own `CLAUDE.md` forbids wiring it to a
product entrypoint without an explicit plan.

Evidence for it, all verified against provider traces rather than relayed:

| Fact | Value |
|---|---|
| Ran on real text | Yes — 2026-07-24, real Slack work-status messages |
| Calls / cost | 95 calls, **$4.28** |
| Output | 823 semantic objects (600 event, 190 state, 33 proposition) |
| Propositional arguments used | **6 of 2,335** (0.26%), all work-item composition |
| `contradicts` / `supersedes` relations | **0** |
| Scored? | **No** — no precision, recall or agreement anywhere |
| Human review | One. Found a safety failure; result rejected |
| Disposition | Plan declared it "not an active acceptance gate" the same day |

**Read with the caveat:** that corpus is event-shaped standup text, not where
propositional arguments would appear. The feature was tested where it would not
be needed, so 6/2,335 is weak evidence against it rather than a settled
negative.

## The consumer, and its current state

**`~/code/onto-canon6`** — the governed-assertion runtime that consumes packs
from this repository. Relevant open pull requests as of 2026-09-06:

- **#360** — frame-backbone-to-pack compiler spike (the "highest-value missing
  build" named by the Ontology Platform architecture).
- **#362** — indexes the merged encyclopedic-core biographical-predicate fix and
  traces an "unreliable extraction" claim across three measured batches.
- **#369** — cross-run aggregation of what the vocabulary fails to express.

**A repository audit of that consumer** is at
`~/projects/data/handoffs/2026-09-05-onto-canon6-repository-audit.md`. Its
verdict bears on anything built here: the product core runs end to end, but its
repository gate had not been green since 2026-07-10 and was red in eleven
independent ways, so "a gate that cannot go green cannot go red either, and the
repo has lost its ability to notice its own regressions." Three repair pull
requests landed 2026-09-05.

**The extraction quality this vocabulary currently serves:**
`onto-canon6/docs/runs/2026-07-07_golden_fidelity_baseline.md` records mean
mean precision **0.349** and recall 0.321, in its own words "roughly a third of
what a faithful reading extracts". The widely-quoted 0.42/0.32 is the original
single-run baseline and that source marks it **superseded**.

The honest version is worse than a passing grade: at the then-current floor of
0.35 **the gate tripped**, missing by 0.001, and the floor was recalibrated to
0.30 — a change the source itself flags as "made by the same agent whose change
tripped the gate", raised for Brian's review. The run was rescored from FAIL to
PASS under the new floor. Every use case in this document inherits this number,
so it should be quoted as 0.349 against a moved floor, not as 0.42 against a
met one.

## The parallel implementation

**`~/code/semantic-foundry`** — an eighteen-phase provenance-first substrate
that has already built pinned PropBank, VerbNet, SUMO and BFO slices with
SemLink cross-checks and nine sealed role-alignment holdouts. 189 tests pass.
It holds the **opposite architectural position** on one axis: never merge, keep
each theory's native meaning, represent correspondences as claims. Its empirical
claim is entirely unmade — **zero live model calls, ever**. Its frozen pilot is
27 calls against a precommitted matrix; the single launch attempt stopped before
request one for want of an API key and DNS.

## The graph-maintenance methodology this would operate inside

**`~/projects/inside-success/planning/plan/second_brain/DYNAMIC_GRAPH_MAINTENANCE_METHODOLOGY.md`**
— version 0.2, status "supporting design encyclopedia, not current execution
authority". Two sections matter here:

- **§22** — 52 failure modes, each with consequence, prevention/detection and
  recovery columns, plus seven recovery invariants. It already covers most of
  what this design reasons about: extraction-as-truth, negation becoming
  positive fact, n-ary roles flattened to binary edges, source time versus valid
  time, correction versus supersession, conflict overwritten.
- **§24** — 17 open questions. Two are the same as this document's:
  **§24.4 proposition identity** ("when two differently worded propositions
  should be considered the same") and **§24.12 lossless composition** between
  binary entity-edge operators and n-ary assertion-and-role operators.

Notably, **none of its 17 open questions asks what the predicate vocabulary
should be.** It assumes a vocabulary exists and reasons downstream of it. This
design is upstream of that document rather than duplicating it.

## The gap-detection loop

`onto-canon6` already records, on every extraction run, which meanings its
vocabulary could not express: each carries `bound`, `unmapped` or
`ambiguous_fit`. It also has a governed proposal-to-overlay path. What was
missing until PR #369 was aggregation across runs — one gap is noise, the same
gap across a corpus is a missing predicate.

First aggregation result: **61.5% expressed** over 153 responses and 697
meanings from 8 documents. Its own honest read is that **all 32 gap clusters
appear in exactly one document**, so that corpus supports no coverage
conclusion. The recurring gap categories were nonetheless legible and match this
design's predictions: spatial relations beyond containment, temporal extent on a
relation, person attributes (descent, occupation, reputation), measurements with
a qualifier, and named relations between works.

**Tyler's Reverse Ontology Engine**
(`Inside-Success/reverse-ontology-engine`) is built around exactly this residual
loop: detect a gap, generate competing candidates, find the evidence that
distinguishes them, measure what the representation failed to explain. It is
early — its first end-to-end trace has not run.

## The source design conversation

**`~/code/requirement-to-runtime-semantic-compiler/sources/semantic_interlingua_part1.md`** — 10,012 lines, a 38-minute session
of 2026-09-05 that produced the interlingua framing. Captured immutably in the
vision wiki as `src-chatgpt-session-927f8f0394b8`. Assessment of it, including
what it assumes away, is at
`~/code/vision/wiki/concepts/semantic-interlingua.md`.

## Cross-project synthesis

The vision wiki (`~/code/vision/wiki/`) holds how this object relates to the
rest of the ecosystem. It is the right place for that and this document does not
duplicate it. Most relevant pages:

- `synthesis/linguistic-core-relevance.md` — eight connections, ranked.
- `concepts/ontology-platform.md` — the multi-repo architecture this sits in.
- `concepts/neurosymbolic-ai-hypothesis.md` — tested twice, unresolved.
- `concepts/world-model-vocabulary.md` — the consumer-side need.
- `concepts/semantic-foundry.md`, `concepts/factgraph.md` — parallel projects.

## External resources

| Resource | Role here | Terms |
|---|---|---|
| [WordNet 3.0](https://wordnet.princeton.edu/) | lexical identity layer | WordNet License; commercial use explicit |
| [VerbNet 3.4](https://uvi.colorado.edu/) | thematic-role backbone; inline crosswalk attributes | CU Boulder license, permissive; **not shipped with the data** |
| [PropBank](https://github.com/propbank/propbank-frames) | predicate-argument structure; its own role links replace SemLink | CC BY-SA 4.0 — **ShareAlike** |
| [FrameNet 1.5–1.7](https://framenet.icsi.berkeley.edu/) | frames and frame elements | CC BY 3.0, grant irrevocable |
| [SUMO](https://www.ontologyportal.org/) | upper-ontology grounding | IEEE permissive core; **GPL** extension modules |
| SemLink | *excluded* — no license in its repository | — |

**One caveat on that exclusion.** The shipped `0.3.0` pack still contains a
single row whose mapping method is `semlink` (`lc:disseminate_scatter_widely` →
FrameNet `Dispersal`). One row in forty-six thousand is very unlikely to matter,
but the design asserts a clean exclusion and the artifact is not yet clean;
removing it costs nothing and makes the claim true. Note also that
`semantic-foundry`, cited approvingly below, uses SemLink cross-checks — so
"excluded" is this object's position, not the ecosystem's.
| NomBank | *excluded* — no license; data is LDC Treebank offsets | — |
