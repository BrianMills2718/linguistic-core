# The Semantic Interlingua — design

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

> **Unresolved, and this document currently says both things.** The commitment
> immediately below states the object is *not* a merge and that semantic-foundry
> holds the same position. The first open question near the end of this document
> states that this design *assumes a single merged object* and that
> semantic-foundry holds the *opposite* principle. Both cannot be true. This is
> flagged rather than silently resolved because which way it goes is a design
> decision, not a correction — and it propagates: the licensing conclusion is
> stated about "a merged artifact", and a canonical layer carrying no verbatim
> source text may not inherit ShareAlike at all.

**Settled: the object is a canonical layer, not a merge.** Canonical classes are
authored independently and each source resource attaches by a versioned mapping
object. Nothing collapses WordNet, PropBank and FrameNet into one table. This
preserves the distinctions the resources exist to make, and it is the same
position [[semantic-foundry]] holds, reached independently.

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
| **Mapping** | How a canonical class attaches to a resource, under a relation vocabulary richer than "same as" |

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

**Reasoning and state.** World modeling, where canonical events carry
preconditions and effects and become state-transition operators. Planning, which
is the same transition model read in the other direction. Counterfactual and
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

## The neurosymbolic question

The thesis is that the neural model interprets messy language and the symbolic
layer represents, constrains and reasons over the interpretation, with the
vocabulary sitting at that boundary.

Tested twice here with split results. A synthetic test found symbolic checking
beating a neural-only pass, but only once the corpus passed roughly 300 items;
below that both were perfect. A real-document test at two documents found no
gap to catch. The honest state is **scale-dependent and unresolved**, which is
a stronger position than either proven or failed.

The design that has never been built is the **loop**: neural proposes uncertain
hypotheses, symbolic constraints revise them, beliefs update. Current systems
here are one-directional — extract, validate, drop.

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
declined to answer it. For the current artifact the question is moot, because it
contains verbatim PropBank description text.

Two unchecked corners, named rather than closed, because the one absence claim
that was wrong in this review was wrong for exactly this reason: NomBank's two
`DOCS` PDFs were not opened, and Colorado serves multi-resource download bundles
behind a page whose linked license file covers VerbNet only. For SemLink
specifically the cheapest real answer is an email to the Colorado group.

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

**`~/code/semantic_interlingua_part1.md`** — 10,012 lines, a 38-minute session
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
