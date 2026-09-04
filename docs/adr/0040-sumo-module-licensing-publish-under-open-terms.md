# ADR 0040: SUMO Module Licensing — Publish Under Open Terms, Exclude Unlicensed Content

**Status:** Accepted
**Date:** 2026-09-04
**Decision owner:** Brian
**Implementation plan:** [linguistic_core completeness resume](../plans/goals/2026-09-03-linguistic-core-completeness-resume.md)

## Context

Plan 0147 pinned an exact SUMO source revision (commit `806b9cd57d1313309aad67dffa12871c06de0f26`, 66 modules) and recorded a per-module license-header classification, but only ever approved one module — `Merge.kif` — for publication into `linguistic_core`
(`docs/runs/artifacts/plan0147_sumo_module_publication_v1.json`,
`publication_disposition: "approved_for_linguistic_bounded_context"`). The
other 65 modules were left `excluded_pending_module_specific_review` — a real
per-file license question that was never actually resolved, only deferred.
This blocked most of the "broadest usable predicate vocabulary" goal on a
licensing question, not an engineering one.

On 2026-09-04, the actual header text of all 65 excluded modules was fetched
directly from the pinned upstream commit
(`github.com/ontologyportal/sumo@806b9cd5`) and read, not just classified by
the earlier automated scanner. Findings, cross-checked against the existing
`header_class` field in the v1 disposition artifact:

- `Merge.kif` (already approved): IEEE license — permissive, attribution-only,
  explicitly grants "a perpetual, non-exclusive, royalty-free, world-wide
  right and license to copy, publish and distribute... and to prepare
  derivative works."
- 41 modules (`header_class: gpl_notice`): SUMO's own standard project-wide
  notice — plain GPL ("by using these products, you agree to be bound by the
  terms of the GPL"), the same wording across most core domain files
  (Anatomy, Geography, Government, Law, Medicine, Military*, Transportation,
  etc.), authored primarily by Adam Pease / Articulate Software.
- 2 modules (`lgpl_notice`): `WorldAirports.kif`, `english_format.kif` — LGPL.
- 2 modules (`creative_commons_notice`): `emotion.kif` (GPL notice on the file
  itself, plus a note that some Wikipedia-sourced documentation text is under
  GNU-FDL) and `pictureList-ImageNet.kif` (explicit CC-BY-ShareAlike 3.0,
  image links only, no relation/predicate content).
- 1 module (`mixed_notice`): `FOAFmap.kif` — GPL text visible in the fetched
  header, but the `mixed_notice` classification implies a second, unreviewed
  notice further in the file; not individually resolved by this ADR.
- 19 modules (`unclassified_no_header_notice`): no license statement of any
  kind. The upstream repository was confirmed to carry no root-level
  `LICENSE`/`LICENSE.md`/`LICENSE.txt` file and no GitHub-reported license
  metadata, so there is no fallback to inherit — the safe default reading is
  all rights reserved.

Brian's stated intent (2026-09-04): this vocabulary will be written up
publicly (a blog post, hosted on GitHub) and may eventually be part of a paid
product. Both are "distribution" in the relevant sense — GPL's and CC's
obligations trigger on distribution/publication, not on whether money changes
hands, and the repository is already an open GitHub project.

## Decision

1. Approve for publication: the 41 `gpl_notice` modules, the 2 `lgpl_notice`
   modules, and `emotion.kif`, on the condition that `linguistic_core`'s
   published derived content (predicates/relations/roles — not raw SUMO
   source text) is itself published under GPL-compatible open terms, with
   clear attribution to SUMO / Articulate Software / the original module
   authors in the pack's own provenance metadata.
2. Do not republish Wikipedia-sourced documentation text carried inside
   `emotion.kif`; only its predicate/relation structure is in scope.
3. Exclude `pictureList-ImageNet.kif` entirely — image-link content only, no
   vocabulary value, not worth a separate CC-BY-ShareAlike attribution
   obligation for zero gain.
4. Exclude `FOAFmap.kif` pending an actual read of its full (not just header)
   license text — its `mixed_notice` classification was never individually
   resolved, and the cost of leaving one module out is negligible.
5. Exclude all 19 no-license modules entirely. No permission was ever granted
   for any use of that content. Do not re-open this bucket without an
   explicit new grant or a license discovered upstream.
6. This ADR deliberately does not resolve whether a predicate/relation
   *identifier* mechanically derived from a GPL module's axioms is itself a
   "derivative work" in the full copyright sense. It sidesteps that question:
   publish the derived vocabulary under GPL-compatible open terms regardless,
   so the compliance question becomes moot even under the most conservative
   reading.
7. If the paid product later wants to keep something closed, keep the
   SUMO-derived vocabulary layer open and put proprietary value (extraction
   pipeline, prompts, verification logic, product surface) in a separate
   layer that does not itself redistribute the licensed content. This ADR
   does not design that separation; it only records the constraint any future
   design must satisfy.
8. This is a non-lawyer reading of publicly available license text, not legal
   advice. Get an actual read from an IP/open-source-licensing lawyer before
   shipping anything commercial that depends on this content — not required
   before a blog post under the terms above.
9. Mechanically: record the widened set as a new, separate disposition
   artifact (`plan0147_sumo_module_publication_v2.json`) rather than
   mutating `plan0147_sumo_module_publication_v1.json` in place — the v1
   artifact is a dated, immutable record of what Plan 0147 actually reviewed
   at the time, and stays valid as historical evidence.

## Consequences

- The great majority of SUMO's core domain content becomes usable, unblocking
  the bulk of the "broadest vocabulary" goal — 44 of 66 modules move from
  blocked to approved.
- `linguistic_core`'s own published content must stay under GPL-compatible
  open terms as long as it carries GPL-derived material. This costs nothing
  today since the project is already public on GitHub, but constrains any
  future decision to make part of the repository closed-source.
- The 19 no-license modules and `pictureList-ImageNet.kif` remain permanently
  excluded unless someone finds or obtains an actual license for them.
- `FOAFmap.kif` remains excluded pending one concrete follow-up check, not a
  structural blocker.
- A future closed/proprietary layer of the paid product must not itself
  redistribute the SUMO-derived vocabulary in a way that removes its open
  terms.

## Rejected Alternatives

### Approve everything, including the no-license bucket

Rejected — no permission was ever granted for that content, for any purpose.
Real, avoidable exposure for a small amount of marginal content.

### Wait for formal legal review before using any of the GPL bucket

Rejected for the immediate use case (a blog post, an already-open GitHub
project). Publishing the derived vocabulary under GPL-compatible terms
resolves the practical risk without waiting. Formal review is worth doing
before the paid product ships, not before a blog post — see Revisit Triggers.

### Treat all 65 excluded modules as one undifferentiated blocked bucket (status quo)

Rejected — the real license terms are materially different module to module
(IEEE vs. GPL vs. LGPL vs. CC vs. none), and treating them as one "pending
review" bucket blocked 44 genuinely usable modules for no reason once the
real text was actually read.

## Failure And Rollback

If any newly-approved module is found to carry a different or more
restrictive notice than recorded here (e.g., a second notice further down the
file, as suspected for `FOAFmap.kif`), pull that specific module's
disposition back to `excluded_pending_module_specific_review` in a new
disposition artifact revision and recompile; this does not require reverting
the whole slice or any other module's disposition.

## Revisit Triggers

Revisit before the paid product depends on any SUMO-derived content directly
— get real legal review at that point, not before. Revisit the no-license
bucket only if an explicit license is later published upstream for those
files.

## Addendum (2026-09-04): `FOAFmap.kif` resolved

Its full text was read. The `mixed_notice` classification was two genuine,
compatible notices rather than a conflict: the file's own
`synonymousExternalConcept` mapping content carries the same standard SUMO
GPL notice as the other 41 modules; a separate note states the external FOAF
vocabulary terms it references (not `linguistic_core` content) are CC-BY
licensed. Both are compatible with this ADR's open-publication approach.
Reclassified `approved_for_linguistic_bounded_context` in
`plan0147_sumo_module_publication_v2.json`. Verified inert: `FOAFmap.kif`
contributes zero rows to `sumo_plus.db`'s `relations`/`relation_constraints`
tables, so `linguistic_core@0.3.2`'s compiled content is unaffected — this
closes the record, not the vocabulary.
