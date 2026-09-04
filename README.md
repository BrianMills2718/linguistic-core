# linguistic-core

A broad, honestly-sourced predicate/relation vocabulary derived from
[SUMO](https://www.ontologyportal.org/) (the Suggested Upper Merged
Ontology), [PropBank](https://propbank.github.io/), and
[FrameNet](https://framenet.icsi.berkeley.edu/), with a governed pipeline for
compiling, verifying, and extending it.

This started as a component pack inside
[onto-canon6](https://github.com/BrianMills2718/onto-canon6)'s
governed-assertion middleware and was split into its own repository (see
[ADR-0040](docs/adr/0040-sumo-module-licensing-publish-under-open-terms.md)
and Plan #205 in onto-canon6) so it could be published, licensed, and
released independently of that platform.

## What's here

- `ontology_packs/linguistic_core/` — the versioned, compiled vocabulary
  pack (predicates, roles, entity types, hierarchy, constraints) as
  JSONL + a manifest per version.
- `src/linguistic_core/` — the compiler, donor-mapping crosswalk, and
  two-independent-model-pass verification pipeline that produced it.
- `scripts/` — CLI entry points for compiling, auditing, and verifying
  the pack against its donor sources.
- `tests/` — the pack's own standalone test suite (schema/compiler
  correctness; does not depend on onto-canon6's runtime).
- `docs/adr/0040-...` — the licensing decision this pack's publication
  terms rely on.

## Licensing and attribution

Published under GPL-compatible open terms per
[ADR-0040](docs/adr/0040-sumo-module-licensing-publish-under-open-terms.md),
which records the real, module-by-module SUMO license basis (most of SUMO's
own project-wide GPL notice, two LGPL modules, one file mixing GPL and CC-BY).
See `LICENSE` for the exact terms.

This work derives from and is grateful to:

- **SUMO** (Suggested Upper Merged Ontology) — Adam Pease / Articulate
  Software and its many module contributors
  ([ontologyportal.org](https://www.ontologyportal.org/)).
- **PropBank** — the PropBank project.
- **FrameNet** — the FrameNet project, ICSI Berkeley.

## Status

`linguistic_core@0.3.2` is the current version: 1,326 relation predicates
from the widened SUMO module set, plus the original FrameNet/PropBank-derived
event vocabulary carried forward from earlier versions. See the pack's own
`ontology_packs/linguistic_core/<version>/manifest.yaml` for exact provenance
per version.
