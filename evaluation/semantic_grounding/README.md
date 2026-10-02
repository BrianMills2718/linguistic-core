# Semantic grounding six-concept probe

**Status:** experimental candidate probe. This directory does not change the published `linguistic_core@0.3.3` pack, the compiler contract, or the living design.

## Question

Can a small set of ordinary semantic targets be decomposed into explicit lower-level factors and then projected into multiple top-level ontologies without treating any one ontology's vocabulary as the grounding basis?

The six targets are:

- `red`
- `object`
- `event`
- `support`
- `sit`
- `chair`

They deliberately span quality-space structure, persistence, temporal occurrence, relational/dispositional structure, embodied action, and a higher-order lexical concept.

## Artifact

- `grounding_ir.schema.json` defines a small experimental Grounding IR.
- `six_concept_specimen.json` instantiates a revised candidate factorization and 6 target concepts.

The key representation rule is that ontology mappings are **projections**, not presumed equivalences. Each projection records structure preserved and structure lost or added.

## Three notions kept separate

The probe distinguishes:

1. **lexical primitive** — irreducible within a lexical-semantic system;
2. **definitional basis** — a controlled vocabulary chosen because it is useful for defining other vocabulary;
3. **grounding primitive** — a factor with an explicit lower-level experiential, psychophysical, sensorimotor, learned, or social grounding path.

This is why NSM and Longman are relevant comparison systems but are not treated as the grounding layer by default.

## Current result

All six concepts remain `partially_grounded`. That is intentional. The probe exposes the missing derivations instead of filling them with asserted equivalences.

The largest gaps are:

- recovering phenomenal geometry from psychophysics;
- deriving object and event identity rather than assuming segmentation;
- distinguishing actual support from a disposition to support;
- deriving sitting across bodily and contextual variation;
- representing social/artifact convention without treating it as a phenomenal primitive;
- distinguishing chair from nearby concepts such as stool, bench, seat, and incidental sitting surfaces.

## Source-check boundary

Top-level ontology targets were spot-checked on 2026-10-01 against maintainer/official material:

- DOLCE overview: https://www.loa.istc.cnr.it/dolce/overview.html
- DOLCE quality/quality-region discussion: https://www.loa.istc.cnr.it/old/Papers/DOLCE-EKAW.pdf
- BFO 2020: https://github.com/BFO-ontology/BFO-2020
- gUFO usage guide: https://nemo-ufes.github.io/gufo/overview.html

The six target words were checked directly against the NSM v20 English semantic-prime chart and the Longman Defining Vocabulary list. None of the six is an NSM prime; all six appear in the Longman defining list. See `semantic_basis_comparison.md` and `semantic_basis_comparison.json`.

The factor-boundary audit also found that the original `support` and `sit` decompositions were too close to the target words. They have been decomposed further into contact, relative-position, load-response, body-posture, and posture-transition structure. See `factor_boundary_review.md`.

The PMG-to-factor derivations are hypotheses from the current Phenomenal Meaning Generator design, not validated cognitive-science results.

## Acceptance gate before expansion

Do not expand to the proposed 20–25 concept benchmark until this specimen can answer, for each target:

- What lower-level factors does it depend on?
- Which dependencies are actually grounded versus simply named?
- Which ontology projections preserve which distinctions?
- Which mappings add commitments not earned by the grounding path?
- What would be lost if two candidate senses were treated as equivalent?

A later slice should add direct NSM/Longman/FrameNet/PropBank/Generative-Lexicon comparisons and connect candidate factors to actual Linguistic Core identities.