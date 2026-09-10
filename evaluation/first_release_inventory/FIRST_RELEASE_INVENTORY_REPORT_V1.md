# Finite first-release inventory v1

Target: `linguistic_core@0.3.3`. Publication status: **not_authorized**.

This is a bounded selection contract, not donor ingestion, audited coverage, release approval, or permission to use excluded sources.

## Selected donors, components, fields, and rights

### `propbank_frames_34` — propbank (3.4 repository state at pinned commit)

- Exact identity: `git:commit=c66e0ccf28b53f00051b187db83e937b5bee2e32;tree=d1e1ef0c13c5ec6e06096b1448cb5f65d4e1b8c7`
- Rights: `verified_redistributable`; redistribution `True`; Retain attribution and ShareAlike terms in any distributed donor-derived layer; M2 itself does not authorize release.

- Component `frames_xml`: **include**, selector `frames/*.xml`, rights scope: PropBank repository LICENSE at the pinned commit
  - Finite count: 7566/7566 `selected_files` bound to `docs/runs/artifacts/plan0147_source_coverage_v1.json`.
  - `roleset.id` — `include` / `retained`: Stable source identity already preserved by the source-native projection.
  - `predicate.lemma` — `include` / `retained`: Required lexical anchor.
  - `roleset.name` — `include` / `retained`: Source sense label is retained without treating it as a full definition.
  - `aliases.text` — `include` / `retained`: Source-declared lexical variants.
  - `aliases.part_of_speech` — `include` / `retained`: Prevents lexical variants from losing syntactic category.
  - `arguments.number` — `include` / `retained`: Source-native argument identity.
  - `arguments.function_tag` — `include` / `retained`: Retains source function typing when present.
  - `arguments.description` — `include` / `retained`: Retains role meaning instead of ARG-number-only alignment.
  - `arguments.role_links` — `include` / `retained`: Preserves donor-native role crosswalks before generated proposals.
  - `roleset.lexical_links` — `include` / `retained`: Preserves donor-native sense links.
  - `examples` — `include` / `not_yet_retained`: Selected for M3 because examples disambiguate rolesets; current projection omits them.
  - `source.xml_bytes` — `exclude` / `not_applicable`: Raw donor files remain in the external cache rather than the release artifact.

### `framenet_17` — framenet (1.7)

- Exact identity: `archive:sha256=22f6aad6fb799ba4dbed0440714e1118442ad7d7345351de37428581284f471c;bytes=99207152;filename=framenet_v17.zip`
- Rights: `verified_redistributable`; redistribution `True`; Preserve supplied FrameNet title, author, URI, and attribution; M2 itself does not authorize release.

- Component `semantic_frame_inventory`: **include**, selector `frame/*.xml + frameIndex.xml + luIndex.xml + frRelation.xml`, rights scope: FrameNet 1.7 CC-BY-3.0 metadata at the pinned NLTK distribution revision
  - Finite count: 1221/1221 `frames` bound to `docs/runs/artifacts/plan0147_source_coverage_v1.json`.
  - `frame.id` — `include` / `retained`: Stable source frame identity.
  - `frame.name` — `include` / `retained`: Source frame label.
  - `frame.definition` — `include` / `retained`: Core source meaning.
  - `frame.semantic_types` — `exclude` / `not_applicable`: The current pinned projection retains semantic types only on frame elements; no frame-level field is claimed.
  - `frame_elements.id` — `include` / `retained`: Stable source role identity.
  - `frame_elements.name` — `include` / `retained`: Source role label.
  - `frame_elements.abbreviation` — `include` / `retained`: Source abbreviation used by FrameNet records.
  - `frame_elements.core_type` — `include` / `retained`: Distinguishes core and peripheral participation.
  - `frame_elements.definition` — `include` / `retained`: Retains role meaning.
  - `frame_elements.semantic_types` — `include` / `retained`: Retains source role restrictions.
  - `lexical_units.id` — `include` / `retained`: Stable source lexical-unit identity.
  - `lexical_units.name` — `include` / `retained`: Source lexical form.
  - `lexical_units.part_of_speech` — `include` / `retained`: Syntactic category.
  - `lexical_units.status` — `include` / `retained`: Source curation status.
  - `lexical_units.definition` — `include` / `retained`: Lexical-unit sense evidence.
  - `frame_relations.direction` — `include` / `retained`: Prevents source relation direction from being flattened.
  - `frame_relations.endpoints` — `include` / `retained`: Related frame identities and roles.
  - `frame_element_relations.endpoints` — `include` / `retained`: Donor-native role correspondences.
  - `source.member_refs` — `include` / `retained`: Byte-bound provenance to archive members.
  - `annotation_sets.sentences` — `exclude` / `not_applicable`: Full annotated corpus is outside the finite semantic-inventory release.
  - `source.archive_bytes` — `exclude` / `not_applicable`: Raw donor archive remains in the external cache.

### `sumo_root_kif` — sumo (root KIF modules at pinned commit)

- Exact identity: `git:commit=806b9cd57d1313309aad67dffa12871c06de0f26;tree=c662412aa248bac1d7bae459752760757dcbfbdb`
- Rights: `mixed_review_required`; redistribution `False`; Include only modules approved by ADR-0040 disposition v2 and publish derived content under GPL-compatible open terms with attribution; public release remains a separate gate.

- Component `approved_modules_v2`: **include**, selector `module_dispositions[publication_disposition=approved_for_linguistic_bounded_context] (46 of 66 pinned modules)`, rights scope: ADR-0040 and plan0147 SUMO module publication disposition v2
  - Finite count: 46/66 `modules` bound to `docs/runs/artifacts/plan0147_sumo_module_publication_v2.json`.
  - `terms.type_symbols` — `include` / `retained`: Source-native class inventory.
  - `terms.relation_symbols` — `include` / `retained`: Source-native relation inventory.
  - `axioms.instance` — `include` / `retained`: Source membership assertions.
  - `axioms.subclass` — `include` / `retained`: Source type hierarchy.
  - `axioms.subrelation` — `include` / `retained`: Source relation hierarchy.
  - `axioms.argument_constraints` — `include` / `retained`: Domain and range restrictions.
  - `axioms.disjoint` — `include` / `retained`: Explicit incompatibility constraints.
  - `source.formula_refs` — `include` / `retained`: Module, formula index, line, and digest provenance.
  - `documentation.text` — `exclude` / `not_applicable`: Excludes donor prose and the separately licensed Wikipedia-derived documentation identified by ADR-0040.
  - `formulas.raw_text` — `exclude` / `not_applicable`: Release retains structured assertions and source references rather than raw KIF text.
  - `excluded_modules` — `exclude` / `not_applicable`: The 20 v2-excluded modules remain outside the release inventory.

## Explicitly unselected candidates

- `nombank` (nombank): `deferred_internal_only` — Internal use is allowed, but no version/component is selected and no public redistribution basis is established.
- `wordnet` (wordnet): `deferred_not_selected` — Existing derivative traces do not substitute for a pinned source-native first-release component.
- `verbnet` (verbnet): `deferred_not_selected` — Existing derivative traces do not substitute for a pinned source-native first-release component.
- `wikidata` (wikidata): `deferred_not_selected` — A bounded property and qualifier selection has not been designed for this release.
- `semlink` (semlink): `deferred_not_selected` — No newly adopted permission, exact dependency, or selected source component exists.

## Two-axis coverage matrix

| Construction \ domain | physical_spatial | time_change | agents_organizations | possession_transfer | social_legal | information_communication | cognition_argument | measurement |
|---|---|---|---|---|---|---|---|---|
| `verbal_predicates` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` |
| `nominal_references` | `explicit_gap` | `explicit_gap` | `explicit_gap` | `explicit_gap` | `explicit_gap` | `explicit_gap` | `explicit_gap` | `explicit_gap` |
| `adjectival_state_predication` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` |
| `light_verb_constructions` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` |
| `alternations_converses` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` |
| `negation_modality_aspect` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` |
| `quantities_comparisons` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `selected_unmeasured` |
| `temporal_scope` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` |
| `generic_kind_claims` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` | `selected_unmeasured` |
| `nested_attributed_claims` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` | `contract_only` |

`selected_unmeasured` means source fields are selected but record-level coverage remains M3 work. `contract_only` means M1 can represent the distinction but this inventory selects no donor field for it. `explicit_gap` means the first release has neither selected donor support nor a completed representation route.

## Counts and boundary

- Selected donors: 3; included components: 3; included fields: 37.
- Included fields not yet retained: 1.
- Matrix cells: 80 ({'selected_unmeasured': 41, 'contract_only': 31, 'explicit_gap': 8, 'out_of_scope_first_release': 0}).
- Excluded/deferred candidate sources: 5.
- Evidence digest: `097cdf1e2a61349fc018c3cf7e542db3cd0b7d1861208297098d927c78ee56ed`.
- Public release remains unauthorized; restricted and unselected sources remain outside the build.
