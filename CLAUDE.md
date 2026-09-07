# linguistic-core

A broad, honestly-sourced predicate and relation vocabulary compiled from SUMO,
PropBank and FrameNet, with a governed pipeline for compiling, verifying and
extending it. Split out of `onto-canon6` so it can be published and licensed
independently of any platform that consumes it.

## Project-information entrypoint

**`docs/design/SEMANTIC_INTERLINGUA.md` is this repository's declared wiki
equivalent** under the ecosystem documentation policy
(`project-meta/docs/ops/WIKI_AND_DOCS_POLICY.md`), in place of a `wiki/index.md`.
Goals, concepts, architecture, decisions, limitations and open questions are
reachable through it; `docs/design/DESIGN_LOG.md` carries the history and
`docs/adr/` the accepted decisions. Cross-project context — how this object
relates to the rest of the ecosystem — lives in `~/code/vision/wiki/` and is
linked from the design rather than copied into it.

## Read first

- `README.md` — what is here and how to build it.
- **`docs/design/SEMANTIC_INTERLINGUA.md`** — the living design. What this
  vocabulary is becoming, what is settled, what is open, and where every piece
  of cited evidence lives. Read this before proposing any change to the pack's
  shape.
- `docs/design/DESIGN_LOG.md` — what changed in that design and why.
- `docs/adr/` — accepted decisions. ADR-0040 governs SUMO module licensing and
  is the reason this repository can be public.

## Working rules

**The design document is living, re-derived rather than appended.** On update,
re-read it in full and rewrite affected sections so it reads as current state.
An overturned claim is corrected or deleted, never left standing beside its
replacement. History goes in the design log, never in the design.

**Attribute precisely.** Keep "this source states", "this was measured", "this
is inference" and "this is contested" visibly distinct. Several positions in the
design were corrected after being stated confidently.

**Goal and intent statements get stricter handling than anything else here.**
They are the one thing that cannot be recovered from the current state of the
code, because the current state is what you would check them against. Any
inconsistency, ambiguity or open question touching what this object *is for*
must be recorded and surfaced immediately, never silently resolved and never
left to be caught on a later pass. A 2026-09-06 cold review found this document
asserting two incompatible things about whether the object is a merge — written
here, unnoticed through several revisions. Before editing a goal statement,
re-read the others.

**Verify before recording.** Numbers should be checked against the thing they
describe, not relayed. Absence claims — "X does not exist", "nothing reads Y" —
are the class that has failed most often here; check them directly.

**Evidence belongs where it was produced.** This repository holds the vocabulary
and its design. Run records, traces and measurements from consumers are cited by
path, not restated as if produced here.

**Licensing is not incidental to this repository, it is a constraint on the
artifact.** PropBank's ShareAlike and SUMO's GPL modules independently prevent a
proprietary merged artifact. Any paid product is a separate layer that does not
redistribute licensed content — see ADR-0040 decision 7. Before adding a source,
read its actual license file or terms page; two planned resources were dropped
in 2026-09 precisely because "expected to be permissive" was wrong.

## Consumers

`onto-canon6` consumes this pack as a pinned external package. It is a consumer:
it cites this design and this design does not describe its runtime. Do not
resolve an onto-canon6 runtime question by changing the pack.
