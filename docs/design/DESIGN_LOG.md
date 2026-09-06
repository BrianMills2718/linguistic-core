# Design log

History of updates to `SEMANTIC_INTERLINGUA.md`, which never contains this log
— see the living-document convention this repo follows. Entries before
2026-09-06 were written when the design lived in
`linguistic-vocabulary-research/PLAN.md`.

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
