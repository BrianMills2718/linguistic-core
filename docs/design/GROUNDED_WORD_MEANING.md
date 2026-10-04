# Grounded word meaning

**Status:** experimental research direction. This document explains an active
line of investigation in Linguistic Core. It is not a claim that the published
`linguistic_core@0.3.3` pack already implements grounded semantics, and it is
not a claim that the Phenomenal Meaning Generator (PMG) or Grounding IR is
validated cognitive science.

## Why this exists

A conventional lexical definition usually explains one word with other words:

```text
chair -> seat -> thing -> object -> ...
```

That is useful for communication and lexicography, but it does not by itself
answer a deeper grounding question:

> What makes the semantic factors in a definition connect to perception,
> action, experience, learning, or social practice rather than only to other
> symbols?

Linguistic Core is exploring representations that make that question explicit.

The intended shape is:

```text
lexical concept
    ↓
explicit semantic factors
    ↓
lower-level experiential / psychophysical / sensorimotor / learned factors
    ↓
observations, evidence, uncertainty, and refusal when evidence is insufficient
```

This is not an attempt to reduce all meaning to sensor values. It is an attempt
to expose the bridge that ordinary dictionary definitions and ontology
equivalences often leave implicit.

## Three different ideas that must not be collapsed

The grounding work distinguishes:

1. **Lexical primitive** — a concept treated as irreducible inside a particular
   lexical-semantic theory.
2. **Definitional basis** — a controlled vocabulary selected because it is
   practical for defining other vocabulary.
3. **Grounding primitive** — a factor with an explicit lower-level path toward
   experiential, psychophysical, sensorimotor, learned, or social evidence.

A word can be useful in a defining vocabulary without being a grounding
primitive. A concept can also be primitive in one lexical theory while still
having an experiential grounding path in another representation.

That distinction is why comparisons with systems such as NSM and Longman's
Defining Vocabulary are useful without treating either system as the grounding
basis.

## What a grounded definition is trying to add

A normal definition might say:

```text
chair = an object designed for a person to sit on
```

That is informative, but it pushes unresolved meaning into `object`, `designed`,
`person`, and `sit`.

The experimental grounding program instead asks whether the concept can be
represented as a composition whose dependencies are visible.

A simplified sketch is:

```text
chair
  ├─ persistent object / artifact structure
  ├─ affordance or functional relation to sitting
  ├─ learned artifact convention / intended use
  └─ distinctions from nearby categories
       ├─ stool
       ├─ bench
       ├─ generic seat
       └─ incidental sitting surface
```

Then `sit` itself must not remain an unexplained primitive:

```text
sit
  ├─ body posture
  ├─ posture transition
  ├─ contact
  ├─ relative position
  ├─ load response
  └─ persistence through time
```

And those factors can be pushed lower again:

```text
contact
  -> cutaneous deformation / pressure evidence
  -> spatial coincidence within tolerance
  -> multi-channel agreement

body posture
  -> proprioceptive body configuration
  -> contact pattern
  -> reference-frame-relative geometry

load response
  -> force / pressure
  -> bounded displacement
  -> temporal stability
```

The important word is **evidence**. Pressure is not identical to support.
Tactile evidence is not metaphysical contact. A pose estimate is not the
meaning of sitting. Lower-level observations support or fail to support
inferred factors; factors support or fail to support semantic classifications.

## Why refusal matters

A grounding system should be able to say "the evidence does not justify this
meaning."

The executable measurement-to-factor probe already includes adversarial cases:

- visual overlap without physical contact;
- transient contact that should not be classified as attachment;
- an object that disappears and reappears with matching appearance but lacks
  enough evidence for identity continuity;
- two visually indistinguishable objects that must not be collapsed into one.

This makes grounding different from merely attaching labels to sensor inputs.
The representation must preserve uncertainty and refuse semantic binding when
the evidence does not earn it.

## The current six-concept specimen

The initial probe covers:

- `red`
- `object`
- `event`
- `support`
- `sit`
- `chair`

They were chosen to exercise different grounding problems:

| Concept | Main grounding challenge |
| --- | --- |
| `red` | relating perceptual/psychophysical structure to a phenomenal quality category |
| `object` | persistence and identity across observations |
| `event` | temporal occurrence and boundaries |
| `support` | contact, relative position, load response, disposition vs actuality |
| `sit` | embodied configuration across variable bodies and contexts |
| `chair` | higher-order artifact meaning plus learned social/functional convention |

All six are currently marked **partially grounded**. The research method
requires ungrounded dependencies to remain visible instead of replacing them
with an asserted ontology equivalence.

## Relationship to ontologies

SUMO, FrameNet, PropBank, DOLCE, BFO, gUFO, WordNet, NSM, and similar resources
can contribute valuable distinctions, mappings, frames, roles, and lexical
structure. But an ontology mapping is not automatically a grounding.

The experimental Grounding IR therefore treats top-level ontology mappings as
**projections**. A projection should record what structure is preserved, what is
lost, and what commitments are added. No donor ontology is presumed to be the
phenomenal or sensorimotor ground truth.

## Grounding floor

The grounding-floor audit asks whether apparently lower-level semantic factors
simply move lexical circularity downward.

For factors such as contact, relative position, load response, body posture,
and persistence, the current audit identifies measurable candidate observables:

- cutaneous deformation and pressure patterns;
- proprioceptive body-configuration signals;
- force/load and muscle-tension signals;
- multisensory gravity and verticality estimates;
- displacement and change signals;
- spatiotemporal and feature correspondence across perceptual episodes.

This provides a useful stopping point for the current program, but not a final
theory of meaning. The bridge from observables to inferred factors remains a
learning and inference problem.

## What this research is not claiming

The current work does **not** establish that:

- sensor measurements are identical to semantic meaning;
- PMG reproduces human phenomenology;
- the Grounding IR is cognitively complete;
- object or event identity has been solved;
- social and artifact concepts can be reduced to raw perception;
- the published Linguistic Core pack already ships these grounded definitions.

The stronger goal is methodological: make semantic dependencies explicit enough
that grounding claims can be inspected, challenged, tested, and refused.

## Where to look next

- [Semantic grounding six-concept probe](../../evaluation/semantic_grounding/README.md)
  — Grounding IR and the six target concepts.
- [Grounding-floor audit](../../evaluation/grounding_floor/README.md)
  — psychophysical and sensorimotor lower-boundary analysis.
- [Measurement-to-factor gate](../../evaluation/measurement_to_factor/README.md)
  — executable raw-observation → factor → semantic-classification cases.
- [Semantic predicate vocabulary design](SEMANTIC_PREDICATE_VOCABULARY.md)
  — the authoritative living design for the broader vocabulary project.

## Short version

The long-term idea is not merely to give machines a larger dictionary.

It is to build semantic representations where a word can carry an inspectable
path from lexical meaning, through explicit factors, toward the kinds of
experience, perception, action, learning, and social structure that could
justify using that word — while recording uncertainty and refusing claims that
have not been earned.
