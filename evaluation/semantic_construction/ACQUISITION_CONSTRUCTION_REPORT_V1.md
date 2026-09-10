# Acquisition semantic construction report v1

This report was executed against one exact declared pack closure; it is not an extractor benchmark.

## Exact closure

- `linguistic_core@0.3.0` — manifest `a30476afa42d9d6974ab5f6734141644fba12c70341acb797dc8df549c2afd65`
- `linguistic_core@0.3.1` — manifest `df50f96ceb6cad83b5152eed60cc0d98239f1629dfeb35e93a40ad8ff2544dd3`
- `linguistic_core@0.3.2` — manifest `4bb2add2a19c082047ceb8d80ea6cb449983715e211f53b950bd1ca112308499`
- `linguistic_core@0.3.3` — manifest `bffd40273ec81400ea52949e330497d8173eb83205f70da80b004e2598e60fa6`

## Machine assertions

### `verbal_nominal_same_proposition` — Acme acquired Beta and Beta's acquisition by Acme preserve the proposition.

- Result: **PASS**; expected `allowed`, observed `allowed` (`ALLOWED`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:acme-beta","occurrence_id":"occ:deal-1","assertion_id":"assert:verbal","support_record_id":"support:wire-1"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:acme-beta","occurrence_id":"occ:deal-1","assertion_id":"assert:nominal","support_record_id":"support:wire-1"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q1","attribution":"wire-1","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q1","attribution":"wire-1","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `identity`, conditions `[]`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `purchase_to_acquisition_allowed` — Buying may project to acquiring when the commercial condition and lost consideration are explicit.

- Result: **PASS**; expected `allowed`, observed `allowed` (`ALLOWED`).
- Predicates: `lc:buy_purchase` → `lc:acquire_get_obtain`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:purchase-1","occurrence_id":"occ:deal-2","assertion_id":"assert:purchase-1","support_record_id":"support:wire-2"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:purchase-1","occurrence_id":"occ:deal-2","assertion_id":"assert:purchase-1","support_record_id":"support:wire-2"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"wire-2","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"wire-2","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `narrowerThan`, conditions `['commercial_transaction']`.
- Roles: source `{'lc.role.buyer': 'entity:acme', 'lc.role.goods': 'entity:beta', 'lc.role.seller': 'entity:gamma'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta', 'lc.role.source': 'entity:gamma'}`; transforms lc.role.buyer → lc.role.recipient, lc.role.goods → lc.role.theme, lc.role.seller → lc.role.source.
- Loss contract: `lossy`; lost distinctions `['commercial_consideration']`.

### `acquisition_to_purchase_rejected` — Acquiring does not license the stronger claim that a purchase occurred.

- Result: **PASS**; expected `rejected`, observed `rejected` (`MAPPING_DIRECTION_UNSUPPORTED declared=lc:buy_purchase->lc:acquire_get_obtain`).
- Predicates: `lc:acquire_get_obtain` → `lc:buy_purchase`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:acquisition-2","occurrence_id":"occ:deal-3","assertion_id":"assert:acquisition-2","support_record_id":"support:wire-3"}`; target `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:acquisition-2","occurrence_id":"occ:deal-3","assertion_id":"assert:acquisition-2","support_record_id":"support:wire-3"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"wire-3","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"wire-3","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `['commercial_transaction']`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta', 'lc.role.source': 'entity:gamma'}`, target `{'lc.role.buyer': 'entity:acme', 'lc.role.goods': 'entity:beta', 'lc.role.seller': 'entity:gamma'}`; transforms lc.role.recipient → lc.role.buyer, lc.role.theme → lc.role.goods, lc.role.source → lc.role.seller.
- Loss contract: `unsupported`; lost distinctions `[]`.

### `seller_buyer_perspectives_same_transaction` — Acme sold Beta to Gamma and Gamma bought Beta from Acme normalize to the same transaction roles.

- Result: **PASS**; expected `allowed`, observed `allowed` (`ALLOWED`).
- Predicates: `lc:buy_purchase` → `lc:buy_purchase`.
- Identity comparison: `occurrence`; source `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:transaction-1","occurrence_id":"occ:transaction-1","assertion_id":"assert:seller-wording","support_record_id":"support:wire-4"}`; target `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:transaction-1","occurrence_id":"occ:transaction-1","assertion_id":"assert:buyer-wording","support_record_id":"support:wire-4"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q3","attribution":"wire-4","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q3","attribution":"wire-4","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `identity`, conditions `[]`.
- Roles: source `{'lc.role.seller': 'entity:acme', 'lc.role.goods': 'entity:beta', 'lc.role.buyer': 'entity:gamma'}`, target `{'lc.role.buyer': 'entity:gamma', 'lc.role.goods': 'entity:beta', 'lc.role.seller': 'entity:acme'}`; transforms lc.role.seller → lc.role.seller, lc.role.goods → lc.role.goods, lc.role.buyer → lc.role.buyer.
- Loss contract: `lossless`; lost distinctions `[]`.

### `buyer_seller_swap_rejected` — A buyer/seller reversal cannot masquerade as the same transaction.

- Result: **PASS**; expected `rejected`, observed `rejected` (`ROLE_FILLER_MISMATCH source_role=lc.role.buyer target_role=lc.role.buyer`).
- Predicates: `lc:buy_purchase` → `lc:buy_purchase`.
- Identity comparison: `occurrence`; source `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:transaction-1","occurrence_id":"occ:transaction-1","assertion_id":"assert:swapped","support_record_id":"support:wire-4"}`; target `{"predicate_id":"lc:buy_purchase","proposition_id":"prop:transaction-1","occurrence_id":"occ:transaction-1","assertion_id":"assert:correct","support_record_id":"support:wire-4"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q3","attribution":"wire-4","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q3","attribution":"wire-4","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `[]`.
- Roles: source `{'lc.role.buyer': 'entity:acme', 'lc.role.goods': 'entity:beta', 'lc.role.seller': 'entity:gamma'}`, target `{'lc.role.buyer': 'entity:gamma', 'lc.role.goods': 'entity:beta', 'lc.role.seller': 'entity:acme'}`; transforms lc.role.buyer → lc.role.buyer, lc.role.goods → lc.role.goods, lc.role.seller → lc.role.seller.
- Loss contract: `lossless`; lost distinctions `[]`.

### `agreement_is_not_completed_acquisition` — An agreement to acquire remains distinct from a completed acquisition.

- Result: **PASS**; expected `rejected`, observed `rejected` (`SCOPE_MISMATCH`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:intended-deal","occurrence_id":"occ:intended-deal","assertion_id":"assert:intended","support_record_id":"support:wire-5"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:completed-deal","occurrence_id":"occ:completed-deal","assertion_id":"assert:completed","support_record_id":"support:wire-5"}`.
- Scope: source `{"polarity":"positive","modality":"intended","aspect":"prospective","temporal_scope":"future","attribution":"wire-5","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q4","attribution":"wire-5","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `[]`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `denial_preserves_embedded_proposition` — A denial can refer to the same embedded acquisition proposition without becoming a positive assertion.

- Result: **PASS**; expected `allowed`, observed `allowed` (`ALLOWED`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:rumored-deal","occurrence_id":"occ:rumored-deal","assertion_id":"assert:denial","support_record_id":"support:denial"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:rumored-deal","occurrence_id":"occ:rumored-deal","assertion_id":"assert:claim","support_record_id":"support:rumor"}`.
- Scope: source `{"polarity":"negative","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q1","attribution":"spokesperson","quantification":"specific"}`; target `{"polarity":"positive","modality":"possible","aspect":"completed","temporal_scope":"2026-Q1","attribution":"rumor","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `identity`, conditions `['compare_embedded_proposition']`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `denial_not_same_assertion` — The denial and positive report are not the same assertion.

- Result: **PASS**; expected `rejected`, observed `rejected` (`SCOPE_MISMATCH`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `assertion`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:rumored-deal","occurrence_id":"occ:rumored-deal","assertion_id":"assert:denial","support_record_id":"support:denial"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:rumored-deal","occurrence_id":"occ:rumored-deal","assertion_id":"assert:claim","support_record_id":"support:rumor"}`.
- Scope: source `{"polarity":"negative","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q1","attribution":"spokesperson","quantification":"specific"}`; target `{"polarity":"positive","modality":"possible","aspect":"completed","temporal_scope":"2026-Q1","attribution":"rumor","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `[]`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `repeated_participants_distinct_occurrences` — The same participants in two acquisitions do not make one occurrence.

- Result: **PASS**; expected `rejected`, observed `rejected` (`IDENTITY_MISMATCH level=occurrence`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `occurrence`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:repeat","occurrence_id":"occ:repeat-1","assertion_id":"assert:repeat-1","support_record_id":"support:repeat-1"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:repeat","occurrence_id":"occ:repeat-2","assertion_id":"assert:repeat-2","support_record_id":"support:repeat-2"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026","attribution":"ledger","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026","attribution":"ledger","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `[]`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `two_sources_same_proposition` — Two sources may support the same acquisition proposition.

- Result: **PASS**; expected `allowed`, observed `allowed` (`ALLOWED`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `proposition`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:corroborated","occurrence_id":"occ:corroborated","assertion_id":"assert:corroborated","support_record_id":"support:source-a"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:corroborated","occurrence_id":"occ:corroborated","assertion_id":"assert:corroborated","support_record_id":"support:source-b"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"source-a","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"source-b","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `identity`, conditions `['compare_embedded_proposition']`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.

### `support_records_remain_distinct` — Corroborating sources remain separate support records.

- Result: **PASS**; expected `rejected`, observed `rejected` (`IDENTITY_MISMATCH level=support_record`).
- Predicates: `lc:acquire_get_obtain` → `lc:acquire_get_obtain`.
- Identity comparison: `support`; source `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:corroborated","occurrence_id":"occ:corroborated","assertion_id":"assert:corroborated","support_record_id":"support:source-a"}`; target `{"predicate_id":"lc:acquire_get_obtain","proposition_id":"prop:corroborated","occurrence_id":"occ:corroborated","assertion_id":"assert:corroborated","support_record_id":"support:source-b"}`.
- Scope: source `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"joint-record","quantification":"specific"}`; target `{"polarity":"positive","modality":"asserted","aspect":"completed","temporal_scope":"2026-Q2","attribution":"joint-record","quantification":"specific"}`.
- Mapping: direction `source_to_target`, relation `none`, conditions `[]`.
- Roles: source `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`, target `{'lc.role.recipient': 'entity:acme', 'lc.role.theme': 'entity:beta'}`; transforms lc.role.recipient → lc.role.recipient, lc.role.theme → lc.role.theme.
- Loss contract: `lossless`; lost distinctions `[]`.


**Result:** 11 passed, 0 failed.

Unsupported directions, absent mappings, scope changes, identity collapses, and role-filler reversals are explicit rejection codes.
