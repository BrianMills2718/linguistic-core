# Design log

History of updates to `SEMANTIC_PREDICATE_VOCABULARY.md`, which never contains this log
— see the living-document convention this repo follows. Entries before
2026-09-06 were written when the design lived in
`linguistic-vocabulary-research/PLAN.md`.

## 2026-09-08 — The relation layer ships as 0.3.3; the consumer contract was the blocker

The 16 predicate relations, 51 role correspondences and 17 symmetric role pairs
sat in `_candidates/` because publishing them would have been a release nothing
could read: onto-canon6's pack `content` block was a **closed nine-key list**
whose resolver iterated only those keys, so any other key a manifest declared
was silently ignored — file never opened, nothing raised.

That contract now carries three optional sections (onto-canon6 PR #375, plan
0214). Optional, not required, so every already-published pack loads unchanged;
declared-but-missing is an error, so the silent-ignore failure cannot recur.
Three authoring rules run over the composed closure at load: the relation must
be one of the nine known names, nothing may relate to itself, and every
predicate and role id must exist in the effective vocabulary.

Rejected: reusing `hierarchy_edges` with new `edge_type` values, which needed
no code change at all — `_load_type_parents` filters on `subtype_of`, so other
edge types are ignored by type inference. Rejected because that section's
validation *also* only inspects `subtype_of` rows, so relations placed there
would have been referentially unchecked, and correspondences and symmetry do
not fit a `(child, parent, type)` triple. Explicit sections fail visibly.

`0.3.3` is released. All 84 rows load and validate against the full
5,995-predicate / 908-role closure from the pack's real published location.
The validation is not vacuous: repointing one relation at an undefined
predicate fails the same load.

This closes VF-04 and supersedes the design's claim that "there are no
predicate-to-predicate relation edges at all". Reachability is not correctness
— two of the sixteen relations were false and were corrected before release,
and whether the 51 correspondences reduce under-collapse is still unmeasured.
Nothing yet *reasons* over these rows; they load, validate and compose.

## 2026-09-08 — The vocabulary wired to a consumer; a stated consequence disproven

First measurement of whether changing the pack changes what a running system
does, rather than how the pack scores against its own key. onto-canon6's
extractor, real OpenRouter, minimal pair, three runs per condition, on a
throwaway pack version composed from a scratch root — nothing published.

The design had said the missing `ARGM-NEG` role makes "did not acquire" and
"acquired" produce identical structures. It does not. On the published pack the
negated sentence produces **zero assertions**, 3 of 3, no error, no partial
object — the extractor records that a meaning existed and emits nothing bound to
it. The failure is silence, not a wrong object, which makes it invisible to
exactly the review a wrong object would survive. Adding the role makes the two
sentences differ in 2 of 3 runs. The affirmative never spuriously gained a
negation role, 6 of 6.

Corrected in three places in the design plus VF-03, and VF-03 linked to VF-14
(empty extraction) as cause to symptom — VF-14's first identified driver.

Two things found on the way that were not the point. **Seven of the eleven
proposed modifier roles already ship** — five under identical ids, and
`ARGM-TMP`/`ARGM-LOC` as `lc.role.time`/`lc.role.location`; loading all eleven
fails composition with an identity conflict. The real gap is four roles, and the
candidates README now says so. And onto-canon6's `max_predicates_in_prompt`
narrows the prompt but not the response schema, so the default
`predicate_variants` mode cannot run against a 5,995-predicate pack at all.

Also recorded: declaring a role buys representability, not a canonical form.
The pack has a `role_expected_value_kind` constraint type and **no published
version uses it even once**. Declaring one for `negation` collapses
`value_kind` to `boolean` in 3 of 3 successful runs, but `normalized` still
alternates between JSON `true` and the string `"true"`, so the two extractions
still differ. The constraint reaches the tag, not the value. The same runs
returned value fillers carrying a meaningless `entity_type`
(`lc:sumo_type.BeliefGroup`) that nothing rejected.

Artifacts: `evaluation/consumer_wiring/` — probe, results, full run log, the
throwaway pack, and the config overlay needed to reproduce.

## 2026-09-06 — A cold review; nine claims corrected, one contradiction flagged

A reviewer with no context read the design and traced its load-bearing numbers
and absence claims to their sources. Nine were wrong. Each was re-verified
directly before being corrected here, rather than accepted on the reviewer's
word.

**The extraction-quality number was wrong in the flattering direction, twice.**
The design cited mean precision 0.42 as the figure every use case inherits, and
said it passed because the floors were low. The source marks 0.42 superseded,
reports 0.349, and records that the gate *tripped* by 0.001 and the floor was
then moved from 0.35 to 0.30 by the same agent whose change tripped it — a
self-recalibration that source flags for review. The run was rescored from FAIL
to PASS under the new floor. Corrected to 0.349 against a moved floor.

**The pack is no longer event-only.** The 4,658-event/11-state split described
`0.3.0`. Since then `0.3.1` added 265 predicates and `0.3.2` added 1,061;
`lc:citizen`, `lc:birthplace` and `lc:birthdate` all ship. Three of the four
examples given as returning zero hits are present. The Wikidata section extends
a populated family rather than founding an empty one, which weakens nothing in
that argument but changes what it is arguing for.

**The mapping-confidence band was a summary, not a measurement.** Stated as 0.7
to 0.95; measured over the 2,262 rows it is 0.1 to 1.0, with 311 below the
stated floor. The quoted field names were the upstream SQLite columns, not the
pack's.

**Two absence claims failed, the class this repository's own rules name as most
failure-prone.** "Not referenced by any product entrypoint" dropped a qualifier
that onto-canon6 carries deliberately and that its own subtree records having
been wrong about before; `__init__.py` re-exports 30 of those modules. "Its
SQLite column has no third case" implied a schema constraint that does not
exist — there is no `CHECK` on `filler_kind` at all. The second correction
strengthens the conclusion it was supporting: a guarantee living only in
application code is harder to widen than one constraint, not easier.

Also corrected: PropBank counts to 4,666 and 11,880; the SemLink exclusion,
which one shipped row contradicts; and the compendium's "every path was
verified", which invited reading it as every number verified.

**Flagged rather than resolved:** the document states the object is a canonical
layer and not a merge, and that semantic-foundry holds the same position — then
states in its open questions that it assumes a single merged object and that
semantic-foundry holds the opposite. Both cannot be true. Which way it resolves
is a design decision, and it propagates: the licensing conclusion is stated
about "a merged artifact", and a canonical layer carrying no verbatim source
text may not inherit ShareAlike at all.

**Left for the next revision**, named here so they are not lost: the port
surface is given as "8 modules and ~7,080 lines" without enumerating the eight;
the design's preferred next step (an evaluation that produces a number) is
already built in this repo as a preregistration whose harness reports
`blocked_missing_activation_inputs` against an empty `0.4.0-rc1` candidate, and
the design does not mention it; and the reviewer's strongest objection is that
propositions-as-role-fillers may not require widening the filler kind at all,
since onto-canon6 already treats assertions as first-class and a stance edge
onto an assertion node would need no new kind. That objection, if right,
invalidates the effort estimate the disposition question rests on.

## 2026-09-08 — The founding premise is measured; role alignment is the gap

Paraphrase invariance had never been scored. It can be now, and the answer is two
numbers that must not be averaged.

**Over-collapse 1 of 35, 3%** — the direction that fabricates, and the one worth
keeping. Capturing polarity and modality alongside the predicate is what controls
it; a scorer asking only for a predicate measured 69%.

**Under-collapse 17 of 22, and it decomposes.** ~4 entity-name variants, outside
the object's boundary by the coreference ruling. ~5 identical fillers under
different role ids. ~4 harness failing its own role constraint. **~4 the real
finding: the pack's role vocabularies diverge between predicates it declares
related** — `kill` has killer/victim, `murder` has cause/instrument/victim.
Declaring that two predicates correspond does nothing if nothing says which of
their roles do. That is VF-09 with a consequence, and it is the next thing to
build.

Getting there required closing two schema gaps first, because a scorer run before
them would have attributed the representation's limits to the extractor.
Fifteen predicate relations closed the under-collapse gap; eleven modifier roles
and a verb-inflection value type closed the over-collapse gap. Both are
candidates, not pack versions — consumers pin versions and neither has earned a
release.

**Three audits ran against this work and each found something the previous had
missed.** Two of fifteen authored relations were disqualifying: one related
resignation to physical motion, the other put a lawsuit in the defendant's slot.
Three of thirteen `MEASURED` taxonomy rows were wrong, all from relaying
subagent numbers without re-deriving them. Two of my own checks disagreed and
exposed a bug in both — each took an arbitrary first element from a multi-valued
field. A provenance rule now says a row is `MEASURED` only when whoever wrote it
derived the number from a durable artifact.

Also corrected: PropBank's `ARGM` tags are not in its frame files at all — zero
occurrences across 3,323 — and live in the annotated corpus as offsets into the
LDC treebank. The inventory is universal and documented, so declaring it needs no
instance data; an earlier revision called this a recovery of dropped donor data,
which it is not. Aspect is not an `ARGM` tag but a field in PropBank's
five-character inflection encoding.

## 2026-09-06 — The fact-oriented hypergraph brief, reconciled

`FACT_ORIENTED_HYPERGRAPH_COMPILER_BRIEF.md` had been referenced but never read
against the specification. Reading it settles one thing and adds four.

**It corroborates the load-bearing commitment independently.** Its §8 asks "when
do I treat a relationship instance as an object that may itself play roles" —
objectification, which is "a proposition can fill a role" reached from a
different direction, by someone designing a schema compiler rather than an
extraction IR. It argues for it as an early feature, not a late one. Two
independent derivations of the same commitment is the strongest evidence this
design has for it.

**Four things folded in rather than listed.** Facts are set-like by default
(§5.3), so one role tuple is one fact unless an occurrence is given identity,
and populations must never drift quietly from sets to bags — added to the
primitives and, because it collides with extracted assertions being asserted
repeatedly by different sources, as an open question in its own right.
Identity is conceptual rather than incidental (§9): every element needs a stable
internal identifier distinct from its display name, so a rename is not an
identity change; this design had been conflating the two. Three different things
get called a constraint (§11) — domain constraints, model-shape lint, and
per-target enforcement status — and that third vocabulary is what the
village-asserted-as-citizen case actually needed: the constraint was
`REPRESENTED_NOT_ENFORCED`, which is a more useful thing to report than "type
constraints work" or "type constraints don't." Folded into the symbolic-side
section. Readings (§10), a human-readable template per predicate, added to the
primitives as a review surface. Roles carry identity independent of ordinal and
player type (§14), which is exactly where a naive hyperedge-of-vertex-types
representation fails.

**Scope difference recorded rather than glossed.** The brief designs a compiler
whose populations are database rows; this is an IR for extracted meaning whose
populations are assertions with provenance. §5's kernel transfers; §17–§25 on
target mapping, round-tripping and the authoring DSL do not.

## 2026-09-05 — The July semantics ran once; the barrier is the promotion core

Audited whether `operational_semantics_v1.py` was ever run. It was, on
2026-07-24, and every number below was verified directly against the provider
traces rather than taken on report.

95 calls, **$4.28**, 80 parseable responses, 823 semantic objects over real
Slack work-status messages. Of **2,335 arguments, 6 pointed at another semantic
object**, all six work-item composition rather than the strong claim-about-claim
case. `contradicts` and `supersedes` never fired.

**Recorded with the caveat the audit did not make:** that corpus is event-shaped
standup text, which is not where propositional arguments would appear. The run
tested the feature where it would not be needed, so 6/2,335 is weak evidence
against it rather than a settled negative.

It was never scored — no precision, recall or agreement anywhere, every relevant
capability box unchecked, no artifact-table row. Its one human review found a
safety failure and rejected the result, and the plan declared it not an
acceptance gate the same day. On the identical document the production
`entity | value` route produced 4 accepted assertions for under a cent.

**The decision-relevant finding is corpus-independent.** The barrier is not the
extraction schema, which is a day's work. It is the governed core: the promoted
filler kind is typed `entity | value`, the store raises on a third value, the
SQLite column has no third case, assertion identity has no branch for a
proposition-valued role, and no adapter exists from the semantic bundle into
candidates or promotion at all. That is a rewrite of the promotion path across
8 modules and ~7,080 lines, not a port.

Also recorded: the only surviving output of that lane is in the observability
database. `var/plan0168/` is gitignored and gone, so every committed run record
cites artifact paths that no longer resolve — a durable record pointing at a
disposable one.

## 2026-09-05 — The claim half was already built in July

The open decision — can a proposition fill a role — turned out to have been made
already. `document_map/operational_semantics_v1.py` types a semantic object as
event, state or proposition and an argument target as entity, semantic object or
literal, plus polarity, modality, temporal scope and a supports/contradicts
relation vocabulary. It has never been wired to the production path, which still
allows only entity, value or unknown as filler kinds. The subtree is marked
retained research and frozen since August.

Two positions settled, both Brian's:

- **The IR permits, the profile restricts.** Propositions-as-arguments is a
  property of the representation, not an obligation on every pack. This removes
  most of the apparent cost, since only use cases needing claims about claims
  pay the query and extraction complexity.
- **Proposition identity is the design, not a tax.** If the object's core value
  is that different phrasings of one meaning get one representation, then
  propositional identity is that value applied to propositions. It is also
  unavoidable: separate machinery for claims would still have to decide when two
  claims are the same in order to aggregate or contradict them.

The open question narrowed accordingly, from a design choice to a disposition:
does the July work become production, get reimplemented, or stay where it is.
The prerequisite is establishing whether it was ever run against real text.

## 2026-09-05 — Wikidata brought back in; use cases consolidated

**Corrected, not hedged: excluding general-purpose knowledge graphs was wrong,
for two successive bad reasons.** First "broadens domain scope," then a shape
mismatch. Shapes differing is an argument for scoping each to what it does well,
not for discarding one. A Wikidata property *is* a state relation, which is one
of the two halves this specification already names. The evidence was already in
hand: nineteen CC0 properties standardized into the pack format bind 5/5 on real
prose. The earlier 47% P-code ceiling is consistent with this rather than
against it — that attempt asked property codes to carry narrative events, which
they cannot. The rule is now scope: property-style vocabulary for states,
verb-sense resources for events, crosswalk between them. ConceptNet stays out on
its own merits, not by association, and has not been re-examined.

**Use cases consolidated.** Earlier passes kept re-deriving a narrow subset.
The full set is now recorded, grouped by what each needs from the object:
normalization, interface, reasoning and state, and generation and evaluation.
The grouping surfaces something the list did not: most are normalization or
interface uses, so the object's value concentrates in being an interface, with
the reasoning applications downstream rather than alongside.

## 2026-09-05 — First draft of what the representation contains

Adds the specification section the plan had been circling without ever writing.
Two commitments recorded as settled: the object is a canonical layer with
resources attached by versioned mapping objects rather than a merge, and a
proposition can fill a role. The second is what makes one mechanism serve both
event-shaped and claim-shaped text, and it means the speech-act frames the
resources already carry do the claim work rather than needing a parallel
vocabulary.

Ten primitives tabled. Three requirements recorded that are easy to get wrong:
gradable terms must stay terms rather than being coerced to invented numbers,
kind-level claims must not flatten into universals, and the three uncertainty
numbers must stay separate.

One distinction clarified after Brian pushed back: ambiguity is handled and is
not a gap, since multiple hypotheses with explicit uncertainty cover it and
where a human cannot resolve it neither can anything else. Vagueness is
different and is a schema requirement rather than a representation limit.

Open questions gained proposition identity and the coherence-instrumentation
answer. Both connect to the Inside Success graph-maintenance methodology, which
records proposition identity (§24.4) and binary/n-ary composition (§24.12) as
open on its own account, and whose §22 carries 52 failure modes each with
prevention and recovery columns. Its per-run gap detection already exists in
onto-canon6; only cross-run aggregation is missing.

## 2026-09-05 — Licensing checked; two resources removed from the architecture

The open licensing question is closed against primary sources. Two of the seven
resources turned out to be unredistributable, and both were load-bearing.

**SemLink has no license.** It was layer 3, the crosswalk the whole integration
depends on. Replaced by two licensed substitutes: PropBank's own rolelink
elements (CC BY-SA 4.0, 39,810 VerbNet and 11,314 FrameNet links) and VerbNet
3.4's inline mapping attributes (permissive, no copyleft, lower FrameNet
coverage). The architecture survives; layer 3 changes shape.

**NomBank has no license**, and its propositions are token offsets into the LDC
Treebank besides. Dropped. The nominal-predicate gap reverts to an open sourcing
question.

**The paid-product goal is now constrained rather than open.** PropBank's
ShareAlike and SUMO's GPL modules independently prevent a proprietary merged
artifact. The Goal section is corrected: the vocabulary is an open object and
the product is a separate layer above it, matching ADR-0040 decision 7.

**One claim in the previous version was too generous.** The PropBank-to-FrameNet
correspondence was described as "not verified against an established
cross-mapping." Inspecting the data shows every row carries
`mapping_source: llm:gemini/gemini-2.5-flash` with a confidence between 0.7 and
0.95. It is a model's guess with a score, and the plan now says so.

Also recorded: a new licensing section with the full table; the finding that
VerbNet's license ships with neither its tarball nor its repository; FrameNet's
grant being perpetual and irrevocable despite a dead host; two live residuals
(CC BY 3.0 to GPL compatibility, and whether ShareAlike reaches derived
mappings, which ADR-0040 declined to answer for SUMO); two unchecked corners
named rather than closed; and two owed fixes on the public `linguistic-core`
repo.

## 2026-09-05 — Re-derived after a long design session

Substantial rewrite, not an append. What changed:

**Goal restated.** The object is now framed as a semantic interlingua — an
intermediate representation converting arbitrary language into typed canonical
events, entities, roles and relations — with the historical resources as
scaffolding rather than the product. Its defining properties (fixed, formal,
human-authored, application-independent) are stated explicitly.

**New section: what richness actually buys.** Separates *fixed* from *rich* and
argues most claimed value is fixedness. Names the three things breadth
specifically buys plus multi-level representation as unique to the full stack.

**New section: use cases.** Five that need breadth, four that don't, and the
pattern that breadth earns out wherever the task is comparison across sources,
languages, time or schemes. Notes that framing detection is already Brian's F1
fixture rather than a new idea.

**New section: canonicalization is the hard part.** Records the Wikidata P-code
inventory — five approaches, 47% ceiling, abandoned February 2026 for a
vocabulary-fit rather than retrieval reason — plus the caution that several of
those documents are titled as successes their bodies do not support.

**Corrected: the exclusion of general-purpose knowledge graphs.** The prior
stated reason (broadens domain scope) is replaced by the measured one
(property-centric versus verb-centric mismatch), and the real counterexample is
recorded: nineteen CC0 Wikidata properties closed the state-relation gap. The
position becomes separation-and-crosswalk rather than exclusion.

**New section: what the symbolic side can and cannot check.** Records that type
constraints ran and failed to catch a village asserted as a citizen, because the
subject type was deliberately widened to avoid hard-failing correct candidates.

**New section: the neurosymbolic question.** Records both tests — positive past
~300 synthetic items, null at two real documents — as scale-dependent and
unresolved, and names the feedback loop as the design never built.

**Open questions expanded.** Added the merged-versus-federated fork raised by
Semantic Foundry's independent existence, with the reading that Brian's own
vision documents may already resolve it by layer; and "which use case first."
Retained the licensing and implementation-location questions unchanged.

## 2026-09-07 — Renamed to resolve a naming collision

`SEMANTIC_INTERLINGUA.md` renamed to `SEMANTIC_PREDICATE_VOCABULARY.md` (H1
retitled to match). An unrelated GitHub repository,
`brianmills-spec/semantic-interlingua`, a neurosymbolic world-model /
semantic-compiler project, was using the same name; it was renamed the same
day to `requirement-to-runtime-semantic-compiler`. This document was never
that project — it is the SUMO/PropBank/FrameNet predicate and relation
vocabulary described throughout this log — but the shared name made the two
easy to conflate, including in `~/code/vision/wiki` pages that cite this
document. No content changed beyond the title and a disambiguation note at
the top; `CLAUDE.md`, `README.md`, and this log's own self-reference were
updated to the new filename.

## 2026-09-04 — Initial synthesis

Repo created. `PLAN.md` established with: the goal (broadest/richest
standalone integration of pre-LLM linguistic research, valued as an object in
its own right, separate from any downstream consumer); the current state of
`linguistic-core` (SUMO 45/66 modules, PropBank/FrameNet at ID-join level
only); the checked gaps (unverified PropBank↔FrameNet correspondence, no
thematic-role backbone, no nominal-predicate coverage, no WordNet layer,
SUMO's own WordNet mapping not imported); the proposed five-layer
architecture (WordNet → VerbNet → SemLink → PropBank/FrameNet/NomBank →
SUMO); and three open questions (licensing checks still needed for
VerbNet/NomBank/SemLink/WordNet, no decision yet on where implementation
would land, and whether donors beyond these four are worth considering).
