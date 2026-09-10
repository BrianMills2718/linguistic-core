---
schema_version: "1.1"
artifact_type: initiative_roadmap
id: linguistic-core-semantic-vocabulary
revision: linguistic-core-roadmap@3
status: active
owner: Brian Mills
dependencies: []
planning_path: durable_solo
planning_path_ref: ../planning/PLANNING_PATH.json
planning_path_sha256: sha256:4ca96561133f0e17e3e35784f9c871ac2e723955da919ae4f43c40963d461dcf
---

# The Semantic Predicate Vocabulary — design

**Status: current living design.** This is the authority for what Linguistic
Core is becoming, not a claim that the planned representation already ships.
[DESIGN_LOG.md](DESIGN_LOG.md) records decisions and the recoverable earlier
design. Raw runs and historical plans remain evidence, not competing roadmaps.

This repository owns the vocabulary, its source mappings, and its compiler.
`onto-canon6` is a consumer; its extraction and reasoning runtime are not owned
here.

**Actor:** Brian and future authorized coding agents continuing the build.
**Continuity consumer:** a fresh session resuming without this conversation.
**Maturity boundary:** prototype construction toward a versioned release; the
active slice does not publish a new pack or change a consumer contract.
**Selected controls:** durable continuity, one writer, reversible repository
changes, no consequential external action, and explicit human gates for spend
or publication.
**Artifact consumer / decision value:** the next authorized implementation
session uses this document to select the dependency-ready construction slice
without reopening the product thesis or inventing later-stage detail.
**Last outcome-bearing update:** `linguistic-core-roadmap@3`, 2026-09-09;
roadmap structure reconciled to the current pack and retained evidence. No
semantic behavior changed in this documentation update.

## Contents

- [Outcome](#outcome)
- [Outcome Boundaries](#outcome-boundaries)
- [Current Truth](#current-truth)
- [Backward Path and Dependencies](#backward-path-and-dependencies)
- [Critical Path](#critical-path)
- [Milestone Horizon](#milestone-horizon)
- [Active Slice](#active-slice)
- [What richness actually buys](#what-richness-actually-buys)
- [What the representation contains — first draft](#what-the-representation-contains--first-draft)
- [Proposed architecture](#proposed-architecture)
- [Canonicalization is the hard part, and there is evidence](#canonicalization-is-the-hard-part-and-there-is-evidence)
- [Canonical Probe](#canonical-probe)
- [Current Evidence](#current-evidence)
- [Failure modes, prevention, and recovery](#failure-modes-prevention-and-recovery)
- [Open questions](#open-questions)
- [Decisions and Assumptions](#decisions-and-assumptions)
- [Course Controls](#course-controls)
- [Decision](#decision)
- [Related work and evidence](#related-work-and-where-the-evidence-lives)

## Outcome

Build the broadest, richest, best-integrated combination of decades of pre-LLM
linguistic and ontological research into a single vocabulary, valued as an
object in its own right rather than for any specific downstream application.

The product is a **semantic interlingua**: a stable, versioned vocabulary and
formal representation contract for expressing entities, events, states,
relations, and claims about claims. Historical resources supply expert-authored
distinctions; they are not forced into one indistinguishable merged ontology.
Canonical concepts coexist with preserved donor senses and typed mappings.

The first-principles argument is conditional and concrete:

- If different phrasings are to be compared, there must be a shared semantic
  contract rather than independently invented labels.
- If a distinction is discarded, downstream logic cannot reliably reconstruct
  it from the normalized object alone. Preserve distinctions before projecting.
- If the foundation is application-independent, its scope cannot be defined
  solely by one application's current corpus.
- If machines are to check or infer anything, identity, roles, scope, and
  permitted transformations must have explicit semantics.

These requirements justify building a rich foundation. They do **not** prove
that a particular predicate count is sufficient, that every application needs
the full vocabulary, or that a vocabulary alone supplies a working reasoner.

“Fixed” means stable identities and pinned versions, not an unchangeable
vocabulary. “Expert-authored” describes the donor knowledge: compiler-authored
and model-proposed mappings must retain their distinct derivation status.
“Formal” means specified machine-interpretable commitments, not that every
constraint is already enforced by every consumer.

The public vocabulary and any separate paid product retain the boundary in
[ADR-0040](../adr/0040-sumo-module-licensing-publish-under-open-terms.md).
Internal-only source experiments are a separate publication scope.

In plain language: **for Brian and future authorized coding agents, change the
current broad but semantically under-specified 0.3.3 pack into a reproducibly
compiled, directly inspectable semantic vocabulary whose identities, roles,
scope, mappings, source meanings, and declared limitations survive across
versions.** The current investment boundary is an internal prototype advancing
toward a finite integrated release, not a public release or application product.

## Outcome Boundaries

**Canonical outcome probe:** start from one pinned source inventory, the
published 0.3.3 closure, and the stable acquisition examples; compile the
selected release closure; load it through the reference package interface; and
request permitted and forbidden mappings. The directly inspectable artifact is
a retained semantic-construction report showing each source reading, canonical
reading, identity level, roles, scope, mapping operation, information loss,
decision, and provenance. The negative case swaps buyer and seller and must fail
visibly.

**Success evidence:** the finite selected inventory is fully dispositioned;
construction assertions pass against the exact reproducible closure; unsupported
or lossy operations are reported rather than silently accepted; and the same
closure loads through the existing `linguistic_core` package seam. This is
construction evidence for the object itself.

**Non-claim:** this does not establish extraction accuracy, application uplift,
complete coverage of language, a working reasoner, or production readiness.
Those require separate consumers and evidence after the foundation exists.

**Non-goals for this initiative:** application workflow semantics, entity
resolution, extraction policy, truth maintenance, world-state execution, a new
database backend, and a proprietary redistribution of donor-derived content.

**Authority limits:** ordinary reversible repository planning and construction
may proceed autonomously. Pause for paid model/data access, public release or
publication, a changed consumer contract, destructive migration, concurrent
writers on the same seam, or any redistribution decision involving an
internal-only source.

## Current Truth

- `linguistic_core@0.3.3` is the canonical merged pack. It contains a 5,995
  predicate / 908 role composed closure and adds explicit predicate relations,
  role correspondences, and symmetric role pairs over its ancestors.
- The pack compiles, loads, and is consumed by `onto-canon6` through a pinned
  external dependency. That proves a live package seam, not full semantic use.
- The semantic contract is partly prose and partly implicit in present schemas.
  Proposition/assertion/occurrence identity, scope, directional mapping
  semantics, conditions, and loss-aware projections are not yet encoded as one
  enforceable contract.
- Current reachability/scoring code treats similarity and specialization as
  collapsing relations and scans multiple pack directories, so its results
  cannot certify one exact release's semantic behavior.
- WordNet and VerbNet source preservation, nominal coverage, richer donor
  fields, and reviewed role alignment remain incomplete. NomBank is permitted
  for an internal profile but is neither selected nor publishable by default.
- Technical execution is partial, the planned construction report is not yet
  reviewable, and the stakeholder outcome has not yet been observed.

Progress is intentionally separated:

| Progress class | Current state |
|---|---|
| Outcome | Not observed: no finite, semantically specified integrated closure yet produces the canonical construction report |
| Enabling | Implemented in part: versioned packs, compiler, provenance fields, relation sections, tests, and a live package consumer seam exist |
| Process | Active: `durable_solo` route and one canonical living roadmap are recorded and machine-validated at the planning-path boundary |

## Backward Path and Dependencies

```text
inspectable integrated semantic report
  <- compile, load, and request allowed/forbidden projections
  <- enforce identity, role, scope, mapping, and loss decisions
  <- preserve selected donor records and adjudicated mappings
  <- pin the exact source inventory, fields, rights, and pack ancestry
```

| Capability | Canonical owner / seam | Dependency | Current evidence | State |
|---|---|---|---|---|
| Semantic contract | Linguistic Core schemas, compiler contracts, and construction assertions | hard | commitments exist in this design; no unified executable contract | first missing boundary |
| Finite source inventory | Linguistic Core source configuration and retained inputs | hard | historical source manifests and coverage reports exist; first-release denominator is not fixed | conditional on contract fields |
| Source-preserving compilation | Linguistic Core compiler and versioned pack manifests | hard | current packs compile, but selected donor meaning is incompletely retained | partial |
| Mapping adjudication | Linguistic Core mapping/provenance records | hard | explicit relation sections ship; semantics and role alignments are not certified | partial |
| Reference package load | `linguistic_core` package seam consumed by `onto-canon6` | evidence | pinned external consumer exists | reuse; no consumer rewrite |
| Internal nominal donor option | private NomBank source boundary | optional | Brian authorized internal use; incremental construction value and retained components are undecided | exploration required after inventory contract |

The first missing boundary is therefore the executable semantic contract, not
additional bulk ingestion. The shortest path stays inside this repository until
the exact closure can produce the directly inspectable report.

## Critical Path

This is a **construction roadmap**, not a sequence of experiments asking
whether the foundation deserves to exist. Construction checks establish that
the object faithfully implements its contract. Downstream comparisons can
later guide application choices; they are not admission gates for this build.

| Stage | Deliverable | Completion evidence |
|---|---|---|
| 1. Fix the semantic contract | Specify identity layers, role fillers, scope, mapping operations, and loss-aware projections; turn the examples below into construction assertions | Each example has an explicit intended representation and allowed/forbidden transformation; unsupported features are named |
| 2. Bound the first release | Pin exact donor versions, selected fields, source scope, and a two-axis coverage matrix | Every selected source record has a disposition; exclusions and unimplemented features are explicit |
| 3. Preserve source meaning | Import selected definitions, roles, restrictions, examples where permitted, and native links without flattening them | Field-level reconciliation against pinned inputs; source assertions are distinguishable from authored/model mappings |
| 4. Integrate deliberately | Use explicit donor crosswalks first; add contextual role alignments and adjudicated proposals where links are missing or inadequate | Mapping operation, direction, conditions, provenance, and review status are inspectable; no ARG-number-only equivalence |
| 5. Compile a coherent release | Compose the exact version closure, validate its semantics, and demonstrate loading/querying it through a reference consumer | Reproducible compilation from retained inputs and decisions; construction assertions pass against that closure; unsupported operations fail visibly |

Stages are dependencies, not a requirement to finish every donor before
exercising the compiler. Carry one stable acquisition example through each
increment, then expand the declared matrix. A source slice may traverse all
five stages while later donors remain explicitly unintegrated.

## Milestone Horizon

| Milestone | Planning state | Inspectable output / stable boundary | Required capability and evidence | Promotion or replan trigger |
|---|---|---|---|---|
| M1. Executable semantic contract | `fully_specifiable_now` | Acquisition construction report against one exact 0.3.3 closure, including the reversed-role failure | Encode identity levels, scope, mapping direction/conditions, role transforms, and loss; focused assertions pass | Promote when the report is retained and unsupported operations fail visibly; replan if the current pack shape cannot express a required distinction |
| M2. Finite first-release inventory | `conditional` | Pinned donor/component/field/rights manifest plus two-axis coverage matrix | M1 identifies the fields and unsupported states the inventory must carry | Promote after M1 stabilizes the contract; replan if a selected donor cannot legally or technically supply a required field |
| M3. Source-preserving donor slices | `conditional` | Reproducible donor records retaining definitions, roles, restrictions, examples where permitted, and native links | M2 denominator and field dispositions; reconciliation against exact retained inputs | Promote donor-by-donor when selected records are accounted for; do not wait for every later donor to exercise compilation |
| M4. Deliberate integration | `conditional` | Reviewed directional mappings with role transforms, conditions, provenance, and explicit unresolved cases | M1 operations plus M3 preserved records; donor-native links reused before generated proposals | Promote mapping families only after contextual review; replan when donors encode genuinely incompatible distinctions |
| M5. Coherent integrated release candidate | `conditional` | Exact closure builds, loads, and emits the canonical report across the selected matrix | M1-M4 accepted for the finite release boundary | Human gate before public release; reset the candidate if reproducibility or source-rights lineage fails |
| M6. Consumer-specific profiles and feedback | `deliberately_deferred` | Smaller loss-declaring projections and downstream observations | One coherent integrated release candidate and a named consumer need | Resume only after M5; application results may shape profiles, not retroactively gate construction of the foundation |

**Execution frontier:** M1 is the sole active outcome-bearing goal. It is a
vertical because it preserves the real pack, compiler/load boundary, semantic
decisions, and a directly inspectable result.

**Design frontier:** only M2's inventory fields and rights/disposition contract
are worth shaping early, because they depend on and exercise M1. Detailed donor
ingestion, mapping campaigns, release mechanics, and consumer profiles remain
conditional; specifying them now would encode guesses as commitments.

## Active Slice

Specify the mapping and scope contract using the acquisition examples below,
then repair the existing validation route to exercise that contract against
**one explicitly selected pack version and its declared ancestors**.

The current reachability/scoring scripts use a `COLLAPSING` set containing
`exactMatch`, `closeMatch`, `broaderThan`, and `narrowerThan`, and use
unordered predicate pairs. They also glob across pack directories, including
candidates. Thus “reachable” currently does not establish sound equivalence
or capability in a particular published version. Fix that before using these
scores to certify mapping semantics. This document changes the plan, not those
scripts or the already-published packs.

This slice does not authorize broad donor ingestion, a consumer-runtime rewrite,
a new database backend, or application benchmark runs.

**Focused check:** the acquisition examples below must distinguish identity,
direction, roles, and scope against one named pack closure. Unsupported mapping
operations fail visibly. Existing published packs remain unchanged during this
slice.

**Visible result:** a human-readable retained construction report for the
acquisition example family, backed by machine assertions, rather than a score or
predicate count.

**Input / output and affected boundaries:** input is one named 0.3.3 closure and
the acquisition cases; output is the report plus validated contract records.
Only Linguistic Core's contract, exact-version loader/validator, and focused
tests change. The `onto-canon6` runtime and published pack contents do not.

**Implementation constraints:** preserve existing IDs and released artifacts;
do not reinterpret `closeMatch`, `broaderThan`, or `narrowerThan` as equality;
keep occurrence, proposition, and assertion identity distinct; retain mapping
direction, conditions, role transforms, provenance, and declared loss.

**Failure, containment, and rollback:** unsupported operations fail with an
inspectable reason. If 0.3.3 cannot carry the contract without changing its
published meaning, add a new candidate contract/version rather than rewriting
0.3.3. The branch and generated candidate artifacts remain recoverable Git
state; no consumer migration occurs in this slice.

### A finite first-release boundary

The aspiration is broad; the first release must have a finite denominator.
Stage 2 produces the actual pinned inventory, not an arbitrary “6,000 is done”
target. The selected source versions and fields are still open decisions.

Track coverage on two axes:

- **Linguistic constructions:** verbal predicates, nominal references and
  nominalizations, adjectival/state predication, light-verb constructions,
  alternations/converses, negation/modality/aspect, quantities/comparisons,
  temporal scope, generic/kind-level claims, and nested/attributed claims.
- **Conceptual domains:** physical and spatial relations; time and change;
  agents and organizations; possession and transfer; social/legal relations;
  information and communication; cognition and argument; measurement.

For each selected source family/field and each matrix cell, name examples,
included scope, exclusions, representational support, and mapping disposition.
Use distinct states such as retained-unmapped, proposed, accepted, rejected,
and unsupported. “No selected records” is not “complete coverage of language.”

A first integrated release is complete when:

1. Every selected input record is accounted for as retained, mapped, rejected
   with reason, or explicitly excluded; every mapping retains its source.
2. Every in-scope construction has a specified representation and passing
   construction assertions; out-of-scope constructions remain explicit.
3. Role alignment, direction, scope, and projection loss are respected.
   Unmapped and unverified content cannot masquerade as verified equivalence.
4. A named release closure compiles and loads deterministically from pinned
   inputs **and retained reviewed proposals**; rerunning an LLM is not a
   reproducibility strategy.
5. Coverage, unresolved mappings, and observed defects are reported separately.
   A predicate total or a resolvable source identifier is not a quality score.

The release number follows this boundary; this update does not declare a
`1.0` release or revive an old `0.4.0-rc1` candidate.

## What richness actually buys

A shared vocabulary reduces representational drift. Richness additionally
allows distinctions across senses, constructions, and domains to survive.
These are separate benefits: a small fixed vocabulary can be stable while
being unable to preserve a sentence's meaning.

Breadth increases the number of distinctions and mappings to manage. That is
a construction obligation, not proof that breadth should be abandoned.
Profiles may expose small task-specific subsets without redefining the source
meaning or silently erasing distinctions in the stored object.

## What the representation contains — first draft

The commitments below define the target contract. Their concrete serialized
shape and consumer support must be specified in stage 1 rather than inferred
from the present pack.

### The primitives

| Primitive | Contract |
|---|---|
| Entity | Persistent identity supplied by an upstream identity/resolution stage |
| Predicate/type | A reusable meaning, distinct from an occurrence of that meaning |
| Event/process/state instance | An identity-bearing occurrence or state, with participants and applicable temporal scope |
| Proposition | Truth-evaluable content that can fill a role in another proposition |
| Assertion/support | A source's assertion of content, with attribution and provenance; repeated assertions need not create new proposition content |
| Role | Stable typed slot, independent of argument ordinal and player type; fillers may include entities, values, propositions, and occurrence references |
| Scope | Explicit polarity, modality, aspect, attribution, temporal scope, and applicable quantification |
| Value | Typed quantity/unit where specified; qualitative degree remains qualitative |
| Reading | Human-readable template preserving role identity for review and verbalization |
| Mapping | Typed, directional where appropriate, versioned correspondence with conditions and provenance |

Do not conflate “same predicate,” “same proposition,” and “same event.”
Two purchases by Acme from Beta on different occasions can share a predicate
and participants without being one occurrence. Two reports can support one
proposition without becoming one source assertion. Structural hashing alone
does not resolve occurrence identity.

### Three requirements that are easy to get wrong

- “A significant increase” does not license inventing a numerical threshold.
- “Dogs bark” is a generic statement about a kind, not “every dog always barks.”
- Parser confidence, evidential support, and stated likelihood are separate
  concepts; none automatically calibrates the others.

Source/assertion time is not the event's valid time. Unknown time is not an
all-time claim. Ambiguous readings remain alternatives with uncertainty; their
existence does not mean disambiguation is solved.

### Settled: the IR permits, the profile restricts

Propositions-as-arguments belongs in the representation. A profile may restrict
which features it supports. A consumer must disclose those restrictions rather
than flattening an unsupported nested claim into an asserted fact.

### Settled: proposition identity is the design, not a tax on it

Identity is part of normalization, but its complete decision procedure is not
settled. Separate content identity, assertion identity, and occurrence identity
first. Equivalence must respect roles, scope, and resolved references.

### The mapping relation vocabulary

The existing nine names are retained, but their names are not executable
semantics by themselves. The contract must specify source/target kinds,
direction, conditions, role transformations, and permitted composition.

| Relation | Permitted interpretation | Must not imply |
|---|---|---|
| `exactMatch` | Equivalent meaning within a stated context, with validated role alignment and scope | Universal substitutability merely because a row exists |
| `closeMatch` | Approximate correspondence for retrieval/review | Equality, bidirectional entailment, or transitive collapse |
| `narrowerThan` | A specialization; narrower-to-broader inference only when declared conditions and role mapping justify it | The reverse inference or deletion of the narrower assertion |
| `broaderThan` | The converse direction of the specialization relation | Broader-to-narrower inference |
| `lexicalizes` | A lexical form/sense expresses a concept | Identity of the lexical entry and concept |
| `evokes` | A lexical unit evokes a frame | Equivalence of the frame and every evoking predicate |
| `roleEquivalentInContext` | Roles align under a specified predicate/context mapping | Global interchangeability of similarly named or numbered slots |
| `roleSpecializes` | A role is more specific in a stated context | Unconditional role equality |
| `incompatibleWith` | The proposed mapping is semantically incompatible in the declared scope | That two real-world events cannot both occur |

Converse and symmetric behavior additionally require explicit role
transformations. “Buy”/“sell” requires aligning buyer and seller under the
same transaction conditions, not blindly reversing all arguments. Symmetry
applies to declared roles of a predicate, not all its fillers.

The operational contract remains to be encoded and enforced. Existing
published rows are not retroactively certified by this specification.

## Proposed architecture

Keep three separable layers:

1. **Preserved donor records:** native identifiers, versions, definitions,
   roles, restrictions, native mappings, and retained examples where permitted.
2. **Canonical semantic layer:** stable `lc:` identities and the representation
   contract. No donor's identifiers alone define canonical identity.
3. **Versioned mapping/projection layer:** explicit relations from donor senses
   to canonical meanings and between canonical meanings, with provenance,
   conditions, review status, and declared information loss.

WordNet supplies a lexical-sense layer, not a mandatory identity authority for
every entity, event, or proposition. VerbNet contributes role and alternation
structure; PropBank predicate-argument structure and its native links; FrameNet
frames and frame elements; SUMO ontological grounding. Their perspectives can
overlap without being interchangeable.

**Planned source choices are not installed capabilities.** Select exact
versions and fields in stage 2. Prefer a donor's explicit links as evidence
before generating replacements, but inspect what each link actually asserts:
an identifier correspondence alone does not prove aligned role semantics.

NomBank is **eligible for internal consideration**, following Brian's explicit
permission. Adoption is not decided. Evaluate its incremental nominal coverage,
the usable components, and the private/public artifact boundary before adding
it. Do not publish restricted source content, examples, or derived artifacts
whose distribution basis has not been established.

### Three defects, one cause: the import kept less than the source had

Shallow imports can lose the definitions needed to distinguish senses, preserve
roles, or judge frame mappings. Recovering source content is therefore a
prerequisite to trustworthy integration, not proof that all integration
problems disappear. Donor senses can still disagree or align only in context.
Argument number alone is not a cross-predicate semantic role.

## Canonicalization is the hard part, and there is evidence

Canonicalization should normalize equivalent expression while preserving
non-equivalent meaning. Similarity, entailment, and identity are different
operations and must not share a collapse rule.

### Settled 2026-09-07: what this object discards, and what it does not

The earlier user rulings remain binding:

1. **Coreference/entity resolution is upstream**, not a vocabulary capability.
   Construction assertions use controlled entity identities.
2. **Event and resulting state stay distinct and linked.** “Agreed to acquire”
   must never become “acquired”; planned, ongoing, completed, and resulting
   state descriptions retain their distinctions.
3. **Converse predicates remain distinct**, linked through conditional inference
   and explicit role alignments.
4. **“Acme sued Beta” and “Acme filed a lawsuit against Beta” normalize to
   `sue`** under the same reading and scope. This does not settle every nominal
   reference.
5. **Select the nearest predicate and retain residual meaning as prose when
   needed.** This remains allowed; residual prose is not automatically available
   to symbolic inference. A formal query must report the unsupported distinction
   rather than treating the approximation as exact.

Different donor rolesets are evidence to preserve a distinction, not a theorem
that no two records can ever align. Identical glosses do not prove identical
senses. Repair impoverished descriptions before proposing consolidation.

### Canonicalization is a choice, not a property

Keep the richest supported interpretation in the canonical object. A profile
can derive a coarser view, but the projection must identify omitted distinctions
and must not overwrite the richer original.

For example, “Acme bought Beta” may support “Acme acquired Beta” under the
appropriate acquisition sense and conditions. The reverse does not establish
purchase: acquisition can have other means. The two are not losslessly
interchangeable simply because the application wants one acquisition category.

## Canonical Probe

Starting state: the published 0.3.3 relation layer and the acquisition examples
below. Action: compile/load one explicitly selected pack closure, then request
each permitted or forbidden projection. Inspectable output: a retained report
showing the source meaning, target meaning, role transform, scope, decision, and
reason for every case. A reversed buyer/seller mapping is the negative case.
Passing this probe establishes the implemented mapping contract for these cases;
it does not establish complete linguistic coverage or downstream application
quality.

| Input/operation | Required behavior |
|---|---|
| “Acme acquired Beta” / “Beta's acquisition by Acme,” with the same resolved event and scope | Preserve one event reading across verbal and nominal expression |
| “Acme bought Beta” projected to acquisition | Permit only the supported direction/conditions; retain purchase-specific meaning in the original |
| Acquisition projected to purchase | Reject unsupported strengthening |
| “Acme sold Beta to Gamma” / “Gamma bought Beta from Acme,” same transaction | Align seller, buyer, and transferred object explicitly |
| Buyer and seller swapped accidentally | Detect the role mismatch |
| “Acme agreed to acquire Beta” / “Acme acquired Beta” | Preserve different modal/event commitments |
| “Acme denied that it acquired Beta” | Preserve attributed denial and embedded proposition; do not assert the acquisition |
| Same participants, two purchase occasions | Preserve distinct occurrences |
| Two sources report the same acquisition | Preserve separate support records, even if proposition content is shared |

The existing pair key remains useful source material, not unquestionable truth:
its “same-object” labels must be qualified by identity level and context before
reuse. Do not silently rescore old runs under the new interpretation.

## Use cases

The representation is intended to support paraphrase normalization, typed
retrieval, event/state comparison, provenance-aware claim aggregation,
contradiction analysis, and meaning-preserving projection. These are motivations
and downstream opportunities, not delivered application capabilities.

Claims about claims require nesting; contradiction analysis additionally needs
compatible subjects, times, scopes, and logical commitments. An attributed
possibility is not automatically contradicted by an assertion of actuality.

## Wikidata belongs in the design, scoped to states

Wikidata is a candidate for relation/state coverage and lexical alignment,
not an instruction to import its entire property universe. Select scoped
properties and qualifiers through the same coverage and provenance contract.
The existing relation vocabulary is not empty; this would extend it.

## What the symbolic side can and cannot check

Separate domain constraints, schema/model-shape lint, and consumer enforcement
status. A represented type restriction is not evidence that extraction enforces
it. Report whether an operation is enforced, represented-but-not-enforced,
metadata-only, or unsupported.

A validator can check implemented type, role, scope, reference, and mapping
rules. It cannot infer truth from a source label or repair unknown semantics
by silently accepting them.

## Gaps this design does not currently address

Entity resolution, extraction policy, cross-document reconciliation, execution
of plans, world-state simulation, and production backend design remain outside
this repository. Their representational needs can inform the contract without
moving those runtimes here.

Time, quantities, process references, causal relations, and hypothetical
scenarios need explicit representational boundaries. Representing a causal
claim does not install a causal rule. A predicate never implies that a consumer
has installed effects, inertia, or an executable world model.

## The neurosymbolic question

A symbolic system needs explicit meanings and valid transformations if it is to
reason over normalized language. Linguistic Core supplies that foundation;
extraction, proof procedures, truth maintenance, and application behavior are
additional components.

Existing consumer experiments inform integration hazards. They do not establish
that this entire representation works, nor does a low use of one feature in one
corpus show that the feature should be removed from an application-independent
foundation. Comparative application tests are not the construction gate.

## Current Evidence

The repository's current pack is
[`linguistic_core@0.3.3`](../../ontology_packs/linguistic_core/0.3.3/manifest.yaml),
a relation-layer extension of `0.3.2`. It declares predicate relations, role
correspondences, and symmetric role pairs, adding no predicates, roles, or
types of its own. Ancestors provide the vocabulary.

This closes the absence of relation sections; it does **not** close
directional inference, contextual equivalence, role-alignment correctness,
or the richer proposition/scope contract above.

### Known gaps in the current integration

- Full source-preserving WordNet/VerbNet integration is planned, not achieved by
  having imported the earlier selected donor predicates.
- Role correspondences derived from matching PropBank argument positions need
  semantic checking. The current derivation script has explicit divergent-role
  exceptions; positional agreement is a proposal mechanism, not certification.
- Candidate modifiers and value types are not equivalent to a published
  composed release. Do not import all candidates blindly: some roles already
  exist under identical or alternative identifiers.
- Current mapping/reachability scripts blur similarity, specialization, and
  equivalence, and mix versions/candidates through directory globs.
- Richer definitions, nominal coverage, scope representation, and explicit
  projection behavior remain construction work.

## Licensing

[ADR-0040](../adr/0040-sumo-module-licensing-publish-under-open-terms.md)
continues to govern the existing public artifact. No publication terms are
changed here, and rewriting glosses is **not** assumed to remove obligations
attached to donor-derived content or mappings.

Brian's internal-use allowance makes NomBank eligible, not selected and not
cleared for public redistribution. Any selected internal-only inputs and their
outputs must remain outside the public build until their publication basis is
established. Record rights metadata per pinned component rather than assigning
one assumed license to a resource name.

SemLink has no newly adopted permission or dependency in this plan. Existing
source records should be accounted for before asserting complete exclusion.
Unresolved distribution/compatibility questions remain at the publication
boundary; they are not a reason to block permitted internal design work.

## Failure modes, prevention, and recovery

These stable IDs preserve references from the design log. Historical measured
rates belong to the cited runs, not to an unqualified present-tense score.

| IDs | Failure to prevent | Current disposition and construction response |
|---|---|---|
| VF-01, VF-10 | Wrong frame mapping or uncalibrated confidence presented as reliable | Historical frame-layer evidence below; preserve full definitions, review mappings, and do not equate confidence with correctness |
| VF-02 | Identical shallow glosses obscure different senses | Restore definitions and sense provenance; do not merge by gloss equality |
| VF-03 | Missing donor fields or representation features silently lose meaning | Reconcile selected source fields; separately specify universal modifiers and scope, rather than pretending every feature lives in frame files |
| VF-04 | Required relations cannot be represented | Relation sections ship in 0.3.3; operational semantics are still incomplete |
| VF-05 | Nominal reference is unsupported | Cover nominal constructions explicitly; internal NomBank is an optional candidate |
| VF-06, VF-07 | Over-collapse or under-collapse | Separate equivalence, entailment, and similarity; test roles and scope independently |
| VF-08 | Broader coverage creates unmanaged mapping ambiguity | Anticipated design tension; preserve source senses and explicit profiles |
| VF-09 | Incorrect cross-predicate role alignment | Published correspondences exist; argument positions alone do not validate them |
| VF-11 | Donor assertion and model proposal have indistinguishable trust status | Keep derivation method, source provenance, and review status separate |
| VF-12 | Coverage is reported as correctness | Report denominator, dispositions, and quality evidence separately |
| VF-13 | Measurement survives without reproducible artifact | Retain inputs, outputs, versions, and scoring semantics; label superseded runs |
| VF-14 | Empty extraction silently means “nothing to say” | Consumer-owned behavior; integration probes must distinguish no content, unsupported meaning, and failure |
| VF-15 | Claims lack cross-document identity/reference support | Specify reference/identity contract here; reconciliation runtime remains consumer-owned |
| VF-16 | Role names are invented per extraction | Stable pack role identities; unsupported roles fail visibly |
| VF-17 | Entity-resolution errors are scored as vocabulary errors | Upstream responsibility; control resolved identities in construction assertions |
| VF-18 | Symmetry is missing or overgeneralized | Symmetric role pairs ship; enforce only declared role permutations |

Historical reachability and collapse scores cannot certify the revised semantics
until their directionality and exact-version handling are repaired. Preserve
the old artifacts unchanged and attach new results to their own contract/version.

## Open questions

These are construction decisions, not reopened questions about the goal:

- What exact donor versions, components, and fields constitute the first
  integrated release, and what does its two-axis matrix exclude?
- Does NomBank add enough distinct nominal structure to select it for the
  internal profile, and which components would that profile retain?
- What serialized identity/reference mechanism distinguishes proposition
  content, source assertion, and repeated event/process occurrences?
- How are mapping context, preconditions, role transforms, composition limits,
  and projection losses encoded and enforced?
- Which scope, quantity/unit, temporal, generic, and process features enter the
  first release, and what are their explicit unsupported cases?
- Which selected source components require a private overlay rather than
  participation in the public artifact?

Canonical-layer architecture, upstream coreference ownership, this repository's
compiler ownership, and the right to build before application benchmarking are
settled; they are not open gates.

## Decisions and Assumptions

| Choice or uncertainty | Disposition | Reason / evidence | Affected boundary |
|---|---|---|---|
| Build the broad foundation before application comparison | `human_set` | Brian rejected downstream uplift as an admission test for constructing its prerequisite | initiative outcome and sequencing |
| Preserve donor meanings behind a canonical layer rather than flattening all sources | `human_set` | accepted design and current architecture | representation and integration |
| Run M1 before further bulk ingestion | `agent_decided_reversible` | the executable semantic contract is the first missing boundary and prevents new ambiguous rows | execution frontier |
| Reuse the current package/consumer seam without changing `onto-canon6` | `agent_decided_reversible` | a live pinned dependency already exists; this slice can prove the object through its own load boundary | reference observation |
| Treat exact donor versions and fields as M2 output | `agent_decided_reversible` | selecting them before M1 would assume contract fields not yet fixed | release boundary |
| NomBank may be evaluated only in a private internal profile | `human_set` | Brian authorized internal use but explicitly did not select it | source and publication boundary |
| The current pack can support M1 through additive candidate contracts | `assumption` | existing versioning and contract machinery suggest this; if false, M1 replans a new candidate pack shape without rewriting releases | active slice |
| Publication of NomBank-derived or other internal-only outputs | `human_required` | internal-use permission is not redistribution authority | release gate only |

## Course Controls

- **Continue** while each increment makes the acquisition report more complete
  or removes a demonstrated direct blocker to it.
- **Change tactics** after two supporting increments without a new inspectable
  report capability, or after three failures at the same semantic boundary
  without new evidence; return to the smallest real acquisition case.
- **Scale** from one example family to the two-axis coverage matrix only after
  M1's exact closure and negative case pass. Scale donor-by-donor, preserving a
  finite denominator and explicit unresolved states.
- **Reset the candidate, not the initiative**, if the representation cannot
  preserve identity/scope/role distinctions, exact compilation is not
  reproducible, or selected-source rights cannot be traced. Do not silently
  weaken the contract to keep a green score.
- **Stop and request human action** only for spend, publication/redistribution,
  a material outcome change, destructive migration, or a real concurrent-write
  collision. Application benchmark results may later change profiles or
  priorities; they do not invalidate the construction-first outcome by default.

## Decision

**Planning path: `durable_solo`.** One contributor directs reversible work that
continues across sessions, so the living design remains the one durable roadmap.
Do not add a work-unit graph, packet per slice, or separate roadmap. Reassess the
path for a slice that introduces concurrent writers, mutates an adopted shared
contract, performs a persistent migration, enters a governed registry, or makes
a consequential external change.

The construction-first outcome and five-stage sequence are accepted. No human
decision is required for the active slice. NomBank adoption and any publication
of internally sourced material remain later human-owned decisions.

**Human decisions:** none for M1. The next human gate is only encountered if a
later milestone proposes selecting restricted NomBank components or publishing
an integrated release.

**Exact next action:** specify the M1 contract for identity, scope, mapping
operations, role transforms, and loss; encode the acquisition cases as
construction assertions; then update the reachability/validation route to load
only `linguistic_core@0.3.3` and its declared ancestors and emit the retained
construction report.

## The sibling project, and why it is not a competitor

Linguistic Core owns the reusable vocabulary and source mappings. Semantic
Foundry and the requirement-to-runtime semantic compiler have complementary
representation/compiler concerns. Preserving source-native meaning behind
versioned canonical mappings is a shared principle, not an opposite architecture.
No current runtime/adoption claim about a sibling is made by this plan.

# Related work, and where the evidence lives

This section is a source map. Historical evidence informs the design without
becoming current execution authority. Re-read primary records before quoting
numbers or making present-tense claims about another repository.

## Prior design work on the same representation question

[Fact-oriented hypergraph compiler brief](FACT_ORIENTED_HYPERGRAPH_COMPILER_BRIEF.md)
supports typed n-ary roles, objectification, stable identities independent of
display labels, human-readable readings, and separation of domain constraints
from schema lint and target enforcement. Set-like proposition content can
coexist with distinct assertion/occurrence identities.

Its PostgreSQL, MongoDB, GraphQL, and DSL implementation plans do not transfer
into this vocabulary roadmap.

## Local construction and integration evidence

- [Canonicalization key and runs](../../evaluation/canonicalization/README.md):
  historical paraphrase judgments and scores. Reuse requires the identity,
  directionality, role, scope, and exact-version corrections above.
- [Frame-layer audit](../../evaluation/frame_layer/README.md): retained sample,
  judge output, and analysis. A sampled result is not a universal defect rate.
- [Consumer-wiring probes](../../evaluation/consumer_wiring/README.md):
  September 8 negation/value-kind probes against a public baseline and scratch
  overlay. They demonstrate scoped integration failures, not a production
  guarantee or the behavior of every negated statement.
- [Source coverage](../runs/artifacts/plan0147_source_coverage_v1.json) and
  [crosswalk coverage](../runs/artifacts/plan0147_linguistic_crosswalk_coverage_v1.json):
  historical inventories; source reachability is not verified semantic alignment.
- [Earlier quality preregistration](../runs/artifacts/plan0147_linguistic_quality_preregistration_v1.json):
  retained historical, unactivated record, not the current build gate. Its old
  baseline/candidate and missing activation inputs are not silently updated.
- [Earlier quality harness record](../runs/artifacts/plan0147_linguistic_quality_harness_v1.json):
  reusable material only after checking that its contract and versions match
  the decision it is being asked to support.

## Cross-project sources

The [design log](DESIGN_LOG.md) retains the dated interpretation of July
`onto-canon6/document_map` work, September consumer wiring, and relation-layer
release evidence. Consumer runtime questions belong to their primary source,
not to this plan's historical account.

The source conversation lives at
`requirement-to-runtime-semantic-compiler/sources/semantic_interlingua_part1.md`.
The [vision knowledge index](https://github.com/BrianMills2718/vision/blob/main/wiki/index.md)
routes cross-project relationships; its summaries are not substitutes for
primary decisions. The previous full design is recoverable through the revision
linked in the log, including its older cross-project evidence inventory.

## External resources

These are donor discovery references, not pinned release inputs or a fresh
license opinion:

- [WordNet](https://wordnet.princeton.edu/) — lexical senses.
- [VerbNet](https://uvi.colorado.edu/) — verb classes, roles, and alternations.
- [PropBank frames](https://github.com/propbank/propbank-frames) — predicate-argument structure.
- [FrameNet](https://framenet.icsi.berkeley.edu/) — frames and frame elements.
- [SUMO](https://www.ontologyportal.org/) — ontological grounding.
- NomBank — optional internal nominal-structure donor; component/version
  selection remains open.
